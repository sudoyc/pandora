"""Browse routes for pandora-daemon.

Provides endpoints for browsing ExHentai: homepage, search, popular,
toplist, watched galleries, and thumbnail proxy.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, Response

from exhentai_api.models.search import SearchParams
from pandora_daemon.dependencies import get_api, get_image_service

router = APIRouter(prefix="/api", tags=["browse"])


def _gallery_item_to_dict(item) -> dict:
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


def _toplist_item_to_dict(item) -> dict:
    return {
        "type": item.type,
        "name": item.name,
        "link": item.link,
    }


def _toplist_to_gallery_item(item) -> dict | None:
    """Convert TopListItem to GalleryItem-compatible dict by parsing link URL."""
    match = re.search(r"/g/(\d+)/([0-9a-f]+)", item.link)
    if not match:
        return None
    gid = match.group(1)
    token = match.group(2)
    return {
        "gid": gid,
        "token": token,
        "title": item.name,
        "category": "",
        "uploader": "",
        "thumb_url": "",
        "posted": "",
        "rating": 0.0,
        "pages": 0,
        "rated": False,
        "thumb_width": 0,
        "thumb_height": 0,
        "url": item.link,
    }


@router.get("/homepage")
async def get_homepage(api=Depends(get_api)):
    """Return the homepage gallery list."""
    items = await api.get_homepage()
    return [_gallery_item_to_dict(item) for item in items]


@router.get("/search")
async def search(
    keyword: str = "",
    page: int = 0,
    min_rating: Optional[int] = None,
    category: Optional[int] = None,
    api=Depends(get_api),
):
    """Search galleries with optional filters."""
    params = SearchParams(f_search=keyword)
    if category is not None:
        params.f_cats = category
    if min_rating is not None:
        params.advsearch = True
        params.f_sr = True
        params.f_srdd = min_rating

    items = await api.search(params, page=page)
    return [_gallery_item_to_dict(item) for item in items]


@router.get("/popular")
async def get_popular(api=Depends(get_api)):
    """Return the popular galleries list."""
    items = await api.get_popular()
    return [_gallery_item_to_dict(item) for item in items]


@router.get("/toplist")
async def get_toplist(tl: str = "15", api=Depends(get_api)):
    """Return toplist entries as GalleryItem-compatible dicts."""
    items = await api.get_toplist(tl)
    result = []
    for item in items:
        converted = _toplist_to_gallery_item(item)
        if converted:
            result.append(converted)
    return result


@router.get("/watched")
async def get_watched(page: int = 0, api=Depends(get_api)):
    """Return watched tag galleries for the given page."""
    items = await api.get_watched(page=page)
    return [_gallery_item_to_dict(item) for item in items]


@router.get("/image/proxy")
async def image_proxy(url: str, image_service=Depends(get_image_service)):
    """Proxy any image URL through the local cache."""
    try:
        data = await image_service.proxy_image(url)
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail=f"Failed to fetch image: {e}")
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
