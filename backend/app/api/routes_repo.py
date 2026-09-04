"""Repo opening, current-repo and single-commit detail endpoints."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from ..models.commit import CommitDetail, CommitFile, RefBadge
from ..models.repo import OpenRepoRequest, OpenRepoResponse, RepoInfo
from ..services import git_reader, recent, view_builder
from ..services.cache import RepoState, cache
from .errors import git_or_404, require_state

router = APIRouter(tags=["repo"])

MAX_SHA_LEN = 40


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
    a 500 from `rev-parse HEAD`. Raises HTTPException with a mapped status
    (400 bad ref, 404 repo gone, 500 genuine git failure) so both routes
    and the watcher get a consistent contract.
    """
    try:
        refs = git_reader.read_refs(path)
        view = view_builder.build_view(path, refs.head)
    except git_reader.RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except git_reader.InvalidRefError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except git_reader.GitError as exc:
        raise HTTPException(status_code=500, detail=f"git error: {exc}") from exc

    state = RepoState(path=path, name=git_reader.repo_name(path), head=refs.head)
    state.head_sha = refs.head_sha
    state.refs = refs
    state.active_ref = refs.head
    state.active_sha = view.head_sha
    state.views[refs.head] = view
    # Any cached badge index from a previous generation is stale.
    state._badge_index = None
    state._badge_index_key = None

    cache.put(state)
    return state


def _badges_for_sha(state: RepoState, sha: str) -> list[RefBadge]:
    """Ref badges pointing at `sha` (branches + tags)."""
    badges: list[RefBadge] = []
    for name, rsha in state.refs.local_branches.items():
        if rsha == sha:
            badges.append(RefBadge(type="local_branch", name=name))
    for name, rsha in state.refs.remote_branches.items():
        if rsha == sha:
            badges.append(RefBadge(type="remote_branch", name=name))
    for name, rsha in state.refs.tags.items():
        if rsha == sha:
            badges.append(RefBadge(type="tag", name=name))
    return badges


@router.get("/commit/detail", response_model=CommitDetail)
def commit_detail(
    path: str = Query(..., description="repo path previously opened"),
    sha: str = Query(..., max_length=MAX_SHA_LEN, description="commit sha (4-40 hex chars)"),
) -> CommitDetail:
    """Full detail for one commit: message body, parents, files, stats."""
    state = require_state(path)
    data = git_or_404(path, git_reader.read_commit_detail, sha)
    return CommitDetail(
        sha=data.sha,
        short_sha=data.sha[:7],
        message_subject=data.subject,
        message_body=data.body,
        author_name=data.author_name,
        author_email=data.author_email,
        timestamp=data.timestamp,
        parents=data.parents,
        refs=_badges_for_sha(state, data.sha),
        additions=data.additions,
        deletions=data.deletions,
        files=[CommitFile(**f) for f in data.files],
        is_head=data.sha == state.head_sha,
    )


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
