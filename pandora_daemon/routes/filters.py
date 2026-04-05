"""Filter routes for pandora-daemon."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pandora_daemon.db import PandoraDB
from pandora_daemon.dependencies import get_db

router = APIRouter(prefix="/api/filters", tags=["filters"])


class AddFilterBody(BaseModel):
    mode: int
    text: str


@router.get("")
async def list_filters(db: PandoraDB = Depends(get_db)):
    return await db.get_filters()


@router.post("")
async def add_filter(body: AddFilterBody, db: PandoraDB = Depends(get_db)):
    new_id = await db.add_filter(body.mode, body.text)
    return {"id": new_id}


@router.put("/{filter_id}")
async def toggle(filter_id: int, db: PandoraDB = Depends(get_db)):
    await db.toggle_filter(filter_id)
    return {"ok": True}


@router.delete("/{filter_id}")
async def delete_filter(filter_id: int, db: PandoraDB = Depends(get_db)):
    await db.delete_filter(filter_id)
    return {"ok": True}
