"""Bounded filesystem scan for git repositories.

Extracted from routes_browse so the `/tags/find` endpoint can reuse the same
discovery without duplicating the depth/results/time budget logic. The scan
is depth-bounded (skip heavy subtrees, dotfiles, symlinks) and refuses to
descend into system directories.
"""
from __future__ import annotations

import os
import time
from typing import Callable

MAX_DEPTH = 3
MAX_RESULTS = 200
SCAN_BUDGET_SECONDS = 10.0

# Heavy/irrelevant subtrees never descended into during a scan.
SKIP_DIRS = frozenset({
    "node_modules", ".venv", "venv", "__pycache__", "target", "build",
    "dist", ".git", ".hg", ".svn", ".tox", ".mypy_cache", ".pytest_cache",
    ".idea", ".vscode",
})

# System roots a local scan refuses outright (enumeration guard).
REFUSED_ROOTS = (r"C:\Windows", r"C:\Program Files", r"C:\Program Files (x86)",
                 "/etc", "/proc", "/sys", "/dev")


def is_git_dir(path: str) -> bool:
    """Cheap git check: a directory whose child `.git` entry exists."""
    try:
        return os.path.isdir(os.path.join(path, ".git"))
    except OSError:
        return False


def is_refused_root(root: str) -> bool:
    norm = os.path.normcase(os.path.normpath(root))
    return any(norm == os.path.normcase(os.path.normpath(r)) or
               norm.startswith(os.path.normcase(os.path.normpath(r)) + os.sep)
               for r in REFUSED_ROOTS)


def scan(root: str, depth: int = 1,
         deadline: float | None = None,
         on_progress: Callable[[int], None] | None = None) -> tuple[list[dict], bool]:
    """Depth-bounded scan under `root`. Returns (found, complete).

    `found` is a list of {"path": ..., "name": ...} entries (each pointing at a
    directory that contains a `.git` child). `complete` is False when the scan
    stopped early due to the time budget or the MAX_RESULTS cap.
    """
    if deadline is None:
        deadline = time.monotonic() + SCAN_BUDGET_SECONDS
    found: list[dict] = []
    complete = _scan(root, depth, deadline, found, on_progress)
    return found, complete


def _scan(root: str, depth: int, deadline: float, found: list[dict],
          on_progress: Callable[[int], None] | None) -> bool:
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name.lower())
    except OSError:
        return True
    for entry in entries:
        if len(found) >= MAX_RESULTS or time.monotonic() > deadline:
            return False
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        if entry.name.startswith(".") or entry.name in SKIP_DIRS:
            continue
        full = entry.path
        if is_git_dir(full):
            found.append({"path": os.path.normpath(full), "name": entry.name})
            if on_progress:
                on_progress(len(found))
        elif depth > 1:
            if not _scan(full, depth - 1, deadline, found, on_progress):
                return False
    return True