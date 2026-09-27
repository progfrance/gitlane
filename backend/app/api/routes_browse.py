"""Browse for git repositories on disk + lightweight path validation (PLAN2 §3.2)."""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Query

from ..services import git_reader, scan
from .errors import git_or_404

log = logging.getLogger("gitlane.browse")

router = APIRouter(tags=["repos"])


@router.get("/repos/browse")
def browse(
    root: str = Query("", description="absolute root directory to scan"),
    depth: int = Query(1, ge=1, le=scan.MAX_DEPTH),
) -> dict:
    """Find git repos under `root` (bounded depth/results/time, skips
    symlinks + dotfiles + heavy dirs like node_modules/.venv).

    Returns {"root": ..., "items": [...], "truncated": bool}.
    """
    if not root or not os.path.isdir(root):
        return {"root": root, "items": [], "truncated": False}
    abs_root = os.path.abspath(root)
    if scan.is_refused_root(abs_root):
        raise HTTPException(status_code=400, detail="scanning system directories is not allowed")
    found, complete = scan.scan(abs_root, depth)
    truncated = not complete or len(found) >= scan.MAX_RESULTS
    if not complete:
        log.info("browse(%s) stopped early: budget/results exhausted", abs_root)
    return {"root": root, "items": found[:scan.MAX_RESULTS], "truncated": truncated}


@router.get("/repos/validate")
def validate(path: str = Query("", max_length=1024, description="absolute path to check")) -> dict:
    """Pre-validate a path without opening it: is_git, name, head."""
    if not path or not os.path.isdir(path):
        return {"is_git": False, "name": None, "head": None}
    if not git_reader.is_git_repo(path):
        return {"is_git": False, "name": None, "head": None}
    refs = git_or_404(path, git_reader.read_refs)
    return {"is_git": True, "name": git_reader.repo_name(path), "head": refs.head}