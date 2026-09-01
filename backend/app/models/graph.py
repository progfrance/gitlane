"""Pydantic models for the lane graph rendering contract."""
from __future__ import annotations

from pydantic import BaseModel


class NodeGeom(BaseModel):
    x: float
    y: float
    r: float
    color: str


class SegmentGeom(BaseModel):
    type: str  # "vertical" | "curve" (bezier) — cx*/cy* present only for curves
    x1: float
    y1: float
    x2: float
    y2: float
    cx1: float | None = None
    cy1: float | None = None
    cx2: float | None = None
    cy2: float | None = None
    color: str
    w: float = 2.0
