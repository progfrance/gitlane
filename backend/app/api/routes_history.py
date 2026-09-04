"""History endpoint with cursor pagination, live search filtering, and
branch switching via the `ref` query parameter."""
from __future__ import annotations

import base64
import hashlib

from fastapi import APIRouter, HTTPException, Query

from ..models.commit import CommitItem, HistoryEnvelope, RefBadge
from ..services import git_reader, view_builder
from ..services.timeline_builder import build_timeline
from ..services.cache import cache

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


def _build_badge_index(state) -> dict[str, list[RefBadge]]:
    """Map sha -> ref badges from for-each-ref data, built ONCE per request.

    Previously `_badges_for` looped over every branch/tag for every commit
    (O(commits x refs)); the inverted index makes per-commit lookup O(1).
    """
    index: dict[str, list[RefBadge]] = {}
    for name, rsha in state.refs.local_branches.items():
        index.setdefault(rsha, []).append(RefBadge(type="local_branch", name=name))
    for name, rsha in state.refs.remote_branches.items():
        index.setdefault(rsha, []).append(RefBadge(type="remote_branch", name=name))
    for name, rsha in state.refs.tags.items():
        index.setdefault(rsha, []).append(RefBadge(type="tag", name=name))
    return index


def _badges_for(index: dict[str, list[RefBadge]], sha: str, decorations: list[str]) -> list[RefBadge]:
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
    # Merge explicit refs known to for-each-ref (covers packed/edge cases).
    known = {b.name for b in badges}
    for b in index.get(sha, ()):
        if b.name not in known:
            badges.append(b)
            known.add(b.name)
    return badges


def _status_checks(sha: str) -> list[str]:
    """Deterministic placeholder status dots (v1 demo — no CI integration)."""
    digest = hashlib.md5(sha.encode()).digest()
    palette = ("success", "success", "failed", "pending", "success", "failed", "success")
    count = 3 + digest[0] % 3
    return [palette[(digest[i + 1] + i) % len(palette)] for i in range(count)]


def _matches(pre: tuple[str, str, str], q_lower: str, badge_names: set[str]) -> bool:
    subject_lower, sha_lower, author_lower = pre
    if q_lower in subject_lower:
        return True
    if q_lower in sha_lower:
        return True
    if q_lower in author_lower:
        return True
    return any(q_lower in name for name in badge_names)


def _resolve_view(state, path: str, ref: str):
    """Resolve the requested ref to its cached view (400 on invalid ref)."""
    try:
        return view_builder.get_view(state, path, ref)
    except git_reader.InvalidRefError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except git_reader.GitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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

    view = _resolve_view(state, path, ref)

    commits = view.commits
    q = q.strip()
    offset = _decode_cursor(cursor)

    # Per-request badge index (O(refs)) + precomputed lowercase haystacks
    # so the search scan stays O(commits) with cheap substring checks.
    badge_index = _build_badge_index(state)
    precomputed: list[tuple] = []
    for c in commits:
        badges = _badges_for(badge_index, c.sha, c.decorations)
        precomputed.append((
            c,
            badges,
            (c.subject.lower(), c.sha.lower(), c.author_name.lower()),
            {b.name.lower() for b in badges},
        ))

    if q:
        q_lower = q.lower()
        filtered = [(c, b) for c, b, pre, names in precomputed if _matches(pre, q_lower, names)]
    else:
        filtered = [(c, b) for c, b, _pre, _names in precomputed]

    page = filtered[offset : offset + limit]
    has_more = offset + limit < len(filtered)

    # Lazy diff stats: one git call for the served page only, cached on the view.
    stats = view_builder.ensure_stats(path, view, [c.sha for c, _ in page])

    layout_by_sha = {r["sha"]: r for r in view.layout_rows}
    items = []
    for c, badges in page:
        lr = layout_by_sha.get(c.sha, {})
        node = lr.get("node") or {"x": 24, "y": 16, "r": 6.5, "color": "#0091ff"}
        segs = lr.get("segments") or []
        adds, dels = stats.get(c.sha, (0, 0))
        items.append(
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
                lane_index=lr.get("lane_index", 0),
                node=node,
                segments=segs,
                status_checks=_status_checks(c.sha),
                additions=adds,
                deletions=dels,
                is_head=c.sha == view.head_sha,
            )
        )
    return HistoryEnvelope(
        items=items,
        next_cursor=_encode_cursor(offset + limit) if has_more else None,
        has_more=has_more,
        total=len(filtered),
        max_lane=view.max_lane,
        active_ref=view.ref,
    )


@router.get("/timeline")
def timeline(
    path: str = Query(..., description="repo path previously opened"),
    ref: str = "HEAD",
    buckets: int = Query(90, ge=10, le=300),
) -> dict:
    try:
        state = cache.require(path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="repo not open — call /repos/open first") from exc

    view = _resolve_view(state, path, ref)

    # Stats converge lazily: pages already served are cached, the remainder
    # is fetched once here so the sparkline always shows real adds/dels.
    view_builder.ensure_all_stats(path, view)
    return build_timeline(
        [c.timestamp for c in view.commits], buckets,
        additions=[view.stats.get(c.sha, (0, 0))[0] for c in view.commits],
        deletions=[view.stats.get(c.sha, (0, 0))[1] for c in view.commits],
    )
