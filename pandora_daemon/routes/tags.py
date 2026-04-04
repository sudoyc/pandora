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
