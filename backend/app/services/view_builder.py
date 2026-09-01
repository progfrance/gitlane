"""Build per-branch views: commits + lane layout for a given ref."""
from __future__ import annotations

import time

from . import git_reader
from .cache import MAX_VIEWS_PER_REPO, RefView, RepoState
from .lane_layout import compute_layout


def resolve_ref(state: RepoState, ref: str) -> str:
    """Normalise a requested ref to a concrete ref name.

    "HEAD" (or empty) maps to the repo's checked-out branch.
    """
    if ref in ("HEAD", ""):
        return state.head
    return ref


def build_view(path: str, ref: str) -> RefView:
    """Read commits for `ref` and compute its lane layout (no caching)."""
    commits = git_reader.read_commits(path, ref=ref, with_stats=True)
    parents_map = {c.sha: c.parents for c in commits}
    rows, max_lane = compute_layout([c.sha for c in commits], parents_map)
    layout_rows = [
        {"sha": r.sha, "lane_index": r.lane_index, "node": r.node, "segments": r.segments}
        for r in rows
    ]
    tip = commits[0].sha if commits else None
    return RefView(
        ref=ref,
        head_sha=tip,
        commits=commits,
        layout_rows=layout_rows,
        max_lane=max_lane,
        loaded_at=time.time(),
    )


def get_view(state: RepoState, path: str, ref: str) -> RefView:
    """Return the (cached) view for `ref`, refreshing it on demand.

    Keeps a small LRU per repo so revisiting a branch is instant while
    memory stays bounded.
    """
    ref = resolve_ref(state, ref)
    view = state.views.get(ref)
    if view is not None:
        state.active_ref = ref
        state.active_sha = view.head_sha
        return view
    view = build_view(path, ref)
    if len(state.views) >= MAX_VIEWS_PER_REPO:
        oldest = min(state.views, key=lambda k: state.views[k].loaded_at)
        del state.views[oldest]
    state.views[ref] = view
    state.active_ref = ref
    state.active_sha = view.head_sha
    return view
