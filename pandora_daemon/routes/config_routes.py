"""Config and WebSocket routes for pandora-daemon."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from pandora_daemon.config import save_config
from pandora_daemon.dependencies import get_state
from pandora_daemon.state import AppState

router = APIRouter(tags=["config"])


def _pandora_version() -> str:
    try:
        return version("pandora")
    except PackageNotFoundError:
        return "0.2.0"


@router.get("/api/config")
async def get_config(state: AppState = Depends(get_state)):
    return state.config.to_public_dict()


@router.get("/api/health")
async def get_health(state: AppState = Depends(get_state)):
    config = state.config
    return {
        "ok": True,
        "version": _pandora_version(),
        "service": "pandora-daemon",
        "auth_configured": bool(config.credentials.igneous and config.credentials.ipb_member_id),
        "capabilities": {
            "browse": True,
            "gallery_detail": True,
            "downloads": True,
            "library": True,
            "tags": True,
            "favorites": True,
            "websocket": True,
        },
    }


@router.put("/api/config")
async def update_config(body: dict, state: AppState = Depends(get_state)):
    config = state.config
    if "server" in body:
        for k, v in body["server"].items():
            if hasattr(config.server, k):
                setattr(config.server, k, v)
    if "download" in body:
        for k, v in body["download"].items():
            if hasattr(config.download, k):
                setattr(config.download, k, v)
    if "cache" in body:
        for k, v in body["cache"].items():
            if hasattr(config.cache, k):
                setattr(config.cache, k, v)
    save_config(config, state.config_path)
    return config.to_public_dict()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    state: AppState = ws.app.state.pandora
    await state.ws.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        state.ws.disconnect(ws)
