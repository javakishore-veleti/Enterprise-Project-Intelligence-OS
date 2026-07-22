"""Tests for the release/component/tag evidence backfill helpers.

Loads ``Database/MongoDB/backfill/backfill_release_fields.py`` by path (it lives
outside the DAG package) and checks its pure extraction — asserting parity with
Phase 2a's ``project_dataset_ingest.tasks._names`` so the two stay in lock-step —
plus the ``$set`` builder and a batched backfill against a tiny fake collection.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from project_dataset_ingest import tasks

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKFILL = _REPO_ROOT / "Database" / "MongoDB" / "backfill" / "backfill_release_fields.py"


def _load_backfill():
    spec = importlib.util.spec_from_file_location("backfill_release_fields", _BACKFILL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


backfill = _load_backfill()


@pytest.mark.parametrize("value", [
    None, "not-a-list", {"name": "x"}, [], [{"name": "A"}, {"name": "B"}],
    ["bare", "tags"], [{"name": ""}, {"name": None}, {"nope": "z"}],
    [{"name": "keep"}, "  ", "also"],
])
def test_extract_names_matches_phase_2a_names(value) -> None:
    assert backfill.extract_names(value) == tasks._names(value)


def test_build_set_only_the_three_fields() -> None:
    raw = {"key": "AP-1", "fields": {
        "fixVersions": [{"name": "2.0"}], "components": [{"name": "core"}],
        "labels": ["perf", "ux"], "status": {"name": "Open"}}}
    assert backfill.build_set(raw) == {
        "fix_versions": ["2.0"], "components": ["core"], "labels": ["perf", "ux"]}


def test_build_set_defaults_empty_when_absent() -> None:
    assert backfill.build_set({"key": "X-1", "fields": {}}) == {
        "fix_versions": [], "components": [], "labels": []}


class _FakeEvidence:
    """Captures bulk_write ops and reports matched/modified counts."""

    def __init__(self, existing_keys: set[str]) -> None:
        self._existing = existing_keys
        self.ops: list = []

    def bulk_write(self, ops, ordered=False):
        self.ops.extend(ops)
        matched = sum(1 for op in ops if op._filter["issue_key"] in self._existing)
        return type("R", (), {"matched_count": matched, "modified_count": matched})()


class _FakeRaw:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def find(self, flt, projection):
        class _C:
            def __init__(self, docs):
                self._docs = docs

            def limit(self, n):
                return iter(self._docs[:n]) if n else iter(self._docs)

            def __iter__(self):
                return iter(self._docs)
        return _C(self._docs)


def test_backfill_collection_batches_and_counts() -> None:
    pytest.importorskip("pymongo")  # UpdateOne is used inside backfill_collection
    raw = _FakeRaw([
        {"key": "AP-1", "fields": {"fixVersions": [{"name": "2.0"}]}},
        {"key": "AP-2", "fields": {"labels": ["perf"]}},
        {"id": "AP-3", "fields": {}},          # identity via id
        {"fields": {"labels": ["x"]}},          # no key/id -> skipped
    ])
    evidence = _FakeEvidence(existing_keys={"AP-1", "AP-3"})
    counts = backfill.backfill_collection(raw, evidence, batch_size=2, limit=0, log=lambda *_: None)

    assert counts["scanned"] == 3           # the keyless doc is skipped
    assert counts["matched"] == 2           # AP-1, AP-3 exist in evidence
    assert len(evidence.ops) == 3
