"""Central error mapping: git/service exceptions -> HTTP status codes.

400 for caller mistakes (invalid ref/sha, bad cursor), 404 when the repo
vanished mid-session, 500 (logged server-side) for genuine git failures.
Routes must use these helpers instead of ad-hoc try/except mapping.
"""
from __future__ import annotations

import logging
import os

from fastapi import HTTPException

from ..services import git_reader

log = logging.getLogger("gitlane.api")


def require_state(path: str):
    """Fetch the cached repo state, self-healing an LRU eviction.

    A repo evicted from the cache (e.g. the user switched away and back) is
    transparently reloaded from disk when the path is still a valid git
    repository — in-flight /history or /refs calls must not 404 mid-switch.
    Only paths that are not (or no longer) a repo raise 404.
    """
    from ..services.cache import cache
    from .routes_repo import reload_state

    state = cache.get(path)
    if state is not None:
        return state
    if os.path.isdir(path) and git_reader.is_git_repo(path):
        return reload_state(path)
    raise HTTPException(status_code=404, detail="repo not open — call /repos/open first")


def resolve_view(state, path: str, ref: str):
    """Resolve the requested ref to its cached view with mapped errors."""
    from ..services import view_builder

    try:
        return view_builder.get_view(state, path, ref)
    except git_reader.InvalidRefError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except git_reader.RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except git_reader.GitError as exc:
        log.warning("git failure for %s ref %s: %s", path, ref, exc)
        raise HTTPException(status_code=500, detail="git failed to read history") from exc


def git_or_404(path: str, fn, *args, **kwargs):
    """Run a git reader call, mapping RepoNotFoundError->404, GitError->500."""
    try:
        return fn(path, *args, **kwargs)
    except git_reader.RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except git_reader.InvalidRefError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except git_reader.GitError as exc:
        log.warning("git failure for %s: %s", path, exc)
        raise HTTPException(status_code=500, detail="git operation failed") from exc
