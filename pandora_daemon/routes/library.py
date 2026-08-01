"""Library routes for pandora-daemon.

Provides endpoints for browsing downloaded galleries from the local filesystem.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import NoReturn

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from starlette.requests import Request

from pandora_daemon.diagnostics import get_correlation_id, get_request_id
from pandora_daemon.pdf_export import (
    PdfExportError,
    execute_gallery_pdf_export,
    plan_gallery_pdf_export,
)

router = APIRouter(prefix="/api/library", tags=["library"])
logger = logging.getLogger(__name__)


class PdfExportBody(BaseModel):
    password: str | None = None
    output_name: str | None = None
    include_cover: bool = False


def _find_gallery_dir(download_path: Path, gid: str) -> Path | None:
    """Find gallery directory matching {gid}-* pattern."""
    if not download_path.exists():
        return None
    for d in download_path.iterdir():
        if d.is_dir() and d.name.startswith(f"{gid}-"):
            return d
    return None

def _library_path(request: Request) -> Path:
    return request.app.state.pandora.downloads.download_path


def _detect_media_type(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:4] == b"GIF8":
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


async def _broadcast_pdf_event(
    ws,
    event: str,
    gid: str,
    request_id: str,
    correlation_id: str,
    **fields,
) -> None:
    payload = {
        **fields,
        "event": event,
        "gid": gid,
        "request_id": request_id,
        "correlation_id": correlation_id,
    }
    logger.info(
        "PDF export event request_id=%s correlation_id=%s gid=%s event=%s",
        request_id,
        correlation_id,
        gid,
        event,
    )
    if ws is not None:
        await ws.broadcast(payload)


async def _raise_pdf_export_http_error(
    ws,
    gid: str,
    request_id: str,
    correlation_id: str,
    exc: Exception,
) -> NoReturn:
    await _broadcast_pdf_event(
        ws,
        "pdf_export_error",
        gid,
        request_id,
        correlation_id,
        error="PDF export failed",
    )
    logger.warning(
        "PDF export failed request_id=%s correlation_id=%s gid=%s exception=%s",
        request_id,
        correlation_id,
        gid,
        type(exc).__name__,
    )
    status_code = 400 if isinstance(exc, PdfExportError) else 500
    raise HTTPException(status_code=status_code, detail="PDF export failed") from exc


@router.get("")
async def list_library(request: Request):
    """List all downloaded galleries by scanning download directory."""
    download_path = _library_path(request)
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


@router.post("/{gid}/export/pdf")
async def export_library_pdf(gid: str, body: PdfExportBody, request: Request):
    request_id = get_request_id(request)
    correlation_id = get_correlation_id(request)
    if not gid.isdigit():
        raise HTTPException(status_code=400, detail="Invalid gallery ID")

    download_path = _library_path(request)
    gallery_dir = _find_gallery_dir(download_path, gid)
    if gallery_dir is None:
        raise HTTPException(status_code=404, detail=f"Gallery {gid} not found")

    ws = getattr(request.app.state.pandora, "ws", None)

    try:
        plan = plan_gallery_pdf_export(
            gallery_dir,
            gid,
            output_name=body.output_name,
            include_cover=body.include_cover,
        )
    except Exception as exc:
        await _raise_pdf_export_http_error(
            ws,
            gid,
            request_id,
            correlation_id,
            exc,
        )

    await _broadcast_pdf_event(
        ws,
        "pdf_export_started",
        gid,
        request_id,
        correlation_id,
    )

    try:
        result = execute_gallery_pdf_export(plan, password=body.password)
    except Exception as exc:
        await _raise_pdf_export_http_error(
            ws,
            gid,
            request_id,
            correlation_id,
            exc,
        )

    payload = result.to_dict()
    payload["request_id"] = request_id
    payload["correlation_id"] = correlation_id
    await _broadcast_pdf_event(
        ws,
        "pdf_export_complete",
        gid,
        request_id,
        correlation_id,
        path=payload["path"],
        password_protected=payload["password_protected"],
    )
    return payload


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
    download_path = _library_path(request)
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
