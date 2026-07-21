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


class PagedHttp:
    """Returns full pages then a short final page, keyed by the offset= in the URL."""
    def __init__(self, pages):
        self._pages = pages  # list of item-lists, one per offset step
        self.gets = []

    def get(self, url, timeout=120):
        self.gets.append(url)
        offset = int(url.split("offset=")[1])
        idx = offset // 200
        items = self._pages[idx] if idx < len(self._pages) else []
        return FakeResponse({"items": items})


def test_list_project_keys_paginates_past_the_200_cap():
    # 200 on page 1 (full -> keep going), 3 on page 2 (short -> stop).
    page1 = [{"project_key": f"P{i}"} for i in range(200)]
    page2 = [{"project_key": "X"}, {"project_key": "Y"}, {"project_key": "Z"}]
    http = PagedHttp([page1, page2])
    keys = tasks.list_project_keys("http://base", http, page_size=200)
    assert len(keys) == 203 and keys[-1] == "Z"
    assert http.gets == ["http://base/api/v1/projects?limit=200&offset=0",
                         "http://base/api/v1/projects?limit=200&offset=200"]


def test_compute_project_posts_to_compute_endpoint():
    http = FakeHttp(post_payload={"project_key": "APACHE", "backlog_growth": 0.2})
    out = tasks.compute_project("http://base", http, "APACHE")
    assert out["backlog_growth"] == 0.2
    assert http.posts[0].endswith("/api/v1/projects/APACHE/metrics/compute")
