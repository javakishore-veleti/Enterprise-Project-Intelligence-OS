"""Unit tests for the tracker-repository sync path (hermetic).

No network, no live tracker, no Airflow scheduler, no Mongo server. A fake
staging DB stands in for the restored ``jira_repos`` dump the FakeConnector
replays; fake evidence-writer + project-registrar capture the side effects.
"""
from datetime import datetime, timezone
from pathlib import Path

from tracker_sync import sync_engine, tasks
from tracker_sync.connectors import FakeConnector, build_connector
from tracker_sync.connectors.live_stubs import JiraConnector

DAGS_DIR = Path(__file__).resolve().parents[2] / "dags"


def _issue(key, status="Open", updated="2021-06-01T00:00:00.000+0000"):
    return {
        "key": key,
        "fields": {
            "status": {"name": status}, "priority": {"name": "Major"},
            "created": "2021-01-02T03:04:05.000+0000", "updated": updated,
            "resolutiondate": None,
            "issuelinks": [{"type": {"name": "Blocks"}, "outwardIssue": {"key": f"{key}-x"}}],
        },
        "changelog": {"histories": [
            {"created": "2021-03-01T00:00:00.000+0000", "author": {"name": "carol"},
             "items": [{"field": "status", "toString": "Closed"}]}]},
    }


class FakeStagingCollection:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, flt=None):
        return iter(self._docs)


class FakeStagingDb:
    def __init__(self, repos):
        self._repos = {name: FakeStagingCollection(docs) for name, docs in repos.items()}

    def __getitem__(self, name):
        return self._repos.get(name, FakeStagingCollection([]))

    def list_collection_names(self):
        return list(self._repos)


class FakeEvidenceWriter:
    """Upserts by issue_key so re-syncs prove idempotency; records stamped rows."""

    def __init__(self):
        self.issues = {}       # issue_key -> stamped issue row
        self.children = {"issue_histories": [], "comments": [], "issue_links": []}
        self.projects = set()
        self.write_calls = 0

    def write(self, project_key, rows):
        self.write_calls += 1
        for issue in rows.get("issues", []):
            self.issues[issue["issue_key"]] = issue
        for coll in self.children:
            self.children[coll].extend(rows.get(coll, []))
        self.projects.add(project_key)
        return len(rows.get("issues", []))


class FakeRegistrar:
    def __init__(self):
        self.calls = []

    def register(self, repo_id, projects):
        self.calls.append((repo_id, [p["external_key"] for p in projects]))


REPO_CTX = {
    "repo_id": "repo-123", "org_id": "org-1", "root_org_id": "root-1",
    "provider": "fake", "connection_config": {"fake_repos": ["Sakai", "Spring"]},
}


def _staging():
    return FakeStagingDb({
        "Sakai": [_issue("SAKAI-1"), _issue("SAKAI-2"), _issue("SAKAI-3")],
        "Spring": [_issue("SPR-1")],
        "JFrog": [_issue("JF-1")],  # present in staging but not selected by connection_config
    })


# --- connector ---------------------------------------------------------------
def test_dagbag_imports_without_errors():
    from airflow.models import DagBag

    bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert bag.import_errors == {}
    assert "tracker_repository_sync" in bag.dags


def test_fake_connector_lists_selected_repos_only():
    conn = FakeConnector(_staging())
    keys = [p["external_key"] for p in conn.list_projects(REPO_CTX["connection_config"])]
    assert keys == ["Sakai", "Spring"]           # JFrog excluded (not in fake_repos)
    assert conn.count_issues(REPO_CTX["connection_config"], "Sakai") == 3
    assert conn.test_connection(REPO_CTX["connection_config"]) is True


def test_fake_connector_windowing_and_since_delta():
    docs = [_issue("A-1", updated="2021-01-01T00:00:00.000+0000"),
            _issue("A-2", updated="2021-12-31T00:00:00.000+0000")]
    conn = FakeConnector(FakeStagingDb({"Repo": docs}))
    cfg = {"fake_repos": ["Repo"]}
    # since filters on fields.updated -> only the late-updated issue.
    since = datetime(2021, 6, 1, tzinfo=timezone.utc)
    assert conn.count_issues(cfg, "Repo", since=since) == 1
    delta = list(conn.fetch_issues(cfg, "Repo", since=since))
    assert [d["key"] for d in delta] == ["A-2"]
    # offset/limit windows are deterministic (sorted by key).
    win = list(conn.fetch_issues(cfg, "Repo", offset=1, limit=1))
    assert [d["key"] for d in win] == ["A-2"]


