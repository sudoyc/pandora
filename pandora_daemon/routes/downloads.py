"""Download routes for pandora-daemon.

Provides endpoints for submitting, listing, and cancelling gallery downloads.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from pandora_daemon.dependencies import get_downloads
from pandora_daemon.download import DownloadManager

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


class SubmitBody(BaseModel):
    gid: str
    token: str


@router.post("")
async def submit_download(body: SubmitBody, downloads: DownloadManager = Depends(get_downloads)):
    """Submit a gallery for download."""
    try:
        task = await downloads.submit(body.gid, body.token)
        return task.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("")
async def list_downloads(downloads: DownloadManager = Depends(get_downloads)):
    """Return all known download tasks."""
    tasks = downloads.status()
    return [t.to_dict() for t in tasks]


@router.delete("/{gid}")
async def cancel_download(gid: str, downloads: DownloadManager = Depends(get_downloads)):
    """Cancel a download task by gid."""
    result = await downloads.cancel(gid)
    return {"success": result}
