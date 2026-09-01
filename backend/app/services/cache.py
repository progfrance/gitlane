"""In-memory repository state cache (one entry per opened repo path)."""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from .git_reader import CommitData, RefsData

MAX_CACHED_REPOS = 4


@dataclass
class RepoState:
    path: str
    name: str
    head: str
    head_sha: str | None = None
    refs: RefsData = field(default_factory=RefsData)
    commits: list[CommitData] = field(default_factory=list)
    loaded_at: float = 0.0
    # Populated by the lane engine:
    layout_rows: list[dict] = field(default_factory=list)
    max_lane: int = 0


class RepoCache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._states: OrderedDict[str, RepoState] = OrderedDict()

    def get(self, path: str) -> RepoState | None:
        with self._lock:
            return self._states.get(path)

    def require(self, path: str) -> RepoState:
        state = self.get(path)
        if state is None:
            raise KeyError(f"repo not open: {path}")
        return state

    def put(self, state: RepoState) -> RepoState:
        with self._lock:
            state.loaded_at = time.time()
            self._states[state.path] = state
            self._states.move_to_end(state.path)
            while len(self._states) > MAX_CACHED_REPOS:
                self._states.popitem(last=False)
        return state

    def invalidate(self, path: str) -> None:
        with self._lock:
            self._states.pop(path, None)

    def all_paths(self) -> list[str]:
        with self._lock:
            return list(self._states.keys())


cache = RepoCache()
