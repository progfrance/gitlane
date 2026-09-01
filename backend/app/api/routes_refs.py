"""Refs endpoint: branches, remotes, tags and HEAD.

Refreshes refs from the git repo on every call so the branch selector
always sees newly created branches.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.repo import RefsResponse, RepoRef
from ..services import git_reader
from ..services.cache import cache

router = APIRouter(tags=["refs"])


@router.get("/refs", response_model=RefsResponse)
def refs(path: str = Query(..., description="repo path previously opened")) -> RefsResponse:
    try:
        state = cache.require(path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="repo not open — call /repos/open first") from exc

    # Re-read refs from git so the branch selector sees new branches even
    # after the initial open.
    try:
        fresh = git_reader.read_refs(path)
    except git_reader.GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    state.refs = fresh

    return RefsResponse(
        head=fresh.head,
        head_sha=fresh.head_sha,
        local_branches=[RepoRef(name=n, kind="local_branch", sha=s) for n, s in sorted(fresh.local_branches.items())],
        remote_branches=[RepoRef(name=n, kind="remote_branch", sha=s) for n, s in sorted(fresh.remote_branches.items())],
        tags=[RepoRef(name=n, kind="tag", sha=s) for n, s in sorted(fresh.tags.items())],
    )