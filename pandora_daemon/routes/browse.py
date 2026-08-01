"""Browse routes for pandora-daemon.

Provides endpoints for browsing galleries: homepage, search, popular, toplist,
watched galleries, and thumbnail proxy.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response

from pandora_daemon.dependencies import get_gallery_provider, get_image_service
from pandora_daemon.providers import GalleryProvider, GallerySearchQuery, GallerySummary

router = APIRouter(prefix="/api", tags=["browse"])


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


@router.get("/homepage")
async def get_homepage(
    next_gid: Optional[int] = Query(None, alias="next", ge=1),
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Return the homepage gallery list."""
    if next_gid is None:
        items = await provider.get_homepage()
    else:
        items = await provider.get_homepage(next_gid=str(next_gid))
    return [_gallery_item_to_dict(item) for item in items]


@router.get("/search")
async def search(
    keyword: str = "",
    page: int = 0,
    min_rating: Optional[int] = None,
    category: Optional[int] = None,
    search_name: bool = False,
    search_tags: bool = False,
    search_description: bool = False,
    search_torrent: bool = False,
    search_low_power_tags: bool = False,
    disable_language_filter: bool = False,
    show_expunged: bool = False,
    min_pages: Optional[int] = None,
    max_pages: Optional[int] = None,
    next_gid: Optional[int] = Query(None, alias="next", ge=1),
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Search galleries with optional filters."""
    query = GallerySearchQuery(
        keyword=keyword,
        category=category,
        minimum_rating=min_rating,
        search_name=search_name,
        search_tags=search_tags,
        search_description=search_description,
        search_torrents=search_torrent,
        search_low_power_tags=search_low_power_tags,
        disable_language_filter=disable_language_filter,
        show_expunged=show_expunged,
        minimum_pages=min_pages,
        maximum_pages=max_pages,
    )

    if next_gid is None:
        items = await provider.search(query, page=page)
    else:
        items = await provider.search(query, page=page, next_gid=str(next_gid))
    return [_gallery_item_to_dict(item) for item in items]


@router.get("/popular")
async def get_popular(
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Return the popular galleries list."""
    items = await provider.get_popular()
    return [_gallery_item_to_dict(item) for item in items]


@router.get("/toplist")
async def get_toplist(
    tl: str = "15",
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Return toplist entries as GalleryItem-compatible dicts."""
    items = await provider.get_toplist(tl)
    return [_gallery_item_to_dict(item) for item in items]


@router.get("/watched")
async def get_watched(
    page: int = 0,
    next_gid: Optional[int] = Query(None, alias="next", ge=1),
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Return watched tag galleries for the given page."""
    if next_gid is None:
        items = await provider.get_watched(page=page)
    else:
        items = await provider.get_watched(page=page, next_gid=str(next_gid))
    return [_gallery_item_to_dict(item) for item in items]


@router.get("/image/proxy")
async def image_proxy(url: str, image_service=Depends(get_image_service)):
    """Proxy any image URL through the local cache."""
    try:
        data = await image_service.proxy_image(url)
    except (PermissionError, ValueError):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Invalid image URL")
    except Exception:
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail="Failed to fetch image")
    lower_url = url.lower()
    if lower_url.endswith(".png"):
        media_type = "image/png"
    elif lower_url.endswith(".gif"):
        media_type = "image/gif"
    elif lower_url.endswith(".webp"):
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"
    return Response(content=data, media_type=media_type)
