"""Favorites routes for pandora-daemon.

Provides endpoints for listing, adding, and modifying gallery favorites.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pandora_daemon.dependencies import get_gallery_provider
from pandora_daemon.providers.contracts import (
    FavoritesPage,
    GalleryProvider,
    GallerySummary,
)

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


# ---------------------------------------------------------------------------
# Request body models
# ---------------------------------------------------------------------------

class AddFavoriteBody(BaseModel):
    gid: str
    token: str
    slot: int = 0
    note: str = ""


class ModifyFavoritesBody(BaseModel):
    gids: list[str]
    action: str


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _gallery_item_to_dict(item: GallerySummary) -> dict[str, object]:
    return {
        "gid": item.gid,
        "token": item.token,
        "title": item.title,
        "category": item.category,
        "uploader": item.uploader,
        "thumb_url": item.thumb_url,
        "posted": item.posted,
        "rating": item.rating,
        "pages": item.pages,
        "rated": item.rated,
        "thumb_width": item.thumb_width,
        "thumb_height": item.thumb_height,
        "url": item.url,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
async def get_favorites(
    slot: int = -1,
    page: int = 0,
    keyword: str = "",
    sn: bool = False,
    st: bool = False,
    sf: bool = False,
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Return favorites list with categories and galleries."""
    response: FavoritesPage = await provider.get_favorites(
        slot=slot,
        page=page,
        keyword=keyword,
        search_name=sn,
        search_tags=st,
        search_notes=sf,
    )
    return {
        "categories": [
            {"slot": category.slot, "name": category.name, "count": category.count}
            for category in response.categories
        ],
        "galleries": [_gallery_item_to_dict(gallery) for gallery in response.galleries],
    }


@router.post("")
async def add_favorite(
    body: AddFavoriteBody,
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Add a gallery to favorites."""
    await provider.add_favorite(
        body.gid,
        body.token,
        slot=body.slot,
        note=body.note,
    )
    return {"ok": True}


@router.delete("")
async def modify_favorites(
    body: ModifyFavoritesBody,
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Modify (e.g. delete) favorites entries."""
    await provider.modify_favorites(body.gids, body.action)
    return {"ok": True}
