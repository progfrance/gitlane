"""API contract tests: run the FastAPI app against a fixture repo."""
from __future__ import annotations

import warnings

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.cache import cache  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def opened(client, repo_with_merge):
    cache.invalidate(str(repo_with_merge))
    r = client.post("/repos/open", json={"path": str(repo_with_merge)})
    assert r.status_code == 200, r.text
    return str(repo_with_merge)


class TestOpenRepo:
    def test_open_ok(self, client, git_repo):
        r = client.post("/repos/open", json={"path": str(git_repo)})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["repo"]["name"] == git_repo.name
        assert body["repo"]["commit_count"] >= 1

    def test_open_rejects_missing_dir(self, client, tmp_path):
        r = client.post("/repos/open", json={"path": str(tmp_path / "nope")})
        assert r.status_code == 400

    def test_open_rejects_relative_path(self, client):
        r = client.post("/repos/open", json={"path": "relative/path"})
        assert r.status_code == 400

    def test_open_rejects_non_repo(self, client, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        r = client.post("/repos/open", json={"path": str(plain)})
        assert r.status_code == 400


class TestHistory:
    def test_history_contract(self, opened, client):
        r = client.get("/history", params={"path": opened, "limit": 2})
        assert r.status_code == 200
        body = r.json()
        assert set(body) >= {"items", "next_cursor", "has_more", "total", "max_lane"}
        for item in body["items"]:
            assert set(item) >= {
                "sha", "short_sha", "message_subject", "author_name",
                "author_email", "timestamp", "relative_time", "parents",
                "refs", "lane_index", "node", "segments", "status_checks",
            }
            node = item["node"]
            assert {"x", "y", "r", "color"} <= set(node)
            for seg in item["segments"]:
                assert {"type", "x1", "y1", "x2", "y2", "color", "w"} <= set(seg)

    def test_pagination(self, opened, client):
        r1 = client.get("/history", params={"path": opened, "limit": 2})
        b1 = r1.json()
        assert b1["has_more"] is True and b1["next_cursor"]
        r2 = client.get("/history", params={"path": opened, "limit": 2, "cursor": b1["next_cursor"]})
        b2 = r2.json()
        assert b2["items"]
        assert b1["items"][0]["sha"] != b2["items"][0]["sha"]

    def test_search_filters(self, opened, client):
        r = client.get("/history", params={"path": opened, "q": "feature"})
        body = r.json()
        assert body["total"] >= 1
        assert all("feature" in i["message_subject"].lower() for i in body["items"])

    def test_history_requires_open(self, client, tmp_path):
        r = client.get("/history", params={"path": str(tmp_path)})
        assert r.status_code == 404


class TestRefs:
    def test_refs_lists_branches(self, opened, client):
        r = client.get("/refs", params={"path": opened})
        assert r.status_code == 200
        body = r.json()
        names = [b["name"] for b in body["local_branches"]]
        assert "main" in names and "feature" in names
        kinds = {b["kind"] for b in body["local_branches"]}
        assert kinds == {"local_branch"}


class TestLayoutInHistory:
    def test_merge_commit_has_merge_curve(self, opened, client):
        r = client.get("/history", params={"path": opened, "limit": 50})
        items = r.json()["items"]
        merge = next(i for i in items if "merge" in i["message_subject"])
        curves = [s for s in merge["segments"] if s["type"] == "curve"]
        assert curves, "merge commit must carry a curve segment"

    def test_lane_colors_valid(self, opened, client):
        r = client.get("/history", params={"path": opened, "limit": 50})
        palette = {
            "#f79ac0", "#8dd3ff", "#9ee6b5", "#ffd48a", "#c3b6ff", "#ffb2a6",
            "#94e2d5", "#b7e48a", "#f6b0e5", "#a0c4ff", "#ffd6a5", "#caffbf",
        }
        for item in r.json()["items"]:
            assert item["node"]["color"] in palette
            for seg in item["segments"]:
                assert seg["color"] in palette


class TestEvents:
    def test_websocket_connects(self, client):
        with client.websocket_connect("/events") as ws:
            # Session alive: a send must not raise (server keeps reading).
            ws.send_text("ping")
            assert ws.send_text("pong") is None
