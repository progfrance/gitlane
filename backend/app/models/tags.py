"""Pydantic models for the cross-repo tag search endpoint."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TagHit(BaseModel):
    repo_name: str
    repo_path: str
    tag_name: str
    sha: str
    age_seconds: int = Field(0, description="0 for lightweight tags (no tagger)")


class TagsFindResponse(BaseModel):
    root: str
    tag: str
    scanned: int = Field(0, description="number of git repos visited")
    truncated: bool = Field(False, description="scan stopped before completion (budget/results)")
    items: list[TagHit] = []
    missing: list[str] = Field(default_factory=list, description="repo paths where git failed")