"""Endpoints for recently-opened repos (PLAN2 §3.2)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import recent, git_reader

router = APIRouter(tags=["repos"])


@router.get("/repos/recent")
def get_recent() -> list[dict]:
    """Return the list of recently opened repos (max 10, newest first)."""
    return recent.load_recent()


@router.post("/repos/recent")
def post_recent(body: dict) -> list[dict]:
    """Push a repo path to the recent list (deduplicates, caps at 10)."""
    path = body.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    return recent.add_recent(path)