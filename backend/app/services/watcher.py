"""Filesystem watcher: polls .git metadata and broadcasts change events.

Light polling (2s) on HEAD, refs and index mtimes — no external dependency,
works on every platform. On change, the affected repo cache entry is
invalidated and a websocket event is broadcast to all clients (PLAN 7.4).
"""
from __future__ import annotations

import os
import threading
import time

from .cache import cache
from .git_reader import GitError, read_commits, read_refs

POLL_INTERVAL = 2.0


def _snapshot(repo_path: str) -> tuple:
    """Signature of the repo's volatile metadata."""
    parts = []
    git_dir = os.path.join(repo_path, ".git")
    candidates = [
        os.path.join(git_dir, "HEAD"),
        os.path.join(git_dir, "packed-refs"),
        os.path.join(git_dir, "index"),
        os.path.join(git_dir, "logs", "HEAD"),
    ]
    refs_dir = os.path.join(git_dir, "refs")
    if os.path.isdir(refs_dir):
        for root, _dirs, files in os.walk(refs_dir):
            for f in files:
                candidates.append(os.path.join(root, f))
    for p in candidates:
        try:
            parts.append((p, os.stat(p).st_mtime_ns))
        except OSError:
            parts.append((p, 0))
    return tuple(parts)


class RepoWatcher(threading.Thread):
    """Daemon polling all open repos; emits events through the WS manager."""

    def __init__(self, manager) -> None:
        super().__init__(daemon=True, name="gitlane-watcher")
        self.manager = manager
        self._signatures: dict[str, tuple] = {}
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.wait(POLL_INTERVAL):
            for path in cache.all_paths():
                state = cache.get(path)
                if state is None:
                    continue
                sig = _snapshot(path)
                old = self._signatures.get(path)
                if old is None:
                    # First sighting after open: baseline, no event.
                    self._signatures[path] = sig
                    continue
                if sig == old:
                    continue
                self._signatures[path] = sig
                self._on_change(state)

    def _on_change(self, state) -> None:
        events: list[dict] = [{"type": "repo_updated", "path": state.path}]
        try:
            refs = read_refs(state.path)
            new_head_sha = refs.head_sha
            new_count = len(read_commits(state.path, ref=refs.head))
            old_count = len(state.commits)
            if new_head_sha and new_head_sha != state.head_sha:
                events.append({"type": "head_changed", "path": state.path, "head": refs.head})
            if new_count > old_count:
                events.append({"type": "new_commit", "path": state.path, "count": new_count})
            # Refresh cached state (refs, commits, layout) for next fetches.
            from ..api.routes_repo import reload_state

            reload_state(state.path)
        except (GitError, OSError):
            pass
        for ev in events:
            self.manager.broadcast_threadsafe(ev)


_watcher: RepoWatcher | None = None


def start_watcher(manager) -> None:
    global _watcher
    if _watcher is None or not _watcher.is_alive():
        _watcher = RepoWatcher(manager)
        _watcher.start()


def stop_watcher() -> None:
    if _watcher is not None:
        _watcher.stop()
