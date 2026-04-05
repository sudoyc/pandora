"""Library routes for pandora-daemon.

Provides endpoints for browsing downloaded galleries from the local filesystem.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from starlette.requests import Request

router = APIRouter(prefix="/api/library", tags=["library"])


def _find_gallery_dir(download_path: Path, gid: str) -> Path | None:
    """Find gallery directory matching {gid}-* pattern."""
    if not download_path.exists():
        return None
    for d in download_path.iterdir():
        if d.is_dir() and d.name.startswith(f"{gid}-"):
            return d
    return None


def _detect_media_type(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:4] == b"GIF8":
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


@router.get("")
async def list_library(request: Request):
    """List all downloaded galleries by scanning download directory."""
    config = request.app.state.pandora.config
    download_path = Path(config.download.path).expanduser()
    if not download_path.exists():
        return []

    galleries = []
    for d in sorted(download_path.iterdir()):
        if not d.is_dir():
            continue
        meta_file = d / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            gid = meta.get("gid", "")
            if gid:
                meta["thumb_url"] = f"/api/library/{gid}/file?path=cover"
            galleries.append(meta)
        except (json.JSONDecodeError, OSError):
            continue
    return galleries


@router.get("/{gid}/file")
async def get_library_file(
    gid: str,
    request: Request,
    path: str = Query(..., description="cover | thumb/{page} | page/{page}"),
):
    """Serve a file from a downloaded gallery."""
    # Validate gid is numeric to prevent path traversal
    if not gid.isdigit():
        raise HTTPException(status_code=400, detail="Invalid gallery ID")
    config = request.app.state.pandora.config
    download_path = Path(config.download.path).expanduser()
    gallery_dir = _find_gallery_dir(download_path, gid)
    if gallery_dir is None:
        raise HTTPException(status_code=404, detail=f"Gallery {gid} not found")

    if path == "cover":
        for ext in ("jpg", "jpeg", "png", "webp", "gif"):
            cover = gallery_dir / f"cover.{ext}"
            if cover.exists():
                data = cover.read_bytes()
                return Response(content=data, media_type=_detect_media_type(data))
        raise HTTPException(status_code=404, detail="Cover not found")

    match = re.match(r"^(thumb|page)/(\d+)$", path)
    if not match:
        raise HTTPException(status_code=400, detail=f"Invalid path: {path}")

    file_type = match.group(1)
    page_num = int(match.group(2))
    subdir = "thumbs" if file_type == "thumb" else "pages"
    target_dir = gallery_dir / subdir

    if not target_dir.exists():
        raise HTTPException(status_code=404, detail=f"{subdir}/ not found")

    matches = list(target_dir.glob(f"{page_num:04d}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"{file_type} {page_num} not found")

    data = matches[0].read_bytes()
    return Response(content=data, media_type=_detect_media_type(data))
