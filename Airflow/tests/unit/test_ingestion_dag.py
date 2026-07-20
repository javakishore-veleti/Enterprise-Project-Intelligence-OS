"""Unit tests for the mongorestore + normalize ingestion DAG (hermetic).

No network, no live Ingestion-API, no scheduler, no mongorestore, no Mongo server.
"""

from datetime import datetime
from pathlib import Path

from project_dataset_ingest import tasks

DAGS_DIR = Path(__file__).resolve().parents[2] / "dags"


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
