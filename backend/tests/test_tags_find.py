"""Tests for /tags/find: cross-repo tag search."""
from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, timeout=30)


def _make_tagged_repo(tmp_path, name: str, tag: str | None) -> "Path":
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Alice")
    _git(repo, "config", "user.email", "alice@example.com")
    (repo / "f.txt").write_text("1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    if tag:
        _git(repo, "tag", tag)
    return repo


class TestTagsFind:
    def test_finds_tag_in_two_of_three_repos(self, client, tmp_path):
        a = _make_tagged_repo(tmp_path, "repo-a", tag="v1.2.0")
        b = _make_tagged_repo(tmp_path, "repo-b", tag="v1.2.0")
        _make_tagged_repo(tmp_path, "repo-c", tag=None)

        r = client.get("/tags/find", params={"root": str(tmp_path), "tag": "v1.2.0", "depth": 1})
        assert r.status_code == 200
        body = r.json()
        paths = {item["repo_path"] for item in body["items"]}
        assert str(a) in paths
        assert str(b) in paths
        assert len(body["items"]) == 2
        for item in body["items"]:
            assert item["tag_name"] == "v1.2.0"
            assert len(item["sha"]) == 40

    def test_unknown_tag_returns_empty(self, client, tmp_path):
        _make_tagged_repo(tmp_path, "repo-a", tag="v1.0.0")
        r = client.get("/tags/find", params={"root": str(tmp_path), "tag": "nope", "depth": 1})
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["scanned"] == 1
        assert body["truncated"] is False

    def test_refuses_system_root(self, client):
        import sys
        root = r"C:\Windows" if sys.platform == "win32" else "/proc"
        r = client.get("/tags/find", params={"root": root, "tag": "v1", "depth": 1})
        assert r.status_code == 400

    def test_invalid_tag_name_rejected(self, client, tmp_path):
        for bad in ("v 1", "v:1", "-leading", "..", "x@{y}"):
            r = client.get("/tags/find", params={"root": str(tmp_path), "tag": bad, "depth": 1})
            assert r.status_code == 400, f"tag {bad!r} should be rejected"

    def test_root_not_a_directory(self, client, tmp_path):
        r = client.get("/tags/find", params={"root": str(tmp_path / "nope"), "tag": "v1", "depth": 1})
        assert r.status_code == 400

    def test_results_sorted_by_recency(self, client, tmp_path):
        old = _make_tagged_repo(tmp_path, "old", tag="v1")
        new = _make_tagged_repo(tmp_path, "new", tag="v1")
        r = client.get("/tags/find", params={"root": str(tmp_path), "tag": "v1", "depth": 1})
        assert r.status_code == 200
        body = r.json()
        paths = [item["repo_path"] for item in body["items"]]
        assert paths.index(str(new)) < paths.index(str(old))