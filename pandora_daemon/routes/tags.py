"""Tag suggest routes for pandora-daemon."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pandora_daemon.dependencies import get_tag_database
from pandora_daemon.tag_database import TagDatabase

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("/suggest")
async def suggest_tags(
    q: str = Query("", description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    tag_db: TagDatabase = Depends(get_tag_database),
):
    """Return tag suggestions matching the query."""
    results = tag_db.suggest(q, limit=limit)
    return {
        "suggestions": [
            {"namespace": r.namespace, "tag": r.tag, "translation": r.translation}
            for r in results
        ]
    }


@router.get("/status")
async def tag_database_status(tag_db: TagDatabase = Depends(get_tag_database)):
    """Return tag translation database cache/load status."""
    return tag_db.status()


@router.post("/refresh")
async def refresh_tag_database(
    force: bool = Query(False, description="Force download without If-None-Match"),
    tag_db: TagDatabase = Depends(get_tag_database),
):
    """Refresh the tag translation database cache."""
    return await tag_db.refresh(force=force)
