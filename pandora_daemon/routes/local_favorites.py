"""Local favorites routes for pandora-daemon."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pandora_daemon.db import PandoraDB
from pandora_daemon.dependencies import get_db

router = APIRouter(prefix="/api/local-favorites", tags=["local-favorites"])


class AddFavoriteBody(BaseModel):
    gid: str
    token: str
    title: str
    title_jpn: str | None = None
    category: str = ""
    uploader: str = ""
    thumb_url: str = ""
    posted: str = ""
    rating: float = 0.0
    pages: int = 0


def _public_favorite(item: dict) -> dict:
    public = dict(item)
    public.pop("token", None)
    return public


@router.get("")
async def list_favorites(limit: int = 50, offset: int = 0, db: PandoraDB = Depends(get_db)):
    return [_public_favorite(item) for item in await db.get_local_favorites(limit, offset)]


@router.post("")
async def add_favorite(body: AddFavoriteBody, db: PandoraDB = Depends(get_db)):
    await db.add_local_favorite(body)
    return {"ok": True}


@router.delete("/{gid}")
async def remove_favorite(gid: str, db: PandoraDB = Depends(get_db)):
    await db.remove_local_favorite(gid)
    return {"ok": True}
