"""Tests for the recent-repos persistence service (PLAN2 §3.2)."""
from __future__ import annotations

import json

import pytest

from app.services import recent


@pytest.fixture
def recent_file(tmp_path, monkeypatch):
    """Point RECENT_FILE at a temp path so tests don't touch ~/.gitlane_recent.json."""
    target = tmp_path / "recent.json"
    monkeypatch.setattr(recent, "RECENT_FILE", str(target))
    return target


def test_load_empty_when_missing(recent_file):
    assert recent.load_recent() == []


def test_add_and_load(recent_file):
    recent.add_recent(r"C:\Users\Dell\repos\alpha")
    items = recent.load_recent()
    assert len(items) == 1
    assert items[0]["path"] == r"C:\Users\Dell\repos\alpha"
    assert items[0]["name"] == "alpha"
    assert "last_open" in items[0]


def test_deduplicates_on_path(recent_file):
    recent.add_recent(r"C:\Users\Dell\repos\alpha")
    recent.add_recent(r"C:\Users\Dell\repos\beta")
    recent.add_recent(r"C:\Users\Dell\repos\alpha")
    items = recent.load_recent()
    assert [i["path"] for i in items] == [r"C:\Users\Dell\repos\alpha", r"C:\Users\Dell\repos\beta"]


def test_caps_at_max_items(recent_file):
    for i in range(15):
        recent.add_recent(rf"C:\Users\Dell\repos\repo{i}")
    items = recent.load_recent()
    assert len(items) == recent.MAX_ITEMS == 10
    # Newest first: repo14 is the most recent.
    assert items[0]["path"] == r"C:\Users\Dell\repos\repo14"
    assert items[-1]["path"] == r"C:\Users\Dell\repos\repo5"


def test_last_repo(recent_file):
    assert recent.last_repo() is None
    recent.add_recent(r"C:\Users\Dell\repos\alpha")
    assert recent.last_repo() == r"C:\Users\Dell\repos\alpha"


def test_write_is_versioned_json(recent_file):
    recent.add_recent(r"C:\Users\Dell\repos\alpha")
    raw = json.loads(recent_file.read_text(encoding="utf-8"))
    assert raw["v"] == 1
    assert raw["last_repo"] == r"C:\Users\Dell\repos\alpha"
    assert len(raw["items"]) == 1


def test_corrupt_file_returns_empty(recent_file):
    recent_file.write_text("{not json", encoding="utf-8")
    assert recent.load_recent() == []


def test_non_writable_is_nonfatal(recent_file, monkeypatch):
    def boom(items):
        raise OSError("read-only")
    monkeypatch.setattr(recent, "_write", boom)
    # Should not raise; list is computed and returned.
    items = recent.add_recent(r"C:\Users\Dell\repos\alpha")
    assert items[0]["path"] == r"C:\Users\Dell\repos\alpha"