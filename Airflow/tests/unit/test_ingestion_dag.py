"""Unit tests for the mongorestore + normalize ingestion DAG (hermetic).

No network, no live Ingestion-API, no scheduler, no mongorestore, no Mongo server.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from project_dataset_ingest import probe_schema, tasks

DAGS_DIR = Path(__file__).resolve().parents[2] / "dags"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeHttp:
    def __init__(self, get_payload=None):
        self._get = get_payload or {}
        self.posts = []
        self.puts = []

    def get(self, url, timeout=60):
        return FakeResponse(self._get)

    def post(self, url, json, timeout=60):
        self.posts.append((url, json))
        return FakeResponse({})

    def put(self, url, json, timeout=60):
        self.puts.append((url, json))
        return FakeResponse({})


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.upserts = []
        self.deletes = []
        self.inserts = []

    def find(self, flt=None):
        return iter(self.docs)

    def update_one(self, flt, update, upsert=False):
        self.upserts.append((flt, update["$set"]))

    def delete_many(self, flt):
        self.deletes.append(flt)

    def insert_many(self, rows):
        self.inserts.extend(rows)


class FakeDb:
    def __init__(self):
        self.colls = {}

    def __getitem__(self, name):
        return self.colls.setdefault(name, FakeCollection())


_JIRA_ISSUE = {
    "key": "APACHE-1",
    "fields": {
        "status": {"name": "Open"},
        "priority": {"name": "Blocker"},
        "created": "2021-01-02T03:04:05.000+0000",
        "resolutiondate": None,
        "comment": {"comments": [{"author": {"name": "alice"}, "created": "2021-02-01T00:00:00.000+0000"},
                                 {"author": {"name": "bob"}, "created": "2021-02-02T00:00:00.000+0000"}]},
        "issuelinks": [{"type": {"name": "Blocks"}, "outwardIssue": {"key": "APACHE-2"}}],
    },
    "changelog": {"histories": [
        {"created": "2021-03-01T00:00:00.000+0000", "author": {"name": "carol"},
         "items": [{"field": "status", "toString": "Reopened"}]}]},
}


def test_dagbag_imports_without_errors():
    from airflow.models import DagBag

    bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert bag.import_errors == {}
    assert "project_dataset_ingest" in bag.dags


def test_transform_issue_maps_all_evidence():
    out = tasks.transform_issue(_JIRA_ISSUE, "APACHE")
    issue = out["issues"][0]
    assert issue["issue_key"] == "APACHE-1" and issue["status"] == "Open" and issue["priority"] == "Blocker"
    assert isinstance(issue["created_at"], datetime) and issue["created_at"].year == 2021
    assert issue["resolved_at"] is None
    assert out["issue_histories"][0]["to_value"] == "Reopened"
    assert {c["author"] for c in out["comments"]} == {"alice", "bob"}
    assert out["issue_links"][0]["target_issue_key"] == "APACHE-2"
    assert out["issue_links"][0]["link_type"] == "Blocks"


def test_transform_handles_missing_fields():
    out = tasks.transform_issue({"key": "X-1", "fields": {}}, "X")
    assert out["issues"][0]["status"] == "Unknown"
    assert out["issues"][0]["priority"] is None
    assert out["issue_histories"] == [] and out["comments"] == [] and out["issue_links"] == []


def test_build_mongorestore_cmd():
    cmd = tasks.build_mongorestore_cmd("/data/d.archive", "mongodb://h:27017/epi_os")
    assert cmd[0] == "mongorestore" and "--gzip" in cmd
    assert "--archive=/data/d.archive" in cmd
    assert "--nsFrom=JiraReposAnon.*" in cmd and "--nsTo=jira_repos.*" in cmd
    assert not any(a.startswith("--nsInclude") for a in cmd)  # full restore by default


def test_build_mongorestore_cmd_bounded_repos():
    cmd = tasks.build_mongorestore_cmd("/d.archive", "mongodb://h/epi_os", repos=["Mindville", "Sakai"])
    assert "--nsInclude=JiraReposAnon.Mindville" in cmd
    assert "--nsInclude=JiraReposAnon.Sakai" in cmd
    assert "--nsFrom=JiraReposAnon.*" in cmd and "--nsTo=jira_repos.*" in cmd  # still remapped


def test_run_mongorestore_uses_injected_runner():
    calls = []
    tasks.run_mongorestore(["mongorestore", "x"], runner=lambda c: calls.append(c))
    assert calls == [["mongorestore", "x"]]


def test_iter_issue_batches(tmp_path):
    coll = FakeCollection([{"key": f"A-{i}"} for i in range(7)])
    batches = list(tasks.iter_issue_batches(coll, batch_size=3))
    assert [len(d) for _, _, d in batches] == [3, 3, 1]


def test_upsert_evidence_writes_normalized_rows():
    db = FakeDb()
    n = tasks.upsert_evidence(db, "APACHE", [_JIRA_ISSUE])
    assert n == 1
    assert db["issues"].upserts[0][1]["issue_key"] == "APACHE-1"
    assert db["comments"].inserts and db["issue_links"].inserts
    assert db["projects"].upserts[0][1]["project_key"] == "APACHE"


def test_status_callbacks():
    http = FakeHttp(get_payload={"batch_numbers": [0, 1]})
    assert tasks.committed_batches("http://b", http, "r", "APACHE") == {0, 1}
    tasks.report_batch("http://b", http, "r", entity="APACHE", batch_no=2, source_offset=2000,
                       record_count=1000, records_done=3000, records_total=5000)
    tasks.finalize_run("http://b", http, "r", "COMPLETED")
    assert http.posts[0][0].endswith("/runs/r/progress")
    assert http.puts[0][1]["status"] == "COMPLETED"


# --- Schema-mapping coverage (confirm the real dump matches transform_issue) - #
def test_field_presence_full_and_sparse():
    full = tasks.field_presence(_JIRA_ISSUE)
    assert full["key"] and full["fields.status.name"] and full["changelog.histories"]
    assert full["fields.comment.comments"] and full["fields.issuelinks"]
    sparse = tasks.field_presence({"id": "X-1", "fields": {"summary": "s"}})
    assert sparse["key"] and sparse["fields"]
    assert not sparse["fields.status.name"] and not sparse["changelog.histories"]


def test_issue_is_mapped():
    assert tasks.issue_is_mapped(_JIRA_ISSUE) is True
    assert tasks.issue_is_mapped({"id": "X-1", "fields": {}}) is True   # recognized, just sparse
    assert tasks.issue_is_mapped({"summary": "renamed shape"}) is False  # no key/id + no fields
    assert tasks.issue_is_mapped({"key": "X-1"}) is False                # no fields block


def test_batch_coverage_counts_unmapped_and_presence():
    docs = [_JIRA_ISSUE, {"id": "X-1", "fields": {}}, {"weird": "shape"}]
    cov = tasks.batch_coverage(docs)
    assert cov["docs"] == 3 and cov["unmapped"] == 1
    assert cov["present"]["fields.status.name"] == 1   # only the full issue
    assert cov["present"]["key"] == 2                  # full + sparse have identity


def test_merge_coverage_sums():
    a = tasks.batch_coverage([_JIRA_ISSUE])
    b = tasks.batch_coverage([{"weird": "shape"}])
    m = tasks.merge_coverage(a, b)
    assert m["docs"] == 2 and m["unmapped"] == 1
    assert m["present"]["fields.status.name"] == 1


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def limit(self, n):
        return iter(self._docs[:n])


class FakeSampleCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, flt=None):
        return FakeCursor(self._docs)


def test_probe_collection_and_problem_detection():
    clean = probe_schema.probe_collection(FakeSampleCollection([_JIRA_ISSUE]), sample=10)
    assert clean["coverage"]["unmapped"] == 0
    assert probe_schema.collection_has_problem(clean) is False
    assert "example doc" not in probe_schema.format_report("APACHE", clean)

    broken = probe_schema.probe_collection(FakeSampleCollection([{"weird": "shape"}]), sample=10)
    assert probe_schema.collection_has_problem(broken) is True
    report = probe_schema.format_report("BROKEN", broken)
    assert "CORE PATH ABSENT" in report


def test_real_jira_issue_fixture_maps_cleanly():
    """Lock transform_issue against the CONFIRMED real dataset shape.

    fixtures/real_jira_issue.json mirrors the structure verified 2026-07-21 against
    a live Mindville restore of the public JiraReposAnon mongodump (anonymized
    author tokens, changelog.histories[].items[].toString, issuelinks[].type.name).
    Values are synthetic so the dataset stays out of the repo (see fixtures/README.md).
    """
    fixture = FIXTURES_DIR / "real_jira_issue.json"
    if not fixture.exists():
        pytest.skip("no real_jira_issue.json fixture yet (add one after a partial restore)")
    issue = json.loads(fixture.read_text())
    assert tasks.issue_is_mapped(issue), "real doc shape not recognized — update transform_issue"
    out = tasks.transform_issue(issue, "REAL")

    row = out["issues"][0]
    assert row["issue_key"] and row["status"] != "Unknown", "status path missed the real shape"
    assert row["priority"] and row["created_at"] and row["resolved_at"], "priority/date paths missed"
    # changelog -> status history: only the status item, with its toString value.
    assert [h["to_value"] for h in out["issue_histories"]] == ["Closed"], "changelog status mapping wrong"
    assert out["issue_histories"][0]["author"], "anonymized author token not carried through"
    # issuelinks -> outwardIssue.key + type.name.
    assert out["issue_links"] and out["issue_links"][0]["link_type"], "issuelinks mapping wrong"
    # The real dataset carries no fields.comment, so comments are expected to be empty.
    assert out["comments"] == [], "real dataset has no comments — mapping should yield none"
