"""Persistence of recently opened repositories (`~/.gitlane_recent.json`).

Versioned JSON file, max 10 entries, deduplicated by normalized path,
newest first. Survives server restarts (PLAN2 §3.2).
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path

from .git_reader import repo_name

RECENT_FILE = os.path.expanduser("~/.gitlane_recent.json")
MAX_ITEMS = 10
SCHEMA_VERSION = 1

_lock = threading.Lock()


def _norm(path: str) -> str:
    # Display form: absolute + normalized separators, original case kept.
    return os.path.normpath(os.path.abspath(path))


def _key(path: str) -> str:
    # Dedup key: case-insensitive on Windows (C:\Repo vs c:\repo\.\ ).
    return os.path.normcase(_norm(path))


def load_recent() -> list[dict]:
    """Read the recent-repos list (empty list on any error)."""
    try:
        data = json.loads(Path(RECENT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = data.get("items", [])
    if not isinstance(items, list):
        return []
    return [i for i in items if isinstance(i, dict) and isinstance(i.get("path"), str)]


def add_recent(path: str) -> list[dict]:
    """Push `path` to the front of the recent list (dedup + cap)."""
    norm = _norm(path)
    now = int(time.time())
    with _lock:
        items = [i for i in load_recent() if _key(i["path"]) != _key(norm)]
        items.insert(0, {"path": norm, "name": repo_name(norm), "last_open": now})
        items = items[:MAX_ITEMS]
        try:
            _write(items)
        except OSError:
            # Non-fatal: the app keeps working, just without cross-restart history.
            pass
    return items


def last_repo() -> str | None:
    """Path of the most recently opened repo, if any."""
    items = load_recent()
    return items[0]["path"] if items else None


def _write(items: list[dict]) -> None:
    payload = {"v": SCHEMA_VERSION, "last_repo": items[0]["path"] if items else None, "items": items}
    target = Path(RECENT_FILE)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp file in the same directory + os.replace, so a
        # crash or concurrent writer never leaves a truncated JSON behind.
        fd, tmp_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=target.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, indent=2, ensure_ascii=False))
            os.replace(tmp_name, target)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    except OSError:
        # Non-fatal: the app keeps working, just without cross-restart history.
        pass
