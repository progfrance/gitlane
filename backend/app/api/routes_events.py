"""WebSocket events: repo change notifications broadcast to all clients.

Bursts (e.g. a `git pull` adding 50 commits) are coalesced: each repo path
sees at most one outbound event per `~200ms` window, and per-repo counters
of head_change / new_commit are summed. The frontend then re-reads git once
instead of 50 times.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["events"])

# Coalesce window: any new event for a path within this many ms of the
# last one is folded into the in-flight event.
COALESCE_MS = 200


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        # Per-path pending event: { payload, handle } — handle is the
        # scheduled future for the broadcast, or None if not yet scheduled.
        self._pending: dict[str, dict] = {}

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        self._loop = asyncio.get_running_loop()

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    def broadcast_threadsafe(self, payload: dict) -> None:
        """Called from watcher threads — schedules an async broadcast.

        Multiple calls within `COALESCE_MS` for the same path are merged:
        a single `repo_updated` event is emitted with summed counters and
        an OR-folded `head_changed` flag.
        """
        if not self._connections or self._loop is None:
            return
        path = payload.get("path", "")
        existing = self._pending.get(path)
        if existing is not None:
            # Fold counters and flags into the in-flight payload.
            if "count" in payload and "count" in existing["payload"]:
                existing["payload"]["count"] += payload["count"]
            if payload.get("type") == "head_changed":
                existing["payload"]["type"] = "head_changed"
            return
        # First event for this path in the window: schedule a broadcast.
        if payload.get("type") in ("repo_updated", "new_commit", "head_changed"):
            # Normalize to repo_updated; head_changed is folded via the
            # type override above.
            payload = {**payload}
            if payload.get("type") == "new_commit":
                payload.setdefault("count", 1)
            elif payload.get("type") == "head_changed":
                payload.setdefault("count", 0)
            elif payload.get("type") == "repo_updated":
                payload.setdefault("count", 0)
        future = asyncio.run_coroutine_threadsafe(
            self._delayed_broadcast(path, payload), self._loop
        )
        self._pending[path] = {"payload": payload, "handle": future}

    async def _delayed_broadcast(self, path: str, payload: dict) -> None:
        await asyncio.sleep(COALESCE_MS / 1000)
        # Drop the entry first so a burst arriving just after this fires
        # schedules a fresh broadcast (rather than getting merged late).
        self._pending.pop(path, None)
        await self._broadcast(payload)

    async def _broadcast(self, payload: dict) -> None:
        message = json.dumps(payload)
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/events")
async def events(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        while True:
            # Client pings keep the socket alive; server pushes push events.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
