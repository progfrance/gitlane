"""Pydantic models for commit items and history envelopes."""
from __future__ import annotations

from pydantic import BaseModel

from .graph import NodeGeom, SegmentGeom


class RefBadge(BaseModel):
    type: str  # "local_branch" | "remote_branch" | "tag"
    name: str


class CommitItem(BaseModel):
    sha: str
    short_sha: str
    message_subject: str
    author_name: str
    author_email: str
    timestamp: int
    parents: list[str]
    refs: list[RefBadge] = []
    lane_index: int = 0
    node: NodeGeom | None = None
    segments: list[SegmentGeom] = []
    additions: int = 0
    deletions: int = 0
    is_head: bool = False
    matched: bool = True


class HistoryEnvelope(BaseModel):
    items: list[CommitItem]
    next_cursor: str | None = None
    has_more: bool = False
    total: int = 0
    # Of the filtered set: how many are actual search hits (the rest are
    # parent-context rows kept for graph connectivity). Equals total when
    # there is no query.
    matched_total: int = 0
    max_lane: int = 0
    active_ref: str = "HEAD"


class TimelinePoint(BaseModel):
    t: int
    count: int
    adds: int = 0
    dels: int = 0


class TimelineResponse(BaseModel):
    t_min: int | None = None
    t_max: int | None = None
    points: list[TimelinePoint] = []


class CommitFile(BaseModel):
    path: str
    status: str  # "added" | "modified" | "deleted" | "renamed" | "other"
    additions: int = 0
    deletions: int = 0


class CommitDetail(BaseModel):
    sha: str
    short_sha: str
    message_subject: str
    message_body: str = ""
    author_name: str
    author_email: str
    timestamp: int
    parents: list[str]
    refs: list[RefBadge] = []
    additions: int = 0
    deletions: int = 0
    files: list[CommitFile] = []
    is_head: bool = False
