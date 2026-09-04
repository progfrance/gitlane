"""Pydantic models for repository information and API contracts."""
from __future__ import annotations

from pydantic import BaseModel, Field


class OpenRepoRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=1024, description="Absolute path to a local git repository")


class RepoInfo(BaseModel):
    name: str
    path: str
    head: str
    commit_count: int = 0
    remote: str | None = None


class OpenRepoResponse(BaseModel):
    ok: bool
    repo: RepoInfo


class RepoRef(BaseModel):
    name: str
    kind: str  # "local_branch" | "remote_branch" | "tag"
    sha: str


class RefsResponse(BaseModel):
    head: str
    head_sha: str | None = None
    local_branches: list[RepoRef] = []
    remote_branches: list[RepoRef] = []
    tags: list[RepoRef] = []


class RecentRepoRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=1024)
