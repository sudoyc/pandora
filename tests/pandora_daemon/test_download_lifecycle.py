"""Lifecycle contract tests for resumable gallery downloads."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pandora_daemon.config import DownloadConfig
from pandora_daemon.download import DownloadManager, DownloadTask


@pytest.fixture
def manager(tmp_path):
    config = DownloadConfig(
        path=str(tmp_path / "downloads"),
        gallery_concurrency=1,
        page_concurrency=2,
        max_retry=0,
    )
    provider = AsyncMock()
    ws = AsyncMock()
    image_service = AsyncMock()
    image_service.proxy_image.return_value = b"\xff\xd8\xffcover"
    image_service.get_page_image.return_value = b"\xff\xd8\xffpage"
    image_service.get_thumbnail.return_value = b"\x89PNG\r\n\x1a\nthumb"
    return DownloadManager(provider, config, ws, image_service, tmp_path / "downloads.json")


def _task(manager: DownloadManager, *, status: str, total_pages: int = 3) -> DownloadTask:
    return DownloadTask(
        gid="123",
        token="token",
        title="Gallery",
        total_pages=total_pages,
        output_dir=str(Path(manager._config.path) / "123-Gallery"),
        status=status,
        metadata_saved=True,
        cover_downloaded=True,
    )


def _write_page(task: DownloadTask, page: int) -> None:
    pages_dir = Path(task.output_dir) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / f"{page:04d}.jpg").write_bytes(b"existing")


def _events(manager: DownloadManager) -> list[dict]:
    return [call.args[0] for call in manager._ws.broadcast.await_args_list]


def test_public_task_uses_completed_page_state_without_mutating_internal_state(manager):
    task = _task(manager, status="completed", total_pages=2)
    task.page_states = {1: "done", 2: "failed"}

    public = task.to_public_dict()

    assert public["page_states"] == {1: "completed", 2: "failed"}
    assert task.page_states == {1: "done", 2: "failed"}


@pytest.mark.asyncio
async def test_cancel_is_idempotent_and_emits_one_terminal_event(manager):
    task = _task(manager, status="queued")
    manager._tasks[task.gid] = task
    request_id = "1" * 32

    assert await manager.cancel(task.gid, request_id=request_id) is True
    assert await manager.cancel(task.gid) is False

    assert task.status == "cancelled"
    assert _events(manager) == [
        {
            "event": "download_cancelled",
            "gid": task.gid,
            "request_id": request_id,
            "correlation_id": task.correlation_id,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "completed_with_errors", "failed", "cancelled"])
async def test_cancel_does_not_rewrite_terminal_tasks(manager, status):
    task = _task(manager, status=status)
    manager._tasks[task.gid] = task

    assert await manager.cancel(task.gid) is False
    assert task.status == status
    manager._ws.broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_accepts_paused_task(manager):
    task = _task(manager, status="paused")
    manager._tasks[task.gid] = task

    assert await manager.cancel(task.gid) is True
    assert task.status == "cancelled"


@pytest.mark.asyncio
async def test_resume_reconciles_disk_clears_error_and_emits_queued(manager):
    task = _task(manager, status="paused")
    task.page_states = {1: "done", 2: "failed", 3: "downloading"}
    task.downloaded_pages = 3
    task.failed_pages = [2, 3]
    task.error = "image limit"
    _write_page(task, 2)
    manager._tasks[task.gid] = task

    assert await manager.resume(task.gid) is True

    assert task.status == "queued"
    assert task.error == ""
    assert task.downloaded_pages == 1
    assert task.failed_pages == []
    assert task.page_states == {1: "pending", 2: "done", 3: "pending"}
    assert manager._queue.get_nowait() == task.gid
    assert _events(manager) == [
        {
            "event": "download_queued",
            "gid": task.gid,
            "title": task.title,
            "request_id": task.request_id,
            "correlation_id": task.correlation_id,
        }
    ]
    persisted = json.loads(manager._state_file.read_text(encoding="utf-8"))
    assert persisted["tasks"][task.gid]["status"] == "queued"
    assert persisted["tasks"][task.gid]["downloaded_pages"] == 1


@pytest.mark.asyncio
async def test_retry_completed_task_redownloads_page_missing_from_disk(manager):
    task = _task(manager, status="completed", total_pages=2)
    task.page_states = {1: "done", 2: "done"}
    task.downloaded_pages = 2
    _write_page(task, 1)
    manager._tasks[task.gid] = task

    assert await manager.retry_failed(task.gid) is True
    assert task.status == "queued"
    assert task.page_states == {1: "done", 2: "pending"}
    assert task.downloaded_pages == 1

    await manager._download_gallery(task)

    assert task.status == "completed"
    assert task.error == ""
    assert task.failed_pages == []
    assert task.downloaded_pages == 2
    manager._image_service.get_page_image.assert_awaited_once_with(task.gid, task.token, 2)
    manager._provider.get_gallery_details.assert_not_awaited()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_retry_completed_task_with_all_pages_is_noop(manager):
    task = _task(manager, status="completed", total_pages=2)
    task.page_states = {1: "done", 2: "done"}
    task.downloaded_pages = 2
    _write_page(task, 1)
    _write_page(task, 2)
    manager._tasks[task.gid] = task

    assert await manager.retry_failed(task.gid) is False
    assert task.status == "completed"
    assert manager._queue.empty()
    manager._ws.broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_normalizes_restored_failed_pages_without_network_work(manager):
    task = _task(manager, status="completed_with_errors", total_pages=2)
    task.page_states = {1: "done", 2: "failed"}
    task.downloaded_pages = 1
    task.failed_pages = [2]
    task.error = "1 pages failed"
    _write_page(task, 1)
    _write_page(task, 2)
    manager._tasks[task.gid] = task

    assert await manager.retry_failed(task.gid) is True

    assert task.status == "completed"
    assert task.error == ""
    assert task.downloaded_pages == 2
    assert task.failed_pages == []
    assert task.page_states == {1: "done", 2: "done"}
    assert manager._queue.empty()
    assert _events(manager) == [
        {
            "event": "download_complete",
            "gid": task.gid,
            "request_id": task.request_id,
            "correlation_id": task.correlation_id,
        }
    ]
    manager._image_service.get_page_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_all_failed_pages_without_prior_success_skips_completed_phases(manager):
    task = _task(manager, status="completed_with_errors", total_pages=2)
    task.page_states = {1: "failed", 2: "failed"}
    task.failed_pages = [1, 2]
    task.error = "2 pages failed"
    manager._tasks[task.gid] = task

    assert await manager.retry_failed(task.gid) is True

    await manager._download_gallery(task)

    assert task.status == "completed"
    assert task.error == ""
    assert task.downloaded_pages == 2
    assert task.failed_pages == []
    manager._provider.get_gallery_details.assert_not_awaited()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_retry_downloads_repaired_task_without_transport_locators(manager):
    task = _task(manager, status="completed", total_pages=1)
    task.page_states = {1: "done"}
    task.downloaded_pages = 1
    manager._tasks[task.gid] = task

    assert await manager.retry_failed(task.gid) is True
    await manager._download_gallery(task)

    assert task.status == "completed"
    manager._image_service.get_page_image.assert_awaited_once_with(task.gid, task.token, 1)
    manager._provider.get_gallery_details.assert_not_awaited()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_restart_reconciles_and_persists_active_tasks_before_requeue(tmp_path):
    config = DownloadConfig(
        path=str(tmp_path / "downloads"),
        gallery_concurrency=0,
        page_concurrency=1,
    )
    state_file = tmp_path / "downloads.json"
    seed = DownloadManager(AsyncMock(), config, AsyncMock(), AsyncMock(), state_file)
    queued = _task(seed, status="queued", total_pages=2)
    queued.page_states = {1: "done", 2: "done"}
    queued.downloaded_pages = 2
    queued.error = "stale"
    _write_page(queued, 1)
    downloading = DownloadTask(
        **{
            **_task(seed, status="downloading", total_pages=1).to_dict(),
            "gid": "456",
            "output_dir": str(Path(config.path) / "456-Gallery"),
        }
    )
    completed = DownloadTask(
        **{
            **_task(seed, status="completed", total_pages=1).to_dict(),
            "gid": "789",
            "output_dir": str(Path(config.path) / "789-Gallery"),
        }
    )
    state_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tasks": {
                    queued.gid: queued.to_dict(),
                    downloading.gid: downloading.to_dict(),
                    completed.gid: completed.to_dict(),
                },
            }
        ),
        encoding="utf-8",
    )
    manager = DownloadManager(AsyncMock(), config, AsyncMock(), AsyncMock(), state_file)

    await manager.start()

    assert manager._tasks[queued.gid].status == "queued"
    assert manager._tasks[queued.gid].downloaded_pages == 1
    assert manager._tasks[queued.gid].page_states == {1: "done", 2: "pending"}
    assert manager._tasks[queued.gid].error == ""
    assert manager._tasks[downloading.gid].status == "queued"
    assert manager._tasks[completed.gid].status == "completed"
    requeued = [manager._queue.get_nowait(), manager._queue.get_nowait()]
    assert requeued == [queued.gid, downloading.gid]
    persisted = json.loads(state_file.read_text(encoding="utf-8"))["tasks"]
    assert persisted[queued.gid]["status"] == "queued"
    assert persisted[queued.gid]["downloaded_pages"] == 1
    assert persisted[downloading.gid]["status"] == "queued"
    await manager.shutdown()


@pytest.mark.asyncio
async def test_pause_from_another_worker_cannot_be_overwritten_by_completion(manager):
    task = _task(manager, status="downloading", total_pages=1)
    manager._tasks[task.gid] = task

    async def pause_during_pages(current):
        await manager._pause_all_tasks()
        current.page_states = {1: "done"}
        current.downloaded_pages = 1

    manager._download_pages = AsyncMock(side_effect=pause_during_pages)

    await manager._download_gallery(task)

    assert task.status == "paused"
    events = {event["event"] for event in _events(manager)}
    assert "download_paused" in events
    assert not events & {
        "download_auth_failed",
        "download_complete",
        "download_complete_with_errors",
        "download_error",
    }
