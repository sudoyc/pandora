"""Download manager for pandora-daemon.

Produces complete offline gallery clones in the library directory.
Each gallery gets: metadata.json, cover, thumbs/, pages/.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from exhentai_api.exceptions import (
    AuthenticationError, ImageLimitError, GalleryNotFoundError,
    NetworkError, ParseError,
)
from exhentai_api.parsers.gallery_detail import parse_gallery_detail
from exhentai_api.parsers.image import parse_image_viewer
from pandora_daemon.cache import _ext_from_url


def _sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in file/directory names."""
    return re.sub(r'[\\/*?:"<>|]', "", name)


def _atomic_write(path: Path, data: bytes) -> None:
    """Write via temp file + rename to prevent partial writes on crash."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(data)
    tmp_path.rename(path)


@dataclass
class DownloadTask:
    """Represents a single gallery download task."""

    gid: str
    token: str
    title: str
    total_pages: int
    output_dir: str
    status: str = "queued"
    downloaded_pages: int = 0
    downloaded_thumbs: int = 0
    cover_downloaded: bool = False
    metadata_saved: bool = False
    error: str = ""
    created_at: str = ""
    preview_urls: list[str] = field(default_factory=list)
    thumb_urls: list[str] = field(default_factory=list)
    thumb_sprites: list[dict] = field(default_factory=list)  # [{url, offset_x, offset_y, width, height}]
    page_states: dict[int, str] = field(default_factory=dict)
    failed_pages: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


class DownloadManager:
    """Produces complete offline gallery clones with metadata, covers, thumbs, and pages."""

    def __init__(self, api, config, ws, image_service, state_file: Path) -> None:
        self._api = api
        self._config = config
        self._ws = ws
        self._image_service = image_service
        self._state_file = state_file
        self._download_path = Path(config.path).expanduser()
        self._tasks: dict[str, DownloadTask] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._cancelled: set[str] = set()
        self._save_dirty: bool = False
        self._save_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._load_state()
        for task in list(self._tasks.values()):
            if task.status in ("queued", "downloading"):
                task.status = "queued"
                await self._queue.put(task.gid)

        for _ in range(self._config.gallery_concurrency):
            worker = asyncio.create_task(self._worker())
            self._workers.append(worker)

    async def shutdown(self) -> None:
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
            await asyncio.gather(self._save_task, return_exceptions=True)
        self._save_state()

    async def submit(self, gid: str, token: str) -> DownloadTask:
        existing = self._tasks.get(gid)
        if existing and existing.status in ("queued", "downloading"):
            raise ValueError(f"Gallery {gid} is already queued or downloading")

        detail = await self._api.get_gallery_details(gid, token)

        # Collect all preview URLs, thumb URLs, and sprite info across ALL preview pages
        preview_urls = list(detail.preview_urls)
        thumb_urls = list(detail.thumb_urls)
        thumb_sprites = [asdict(s) for s in detail.thumb_sprites]
        if detail.preview_pages > 1:
            for p in range(1, detail.preview_pages):
                page_url = f"{detail.url}?p={p}"
                html = await self._api.client.get_html(page_url)
                page_detail = parse_gallery_detail(html, gid, token)
                preview_urls.extend(page_detail.preview_urls)
                thumb_urls.extend(page_detail.thumb_urls)
                thumb_sprites.extend(asdict(s) for s in page_detail.thumb_sprites)

        safe_title = _sanitize_filename(detail.title)
        output_dir = str(self._download_path / f"{gid}-{safe_title}")

        task = DownloadTask(
            gid=gid,
            token=token,
            title=detail.title,
            total_pages=detail.pages,
            output_dir=output_dir,
            preview_urls=preview_urls,
            thumb_urls=thumb_urls,
            thumb_sprites=thumb_sprites,
        )
        self._tasks[gid] = task
        await self._queue.put(gid)

        await self._ws.broadcast({"event": "download_queued", "gid": gid, "title": detail.title})
        self._save_state()
        return task

    async def cancel(self, gid: str) -> bool:
        task = self._tasks.get(gid)
        if task is None:
            return False

        self._cancelled.add(gid)
        task.status = "cancelled"
        await self._ws.broadcast({"event": "download_cancelled", "gid": gid})
        self._save_state()
        return True

    def status(self) -> list[DownloadTask]:
        return list(self._tasks.values())

    def _write_metadata(self, detail, output_dir: str) -> None:
        """Write metadata.json with complete gallery info."""
        meta = {
            "gid": detail.gid,
            "token": detail.token,
            "url": detail.url,
            "title": detail.title,
            "title_jpn": getattr(detail, "title_jpn", None),
            "category": detail.category,
            "uploader": detail.uploader,
            "cover_url": detail.cover_url,
            "tags": detail.tags,
            "pages": detail.pages,
            "size": detail.size,
            "posted": detail.posted,
            "rating": detail.rating,
            "rating_count": detail.rating_count,
            "favorite_count": detail.favorite_count,
            "favorite_slot": detail.favorite_slot,
            "torrent_count": detail.torrent_count,
            "comments": [
                {"id": c.id, "user": c.user, "comment": c.comment,
                 "score": c.score, "time": c.time}
                for c in detail.comments
            ] if detail.comments else [],
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
        path = Path(output_dir) / "metadata.json"
        path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    async def _worker(self) -> None:
        while True:
            try:
                gid = await self._queue.get()
            except asyncio.CancelledError:
                return

            task = self._tasks.get(gid)
            if task is None:
                self._queue.task_done()
                continue

            if gid in self._cancelled or task.status == "cancelled":
                self._queue.task_done()
                continue

            task.status = "downloading"
            self._save_state()

            try:
                await self._download_gallery(task)
            except asyncio.CancelledError:
                if task.status == "downloading":
                    task.status = "queued"
                    self._save_state()
                self._queue.task_done()
                return
            except Exception as exc:
                task.status = "failed"
                task.error = str(exc)
                await self._ws.broadcast(
                    {"event": "download_error", "gid": gid, "error": str(exc)}
                )
                self._save_state()

            self._queue.task_done()

    async def _download_pages(self, task: DownloadTask) -> None:
        """Concurrent page download with inline retry."""
        semaphore = asyncio.Semaphore(self._config.page_concurrency)
        pages_dir = Path(task.output_dir) / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        stop_event = asyncio.Event()
        stop_reason: Exception | None = None

        # Clean leftover .tmp files
        for tmp_file in pages_dir.glob("*.tmp"):
            tmp_file.unlink(missing_ok=True)

        # Initialize page states
        for i in range(1, task.total_pages + 1):
            if task.page_states.get(i) != "done":
                task.page_states[i] = "pending"

        async def _download_single_page(page_num: int) -> None:
            nonlocal stop_reason
            if stop_event.is_set():
                return
            if task.page_states.get(page_num) == "done":
                return
            # File system check (exclude .tmp)
            existing = [f for f in pages_dir.glob(f"{page_num:04d}.*")
                        if not f.name.endswith(".tmp")]
            if existing:
                task.page_states[page_num] = "done"
                return

            async with semaphore:
                if stop_event.is_set() or task.gid in self._cancelled:
                    return

                idx = page_num - 1
                if idx >= len(task.preview_urls):
                    task.page_states[page_num] = "failed"
                    task.failed_pages.append(page_num)
                    return

                viewer_url = task.preview_urls[idx]
                last_exc = None

                for attempt in range(self._config.max_retry + 1):
                    if stop_event.is_set() or task.gid in self._cancelled:
                        return
                    try:
                        task.page_states[page_num] = "downloading"
                        html = await self._api.client.get_html(viewer_url)
                        image_url, _ = parse_image_viewer(html)
                        if not image_url:
                            raise ParseError(f"No image URL for page {page_num}")
                        data = await self._fetch_image(image_url)
                        ext = _ext_from_url(image_url)
                        _atomic_write(pages_dir / f"{page_num:04d}{ext}", data)
                        task.page_states[page_num] = "done"
                        task.downloaded_pages += 1
                        last_exc = None
                        break

                    except (AuthenticationError, ImageLimitError, GalleryNotFoundError) as e:
                        stop_reason = e
                        stop_event.set()
                        task.page_states[page_num] = "failed"
                        return

                    except (NetworkError, ParseError) as e:
                        last_exc = e
                        if attempt < self._config.max_retry:
                            delay = self._config.retry_base_delay * (2 ** attempt)
                            await asyncio.sleep(delay)

                    except Exception as e:
                        last_exc = e
                        break

                if last_exc is not None:
                    task.page_states[page_num] = "failed"
                    task.failed_pages.append(page_num)

                await self._ws.broadcast({
                    "event": "download_progress", "gid": task.gid,
                    "phase": "pages", "page": page_num, "total": task.total_pages,
                })
                self._mark_dirty()

        coros = [_download_single_page(p) for p in range(1, task.total_pages + 1)]
        await asyncio.gather(*coros)

        if stop_reason is not None:
            raise stop_reason

    async def _download_gallery(self, task: DownloadTask) -> None:
        """Download complete gallery: metadata, cover, thumbs, pages."""
        output_dir = Path(task.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        thumbs_dir = output_dir / "thumbs"
        thumbs_dir.mkdir(exist_ok=True)
        pages_dir = output_dir / "pages"
        pages_dir.mkdir(exist_ok=True)

        # Fetch gallery detail once for metadata and cover
        detail = await self._api.get_gallery_details(task.gid, task.token)

        # 1. Write metadata
        if not task.metadata_saved:
            self._write_metadata(detail, str(output_dir))
            task.metadata_saved = True
            self._save_state()

        # 2. Download cover
        if not task.cover_downloaded:
            if detail.cover_url:
                try:
                    cover_data = await self._fetch_image(detail.cover_url)
                    ext = _ext_from_url(detail.cover_url)
                    (output_dir / f"cover{ext}").write_bytes(cover_data)
                except Exception:
                    pass  # Cover failure is non-fatal
            task.cover_downloaded = True
            await self._ws.broadcast({"event": "download_progress", "gid": task.gid, "phase": "cover"})
            self._save_state()

        # 3. Download thumbnails (with sprite cropping for gdtm mode)
        sprite_cache: dict[str, bytes] = {}  # url → downloaded sprite bytes
        for idx in range(len(task.thumb_sprites or task.thumb_urls)):
            if task.gid in self._cancelled:
                task.status = "cancelled"
                self._save_state()
                return

            page_num = idx + 1
            existing = list(thumbs_dir.glob(f"{page_num:04d}.*"))
            if existing:
                task.downloaded_thumbs = page_num
                continue

            try:
                sprite = task.thumb_sprites[idx] if task.thumb_sprites else None
                if sprite and sprite.get("width", 0) > 0:
                    # Sprite mode: download sprite once, crop individual thumbnail
                    sprite_url = sprite["url"]
                    if sprite_url not in sprite_cache:
                        sprite_cache[sprite_url] = await self._fetch_image(sprite_url)
                    result = self._crop_sprite(
                        sprite_cache[sprite_url],
                        sprite["offset_x"], sprite["offset_y"],
                        sprite["width"], sprite["height"],
                    )
                    if result:
                        data, ext = result
                        (thumbs_dir / f"{page_num:04d}{ext}").write_bytes(data)
                elif idx < len(task.thumb_urls):
                    # Direct image mode (gdtl)
                    thumb_url = task.thumb_urls[idx]
                    data = await self._fetch_image(thumb_url)
                    ext = _ext_from_url(thumb_url)
                    (thumbs_dir / f"{page_num:04d}{ext}").write_bytes(data)
            except Exception:
                pass

            task.downloaded_thumbs = page_num
            await self._ws.broadcast({
                "event": "download_progress", "gid": task.gid,
                "phase": "thumbs", "page": page_num, "total": task.total_pages,
            })
            self._save_state()

        # 4. Download full-size pages
        for idx, viewer_url in enumerate(task.preview_urls):
            if task.gid in self._cancelled:
                task.status = "cancelled"
                self._save_state()
                return

            page_num = idx + 1

            # Check if already downloaded (resume support)
            existing = list(pages_dir.glob(f"{page_num:04d}.*"))
            if existing:
                task.downloaded_pages = page_num
                continue

            try:
                html = await self._api.client.get_html(viewer_url)
                image_url, _ = parse_image_viewer(html)
                if not image_url:
                    continue

                data = await self._fetch_image(image_url)
                ext = _ext_from_url(image_url)
                (pages_dir / f"{page_num:04d}{ext}").write_bytes(data)
            except Exception as exc:
                task.error = f"Page {page_num}: {exc}"

            task.downloaded_pages = page_num
            await self._ws.broadcast({
                "event": "download_progress", "gid": task.gid,
                "phase": "pages", "page": page_num, "total": task.total_pages,
            })
            self._save_state()

        if task.gid not in self._cancelled:
            task.status = "completed"
            await self._ws.broadcast(
                {"event": "download_complete", "gid": task.gid, "path": task.output_dir}
            )
            self._save_state()

    @staticmethod
    def _crop_sprite(sprite_data: bytes, x: int, y: int, w: int, h: int) -> tuple[bytes, str] | None:
        """Crop a single thumbnail from a CSS sprite sheet. Returns (data, ext) or None."""
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(sprite_data))
            cropped = img.crop((x, y, x + w, y + h))
            buf = io.BytesIO()
            # Preserve original format
            fmt = img.format or "JPEG"
            if fmt == "WEBP":
                cropped.save(buf, format="WEBP", quality=90)
                ext = ".webp"
            elif fmt == "PNG":
                cropped.save(buf, format="PNG")
                ext = ".png"
            else:
                cropped.save(buf, format="JPEG", quality=90)
                ext = ".jpg"
            return buf.getvalue(), ext
        except Exception:
            return None

    async def _fetch_image(self, url: str) -> bytes:
        """Fetch image bytes via ImageService (cache-first)."""
        return await self._image_service.proxy_image(url)

    def _mark_dirty(self) -> None:
        """Mark state as dirty, start delayed save."""
        self._save_dirty = True
        if self._save_task is None or self._save_task.done():
            self._save_task = asyncio.create_task(self._debounced_save())

    async def _debounced_save(self) -> None:
        """Save after 5s delay, coalescing multiple writes."""
        await asyncio.sleep(5)
        if self._save_dirty:
            self._save_state()
            self._save_dirty = False

    def _save_state(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {gid: task.to_dict() for gid, task in self._tasks.items()}
        self._state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            raw = self._state_file.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            return
        for gid, task_dict in data.items():
            try:
                task = DownloadTask(**task_dict)
                self._tasks[gid] = task
            except Exception:
                continue
