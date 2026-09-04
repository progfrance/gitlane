"""Tests for /repos/browse and /repos/validate (PLAN2 §3.2)."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestBrowse:
    def test_finds_git_repos(self, client, tmp_path):
        repo_a = tmp_path / "a-repo"
        repo_a.mkdir()
        (repo_a / ".git").mkdir()
        repo_b = tmp_path / "b-repo"
        repo_b.mkdir()
        (repo_b / ".git").mkdir()
        (tmp_path / "plain").mkdir()

        r = client.get("/repos/browse", params={"root": str(tmp_path), "depth": 1})
        assert r.status_code == 200
        body = r.json()
        names = {i["name"] for i in body["items"]}
        assert names == {"a-repo", "b-repo"}

    def test_depth_excludes_nested(self, client, tmp_path):
        # outer is NOT a git repo; inner (depth 2) is. depth=1 must skip it.
        outer = tmp_path / "outer"
        outer.mkdir()
        inner = outer / "inner"
        inner.mkdir()
        (inner / ".git").mkdir()

        r = client.get("/repos/browse", params={"root": str(tmp_path), "depth": 1})
        assert r.status_code == 200
        assert not any(i["name"] == "inner" for i in r.json()["items"])

        r2 = client.get("/repos/browse", params={"root": str(tmp_path), "depth": 2})
        assert any(i["name"] == "inner" for i in r2.json()["items"])

    def test_git_dir_is_leaf(self, client, tmp_path):
        # A directory that IS a git repo is returned as a leaf (no recursion).
        outer = tmp_path / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()
        inner = outer / "inner"
        inner.mkdir()
        (inner / ".git").mkdir()

        r = client.get("/repos/browse", params={"root": str(tmp_path), "depth": 3})
        names = {i["name"] for i in r.json()["items"]}
        assert "outer" in names
        assert "inner" not in names

    def test_missing_root_returns_empty(self, client, tmp_path):
        r = client.get("/repos/browse", params={"root": str(tmp_path / "nope"), "depth": 1})
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_depth_clamped(self, client, tmp_path):
        r = client.get("/repos/browse", params={"root": str(tmp_path), "depth": 99})
        assert r.status_code == 422

    def test_ignores_dotfiles(self, client, tmp_path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden" / ".git").mkdir()
        names = {i["name"] for i in client.get("/repos/browse", params={"root": str(tmp_path), "depth": 1}).json()["items"]}
        assert ".hidden" not in names


class TestValidate:
    def test_git_repo(self, client, git_repo):
        r = client.get("/repos/validate", params={"path": str(git_repo)})
        body = r.json()
        assert body["is_git"] is True
        assert body["name"] == git_repo.name
        assert body["head"] == "main"

    def test_not_a_repo(self, client, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        r = client.get("/repos/validate", params={"path": str(plain)})
        assert r.json()["is_git"] is False

    def test_missing_dir(self, client, tmp_path):
        r = client.get("/repos/validate", params={"path": str(tmp_path / "nope")})
        assert r.json()["is_git"] is False

class TestBrowseGuards:
    def test_truncated_field_present(self, client, tmp_path):
        r = client.get("/repos/browse", params={"root": str(tmp_path), "depth": 1})
        assert r.status_code == 200
        assert "truncated" in r.json()

    def test_skips_node_modules(self, client, tmp_path):
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / ".git").mkdir()
        r = client.get("/repos/browse", params={"root": str(tmp_path), "depth": 2})
        assert r.status_code == 200
        assert not any(i["name"] == "pkg" for i in r.json()["items"])

    def test_refuses_system_root(self, client):
        import sys
        root = r"C:\Windows" if sys.platform == "win32" else "/proc"
        r = client.get("/repos/browse", params={"root": root, "depth": 1})
        assert r.status_code == 400
