"""Endpoints for recently-opened repos (PLAN2 §3.2)."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from ..models.repo import RecentRepoRequest
from ..services import git_reader, recent

router = APIRouter(tags=["repos"])


@router.get("/repos/recent")
def get_recent() -> list[dict]:
    """Return the list of recently opened repos (max 10, newest first)."""
    return recent.load_recent()


@router.post("/repos/recent")
def post_recent(body: RecentRepoRequest) -> list[dict]:
    """Push a repo path to the recent list (deduplicates, caps at 10).

    Only real git repositories are recorded — unlike an open `dict` body,
    a stray path can no longer pollute the recents. Path must be absolute
    so the normalized key matches what the picker hands back.
    """
    raw = body.path
    if not os.path.isabs(raw):
        raise HTTPException(status_code=400, detail=f"path must be absolute: {raw!r}")
    path = os.path.normpath(os.path.abspath(raw))
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"directory not found: {path}")
    if not git_reader.is_git_repo(path):
        raise HTTPException(status_code=400, detail=f"not a git repository: {path}")
    return recent.add_recent(path)
