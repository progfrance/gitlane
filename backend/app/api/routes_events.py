"""WebSocket events: repo change notifications broadcast to all clients."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["events"])


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        self._loop = asyncio.get_running_loop()

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    def broadcast_threadsafe(self, payload: dict) -> None:
        """Called from watcher threads — schedules an async broadcast."""
        if not self._connections or self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)

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
