"""Build per-branch views: commits + lane layout for a given ref."""
from __future__ import annotations

import logging
import os
import time

from . import git_reader
from .cache import MAX_VIEWS_PER_REPO, RefView, RepoState
from .lane_layout import compute_layout

log = logging.getLogger("gitlane.views")


def resolve_ref(state: RepoState, ref: str) -> str:
    """Normalise a requested ref to a concrete ref name.

    "HEAD" (or empty) maps to the repo's checked-out branch.
    """
    if ref in ("HEAD", ""):
        return state.head
    return ref


def build_view(path: str, ref: str) -> RefView:
    """Read commits for `ref` and compute its lane layout (no caching).

    Diff stats are NOT loaded here: they are filled lazily per served page
    (see ensure_stats) so opening a large repo never pays a second full
    `git log --numstat` walk upfront.
    """
    commits = git_reader.read_commits(path, ref=ref)
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

    LRU eviction: `loaded_at` is refreshed on every hit so a frequently
    visited branch is not evicted as "oldest".
    """
    ref = resolve_ref(state, ref)
    view = state.views.get(ref)
    if view is not None:
        view.loaded_at = time.time()
        state.active_ref = ref
        state.active_sha = view.head_sha
        return view
    if not os.path.isdir(path):
        raise git_reader.RepoNotFoundError(f"repo directory gone: {path}")
    try:
        view = build_view(path, ref)
    except git_reader.InvalidRefError:
        raise
    except git_reader.RepoNotFoundError:
        raise
    except git_reader.GitError as exc:
        # Genuine git failure (timeout, binary, I/O) — NOT a 400: let the
        # route map it to a 500 instead of blaming the caller's ref.
        log.warning("get_view(%s, %s) git failure: %s", path, ref, exc)
        raise
    if len(state.views) >= MAX_VIEWS_PER_REPO:
        oldest = min(state.views, key=lambda k: state.views[k].loaded_at)
        del state.views[oldest]
        log.info("cache: evicted view %s for %s", oldest, path)
    state.views[ref] = view
    state.active_ref = ref
    state.active_sha = view.head_sha
    return view


def ensure_stats(path: str, view: RefView, shas: list[str]) -> dict[str, tuple[int, int]]:
    """Fill additions/deletions for `shas`, one git call, cached on the view.

    Only missing SHAs are fetched, so paginated history and the timeline
    converge toward a fully-populated cache without ever re-walking the
    whole log. Failures degrade to (0, 0) for the missing SHAs.
    """
    missing = [s for s in shas if s not in view.stats]
    if missing:
        try:
            fetched = git_reader.read_diff_stats_for_shas(path, missing)
        except git_reader.GitError as exc:
            log.warning("ensure_stats(%s) failed: %s", path, exc)
            fetched = {}
        for s in missing:
            view.stats[s] = fetched.get(s, (0, 0))
    return {s: view.stats.get(s, (0, 0)) for s in shas}
