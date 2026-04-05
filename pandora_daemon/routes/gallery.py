"""Gallery routes for pandora-daemon.

Provides endpoints for gallery details, comments, ratings, vote comments,
torrents, and archives.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from pandora_daemon.dependencies import get_api, get_cache, get_image_service

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


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

def _comment_to_dict(c) -> dict:
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


def _detail_to_dict(d) -> dict:
    return {
        "gid": d.gid,
        "token": d.token,
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
        "preview_pages": d.preview_pages,
        "thumb_urls": d.thumb_urls,
        "rating": d.rating,
        "rating_count": d.rating_count,
        "favorite_count": d.favorite_count,
        "torrent_count": d.torrent_count,
        "comments": [_comment_to_dict(c) for c in d.comments],
        "comments_has_more": d.comments_has_more,
        "api_uid": d.api_uid,
        "api_key": d.api_key,
        "url": d.url,
    }


def _torrent_to_dict(t) -> dict:
    return {
        "name": t.name,
        "url": t.url,
    }


def _archive_to_dict(a) -> dict:
    result: dict = {"funds": a.funds}
    if a.original:
        result["original"] = {
            "url": a.original.url,
            "size": a.original.size,
            "cost": a.original.cost,
        }
    if a.resample:
        result["resample"] = {
            "url": a.resample.url,
            "size": a.resample.size,
            "cost": a.resample.cost,
        }
    return result


# ---------------------------------------------------------------------------
# Cache helper
# ---------------------------------------------------------------------------

async def _get_detail(gid: str, token: str, api, cache):
    """Return gallery detail from cache or fetch and cache it."""
    cached = cache.get_gallery(gid, token)
    if cached is not None:
        return cached
    detail = await api.get_gallery_details(gid, token)
    cache.put_gallery(detail)
    return detail


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{gid}/{token}")
async def get_gallery_detail(gid: str, token: str, api=Depends(get_api), cache=Depends(get_cache)):
    """Return gallery detail. Checks cache first; fetches and caches on miss."""
    detail = await _get_detail(gid, token, api, cache)
    return _detail_to_dict(detail)


@router.post("/{gid}/{token}/comment")
async def comment_gallery(
    gid: str,
    token: str,
    body: CommentBody,
    api=Depends(get_api),
):
    """Post or edit a comment on a gallery."""
    result = await api.comment_gallery(gid, token, body.comment, edit_id=body.edit_id)
    return {"ok": True, "result": result}


@router.post("/{gid}/{token}/rate")
async def rate_gallery(
    gid: str,
    token: str,
    body: RateBody,
    api=Depends(get_api),
    cache=Depends(get_cache),
):
    """Rate a gallery. Fetches api_uid/api_key from gallery detail (uses cache)."""
    detail = await _get_detail(gid, token, api, cache)
    result = await api.rate_gallery(detail.api_uid, detail.api_key, int(gid), token, body.rating)
    return {"ok": True, "result": result}


@router.post("/{gid}/{token}/vote_comment")
async def vote_comment(
    gid: str,
    token: str,
    body: VoteCommentBody,
    api=Depends(get_api),
    cache=Depends(get_cache),
):
    """Vote on a comment. Fetches api_uid/api_key from gallery detail (uses cache)."""
    detail = await _get_detail(gid, token, api, cache)
    result = await api.vote_comment(
        detail.api_uid,
        detail.api_key,
        int(gid),
        token,
        body.comment_id,
        body.vote,
    )
    return {"ok": True, "result": result}


@router.get("/{gid}/{token}/torrents")
async def get_torrents(gid: str, token: str, api=Depends(get_api)):
    """Return the torrent list for a gallery."""
    torrents = await api.get_torrent_list(gid, token)
    return [_torrent_to_dict(t) for t in torrents]


@router.get("/{gid}/{token}/archive")
async def get_archive(gid: str, token: str, api=Depends(get_api)):
    """Return the archive download options for a gallery."""
    archive = await api.get_archive_list(gid, token)
    return _archive_to_dict(archive)


@router.get("/{gid}/{token}/page/{page}")
async def get_page_image(gid: str, token: str, page: int, image_service=Depends(get_image_service)):
    """Return full-size image bytes for a gallery page."""
    try:
        data = await image_service.get_page_image(gid, token, page)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Detect media type from magic bytes
    if data[:4] == b"\x89PNG":
        media_type = "image/png"
    elif data[:4] == b"GIF8":
        media_type = "image/gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Length": str(len(data))},
    )


@router.post("/{gid}/{token}/prefetch")
async def prefetch_pages(
    gid: str,
    token: str,
    body: PrefetchBody,
    api=Depends(get_api),
    cache=Depends(get_cache),
    image_service=Depends(get_image_service),
):
    """Report current page and trigger background prefetch."""
    detail = await _get_detail(gid, token, api, cache)
    await image_service.prefetch(gid, token, body.current_page, detail.pages)
    return {"ok": True}
