"""GitLane backend entrypoint."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import routes_events, routes_history, routes_refs, routes_repo
from .services.watcher import start_watcher

app = FastAPI(title="GitLane", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_repo.router)
app.include_router(routes_history.router)
app.include_router(routes_refs.router)
app.include_router(routes_events.router)


@app.on_event("startup")
def _startup() -> None:
    start_watcher(routes_events.manager)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "gitlane"}


# Serve the built frontend in production (single-process deploy).
_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
