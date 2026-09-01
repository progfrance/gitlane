"""Pydantic models for repository information and API contracts."""
from __future__ import annotations

from pydantic import BaseModel, Field


class OpenRepoRequest(BaseModel):
    path: str = Field(..., description="Absolute path to a local git repository")


class RepoInfo(BaseModel):
    name: str
    path: str
    head: str
    commit_count: int = 0


class OpenRepoResponse(BaseModel):
    ok: bool
    repo: RepoInfo | None = None
    error: str | None = None


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
