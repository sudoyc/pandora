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


@router.post("/{gid}/retry")
async def retry_download(gid: str, downloads: DownloadManager = Depends(get_downloads)):
    result = await downloads.retry_failed(gid)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found or not in completed_with_errors state")
    return {"success": True}


@router.post("/{gid}/resume")
async def resume_download(gid: str, downloads: DownloadManager = Depends(get_downloads)):
    result = await downloads.resume(gid)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found or not paused")
    return {"success": True}


@router.get("/{gid}/pages")
async def get_page_status(gid: str, downloads: DownloadManager = Depends(get_downloads)):
    tasks = {t.gid: t for t in downloads.status()}
    task = tasks.get(gid)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "gid": task.gid,
        "total_pages": task.total_pages,
        "downloaded_pages": task.downloaded_pages,
        "failed_pages": task.failed_pages,
        "page_states": task.page_states,
    }
