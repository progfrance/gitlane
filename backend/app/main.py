"""GitLane backend entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api import routes_browse, routes_events, routes_history, routes_recent, routes_refs, routes_repo
from .services.watcher import start_watcher, stop_watcher
from .services import recent
from .services.cache import cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_watcher(routes_events.manager)
    yield
    stop_watcher()


app = FastAPI(title="GitLane", version="0.1.0", lifespan=lifespan)

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
app.include_router(routes_recent.router)
app.include_router(routes_browse.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "gitlane"}


# Serve the built frontend in production (single-process deploy).
_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
_STATIC = os.path.join(os.path.dirname(__file__), "api", "static")


class _FrontendStaticFiles(StaticFiles):
    """A root mount must never receive websocket scopes (uvicorn asserts hard
    on them); reject the handshake cleanly instead of a 500 traceback."""

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            while True:
                message = await receive()
                if message["type"] == "websocket.connect":
                    break
            await send({"type": "websocket.close", "code": 1008})
            return
        await super().__call__(scope, receive, send)


@app.get("/picker", response_model=None)
def picker() -> FileResponse:
    """Serve the repo-picker page (pure HTML+JS — no React/npm needed)."""
    idx = os.path.join(_STATIC, "repos.html")
    if os.path.isfile(idx):
        return FileResponse(idx)
    return FileResponse(os.path.join(_DIST, "index.html"))


@app.get("/", response_model=None)
def index_or_picker(request: Request) -> FileResponse | RedirectResponse:
    """Redirect to /picker only on direct HTML navigation with no repo open."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept and not cache.all_paths() and not recent.load_recent():
        return RedirectResponse(url="/picker")
    return FileResponse(os.path.join(_DIST, "index.html"))


if os.path.isdir(_STATIC):
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")

if os.path.isdir(_DIST):
    app.mount("/", _FrontendStaticFiles(directory=_DIST, html=True), name="frontend")
