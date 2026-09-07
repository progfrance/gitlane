"""Tests for the recent-repos persistence service (PLAN2 §3.2).

Paths come from tmp_path so they are absolute and platform-neutral: a
hardcoded Windows path would be treated as relative on Linux CI and get
the CWD prepended by abspath, breaking the normalization assertions.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import recent


@pytest.fixture
def recent_file(tmp_path, monkeypatch):
    """Point RECENT_FILE at a temp path so tests don't touch ~/.gitlane_recent.json."""
    target = tmp_path / "recent.json"
    monkeypatch.setattr(recent, "RECENT_FILE", str(target))
    return target


@pytest.fixture
def repo_path(tmp_path):
    """Factory: an absolute repo dir path under tmp_path (created)."""
    def make(name: str) -> str:
        d = tmp_path / "repos" / name
        d.mkdir(parents=True, exist_ok=True)
        return str(d)
    return make


def test_load_empty_when_missing(recent_file):
    assert recent.load_recent() == []


def test_add_and_load(recent_file, repo_path):
    alpha = repo_path("alpha")
    recent.add_recent(alpha)
    items = recent.load_recent()
    assert len(items) == 1
    assert items[0]["path"] == alpha
    assert items[0]["name"] == "alpha"
    assert "last_open" in items[0]


def test_deduplicates_on_path(recent_file, repo_path):
    alpha, beta = repo_path("alpha"), repo_path("beta")
    recent.add_recent(alpha)
    recent.add_recent(beta)
    recent.add_recent(alpha)
    items = recent.load_recent()
    assert [i["path"] for i in items] == [alpha, beta]


def test_caps_at_max_items(recent_file, repo_path):
    for i in range(15):
        recent.add_recent(repo_path(f"repo{i}"))
    items = recent.load_recent()
    assert len(items) == recent.MAX_ITEMS == 10
    # Newest first: repo14 is the most recent.
    assert Path(items[0]["path"]).name == "repo14"
    assert Path(items[-1]["path"]).name == "repo5"


def test_last_repo(recent_file, repo_path):
    assert recent.last_repo() is None
    alpha = repo_path("alpha")
    recent.add_recent(alpha)
    assert recent.last_repo() == alpha


def test_write_is_versioned_json(recent_file, repo_path):
    alpha = repo_path("alpha")
    recent.add_recent(alpha)
    raw = json.loads(recent_file.read_text(encoding="utf-8"))
    assert raw["v"] == 1
    assert raw["last_repo"] == alpha
    assert len(raw["items"]) == 1


def test_corrupt_file_returns_empty(recent_file):
    recent_file.write_text("{not json", encoding="utf-8")
    assert recent.load_recent() == []


def test_non_writable_is_nonfatal(recent_file, repo_path, monkeypatch):
    def boom(items):
        raise OSError("read-only")
    monkeypatch.setattr(recent, "_write", boom)
    # Should not raise; list is computed and returned.
    alpha = repo_path("alpha")
    items = recent.add_recent(alpha)
    assert items[0]["path"] == alpha