def test_build_connector_factory():
    assert isinstance(build_connector("fake", _staging()), FakeConnector)
    assert isinstance(build_connector("jira"), JiraConnector)


# --- plan_batches ------------------------------------------------------------
def test_plan_batches_windows():
    assert sync_engine.plan_batches(0, 2) == []
    assert sync_engine.plan_batches(5, 2) == [
        {"batch_no": 0, "offset": 0, "limit": 2},
        {"batch_no": 1, "offset": 2, "limit": 2},
        {"batch_no": 2, "offset": 4, "limit": 2},
    ]


# --- sync_repository: normalization + stamping + registration ---------------
def test_sync_repository_normalizes_stamps_and_registers():
    conn = FakeConnector(_staging())
    writer, registrar = FakeEvidenceWriter(), FakeRegistrar()
    summary = sync_engine.sync_repository(conn, REPO_CTX, writer, registrar, batch_size=2)

    # (a) issues normalized + written, each stamped with org/root/repo ids additively.
    assert summary["issues_synced"] == 4                     # 3 Sakai + 1 Spring
    assert set(writer.issues) == {"SAKAI-1", "SAKAI-2", "SAKAI-3", "SPR-1"}
    row = writer.issues["SAKAI-1"]
    assert row["org_id"] == "org-1" and row["root_org_id"] == "root-1" and row["repo_id"] == "repo-123"
    assert row["status"] == "Open"                            # transform_issue mapping intact
    assert all(h["repo_id"] == "repo-123" for h in writer.children["issue_histories"])
    assert all(link["org_id"] == "org-1" for link in writer.children["issue_links"])

    # (b) tracker_projects registered under the repo.
    assert registrar.calls == [("repo-123", ["Sakai", "Spring"])]

    # Bounded batches: Sakai (3 issues @ batch_size 2) took 2 writes + Spring 1 = 3 writes.
    assert writer.write_calls == 3
    assert [p["project_key"] for p in summary["projects"]] == ["Sakai", "Spring"]
    assert summary["projects"][0]["batches_total"] == 2


def test_resync_is_idempotent():
    conn = FakeConnector(_staging())
    writer, registrar = FakeEvidenceWriter(), FakeRegistrar()
    sync_engine.sync_repository(conn, REPO_CTX, writer, registrar, batch_size=2)
    sync_engine.sync_repository(conn, REPO_CTX, writer, registrar, batch_size=2)
    # Upsert-by-issue_key: a second full sync yields the SAME 4 issues, not 8.
    assert set(writer.issues) == {"SAKAI-1", "SAKAI-2", "SAKAI-3", "SPR-1"}


def test_committed_batches_are_skipped_on_resume():
    conn = FakeConnector(_staging())
    writer = FakeEvidenceWriter()
    # Simulate batch 0 of Sakai already committed -> only batch 1 (SAKAI-3) re-runs.
    summary = sync_engine.sync_project(
        conn, REPO_CTX, "Sakai", writer, batch_size=2, committed_batches={0})
    assert summary["batches_total"] == 2 and summary["batches_done"] == 1
    assert set(writer.issues) == {"SAKAI-3"}


def test_since_delta_only_fetches_updated_issues():
    docs = [_issue("SAKAI-1", updated="2021-01-01T00:00:00.000+0000"),
            _issue("SAKAI-2", updated="2021-12-01T00:00:00.000+0000")]
    conn = FakeConnector(FakeStagingDb({"Sakai": docs}))
    ctx = {**REPO_CTX, "connection_config": {"fake_repos": ["Sakai"]}}
    writer, registrar = FakeEvidenceWriter(), FakeRegistrar()
    since = datetime(2021, 6, 1, tzinfo=timezone.utc)
    summary = sync_engine.sync_repository(conn, ctx, writer, registrar, since=since, batch_size=10)
    assert summary["issues_synced"] == 1
    assert set(writer.issues) == {"SAKAI-2"}                  # only the delta issue


# --- pure task helpers -------------------------------------------------------
def test_build_batch_specs_skips_committed():
    specs = tasks.build_batch_specs("Sakai", total=5, batch_size=2, already={1})
    assert [s["batch_no"] for s in specs] == [0, 2]           # batch 1 skipped


def test_parse_since():
    assert tasks.parse_since(None) is None
    assert tasks.parse_since("") is None
    assert tasks.parse_since("2021-06-01T00:00:00+00:00").year == 2021
