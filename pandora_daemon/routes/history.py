"""History routes for pandora-daemon."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from pandora_daemon.db import PandoraDB
from pandora_daemon.dependencies import get_db

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def get_history(limit: int = 50, offset: int = 0, db: PandoraDB = Depends(get_db)):
    return await db.get_history(limit, offset)


@router.delete("")
async def clear_all(db: PandoraDB = Depends(get_db)):
    await db.clear_history()
    return {"ok": True}


@router.delete("/{gid}")
async def delete_one(gid: str, db: PandoraDB = Depends(get_db)):
    await db.delete_history(gid)
    return {"ok": True}
