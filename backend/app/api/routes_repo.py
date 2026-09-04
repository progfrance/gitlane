"""Repo opening and current-repo endpoints."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from ..models.repo import OpenRepoRequest, OpenRepoResponse, RepoInfo
from ..services import git_reader, recent, view_builder
from ..services.cache import RepoState, cache

router = APIRouter(tags=["repo"])


@router.post("/repos/open", response_model=OpenRepoResponse)
def open_repo(body: OpenRepoRequest) -> OpenRepoResponse:
    path = os.path.normpath(os.path.abspath(body.path))
    if not os.path.isabs(path):
        raise HTTPException(status_code=400, detail="path must be absolute")
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"directory not found: {path}")
    if not git_reader.is_git_repo(path):
        raise HTTPException(status_code=400, detail=f"not a git repository: {path}")
    state = reload_state(path)
    recent.add_recent(path)
    return OpenRepoResponse(
        ok=True,
        repo=RepoInfo(
            name=state.name,
            path=state.path,
            head=state.head,
            commit_count=len(state.commits),
            remote=git_reader.read_remote(path),
        ),
    )


def reload_state(path: str) -> RepoState:
    """(Re)read refs, commits and lane layout for an open repo (HEAD view).

    Empty repos (no commits yet) open cleanly with zero commits instead of
    a 500 from `rev-parse HEAD`.
    """
    try:
        refs = git_reader.read_refs(path)
        view = view_builder.build_view(path, refs.head)
    except git_reader.GitError as exc:
        raise HTTPException(status_code=500, detail=f"git error: {exc}") from exc

    state = RepoState(path=path, name=git_reader.repo_name(path), head=refs.head)
    state.head_sha = refs.head_sha
    state.refs = refs
    state.commits = view.commits
    state.layout_rows = view.layout_rows
    state.max_lane = view.max_lane
    state.active_ref = refs.head
    state.active_sha = view.head_sha
    state.views[refs.head] = view

    cache.put(state)
    return state


@router.get("/repos/current", response_model=RepoInfo | None)
def current_repo() -> RepoInfo | None:
    paths = cache.all_paths()
    if paths:
        state = cache.require(paths[-1])
        return RepoInfo(
            name=state.name, path=state.path, head=state.head,
            commit_count=len(state.commits), remote=git_reader.read_remote(state.path),
        )
    # Cold start: reopen the most recently opened repo from persistence.
    last = recent.last_repo()
    if last and os.path.isdir(last) and git_reader.is_git_repo(last):
        try:
            state = reload_state(last)
            return RepoInfo(
                name=state.name, path=state.path, head=state.head,
                commit_count=len(state.commits), remote=git_reader.read_remote(state.path),
            )
        except HTTPException:
            return None
    return None
