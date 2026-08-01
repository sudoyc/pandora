"""Gallery routes for pandora-daemon.

Provides endpoints for gallery details, comments, ratings, vote comments,
torrents, and archives.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from pandora_daemon.dependencies import get_gallery_provider, get_cache, get_image_service, get_db
from pandora_daemon.providers.contracts import (
    ArchiveOptions,
    GalleryComment,
    GalleryDetail,
    GalleryProvider,
    GalleryTorrent,
)

router = APIRouter(prefix="/api/gallery", tags=["gallery"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request body models
# ---------------------------------------------------------------------------

class CommentBody(BaseModel):
    comment: str
    edit_id: Optional[int] = None


class RateBody(BaseModel):
    rating: int


class VoteCommentBody(BaseModel):
    comment_id: int
    vote: int


class PrefetchBody(BaseModel):
    current_page: int


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _comment_to_dict(c: GalleryComment) -> dict[str, object]:
    return {
        "id": c.id,
        "user": c.user,
        "comment": c.comment,
        "score": c.score,
        "time": c.time,
        "is_uploader": c.is_uploader,
        "vote_up_able": c.vote_up_able,
        "vote_down_able": c.vote_down_able,
        "vote_up_ed": c.vote_up_ed,
        "vote_down_ed": c.vote_down_ed,
        "editable": c.editable,
        "last_edited": c.last_edited,
    }


def _detail_to_dict(d: GalleryDetail) -> dict[str, object]:
    return {
        "gid": d.gid,
        "title": d.title,
        "title_jpn": d.title_jpn,
        "category": d.category,
        "uploader": d.uploader,
        "cover_url": d.cover_url,
        "tags": d.tags,
        "pages": d.pages,
        "size": d.size,
        "posted": d.posted,
        "favorite_slot": d.favorite_slot,
        "preview_pages": d.preview_page_count,
        "rating": d.rating,
        "rating_count": d.rating_count,
        "favorite_count": d.favorite_count,
        "torrent_count": d.torrent_count,
        "comments": [_comment_to_dict(c) for c in d.comments],
        "comments_has_more": d.comments_has_more,
        "url": d.url,
    }


def _torrent_to_dict(torrent: GalleryTorrent) -> dict[str, str]:
    return {
        "name": torrent.name,
        "url": torrent.url,
    }


def _archive_to_dict(archive: ArchiveOptions) -> dict[str, object]:
    result: dict[str, object] = {"funds": archive.funds}
    if archive.original:
        result["original"] = {
            "url": archive.original.url,
            "size": archive.original.size,
            "cost": archive.original.cost,
        }
    if archive.resample:
        result["resample"] = {
            "url": archive.resample.url,
            "size": archive.resample.size,
            "cost": archive.resample.cost,
        }
    return result


def _media_type_from_image_bytes(data: bytes) -> str:
    """Infer an image response media type from its magic bytes."""
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:4] == b"GIF8":
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


# ---------------------------------------------------------------------------
# Cache helper
# ---------------------------------------------------------------------------

async def _get_detail(
    gid: str,
    token: str,
    provider: GalleryProvider,
    cache,
) -> GalleryDetail:
    """Return gallery detail from cache or fetch and cache it."""
    cached = cache.get_gallery(gid, token)
    if cached is not None:
        return cached
    detail = await provider.get_gallery_details(gid, token)
    cache.put_gallery(detail)
    return detail


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{gid}/{token}")
async def get_gallery_detail(gid: str, token: str, provider: GalleryProvider = Depends(get_gallery_provider), cache=Depends(get_cache), db=Depends(get_db)):
    """Return gallery detail. Checks cache first; fetches and caches on miss."""
    detail = await _get_detail(gid, token, provider, cache)
    await db.put_history(detail)
    return _detail_to_dict(detail)


@router.post("/{gid}/{token}/comment")
async def comment_gallery(
    gid: str,
    token: str,
    body: CommentBody,
    provider: GalleryProvider = Depends(get_gallery_provider),
):
    """Post or edit a comment on a gallery."""
    result = await provider.comment_gallery(gid, token, body.comment, edit_id=body.edit_id)
    return {"ok": True, "result": result}


@router.post("/{gid}/{token}/rate")
async def rate_gallery(
    gid: str,
    token: str,
    body: RateBody,
    provider: GalleryProvider = Depends(get_gallery_provider),
    cache=Depends(get_cache),
):
    """Rate a gallery using its normalized detail."""
    detail = await _get_detail(gid, token, provider, cache)
    result = await provider.rate_gallery(detail, body.rating)
    return {"ok": True, "result": result}


@router.post("/{gid}/{token}/vote_comment")
async def vote_comment(
    gid: str,
    token: str,
    body: VoteCommentBody,
    provider: GalleryProvider = Depends(get_gallery_provider),
    cache=Depends(get_cache),
):
    """Vote on a comment using its normalized gallery detail."""
    detail = await _get_detail(gid, token, provider, cache)
    result = await provider.vote_comment(detail, body.comment_id, body.vote)
    return {"ok": True, "result": result}


@router.get("/{gid}/{token}/torrents")
async def get_torrents(gid: str, token: str, provider: GalleryProvider = Depends(get_gallery_provider)):
    """Return the torrent list for a gallery."""
    torrents = await provider.get_torrent_list(gid, token)
    return [_torrent_to_dict(t) for t in torrents]


@router.get("/{gid}/{token}/archive")
async def get_archive(gid: str, token: str, provider: GalleryProvider = Depends(get_gallery_provider)):
    """Return the archive download options for a gallery."""
    archive = await provider.get_archive_list(gid, token)
    return _archive_to_dict(archive)


@router.get("/{gid}/{token}/page/{page}")
async def get_page_image(gid: str, token: str, page: int, image_service=Depends(get_image_service)):
    """Return full-size image bytes for a gallery page."""
    try:
        data = await image_service.get_page_image(gid, token, page)
    except (ValueError, RuntimeError):
        logger.warning("Invalid page image request gid=%s page=%s", gid, page, exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid page image request")
    except Exception:
        logger.exception("Failed to fetch page image gid=%s page=%s", gid, page)
        raise HTTPException(status_code=502, detail="Failed to fetch page image")
    # Detect media type from magic bytes
    media_type = _media_type_from_image_bytes(data)
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Length": str(len(data))},
    )


@router.get("/{gid}/{token}/thumb/{page}")
async def get_thumb_image(
    gid: str,
    token: str,
    page: int,
    image_service=Depends(get_image_service),
):
    """Return thumbnail bytes for a gallery page."""
    try:
        data = await image_service.get_thumbnail(gid, token, page)
    except (ValueError, RuntimeError):
        logger.warning("Invalid thumbnail request gid=%s page=%s", gid, page, exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid thumbnail request")
    except LookupError:
        logger.warning("Thumbnail unavailable gid=%s page=%s", gid, page, exc_info=True)
        raise HTTPException(status_code=404, detail=f"No thumbnail for page {page}")
    except Exception:
        logger.exception("Failed to fetch thumbnail gid=%s page=%s", gid, page)
        raise HTTPException(status_code=502, detail="Failed to fetch thumbnail")
    return Response(content=data, media_type=_media_type_from_image_bytes(data))


@router.post("/{gid}/{token}/prefetch")
async def prefetch_pages(
    gid: str,
    token: str,
    body: PrefetchBody,
    provider: GalleryProvider = Depends(get_gallery_provider),
    cache=Depends(get_cache),
    image_service=Depends(get_image_service),
    db=Depends(get_db),
):
    """Report current page and trigger background prefetch."""
    detail = await _get_detail(gid, token, provider, cache)
    await db.update_bookmark(
        gid=gid, token=token, title=detail.title,
        thumb_url=detail.cover_url, page=body.current_page, total=detail.pages,
    )
    await image_service.prefetch(gid, token, body.current_page, detail.pages)
    return {"ok": True}
