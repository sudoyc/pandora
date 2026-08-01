"""Download manager for pandora-daemon.

Produces complete offline gallery clones in the library directory.
Each gallery gets: metadata.json, cover, thumbs/, pages/.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pandora_daemon.providers.errors import (
    ProviderAuthenticationError,
    ProviderGalleryNotFoundError,
    ProviderNetworkError,
    ProviderParseError,
    ProviderQuotaError,
)
from pandora_daemon.diagnostics import new_diagnostic_id, normalize_diagnostic_id


logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in file/directory names."""
    return re.sub(r'[\\/*?:"<>|]', "", name)


def _atomic_write(path: Path, data: bytes) -> None:
    """Write via temp file + rename to prevent partial writes on crash."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(data)
    tmp_path.rename(path)


def _ext_from_image_bytes(data: bytes) -> str:
    """Choose a stable image extension from supported image signatures."""
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"

_TERMINAL_ARTIFACT_STATUSES = {"completed", "completed_with_errors"}
_PAGE_FILE_RE = re.compile(r"^(\d{4,})\.[^.]+$")
DOWNLOAD_STATE_SCHEMA_VERSION = 1
_LEGACY_TRANSPORT_STATE_FIELDS = frozenset(
    {"viewer_urls", "thumb_urls", "thumb_sprites"}
)


class UnsupportedDownloadStateVersion(RuntimeError):
    """Raised when a state file was written by an unsupported schema version."""

    def __init__(self, version: object) -> None:
        super().__init__(
            f"Unsupported download state schema version {version}; "
            f"expected {DOWNLOAD_STATE_SCHEMA_VERSION}"
        )


def _read_library_metadata(gallery_dir: Path) -> tuple[str, dict | None]:
    metadata_path = gallery_dir / "metadata.json"
    if not metadata_path.is_file():
        return "missing", None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError):
        return "invalid", None
    if not isinstance(metadata, dict) or not str(metadata.get("gid", "")):
        return "invalid", None
    return "present", metadata


def _present_page_numbers(gallery_dir: Path) -> set[int]:
    pages_dir = gallery_dir / "pages"
    if not pages_dir.is_dir():
        return set()
    pages = set()
    for path in pages_dir.iterdir():
        match = _PAGE_FILE_RE.fullmatch(path.name)
        if path.is_file() and match and path.suffix != ".tmp":
            pages.add(int(match.group(1)))
    return pages


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
    request_id: str = ""
    correlation_id: str = ""
    page_states: dict[int, str] = field(default_factory=dict)
    failed_pages: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        self.request_id = normalize_diagnostic_id(self.request_id) or new_diagnostic_id()
        self.correlation_id = (
            normalize_diagnostic_id(self.correlation_id) or new_diagnostic_id()
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def to_public_dict(self) -> dict:
        """Return the public REST/WS-safe download status shape."""
        return {
            "gid": self.gid,
            "title": self.title,
            "total_pages": self.total_pages,
            "status": self.status,
            "downloaded_pages": self.downloaded_pages,
            "downloaded_thumbs": self.downloaded_thumbs,
            "cover_downloaded": self.cover_downloaded,
            "metadata_saved": self.metadata_saved,
            "error": self.error,
            "created_at": self.created_at,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "page_states": {
                page: "completed" if state == "done" else state
                for page, state in self.page_states.items()
            },
            "failed_pages": self.failed_pages,
        }


class DownloadManager:
    """Produces complete offline gallery clones with metadata, covers, thumbs, and pages."""

    def __init__(self, provider, config, ws, image_service, state_file: Path) -> None:
        self._provider = provider
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
        self._submit_lock = asyncio.Lock()

    async def _broadcast_task_event(
        self,
        task: DownloadTask,
        event: str,
        **fields,
    ) -> None:
        payload = {
            **fields,
            "event": event,
            "gid": task.gid,
            "request_id": task.request_id,
            "correlation_id": task.correlation_id,
        }
        logger.info(
            "Download event request_id=%s correlation_id=%s gid=%s "
            "event=%s status=%s phase=%s",
            task.request_id,
            task.correlation_id,
            task.gid,
            event,
            task.status,
            fields.get("phase", "none"),
        )
        await self._ws.broadcast(payload)

    @staticmethod
    def _set_request_id(task: DownloadTask, request_id: str | None) -> None:
        normalized = normalize_diagnostic_id(request_id)
        if normalized is not None:
            task.request_id = normalized

    async def start(self) -> None:
        self._load_state()
        requeue_gids = []
        for task in list(self._tasks.values()):
            if task.status in ("queued", "downloading"):
                self._reconcile_pages(task)
                task.status = "queued"
                task.error = ""
                self._cancelled.discard(task.gid)
                requeue_gids.append(task.gid)

        if requeue_gids:
            self._save_state()
        for gid in requeue_gids:
            await self._queue.put(gid)

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

    async def submit(
        self,
        gid: str,
        token: str,
        *,
        request_id: str = "",
        correlation_id: str = "",
    ) -> DownloadTask:
        async with self._submit_lock:
            existing = self._tasks.get(gid)
            if existing and existing.status in ("queued", "downloading"):
                raise ValueError(f"Gallery {gid} is already queued or downloading")

            self._cancelled.discard(gid)

            detail = await self._provider.get_gallery_details(gid, token)

            safe_title = _sanitize_filename(detail.title)
            output_dir = str(self._download_path / f"{gid}-{safe_title}")

            task = DownloadTask(
                gid=gid,
                token=token,
                title=detail.title,
                total_pages=detail.pages,
                output_dir=output_dir,
                request_id=request_id,
                correlation_id=correlation_id,
            )
            self._tasks[gid] = task
            await self._queue.put(gid)

            await self._broadcast_task_event(
                task,
                "download_queued",
                title=detail.title,
            )
            self._save_state()
            return task

    async def cancel(self, gid: str, *, request_id: str | None = None) -> bool:
        task = self._tasks.get(gid)
        if task is None or task.status not in {"queued", "downloading", "paused"}:
            return False

        self._cancelled.add(gid)
        self._set_request_id(task, request_id)
        task.status = "cancelled"
        await self._broadcast_task_event(task, "download_cancelled")
        self._save_state()
        return True

    async def resume(self, gid: str, *, request_id: str | None = None) -> bool:
        """Resume a paused task."""
        task = self._tasks.get(gid)
        if task is None or task.status != "paused":
            return False
        self._set_request_id(task, request_id)
        self._cancelled.discard(gid)
        self._reconcile_pages(task)
        task.status = "queued"
        task.error = ""
        self._save_state()
        await self._queue.put(gid)
        await self._broadcast_task_event(
            task,
            "download_queued",
            title=task.title,
        )
        return True

    async def retry_failed(self, gid: str, *, request_id: str | None = None) -> bool:
        """Retry missing pages of a completed or completed_with_errors task."""
        task = self._tasks.get(gid)
        if task is None or task.status not in {"completed", "completed_with_errors"}:
            return False

        expected_pages = set(range(1, task.total_pages + 1))
        present_pages = _present_page_numbers(Path(task.output_dir))
        if task.status == "completed" and expected_pages <= present_pages:
            return False

        self._set_request_id(task, request_id)
        self._cancelled.discard(gid)
        missing_pages = self._reconcile_pages(task, present_pages=present_pages)
        task.error = ""
        if not missing_pages:
            task.status = "completed"
            self._save_state()
            await self._broadcast_task_event(task, "download_complete")
            return True

        task.status = "queued"
        self._save_state()
        await self._queue.put(gid)
        await self._broadcast_task_event(
            task,
            "download_queued",
            title=task.title,
        )
        return True

    def status(self) -> list[DownloadTask]:
        return list(self._tasks.values())

    @staticmethod
    def _reconcile_pages(
        task: DownloadTask,
        *,
        present_pages: set[int] | None = None,
    ) -> list[int]:
        """Make task page state match complete page files currently on disk."""
        if present_pages is None:
            present_pages = _present_page_numbers(Path(task.output_dir))
        expected_pages = set(range(1, task.total_pages + 1))
        completed_pages = expected_pages & present_pages
        task.page_states = {
            page: "done" if page in completed_pages else "pending"
            for page in range(1, task.total_pages + 1)
        }
        task.downloaded_pages = len(completed_pages)
        task.failed_pages = []
        return sorted(expected_pages - completed_pages)

    def _task_is_stopped(self, task: DownloadTask) -> bool:
        return task.gid in self._cancelled or task.status not in {"queued", "downloading"}

    async def repair(self, gid: str, *, apply: bool = False) -> dict:
        """Preview or register one complete, unregistered library entry."""
        async with self._submit_lock:
            result = {
                "operation": "repair",
                "gid": gid,
                "apply": apply,
                "changed": False,
                "actions": [],
            }
            if gid in self._tasks:
                return result

            candidates = []
            if self._download_path.is_dir():
                for gallery_dir in sorted(self._download_path.iterdir()):
                    if not gallery_dir.is_dir():
                        continue
                    metadata_status, metadata = _read_library_metadata(gallery_dir)
                    if metadata_status == "present" and str(metadata["gid"]) == gid:
                        candidates.append((gallery_dir, metadata))

            if not candidates:
                return result
            if len(candidates) > 1:
                raise ValueError(f"Multiple library entries found for gallery {gid}")

            gallery_dir, metadata = candidates[0]
            total_pages = metadata.get("pages")
            if isinstance(total_pages, bool) or not isinstance(total_pages, int) or total_pages < 1:
                raise ValueError(f"Library entry {gid} has invalid page metadata")

            expected_numbers = set(range(1, total_pages + 1))
            page_numbers = _present_page_numbers(gallery_dir)
            missing_pages = sorted(expected_numbers - page_numbers)
            if missing_pages:
                raise ValueError(f"Library entry {gid} has missing pages")

            action = {
                "code": "register_library_task",
                "gid": gid,
                "task_status": "completed",
                "expected_pages": total_pages,
                "present_pages": total_pages,
            }
            result["actions"] = [action]
            if not apply:
                return result

            token = metadata.get("token")
            title = metadata.get("title")
            created_at = metadata.get("downloaded_at")
            task = DownloadTask(
                gid=gid,
                token=token if isinstance(token, str) else "",
                title=title if isinstance(title, str) and title else f"Gallery {gid}",
                total_pages=total_pages,
                output_dir=str(gallery_dir),
                status="completed",
                downloaded_pages=total_pages,
                cover_downloaded=any(
                    path.is_file() and path.suffix != ".tmp"
                    for path in gallery_dir.glob("cover.*")
                ),
                metadata_saved=True,
                created_at=created_at if isinstance(created_at, str) else "",
                page_states={page: "done" for page in range(1, total_pages + 1)},
            )
            self._tasks[gid] = task
            self._save_state()
            result["changed"] = True
            return result

    async def forget(self, gid: str, *, apply: bool = False) -> dict:
        """Preview or remove one inactive task while preserving library files."""
        async with self._submit_lock:
            result = {
                "operation": "forget",
                "gid": gid,
                "apply": apply,
                "changed": False,
                "actions": [],
            }
            task = self._tasks.get(gid)
            if task is None:
                return result
            if task.status in {"queued", "downloading"}:
                raise ValueError(f"Gallery {gid} has an active task and cannot be forgotten")

            result["actions"] = [{
                "code": "forget_task",
                "gid": gid,
                "task_status": task.status,
            }]
            if not apply:
                return result

            self._tasks.pop(gid)
            self._cancelled.discard(gid)
            self._save_state()
            result["changed"] = True
            return result

    def consistency_report(self) -> dict:
        """Compare registered terminal tasks with library files without changing either."""
        issues = []
        terminal_tasks = [
            task for task in self._tasks.values()
            if task.status in _TERMINAL_ARTIFACT_STATUSES
        ]

        def add_issue(
            code: str,
            gid: str,
            task_status: str | None,
            expected_pages: int | None,
            present_pages: int,
            missing_pages: list[int],
        ) -> None:
            issues.append({
                "code": code,
                "gid": gid,
                "task_status": task_status,
                "expected_pages": expected_pages,
                "present_pages": present_pages,
                "missing_pages": missing_pages,
            })

        for task in sorted(terminal_tasks, key=lambda item: item.gid):
            gallery_dir = Path(task.output_dir)
            if gallery_dir.parent != self._download_path or not gallery_dir.is_dir():
                add_issue("orphan_task", task.gid, task.status, task.total_pages, 0, [])
                continue

            page_numbers = _present_page_numbers(gallery_dir)
            expected_numbers = set(range(1, task.total_pages + 1))
            present_pages = len(page_numbers & expected_numbers)
            metadata_status, metadata = _read_library_metadata(gallery_dir)
            if metadata_status == "missing":
                add_issue(
                    "missing_metadata",
                    task.gid,
                    task.status,
                    task.total_pages,
                    present_pages,
                    [],
                )
            elif metadata_status == "invalid" or str(metadata["gid"]) != task.gid:
                add_issue(
                    "invalid_metadata",
                    task.gid,
                    task.status,
                    task.total_pages,
                    present_pages,
                    [],
                )

            missing_pages = sorted(expected_numbers - page_numbers)
            if missing_pages:
                add_issue(
                    "missing_pages",
                    task.gid,
                    task.status,
                    task.total_pages,
                    present_pages,
                    missing_pages,
                )

        registered_gids = {task.gid for task in self._tasks.values()}
        library_entries = 0
        if self._download_path.is_dir():
            for gallery_dir in sorted(self._download_path.iterdir()):
                if not gallery_dir.is_dir():
                    continue
                metadata_status, metadata = _read_library_metadata(gallery_dir)
                if metadata_status != "present":
                    continue
                library_entries += 1
                gid = str(metadata["gid"])
                if gid in registered_gids:
                    continue

                expected_pages = metadata.get("pages")
                if isinstance(expected_pages, bool) or not isinstance(expected_pages, int):
                    expected_pages = None
                page_numbers = _present_page_numbers(gallery_dir)
                if expected_pages is None:
                    present_pages = len(page_numbers)
                    missing_pages = []
                else:
                    expected_numbers = set(range(1, expected_pages + 1))
                    present_pages = len(page_numbers & expected_numbers)
                    missing_pages = sorted(expected_numbers - page_numbers)
                add_issue(
                    "unregistered_library",
                    gid,
                    None,
                    expected_pages,
                    present_pages,
                    missing_pages,
                )

        issues.sort(key=lambda issue: (issue["gid"], issue["code"]))
        return {
            "consistent": not issues,
            "summary": {
                "registered_tasks": len(self._tasks),
                "terminal_tasks": len(terminal_tasks),
                "library_entries": library_entries,
                "affected_galleries": len({issue["gid"] for issue in issues}),
                "issue_count": len(issues),
            },
            "issues": issues,
        }

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

            if gid in self._cancelled or task.status != "queued":
                self._queue.task_done()
                continue

            try:
                await self._download_gallery(task)
            except asyncio.CancelledError:
                if task.status == "downloading":
                    task.status = "queued"
                    self._save_state()
                self._queue.task_done()
                return

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

        self._reconcile_pages(task)

        def _count_done_pages() -> int:
            return sum(
                task.page_states.get(page) == "done"
                for page in range(1, task.total_pages + 1)
            )

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
                task.downloaded_pages = _count_done_pages()
                return

            async with semaphore:
                if stop_event.is_set() or self._task_is_stopped(task):
                    return

                last_exc = None

                for attempt in range(self._config.max_retry + 1):
                    if stop_event.is_set() or self._task_is_stopped(task):
                        return
                    try:
                        task.page_states[page_num] = "downloading"
                        data = await self._image_service.get_page_image(
                            task.gid, task.token, page_num
                        )
                        ext = _ext_from_image_bytes(data)
                        _atomic_write(pages_dir / f"{page_num:04d}{ext}", data)
                        task.page_states[page_num] = "done"
                        task.downloaded_pages = _count_done_pages()
                        last_exc = None
                        break

                    except (ProviderAuthenticationError, ProviderQuotaError, ProviderGalleryNotFoundError) as e:
                        stop_reason = e
                        stop_event.set()
                        task.page_states[page_num] = "failed"
                        return

                    except (ProviderNetworkError, ProviderParseError) as e:
                        last_exc = e
                        if attempt < self._config.max_retry:
                            delay = self._config.retry_base_delay * (2 ** attempt)
                            await asyncio.sleep(delay)

                    except Exception as e:
                        last_exc = e
                        break

                if last_exc is not None:
                    task.page_states[page_num] = "failed"

                await self._broadcast_task_event(
                    task,
                    "download_progress",
                    phase="pages",
                    page=page_num,
                    total=task.total_pages,
                )
                self._mark_dirty()

        coros = [_download_single_page(p) for p in range(1, task.total_pages + 1)]
        await asyncio.gather(*coros)
        task.downloaded_pages = _count_done_pages()
        task.failed_pages = sorted(
            page
            for page in range(1, task.total_pages + 1)
            if task.page_states.get(page) == "failed"
        )

        if stop_reason is not None:
            raise stop_reason

    async def _download_gallery(self, task: DownloadTask) -> None:
        """Download complete gallery: metadata, cover, thumbs, pages."""
        output_dir = Path(task.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            if task.status == "queued":
                task.status = "downloading"
                self._save_state()
            elif task.status != "downloading":
                return

            detail = None
            if not task.metadata_saved or not task.cover_downloaded:
                detail = await self._provider.get_gallery_details(task.gid, task.token)
                if self._task_is_stopped(task):
                    return

            if not task.metadata_saved:
                self._write_metadata(detail, str(output_dir))
                task.metadata_saved = True
                self._save_state()

            if not task.cover_downloaded:
                if detail.cover_url:
                    try:
                        cover_data = await self._image_service.proxy_image(detail.cover_url)
                        ext = _ext_from_image_bytes(cover_data)
                        _atomic_write(output_dir / f"cover{ext}", cover_data)
                    except Exception:
                        pass
                if self._task_is_stopped(task):
                    return
                task.cover_downloaded = True
                await self._broadcast_task_event(
                    task,
                    "download_progress",
                    phase="cover",
                )
                self._save_state()

            thumbs_dir = output_dir / "thumbs"
            thumbs_dir.mkdir(exist_ok=True)
            for page_num in range(1, task.total_pages + 1):
                if self._task_is_stopped(task):
                    return

                existing = [
                    f for f in thumbs_dir.glob(f"{page_num:04d}.*")
                    if not f.name.endswith(".tmp")
                ]
                if existing:
                    task.downloaded_thumbs = page_num
                    continue

                try:
                    data = await self._image_service.get_thumbnail(
                        task.gid, task.token, page_num
                    )
                    ext = _ext_from_image_bytes(data)
                    _atomic_write(thumbs_dir / f"{page_num:04d}{ext}", data)
                except Exception:
                    pass

                if self._task_is_stopped(task):
                    return
                task.downloaded_thumbs = page_num
                await self._broadcast_task_event(
                    task,
                    "download_progress",
                    phase="thumbs",
                    page=page_num,
                    total=task.total_pages,
                )
                self._mark_dirty()

            if self._task_is_stopped(task):
                return
            await self._download_pages(task)
            if self._task_is_stopped(task):
                return

            if task.failed_pages:
                task.status = "completed_with_errors"
                task.error = f"{len(task.failed_pages)} pages failed"
                await self._broadcast_task_event(
                    task,
                    "download_complete_with_errors",
                    failed_pages=task.failed_pages,
                )
            else:
                task.status = "completed"
                task.error = ""
                await self._broadcast_task_event(task, "download_complete")

        except ProviderAuthenticationError as e:
            if self._task_is_stopped(task):
                return
            task.status = "failed"
            task.error = str(e)
            await self._broadcast_task_event(
                task,
                "download_auth_failed",
                error=str(e),
            )
            await self._pause_all_tasks()

        except ProviderQuotaError as e:
            if self._task_is_stopped(task):
                return
            task.status = "paused"
            task.error = str(e)
            await self._broadcast_task_event(
                task,
                "download_paused",
                reason="image_limit",
            )

        except ProviderGalleryNotFoundError as e:
            if self._task_is_stopped(task):
                return
            task.status = "failed"
            task.error = str(e)
            await self._broadcast_task_event(
                task,
                "download_error",
                error=str(e),
            )

        except Exception as e:
            if self._task_is_stopped(task):
                return
            task.status = "failed"
            task.error = str(e)
            await self._broadcast_task_event(
                task,
                "download_error",
                error=str(e),
            )

        finally:
            self._save_state()

    async def _pause_all_tasks(self) -> None:
        """Pause all queued/downloading tasks when authentication fails."""
        for t in self._tasks.values():
            if t.status in ("queued", "downloading"):
                t.status = "paused"
                await self._broadcast_task_event(
                    t,
                    "download_paused",
                    reason="auth_failed",
                )
        self._save_state()


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
        data = {
            "schema_version": DOWNLOAD_STATE_SCHEMA_VERSION,
            "tasks": {gid: task.to_dict() for gid, task in self._tasks.items()},
        }
        tmp_path = self._state_file.with_suffix(self._state_file.suffix + ".tmp")
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_path.replace(self._state_file)

    def _corrupt_state_backup_path(self) -> Path:
        base = self._state_file.with_name(f"{self._state_file.name}.corrupt")
        candidate = base
        index = 1
        while candidate.exists():
            candidate = base.with_name(f"{base.name}.{index}")
            index += 1
        return candidate

    def _recover_corrupt_state(self) -> None:
        backup_path = self._corrupt_state_backup_path()
        self._state_file.replace(backup_path)
        self._save_state()
        logger.warning(
            "Recovered corrupt download state; backup=%s",
            backup_path.name,
        )

    def _load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            raw = self._state_file.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeError):
            self._tasks.clear()
            self._recover_corrupt_state()
            return

        if not isinstance(data, dict):
            self._tasks.clear()
            self._recover_corrupt_state()
            return

        legacy_format = "schema_version" not in data
        if legacy_format:
            task_data = data
        else:
            version = data.get("schema_version")
            if type(version) is not int:
                self._tasks.clear()
                self._recover_corrupt_state()
                return
            if version != DOWNLOAD_STATE_SCHEMA_VERSION:
                raise UnsupportedDownloadStateVersion(version)
            task_data = data.get("tasks")
            if not isinstance(task_data, dict):
                self._tasks.clear()
                self._recover_corrupt_state()
                return

        loaded_tasks = {}
        corrupt_entry = False
        diagnostic_migration = False
        transport_migration = False
        for gid, task_dict in task_data.items():
            try:
                if not isinstance(task_dict, dict):
                    raise ValueError("Download task must be an object")
                normalized = dict(task_dict)
                legacy_fields = _LEGACY_TRANSPORT_STATE_FIELDS.intersection(normalized)
                for field_name in legacy_fields:
                    normalized.pop(field_name)
                transport_migration = transport_migration or bool(legacy_fields)
                page_states = normalized.get("page_states", {})
                if not isinstance(page_states, dict):
                    raise ValueError("Download task page_states must be an object")
                normalized["page_states"] = {
                    int(page): state for page, state in page_states.items()
                }
                task = DownloadTask(**normalized)
                if task.gid != gid:
                    raise ValueError("Download task gid does not match its state key")
                if (
                    normalized.get("request_id") != task.request_id
                    or normalized.get("correlation_id") != task.correlation_id
                ):
                    diagnostic_migration = True
                loaded_tasks[gid] = task
            except Exception:
                corrupt_entry = True

        self._tasks.clear()
        self._tasks.update(loaded_tasks)
        if corrupt_entry:
            self._recover_corrupt_state()
        elif legacy_format or diagnostic_migration or transport_migration:
            self._save_state()
