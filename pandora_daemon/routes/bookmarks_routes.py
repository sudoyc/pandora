"""Bookmarks routes for pandora-daemon."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from pandora_daemon.db import PandoraDB
from pandora_daemon.dependencies import get_db

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


def _public_bookmark(item: dict) -> dict:
    public = dict(item)
    public.pop("token", None)
    return public


@router.get("")
async def list_bookmarks(limit: int = 50, offset: int = 0, db: PandoraDB = Depends(get_db)):
    return [_public_bookmark(item) for item in await db.get_bookmarks(limit, offset)]


@router.get("/{gid}")
async def get_one(gid: str, db: PandoraDB = Depends(get_db)):
    result = await db.get_bookmark(gid)
    if result is None:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return _public_bookmark(result)


@router.delete("/{gid}")
async def delete_one(gid: str, db: PandoraDB = Depends(get_db)):
    await db.delete_bookmark(gid)
    return {"ok": True}
