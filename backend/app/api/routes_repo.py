"""Repo opening and current-repo endpoints."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from ..models.repo import OpenRepoRequest, OpenRepoResponse, RepoInfo
from ..services import git_reader
from ..services.cache import RepoState, cache

router = APIRouter(tags=["repo"])


@router.post("/repos/open", response_model=OpenRepoResponse)
def open_repo(body: OpenRepoRequest) -> OpenRepoResponse:
    path = os.path.normpath(body.path)
    if not os.path.isabs(path):
        raise HTTPException(status_code=400, detail="path must be absolute")
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"directory not found: {path}")
    if not git_reader.is_git_repo(path):
        raise HTTPException(status_code=400, detail=f"not a git repository: {path}")

    try:
        refs = git_reader.read_refs(path)
        commits = git_reader.read_commits(path, ref=refs.head)
    except git_reader.GitError as exc:
        raise HTTPException(status_code=500, detail=f"git error: {exc}") from exc

    state = RepoState(path=path, name=git_reader.repo_name(path), head=refs.head)
    state.head_sha = refs.head_sha
    state.refs = refs
    state.commits = commits
    cache.put(state)

    return OpenRepoResponse(
        ok=True,
        repo=RepoInfo(name=state.name, path=state.path, head=state.head, commit_count=len(commits)),
    )


@router.get("/repos/current", response_model=RepoInfo | None)
def current_repo() -> RepoInfo | None:
    paths = cache.all_paths()
    if not paths:
        return None
    state = cache.require(paths[-1])
    return RepoInfo(name=state.name, path=state.path, head=state.head, commit_count=len(state.commits))
