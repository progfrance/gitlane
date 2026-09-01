"""History endpoint with cursor pagination and live search filtering."""
from __future__ import annotations

import base64
import hashlib

from fastapi import APIRouter, HTTPException, Query

from ..models.commit import CommitItem, HistoryEnvelope, RefBadge
from ..services import git_reader
from ..services.cache import RepoState, cache

router = APIRouter(tags=["history"])

DEFAULT_LIMIT = 300
MAX_LIMIT = 1000


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(base64.b64decode(cursor.encode()).decode()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc


def _encode_cursor(offset: int) -> str:
    return base64.b64encode(str(offset).encode()).decode()


def _badges_for(state: RepoState, sha: str, decorations: list[str]) -> list[RefBadge]:
    badges: list[RefBadge] = []
    for deco in decorations:
        if deco.startswith("HEAD -> "):
            badges.append(RefBadge(type="local_branch", name=deco[len("HEAD -> "):]))
        elif deco.startswith("tag: "):
            badges.append(RefBadge(type="tag", name=deco[len("tag: "):]))
        elif "/" in deco and deco.split("/", 1)[0] in ("origin",) or deco.startswith("origin/"):
            badges.append(RefBadge(type="remote_branch", name=deco))
        else:
            badges.append(RefBadge(type="local_branch", name=deco))
    # Guarantee explicit refs known to for-each-ref (covers packed/edge cases).
    known = {b.name for b in badges}
    for name, rsha in state.refs.local_branches.items():
        if rsha == sha and name not in known:
            badges.append(RefBadge(type="local_branch", name=name))
    for name, rsha in state.refs.remote_branches.items():
        if rsha == sha and name not in known:
            badges.append(RefBadge(type="remote_branch", name=name))
    for name, rsha in state.refs.tags.items():
        if rsha == sha and name not in known:
            badges.append(RefBadge(type="tag", name=name))
    return badges


def _status_checks(sha: str) -> list[str]:
    """Deterministic placeholder status dots (v1 demo — no CI integration)."""
    digest = hashlib.md5(sha.encode()).digest()
    palette = ("success", "success", "failed", "pending", "success", "failed", "success")
    count = 3 + digest[0] % 3
    return [palette[(digest[i + 1] + i) % len(palette)] for i in range(count)]


def _matches(commit, q_lower: str, badge_names: set[str]) -> bool:
    if q_lower in commit.subject.lower():
        return True
    if q_lower in commit.sha.lower():
        return True
    if q_lower in commit.author_name.lower():
        return True
    return any(q_lower in name.lower() for name in badge_names)


@router.get("/history", response_model=HistoryEnvelope)
def history(
    path: str = Query(..., description="repo path previously opened"),
    cursor: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    q: str = "",
    ref: str = "HEAD",
) -> HistoryEnvelope:
    try:
        state = cache.require(path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="repo not open — call /repos/open first") from exc

    if ref != state.head and ref not in (state.refs.local_branches | state.refs.remote_branches | state.refs.tags):
        # Allow any valid ref the repo knows; reload lazily when needed.
        pass

    commits = state.commits
    q = q.strip()
    offset = _decode_cursor(cursor)

    if q:
        q_lower = q.lower()
        filtered = []
        for c in commits:
            badges = _badges_for(state, c.sha, c.decorations)
            if _matches(c, q_lower, {b.name for b in badges}):
                filtered.append((c, badges))
    else:
        filtered = [(c, _badges_for(state, c.sha, c.decorations)) for c in commits]

    page = filtered[offset : offset + limit]
    has_more = offset + limit < len(filtered)
    items = [
        CommitItem(
            sha=c.sha,
            short_sha=c.sha[:7],
            message_subject=c.subject,
            author_name=c.author_name,
            author_email=c.author_email,
            author_avatar_url=None,
            timestamp=c.timestamp,
            relative_time=git_reader.relative_time(c.timestamp),
            parents=c.parents,
            refs=badges,
            lane_index=0,
            status_checks=_status_checks(c.sha),
        )
        for c, badges in page
    ]
    return HistoryEnvelope(
        items=items,
        next_cursor=_encode_cursor(offset + limit) if has_more else None,
        has_more=has_more,
        total=len(filtered),
    )
