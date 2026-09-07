"""History endpoint with cursor pagination, live search filtering, and
branch switching via the `ref` query parameter."""
from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, Query

from ..models.commit import CommitItem, HistoryEnvelope, RefBadge, TimelineResponse
from ..services import view_builder
from ..services.lane_layout import compute_layout
from ..services.timeline_builder import build_timeline
from ..services.cache import RefView
from .errors import require_state, resolve_view

router = APIRouter(tags=["history"])

DEFAULT_LIMIT = 300
MAX_LIMIT = 1000
MAX_QUERY_LEN = 200
MAX_REF_LEN = 250
MAX_CURSOR_LEN = 64


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    if len(cursor) > MAX_CURSOR_LEN:
        raise HTTPException(status_code=400, detail="invalid cursor")
    try:
        return max(0, int(base64.b64decode(cursor.encode()).decode()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc


def _encode_cursor(offset: int) -> str:
    return base64.b64encode(str(offset).encode()).decode()


def _build_badge_index(state) -> dict[str, list[RefBadge]]:
    """Map sha -> ref badges from for-each-ref data.

    Result is cached on the RepoState and rebuilt only when refs change
    (tracked via head_sha), so repeated pages/searches skip the O(refs)
    rebuild. Per-commit lookup stays O(1).
    """
    cached = getattr(state, "_badge_index", None)
    cached_key = getattr(state, "_badge_index_key", None)
    key = (state.head_sha, len(state.refs.local_branches),
           len(state.refs.remote_branches), len(state.refs.tags))
    if cached is not None and cached_key == key:
        return cached
    index: dict[str, list[RefBadge]] = {}
    for name, rsha in state.refs.local_branches.items():
        index.setdefault(rsha, []).append(RefBadge(type="local_branch", name=name))
    for name, rsha in state.refs.remote_branches.items():
        index.setdefault(rsha, []).append(RefBadge(type="remote_branch", name=name))
    for name, rsha in state.refs.tags.items():
        index.setdefault(rsha, []).append(RefBadge(type="tag", name=name))
    state._badge_index = index
    state._badge_index_key = key
    return index


def _badges_for(index: dict[str, list[RefBadge]], sha: str, decorations: list[str]) -> list[RefBadge]:
    badges: list[RefBadge] = []
    for deco in decorations:
        if deco.startswith("HEAD -> "):
            badges.append(RefBadge(type="local_branch", name=deco[len("HEAD -> "):]))
        elif deco.startswith("tag: "):
            badges.append(RefBadge(type="tag", name=deco[len("tag: "):]))
        elif deco.startswith("origin/"):
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
    """Resolve the requested ref to its cached view (mapping via api/errors)."""
    return resolve_view(state, path, ref)


def _search_index(view: RefView, badge_index: dict[str, list[RefBadge]]):
    """Per-view search cache: badges + lowercase haystacks, built once.

    Rebuilt only when the view object changes (new instance after reload),
    so repeated pages and keystrokes scan without reallocating N tuples.
    """
    cached = getattr(view, "_search_cache", None)
    if cached is not None:
        return cached
    rows = []
    for c in view.commits:
        badges = _badges_for(badge_index, c.sha, c.decorations)
        rows.append((
            c,
            badges,
            (c.subject.lower(), c.sha.lower(), c.author_name.lower()),
            {b.name.lower() for b in badges},
        ))
    view._search_cache = rows
    return rows


@router.get("/history", response_model=HistoryEnvelope)
def history(
    path: str = Query(..., description="repo path previously opened"),
    cursor: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    q: str = Query("", max_length=MAX_QUERY_LEN),
    ref: str = Query("HEAD", max_length=MAX_REF_LEN),
) -> HistoryEnvelope:
    state = require_state(path)

    view = _resolve_view(state, path, ref)

    q = q.strip()
    offset = _decode_cursor(cursor)

    # Cached badge index + cached search rows: a page costs O(page), and a
    # search keystroke costs one O(commits) substring scan with no per-commit
    # branch/tag loops and no per-request N-tuple rebuild.
    badge_index = _build_badge_index(state)
    precomputed = _search_index(view, badge_index)

    if q:
        q_lower = q.lower()
        matched = [(c, b) for c, b, pre, names in precomputed if _matches(pre, q_lower, names)]
        # Include the ancestors of every match (transitively, through all
        # parents, within this view) so the lane graph stays connected: a
        # merge hit needs both parents present for its curves to land on a
        # rendered row. Non-matching ancestors render dimmed as context.
        if matched:
            by_sha = {c.sha: (c, b) for c, b, _pre, _names in precomputed}
            matched_shas = {c.sha for c, _ in matched}
            queue = list(matched_shas)
            context: list[tuple] = []
            seen = set(matched_shas)
            while queue:
                sha = queue.pop()
                entry = by_sha.get(sha)
                if entry is None:
                    continue
                for p in entry[0].parents:
                    if p in seen or p not in by_sha:
                        continue
                    seen.add(p)
                    context.append(by_sha[p])
                    queue.append(p)
            # Restore chronological order (children first, like the view).
            order = {c.sha: i for i, (c, _b, _pre, _names) in enumerate(precomputed)}
            filtered = sorted(
                [(c, b, True) for c, b in matched] + [(c, b, False) for c, b in context],
                key=lambda t: order.get(t[0].sha, 0),
            )
        else:
            filtered = []
    else:
        filtered = [(c, b, True) for c, b, _pre, _names in precomputed]

    page = filtered[offset : offset + limit]
    has_more = offset + limit < len(filtered)

    # Lazy diff stats: one git call for the served page only, cached on the view.
    stats = view_builder.ensure_stats(path, view, [c.sha for c, _, _ in page])

    if q:
        # Recompute the lane layout on the served page (matches + parent
        # context) so graph nodes/segments stay connected across the gaps
        # left by non-matching commits — full-history positions would draw
        # dangling curves pointing at rows that are not rendered.
        page_shas = [c.sha for c, _, _ in page]
        page_set = set(page_shas)
        parents_map = {c.sha: [p for p in c.parents if p in page_set] for c, _, _ in page}
        page_rows, page_max_lane = compute_layout(page_shas, parents_map)
        layout_by_sha = {
            r.sha: {"node": r.node, "segments": r.segments, "lane_index": r.lane_index}
            for r in page_rows
        }
        max_lane = page_max_lane
    else:
        layout_by_sha = {r["sha"]: r for r in view.layout_rows if r["sha"] in {c.sha for c, _, _ in page}}
        max_lane = view.max_lane
    items = []
    for c, badges, is_match in page:
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
                timestamp=c.timestamp,
                parents=c.parents,
                refs=badges,
                lane_index=lr.get("lane_index", 0),
                node=node,
                segments=segs,
                additions=adds,
                deletions=dels,
                is_head=c.sha == view.head_sha,
                matched=is_match,
            )
        )
    return HistoryEnvelope(
        items=items,
        next_cursor=_encode_cursor(offset + limit) if has_more else None,
        has_more=has_more,
        total=len(filtered),
        matched_total=sum(1 for _c, _b, m in filtered if m),
        max_lane=max_lane,
        active_ref=view.ref,
    )


@router.get("/timeline", response_model=TimelineResponse)
def timeline(
    path: str = Query(..., description="repo path previously opened"),
    ref: str = Query("HEAD", max_length=MAX_REF_LEN),
    buckets: int = Query(90, ge=10, le=300),
) -> TimelineResponse:
    state = require_state(path)

    view = _resolve_view(state, path, ref)

    # Sample commits per bucket BEFORE fetching stats: one bounded
    # `diff-tree` over ~buckets SHAs instead of all N commits, then aggregate
    # the sampled adds/dels. Cost is O(buckets), not O(history).
    n = len(view.commits)
    if n == 0:
        return TimelineResponse(t_min=None, t_max=None, points=[])
    step = max(1, n // (buckets * 4))
    sampled_shas = [view.commits[i].sha for i in range(0, n, step)]
    stats = view_builder.ensure_stats(path, view, sampled_shas)
    sampled = [
        (view.commits[i].timestamp, *stats.get(view.commits[i].sha, (0, 0)))
        for i in range(0, n, step)
    ]
    data = build_timeline(
        [t for t, _a, _d in sampled], buckets,
        additions=[a for _t, a, _d in sampled],
        deletions=[d for _t, _a, d in sampled],
    )
    return TimelineResponse(**data)
