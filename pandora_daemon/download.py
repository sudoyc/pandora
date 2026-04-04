"""Download manager for pandora-daemon.

Manages a queue of gallery download tasks, persists state to disk, and
broadcasts real-time progress events via WebSocket.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def _sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in file/directory names."""
    return re.sub(r'[\\/*?:"<>|]', "", name)


@dataclass
class DownloadTask:
    """Represents a single gallery download task."""

    gid: str
    token: str
    title: str
    total_pages: int
    output_dir: str
    status: str = "queued"  # "queued"|"downloading"|"completed"|"failed"|"cancelled"
    downloaded_pages: int = 0
    error: str = ""
    created_at: str = ""
    preview_urls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


class DownloadManager:
    """Manages queued gallery downloads with concurrency control and persistence."""

    def __init__(self, api, config, ws, state_file: Path) -> None:
        self._api = api
        self._config = config
        self._ws = ws
        self._state_file = state_file
        self._download_path = Path(config.path).expanduser()
        self._tasks: dict[str, DownloadTask] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._cancelled: set[str] = set()

    async def start(self) -> None:
        """Start worker tasks and reload persisted state."""
        self._load_state()
        # Re-queue tasks that were pending or downloading when daemon stopped
        for task in list(self._tasks.values()):
            if task.status in ("queued", "downloading"):
                task.status = "queued"
                task.downloaded_pages = 0
                await self._queue.put(task.gid)

        concurrency = self._config.concurrency
        for _ in range(concurrency):
            worker = asyncio.create_task(self._worker())
            self._workers.append(worker)

    async def shutdown(self) -> None:
        """Cancel all workers and persist current state."""
        for worker in self._workers:
            worker.cancel()
        # Await cancellation without raising
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._save_state()

    async def submit(self, gid: str, token: str) -> DownloadTask:
        """Fetch gallery detail, create a download task, and enqueue it.

        Raises ValueError if a task for the given gid is already
        queued or downloading.
        """
        existing = self._tasks.get(gid)
        if existing and existing.status in ("queued", "downloading"):
            raise ValueError(f"Gallery {gid} is already queued or downloading")

        detail = await self._api.get_gallery_details(gid, token)

        # Collect preview URLs (page viewer URLs)
        preview_urls = list(detail.preview_urls)
        if detail.preview_pages > 1:
            import bs4

            for p in range(1, detail.preview_pages):
                page_url = f"{detail.url}?p={p}"
                html = await self._api.client.get_html(page_url)
                soup = bs4.BeautifulSoup(html, "html.parser")
                for gdt in soup.find_all(class_=["gdtm", "gdtl"]):
                    a_tag = gdt.find("a")
                    if a_tag and a_tag.get("href"):
                        preview_urls.append(a_tag.get("href"))

        safe_title = _sanitize_filename(detail.title)
        output_dir = str(self._download_path / f"{gid}-{safe_title}")

        task = DownloadTask(
            gid=gid,
            token=token,
            title=detail.title,
            total_pages=detail.pages,
            output_dir=output_dir,
            preview_urls=preview_urls,
        )
        self._tasks[gid] = task
        await self._queue.put(gid)

        await self._ws.broadcast({"event": "download_queued", "gid": gid, "title": detail.title})
        self._save_state()
        return task

    async def cancel(self, gid: str) -> bool:
        """Cancel a download task.

        Returns True if the task was found and cancelled, False otherwise.
        """
        task = self._tasks.get(gid)
        if task is None:
            return False

        self._cancelled.add(gid)
        task.status = "cancelled"
        await self._ws.broadcast({"event": "download_cancelled", "gid": gid})
        self._save_state()
        return True

    def status(self) -> list[DownloadTask]:
        """Return all known download tasks."""
        return list(self._tasks.values())

    async def _worker(self) -> None:
        """Worker coroutine: pull tasks from the queue and download them."""
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
                # Worker was cancelled; put the task back as queued if not done
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

    async def _download_gallery(self, task: DownloadTask) -> None:
        """Download all pages for *task*."""
        from exhentai_api.parsers.image import parse_image_viewer

        output_dir = Path(task.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for idx, viewer_url in enumerate(task.preview_urls):
            if task.gid in self._cancelled:
                task.status = "cancelled"
                self._save_state()
                return

            page_num = idx + 1

            try:
                html = await self._api.client.get_html(viewer_url)
                image_url, _ = parse_image_viewer(html)

                if not image_url:
                    continue

                ext = image_url.rsplit(".", 1)[-1].split("?")[0] or "jpg"
                dest = output_dir / f"{page_num:04d}.{ext}"

                async with self._api.client.session.stream("GET", image_url) as response:
                    response.raise_for_status()
                    with dest.open("wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            f.write(chunk)

            except Exception as exc:
                # Log per-page error but continue with remaining pages
                task.error = f"Page {page_num}: {exc}"

            task.downloaded_pages = page_num
            await self._ws.broadcast(
                {
                    "event": "download_progress",
                    "gid": task.gid,
                    "page": page_num,
                    "total": task.total_pages,
                }
            )
            self._save_state()

        if task.gid not in self._cancelled:
            task.status = "completed"
            await self._ws.broadcast(
                {"event": "download_complete", "gid": task.gid, "path": task.output_dir}
            )
            self._save_state()

    def _save_state(self) -> None:
        """Write the current task list to the state file as JSON."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {gid: task.to_dict() for gid, task in self._tasks.items()}
        self._state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_state(self) -> None:
        """Read task list from the state file (if it exists)."""
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
                # Skip malformed entries
                continue
