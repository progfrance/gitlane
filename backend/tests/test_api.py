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

    def test_open_exposes_remote_url(self, client, git_repo):
        # A repo without a GitHub origin gets remote=None (not an error).
        r = client.post("/repos/open", json={"path": str(git_repo)})
        assert r.status_code == 200
        assert "remote" in r.json()["repo"]
        assert r.json()["repo"]["remote"] is None

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

    def test_refs_refreshes_new_branch(self, client, repo_with_merge, tmp_path):
        import subprocess

        cache.invalidate(str(repo_with_merge))
        client.post("/repos/open", json={"path": str(repo_with_merge)})
        subprocess.run(
            ["git", "-C", str(repo_with_merge), "checkout", "-q", "-b", "fresh-branch"],
            check=True, capture_output=True, timeout=30,
        )
        r = client.get("/refs", params={"path": str(repo_with_merge)})
        names = [b["name"] for b in r.json()["local_branches"]]
        assert "fresh-branch" in names


class TestBranchSwitch:
    """The /history `ref` parameter must filter to the selected branch."""

    def test_history_defaults_to_head(self, opened, client):
        r = client.get("/history", params={"path": opened, "limit": 50})
        body = r.json()
        assert body["active_ref"] == "main"
        assert body["total"] == 4  # c1 c2(merged) c3 c4 — full main history

    def test_history_switches_branch(self, opened, client):
        r = client.get("/history", params={"path": opened, "ref": "feature", "limit": 50})
        assert r.status_code == 200
        body = r.json()
        assert body["active_ref"] == "feature"
        subjects = [i["message_subject"] for i in body["items"]]
        assert "c2 on feature" in subjects
        assert "c3 on main" not in subjects
        assert "c4 merge feature" not in subjects

    def test_history_ref_back_and_forth_uses_cache(self, opened, client):
        r1 = client.get("/history", params={"path": opened, "ref": "feature"})
        r2 = client.get("/history", params={"path": opened, "ref": "main"})
        r3 = client.get("/history", params={"path": opened, "ref": "feature"})
        assert r1.json()["total"] == 2
        assert r2.json()["total"] == 4
        assert r3.json()["total"] == 2
        assert r3.json()["active_ref"] == "feature"

    def test_history_is_head_follows_branch(self, opened, client):
        r = client.get("/history", params={"path": opened, "ref": "feature", "limit": 50})
        items = r.json()["items"]
        head = next(i for i in items if i["is_head"])
        assert head["message_subject"] == "c2 on feature"

    def test_history_unknown_ref_returns_400(self, opened, client):
        r = client.get("/history", params={"path": opened, "ref": "no-such-branch"})
        assert r.status_code == 400

    def test_timeline_honors_ref(self, opened, client):
        r = client.get("/timeline", params={"path": opened, "ref": "feature"})
        assert r.status_code == 200
        total = sum(p["count"] for p in r.json()["points"])
        assert total == 2


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
            "#d6409f", "#8e4ec6", "#0091ff", "#00a2c7", "#f5a623", "#30a46c",
            "#e5484d", "#6e56cf", "#12b5cb", "#e2b714", "#3eb8b3", "#7ee787",
        }
        for item in r.json()["items"]:
            assert item["node"]["color"] in palette
            for seg in item["segments"]:
                assert seg["color"] in palette


class TestGitReaderRemote:
    def test_read_remote_parses_github_urls(self, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "remote-repo"
        repo.mkdir()

        def fake_run(path, args, timeout=15):
            assert args[:2] == ["config", "--get"]
            return "git@github.com:progfrance/gitlane.git\n"

        monkeypatch.setattr(git_reader, "_run", fake_run)
        assert git_reader.read_remote(str(repo)) == "https://github.com/progfrance/gitlane"

    def test_read_remote_https_and_git_suffix(self, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "remote-repo"
        repo.mkdir()
        monkeypatch.setattr(
            git_reader, "_run",
            lambda path, args, timeout=15: "https://github.com/owner/repo.git\n",
        )
        assert git_reader.read_remote(str(repo)) == "https://github.com/owner/repo"

    def test_read_remote_non_github_supported(self, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "remote-repo"
        repo.mkdir()
        monkeypatch.setattr(
            git_reader, "_run",
            lambda path, args, timeout=15: "git@gitlab.com:owner/repo.git\n",
        )
        assert git_reader.read_remote(str(repo)) == "https://gitlab.com/owner/repo"

    def test_read_remote_nested_groups(self, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "remote-repo"
        repo.mkdir()
        monkeypatch.setattr(
            git_reader, "_run",
            lambda path, args, timeout=15: "git@gitlab.com:group/subgroup/repo.git\n",
        )
        assert git_reader.read_remote(str(repo)) == "https://gitlab.com/group/subgroup/repo"

    def test_read_remote_unparsable_is_none(self, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "remote-repo"
        repo.mkdir()
        monkeypatch.setattr(
            git_reader, "_run",
            lambda path, args, timeout=15: "not-a-valid-remote\n",
        )
        assert git_reader.read_remote(str(repo)) is None

    def test_read_remote_missing_remote_is_none(self, tmp_path, monkeypatch):
        from app.services import git_reader
        from app.services.git_reader import GitError

        repo = tmp_path / "remote-repo"
        repo.mkdir()
        monkeypatch.setattr(git_reader, "_run", lambda path, args, timeout=15: (_ for _ in ()).throw(GitError("no remote")))
        assert git_reader.read_remote(str(repo)) is None


class TestEvents:
    def test_websocket_connects(self, client):
        with client.websocket_connect("/events") as ws:
            # Session alive: a send must not raise (server keeps reading).
            ws.send_text("ping")
            assert ws.send_text("pong") is None
