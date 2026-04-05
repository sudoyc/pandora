"""WebSocket connection manager for pandora-daemon."""
import asyncio

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, event: dict) -> None:
        dead = []
        for ws in list(self.connections):
            try:
                await asyncio.wait_for(ws.send_json(event), timeout=5.0)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections.discard(ws)
