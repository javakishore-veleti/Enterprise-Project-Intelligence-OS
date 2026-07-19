"""Unit tests for the real project dataset acquisition DAG.

Hermetic (no network, no live Ingestion-API, no scheduler, no multi-GB download):
1. A DAG-parse test using ``airflow.models.DagBag``.
2. Direct tests of the pure task callables against a *fake* HTTP client + tmp dir.
"""

import hashlib
from pathlib import Path

import pytest

from project_dataset_acquire import tasks

DAGS_DIR = Path(__file__).resolve().parents[2] / "dags"


class FakeJsonResponse:
    def __init__(self, payload, error=None):
        self._payload = payload
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    def json(self):
        return self._payload


class FakeStreamResponse:
    def __init__(self, content: bytes, error=None):
        self._content = content
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    def iter_content(self, chunk_size):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i:i + chunk_size]


class FakeHttp:
    """Records PUT calls; returns queued json responses and a streamed body."""

    def __init__(self, get_json=None, stream_body=b"", get_error=None):
        self._get_json = get_json or {}
        self._stream_body = stream_body
        self._get_error = get_error
        self.puts = []

    def get(self, url, timeout=30, stream=False):
        if stream:
            return FakeStreamResponse(self._stream_body, error=self._get_error)
        return FakeJsonResponse(self._get_json, error=self._get_error)

    def put(self, url, json, timeout=30):
        self.puts.append((url, json))
        return FakeJsonResponse({**json, "ok": True})


# --------------------------------------------------------------------------- #
# DAG parse
# --------------------------------------------------------------------------- #
def test_dagbag_imports_without_errors():
    from airflow.models import DagBag

    bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert bag.import_errors == {}
    assert "project_dataset_acquire" in bag.dags


# --------------------------------------------------------------------------- #
# Task callables
# --------------------------------------------------------------------------- #
def test_fetch_dataset_returns_metadata():
    http = FakeHttp(get_json={"source_url": "http://x/f.zip", "expected_md5": "abc", "file_name": "f.zip"})
    out = tasks.fetch_dataset("http://base", http, "public-jira")
    assert out["source_url"] == "http://x/f.zip" and out["file_name"] == "f.zip"


def test_update_status_posts_state():
    http = FakeHttp()
    tasks.update_status("http://base", http, "public-jira", "DOWNLOADING", downloaded_bytes=0, message="go")
    url, body = http.puts[-1]
    assert url.endswith("/api/v1/ingestion/datasets/public-jira/status")
    assert body["state"] == "DOWNLOADING" and body["downloaded_bytes"] == 0


def test_download_streams_and_computes_md5(tmp_path):
    content = b"hello public jira dataset" * 1000
    expected = hashlib.md5(content).hexdigest()
    http = FakeHttp(stream_body=content)
    dest = str(tmp_path / "sub" / "f.zip")

    result = tasks.download_dataset("http://x/f.zip", dest, http, expected_md5=expected, chunk_size=64)

    assert result["bytes"] == len(content)
    assert result["md5"] == expected
    assert result["skipped"] is False
    assert Path(dest).read_bytes() == content
    assert not Path(dest + ".part").exists()  # atomic rename cleaned up


def test_download_is_idempotent_when_md5_matches(tmp_path):
    content = b"already here"
    expected = hashlib.md5(content).hexdigest()
    dest = tmp_path / "f.zip"
    dest.write_bytes(content)
    http = FakeHttp(stream_body=b"SHOULD NOT BE WRITTEN")  # differs -> proves skip

    result = tasks.download_dataset("http://x/f.zip", str(dest), http, expected_md5=expected)

    assert result["skipped"] is True
    assert dest.read_bytes() == content


def test_verify_md5_raises_on_mismatch():
    with pytest.raises(ValueError):
        tasks.verify_md5("aaa", "bbb")
    tasks.verify_md5("aaa", "aaa")  # matching -> no raise
    tasks.verify_md5("aaa", None)   # no expected -> no raise
