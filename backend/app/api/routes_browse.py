"""Browse for git repositories on disk + lightweight path validation (PLAN2 §3.2)."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from ..services import git_reader

router = APIRouter(tags=["repos"])

MAX_DEPTH = 3


def _is_git_dir(path: str) -> bool:
    """Cheap git check: a directory whose child `.git` entry exists."""
    try:
        return os.path.isdir(os.path.join(path, ".git"))
    except OSError:
        return False


def _scan(root: str, depth: int) -> list[dict]:
    found: list[dict] = []
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name.lower())
    except OSError:
        return found
    for entry in entries:
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        if entry.name.startswith("."):
            continue
        full = entry.path
        if _is_git_dir(full):
            found.append({"path": os.path.normpath(full), "name": entry.name})
        elif depth > 1:
            found.extend(_scan(full, depth - 1))
    return found


@router.get("/repos/browse")
def browse(
    root: str = Query("", description="absolute root directory to scan"),
    depth: int = Query(1, ge=1, le=MAX_DEPTH),
) -> dict:
    """Find git repos under `root` (bounded depth, skips symlinks + dotfiles).

    Returns {"root": ..., "items": [{"path","name"}, ...]}.
    """
    if not root or not os.path.isdir(root):
        return {"root": root, "items": []}
    return {"root": root, "items": _scan(os.path.abspath(root), depth)}


@router.get("/repos/validate")
def validate(path: str = Query("", description="absolute path to check")) -> dict:
    """Pre-validate a path without opening it: is_git, name, head."""
    if not path or not os.path.isdir(path):
        return {"is_git": False, "name": None, "head": None}
    if not git_reader.is_git_repo(path):
        return {"is_git": False, "name": None, "head": None}
    try:
        refs = git_reader.read_refs(path)
        return {"is_git": True, "name": git_reader.repo_name(path), "head": refs.head}
    except git_reader.GitError as exc:
        raise HTTPException(status_code=500, detail=f"git error: {exc}") from exc