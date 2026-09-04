"""Refs endpoint: branches, remotes, tags and HEAD.

Refreshes refs from the git repo on every call so the branch selector
always sees newly created branches. Paginated (q + limit/offset) so repos
with thousands of tags don't blow up the response.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..models.repo import RefsResponse, RepoRef
from ..services import git_reader
from .errors import git_or_404, require_state

router = APIRouter(tags=["refs"])

DEFAULT_REFS_LIMIT = 200
MAX_REFS_LIMIT = 1000


def _page(items: list[RepoRef], limit: int, offset: int) -> list[RepoRef]:
    return items[offset : offset + limit]


@router.get("/refs", response_model=RefsResponse)
def refs(
    path: str = Query(..., description="repo path previously opened"),
    q: str = Query("", max_length=200, description="case-insensitive substring filter"),
    limit: int = Query(DEFAULT_REFS_LIMIT, ge=1, le=MAX_REFS_LIMIT),
    offset: int = Query(0, ge=0),
) -> RefsResponse:
    state = require_state(path)

    # Re-read refs from git so the branch selector sees new branches even
    # after the initial open. Repo gone -> 404, git broken -> 500 (logged).
    fresh = git_or_404(path, git_reader.read_refs)
    state.refs = fresh
    # Invalidate the cached badge index so the next /history rebuilds it.
    state._badge_index = None

    q_lower = q.strip().lower()

    def _refs(mapping: dict[str, str], kind: str) -> list[RepoRef]:
        items = [RepoRef(name=n, kind=kind, sha=s) for n, s in sorted(mapping.items())]
        if q_lower:
            items = [r for r in items if q_lower in r.name.lower()]
        return _page(items, limit, offset)

    return RefsResponse(
        head=fresh.head,
        head_sha=fresh.head_sha,
        local_branches=_refs(fresh.local_branches, "local_branch"),
        remote_branches=_refs(fresh.remote_branches, "remote_branch"),
        tags=_refs(fresh.tags, "tag"),
    )
