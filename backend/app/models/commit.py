"""Pydantic models for commit items and history envelopes."""
from __future__ import annotations

from pydantic import BaseModel

from .graph import NodeGeom, SegmentGeom


class RefBadge(BaseModel):
    type: str  # "local_branch" | "remote_branch" | "tag" | "head"
    name: str


class CommitItem(BaseModel):
    sha: str
    short_sha: str
    message_subject: str
    author_name: str
    author_email: str
    author_avatar_url: str | None = None
    timestamp: int
    relative_time: str
    parents: list[str]
    refs: list[RefBadge] = []
    lane_index: int = 0
    node: NodeGeom | None = None
    segments: list[SegmentGeom] = []
    status_checks: list[str] = []


class HistoryEnvelope(BaseModel):
    items: list[CommitItem]
    next_cursor: str | None = None
    has_more: bool = False
    total: int = 0
    max_lane: int = 0


class TimelinePoint(BaseModel):
    t: int
    count: int


class TimelineResponse(BaseModel):
    t_min: int | None = None
    t_max: int | None = None
    points: list[TimelinePoint] = []
