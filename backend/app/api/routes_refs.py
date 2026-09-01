"""Refs endpoint: branches, remotes, tags and HEAD."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.repo import RefsResponse, RepoRef
from ..services.cache import cache

router = APIRouter(tags=["refs"])


@router.get("/refs", response_model=RefsResponse)
def refs(path: str = Query(..., description="repo path previously opened")) -> RefsResponse:
    try:
        state = cache.require(path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="repo not open — call /repos/open first") from exc

    r = state.refs
    return RefsResponse(
        head=r.head,
        head_sha=r.head_sha,
        local_branches=[RepoRef(name=n, kind="local_branch", sha=s) for n, s in sorted(r.local_branches.items())],
        remote_branches=[RepoRef(name=n, kind="remote_branch", sha=s) for n, s in sorted(r.remote_branches.items())],
        tags=[RepoRef(name=n, kind="tag", sha=s) for n, s in sorted(r.tags.items())],
    )
