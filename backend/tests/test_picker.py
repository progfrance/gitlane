"""Tests for the /picker page and root redirect (PLAN2 §3.3)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import recent
from app.services.cache import cache


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    for p in cache.all_paths():
        cache.invalidate(p)


def _monkeypatch_recent(tmp_path, monkeypatch, items):
    target = tmp_path / "recent.json"
    monkeypatch.setattr(recent, "RECENT_FILE", str(target))
    for it in items:
        recent.add_recent(it)


class TestPickerRoute:
    def test_picker_serves_html(self, client):
        r = client.get("/picker")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "GitLane" in r.text
        assert "repos/recent" in r.text  # JS calls the recent endpoint


class TestRootRedirect:
    def test_redirects_to_picker_when_nothing_open(self, tmp_path, monkeypatch):
        _monkeypatch_recent(tmp_path, monkeypatch, [])
        for p in cache.all_paths():
            cache.invalidate(p)
        # follow_redirects=False to observe the 307 itself.
        client = TestClient(app, follow_redirects=False)
        r = client.get("/", headers={"accept": "text/html"})
        assert r.status_code in (307, 302)
        assert r.headers["location"].endswith("/picker")

    def test_serves_index_when_repo_open(self, client, git_repo, tmp_path, monkeypatch):
        for p in cache.all_paths():
            cache.invalidate(p)
        client.post("/repos/open", json={"path": str(git_repo)})
        r = client.get("/", headers={"accept": "text/html"})
        assert r.status_code == 200
        assert "GitLane" in r.text or "<!doctype" in r.text.lower()

    def test_no_redirect_for_api_accept(self, client, tmp_path, monkeypatch):
        _monkeypatch_recent(tmp_path, monkeypatch, [])
        for p in cache.all_paths():
            cache.invalidate(p)
        r = client.get("/", headers={"accept": "application/json"})
        assert r.status_code == 200