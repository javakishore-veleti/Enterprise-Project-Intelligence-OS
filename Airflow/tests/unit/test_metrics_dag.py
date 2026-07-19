"""Unit tests for the project-metrics compute DAG (hermetic)."""

from pathlib import Path

from project_metrics_compute import tasks

DAGS_DIR = Path(__file__).resolve().parents[2] / "dags"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeHttp:
    def __init__(self, get_payload=None, post_payload=None):
        self._get = get_payload or {}
        self._post = post_payload or {}
        self.posts = []

    def get(self, url, timeout=120):
        return FakeResponse(self._get)

    def post(self, url, timeout=120):
        self.posts.append(url)
        return FakeResponse(self._post)


def test_dagbag_imports_without_errors():
    from airflow.models import DagBag

    bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert bag.import_errors == {}
    assert "project_metrics_compute" in bag.dags


def test_list_project_keys():
    http = FakeHttp(get_payload={"items": [{"project_key": "APACHE"}, {"project_key": "SPARK"}]})
    assert tasks.list_project_keys("http://base", http) == ["APACHE", "SPARK"]


def test_compute_project_posts_to_compute_endpoint():
    http = FakeHttp(post_payload={"project_key": "APACHE", "backlog_growth": 0.2})
    out = tasks.compute_project("http://base", http, "APACHE")
    assert out["backlog_growth"] == 0.2
    assert http.posts[0].endswith("/api/v1/projects/APACHE/metrics/compute")
