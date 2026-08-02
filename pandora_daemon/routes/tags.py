"""Tag suggest routes for pandora-daemon."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pandora_daemon.dependencies import get_gallery_provider
from pandora_daemon.providers import GalleryProvider

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("/suggest")
async def suggest_tags(
    q: str = Query("", description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Return tag suggestions matching the query."""
    results = provider.tag_catalog.suggest(q, limit=limit)
    return {
        "suggestions": [
            {"namespace": r.namespace, "tag": r.tag, "translation": r.translation}
            for r in results
        ]
    }


@router.get("/status")
async def tag_database_status(
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Return tag translation database cache/load status."""
    return provider.tag_catalog.status()


@router.post("/refresh")
async def refresh_tag_database(
    force: bool = Query(False, description="Force download without If-None-Match"),
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Refresh the tag translation database cache."""
    return await provider.tag_catalog.refresh(force=force)
