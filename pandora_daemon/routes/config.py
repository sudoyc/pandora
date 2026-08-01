"""Config and WebSocket routes for pandora-daemon."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pandora_daemon import MACHINE_CONTRACT_VERSION
from pandora_daemon.config import save_config
from pandora_daemon.dependencies import get_state
from pandora_daemon.state import AppState

router = APIRouter(tags=["config"])


class _RejectExplicitNulls(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key, value in data.items():
                if value is None:
                    raise ValueError(f"{key} may not be null")
        return data


class ServerConfigUpdate(_RejectExplicitNulls):
    model_config = ConfigDict(extra="forbid")

    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)


class DownloadConfigUpdate(_RejectExplicitNulls):
    model_config = ConfigDict(extra="forbid")

    path: str | None = Field(default=None, min_length=1)
    gallery_concurrency: int | None = Field(default=None, ge=1)
    page_concurrency: int | None = Field(default=None, ge=1)
    max_retry: int | None = Field(default=None, ge=0)
    retry_base_delay: float | None = Field(default=None, ge=0)


class CacheConfigUpdate(_RejectExplicitNulls):
    model_config = ConfigDict(extra="forbid")

    image_dir: str | None = Field(default=None, min_length=1)
    image_max_size_mb: int | None = Field(default=None, ge=1)
    gallery_ttl_seconds: int | None = Field(default=None, ge=0)
    prefetch_ahead: int | None = Field(default=None, ge=0)
    prefetch_behind: int | None = Field(default=None, ge=0)
    eviction_interval_seconds: int | None = Field(default=None, ge=1)


class ConfigUpdate(_RejectExplicitNulls):
    model_config = ConfigDict(extra="forbid")

    server: ServerConfigUpdate | None = None
    download: DownloadConfigUpdate | None = None
    cache: CacheConfigUpdate | None = None


def _pandora_version() -> str:
    try:
        return version("pandora")
    except PackageNotFoundError:
        return "unknown"


@router.get("/api/config")
async def get_config(state: AppState = Depends(get_state)):
    return state.config.to_public_dict()


@router.get("/api/health")
async def get_health(state: AppState = Depends(get_state)):
    return {
        "ok": True,
        "version": _pandora_version(),
        "contract_version": MACHINE_CONTRACT_VERSION,
        "service": "pandora-daemon",
        "auth_configured": state.provider.auth_configured,
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
async def update_config(body: ConfigUpdate, state: AppState = Depends(get_state)):
    config = state.config
    updates = body.model_dump(exclude_unset=True)
    for section_name, values in updates.items():
        section = getattr(config, section_name)
        for key, value in values.items():
            setattr(section, key, value)
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
