"""Browse for git repositories on disk + lightweight path validation (PLAN2 §3.2)."""
from __future__ import annotations

import logging
import os
import time

from fastapi import APIRouter, HTTPException, Query

from ..services import git_reader
from .errors import git_or_404

log = logging.getLogger("gitlane.browse")

router = APIRouter(tags=["repos"])

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


def _is_git_dir(path: str) -> bool:
    """Cheap git check: a directory whose child `.git` entry exists."""
    try:
        return os.path.isdir(os.path.join(path, ".git"))
    except OSError:
        return False


def _refused(root: str) -> bool:
    norm = os.path.normcase(os.path.normpath(root))
    return any(norm == os.path.normcase(os.path.normpath(r)) or
               norm.startswith(os.path.normcase(os.path.normpath(r)) + os.sep)
               for r in REFUSED_ROOTS)


def _scan(root: str, depth: int, deadline: float, found: list[dict]) -> bool:
    """Depth-bounded scan; returns False when budget/results are exhausted."""
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
        if _is_git_dir(full):
            found.append({"path": os.path.normpath(full), "name": entry.name})
        elif depth > 1:
            if not _scan(full, depth - 1, deadline, found):
                return False
    return True


@router.get("/repos/browse")
def browse(
    root: str = Query("", description="absolute root directory to scan"),
    depth: int = Query(1, ge=1, le=MAX_DEPTH),
) -> dict:
    """Find git repos under `root` (bounded depth/results/time, skips
    symlinks + dotfiles + heavy dirs like node_modules/.venv).

    Returns {"root": ..., "items": [...], "truncated": bool}.
    """
    if not root or not os.path.isdir(root):
        return {"root": root, "items": [], "truncated": False}
    abs_root = os.path.abspath(root)
    if _refused(abs_root):
        raise HTTPException(status_code=400, detail="scanning system directories is not allowed")
    found: list[dict] = []
    complete = _scan(abs_root, depth, time.monotonic() + SCAN_BUDGET_SECONDS, found)
    truncated = not complete or len(found) >= MAX_RESULTS
    if not complete:
        log.info("browse(%s) stopped early: budget/results exhausted", abs_root)
    return {"root": root, "items": found[:MAX_RESULTS], "truncated": truncated}


@router.get("/repos/validate")
def validate(path: str = Query("", max_length=1024, description="absolute path to check")) -> dict:
    """Pre-validate a path without opening it: is_git, name, head."""
    if not path or not os.path.isdir(path):
        return {"is_git": False, "name": None, "head": None}
    if not git_reader.is_git_repo(path):
        return {"is_git": False, "name": None, "head": None}
    refs = git_or_404(path, git_reader.read_refs)
    return {"is_git": True, "name": git_reader.repo_name(path), "head": refs.head}
