"""In-memory repository state cache (one entry per opened repo path).

Each entry keeps the repo's refs plus a small LRU of per-branch "views"
(commits + lane layout) so switching branches never blocks on re-reading
git data for branches already visited.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from .git_reader import CommitData, RefsData

log = logging.getLogger("gitlane.cache")

MAX_CACHED_REPOS = 2
MAX_VIEWS_PER_REPO = 3


@dataclass
class RefView:
    ref: str
    head_sha: str | None
    commits: list[CommitData] = field(default_factory=list)
    layout_rows: list[dict] = field(default_factory=list)
    max_lane: int = 0
    loaded_at: float = 0.0
    # Lazily-filled diff stats (sha -> (additions, deletions)) shared by the
    # history pages and the timeline of this view — no second full `git log`.
    stats: dict[str, tuple[int, int]] = field(default_factory=dict)
    # Per-view search cache: list of (commit, badges, haystacks, badge_names).
    # Rebuilt only when the view instance is replaced (reload), so repeated
    # pages and keystrokes scan without reallocating N tuples.
    _search_cache: list | None = field(default=None, repr=False)


@dataclass
class RepoState:
    path: str
    name: str
    head: str
    head_sha: str | None = None
    refs: RefsData = field(default_factory=RefsData)
    loaded_at: float = 0.0
    # Ref currently served by /history + its tip sha:
    active_ref: str = "HEAD"
    active_sha: str | None = None
    # Per-branch views (LRU) — the HEAD view is seeded on open:
    views: dict[str, RefView] = field(default_factory=dict)
    # Cached sha -> badges index, rebuilt only when refs change.
    _badge_index: dict | None = field(default=None, repr=False)
    _badge_index_key: tuple | None = field(default=None, repr=False)

    @property
    def commits(self) -> list[CommitData]:
        """Commits of the active view (single source of truth)."""
        view = self.views.get(self.active_ref)
        return view.commits if view is not None else []

    @property
    def layout_rows(self) -> list[dict]:
        view = self.views.get(self.active_ref)
        return view.layout_rows if view is not None else []

    @property
    def max_lane(self) -> int:
        view = self.views.get(self.active_ref)
        return view.max_lane if view is not None else 0


class RepoCache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._states: OrderedDict[str, RepoState] = OrderedDict()

    @staticmethod
    def _key(path: str) -> str:
        # Same normalization as routes_repo.open_repo so every entry point
        # (open/history/refs/watcher) hits the same cache slot.
        return os.path.normpath(os.path.abspath(path))

    def get(self, path: str) -> RepoState | None:
        with self._lock:
            state = self._states.get(self._key(path))
            if state is not None:
                # True LRU: a read counts as use, not just a put.
                self._states.move_to_end(self._key(path))
            return state

    def require(self, path: str) -> RepoState:
        state = self.get(path)
        if state is None:
            raise KeyError(f"repo not open: {path}")
        return state

    def put(self, state: RepoState) -> RepoState:
        with self._lock:
            state.loaded_at = time.time()
            self._states[self._key(state.path)] = state
            self._states.move_to_end(self._key(state.path))
            while len(self._states) > MAX_CACHED_REPOS:
                evicted, _ = self._states.popitem(last=False)
                log.info("cache: evicted repo %s", evicted)
        return state

    def invalidate(self, path: str) -> None:
        with self._lock:
            self._states.pop(self._key(path), None)

    def all_paths(self) -> list[str]:
        with self._lock:
            return list(self._states.keys())


cache = RepoCache()
