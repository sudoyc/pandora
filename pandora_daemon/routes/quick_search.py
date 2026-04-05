"""Quick search routes for pandora-daemon."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pandora_daemon.db import PandoraDB
from pandora_daemon.dependencies import get_db

router = APIRouter(prefix="/api/quick-search", tags=["quick-search"])


class AddQuickSearchBody(BaseModel):
    name: str
    keyword: str = ""
    category: int | None = None
    min_rating: int | None = None
    page_from: int | None = None
    page_to: int | None = None


@router.get("")
async def list_searches(db: PandoraDB = Depends(get_db)):
    return await db.get_quick_searches()


@router.post("")
async def add_search(body: AddQuickSearchBody, db: PandoraDB = Depends(get_db)):
    new_id = await db.add_quick_search(
        body.name,
        keyword=body.keyword,
        category=body.category,
        min_rating=body.min_rating,
        page_from=body.page_from,
        page_to=body.page_to,
    )
    return {"id": new_id}


@router.delete("/{search_id}")
async def delete_search(search_id: int, db: PandoraDB = Depends(get_db)):
    await db.delete_quick_search(search_id)
    return {"ok": True}
