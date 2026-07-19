"""Unit tests for the real batch dataset-ingestion DAG.

Hermetic (no network, no live Ingestion-API, no scheduler, no Mongo server):
1. DAG-parse test via ``airflow.models.DagBag``.
2. Direct tests of the pure task callables (extract/discover/batch/upsert/status)
   against a fake HTTP client, a temp dir, and a fake Mongo collection.
"""

import json
import zipfile
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
        self._get_payload = get_payload or {}
        self.posts = []
        self.puts = []

    def get(self, url, timeout=60):
        return FakeResponse(self._get_payload)

    def post(self, url, json, timeout=60):
        self.posts.append((url, json))
        return FakeResponse({})

    def put(self, url, json, timeout=60):
        self.puts.append((url, json))
        return FakeResponse({})


class FakeCollection:
    def __init__(self):
        self.docs = {}
        self.inserts = 0

    def update_one(self, flt, update, upsert=False):
        key = tuple(sorted(flt.items()))
        self.docs[key] = update["$set"]

    def insert_one(self, doc):
        self.inserts += 1


def _write_jsonl(path: Path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


# --------------------------------------------------------------------------- #
def test_dagbag_imports_without_errors():
    from airflow.models import DagBag

    bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert bag.import_errors == {}
    assert "project_dataset_ingest" in bag.dags


def test_extract_and_discover(tmp_path):
    # Build a small archive with two entity files.
    src = tmp_path / "src"
    src.mkdir()
    _write_jsonl(src / "projects.jsonl", [{"project_key": "A"}, {"project_key": "B"}])
    _write_jsonl(src / "issues.ndjson", [{"issue_key": f"A-{i}"} for i in range(5)])
    zip_path = tmp_path / "d.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(src / "projects.jsonl", "projects.jsonl")
        zf.write(src / "issues.ndjson", "issues.ndjson")

    work = tmp_path / "work"
    tasks.extract_archive(str(zip_path), str(work))
    entities = tasks.discover_entities(str(work))

    by = {e: (p, t) for e, p, t in entities}
    assert by["projects"][1] == 2
    assert by["issues"][1] == 5


def test_iter_batches_streams_in_chunks(tmp_path):
    path = tmp_path / "issues.jsonl"
    _write_jsonl(path, [{"issue_key": f"A-{i}"} for i in range(7)])
    batches = list(tasks.iter_batches(str(path), batch_size=3))
    assert [len(recs) for _, _, recs in batches] == [3, 3, 1]
    assert [bn for bn, _, _ in batches] == [0, 1, 2]


def test_upsert_batch_is_idempotent():
    coll = FakeCollection()
    recs = [{"project_key": "A", "v": 1}, {"project_key": "B", "v": 2}]
    tasks.upsert_batch(coll, recs, "project_key")
    tasks.upsert_batch(coll, [{"project_key": "A", "v": 9}], "project_key")  # re-upsert
    assert len(coll.docs) == 2  # no duplicate A
    assert coll.docs[(("project_key", "A"),)]["v"] == 9


def test_upsert_falls_back_to_insert_without_key():
    coll = FakeCollection()
    tasks.upsert_batch(coll, [{"no_key": 1}], "issue_key")
    assert coll.inserts == 1


def test_status_callbacks_hit_expected_endpoints():
    http = FakeHttp(get_payload={"batch_numbers": [0, 1]})
    base = "http://base"
    assert tasks.committed_batches(base, http, "run1", "issues") == {0, 1}
    tasks.report_batch(base, http, "run1", entity="issues", batch_no=2, source_offset=2000,
                       record_count=1000, records_done=3000, records_total=5000)
    tasks.finalize_run(base, http, "run1", "COMPLETED")
    assert http.posts[0][0].endswith("/api/v1/ingestion/runs/run1/progress")
    assert http.posts[0][1]["records_done"] == 3000
    assert http.puts[0][0].endswith("/api/v1/ingestion/runs/run1/status")
    assert http.puts[0][1]["status"] == "COMPLETED"


def test_natural_key_mapping():
    assert tasks.natural_key("projects") == "project_key"
    assert tasks.natural_key("issues") == "issue_key"
    assert tasks.natural_key("unknown") == "id"
