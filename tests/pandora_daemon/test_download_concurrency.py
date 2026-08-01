"""Tests for download concurrency, retry, and atomic write."""
from __future__ import annotations

from pathlib import Path

import pytest

from pandora_daemon.providers.errors import (
    ProviderAuthenticationError,
    ProviderGalleryNotFoundError,
    ProviderNetworkError,
    ProviderParseError,
    ProviderQuotaError,
)
from pandora_daemon.download import DownloadTask, _atomic_write, _ext_from_image_bytes


class TestDownloadTaskNewFields:
    def test_page_states_default_empty(self):
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=5, output_dir="/tmp/dl",
        )
        assert task.page_states == {}
        assert task.failed_pages == []

    def test_page_states_in_to_dict(self):
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=5, output_dir="/tmp/dl",
        )
        task.page_states = {1: "done", 2: "failed"}
        task.failed_pages = [2]
        d = task.to_dict()
        assert d["page_states"] == {1: "done", 2: "failed"}
        assert d["failed_pages"] == [2]

    def test_page_states_serialization_roundtrip(self):
        """page_states keys survive JSON roundtrip (int keys become str)."""
        import json
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir="/tmp/dl",
        )
        task.page_states = {1: "done", 2: "pending", 3: "failed"}
        d = task.to_dict()
        raw = json.dumps(d)
        loaded = json.loads(raw)
        assert loaded["page_states"]["1"] == "done"


class TestAtomicWrite:
    def test_atomic_write_creates_file(self, tmp_path):
        target = tmp_path / "test.jpg"
        _atomic_write(target, b"image data")
        assert target.exists()
        assert target.read_bytes() == b"image data"

    def test_atomic_write_no_tmp_left(self, tmp_path):
        target = tmp_path / "test.jpg"
        _atomic_write(target, b"data")
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []

    def test_atomic_write_overwrites_existing(self, tmp_path):
        target = tmp_path / "test.jpg"
        target.write_bytes(b"old")
        _atomic_write(target, b"new")
        assert target.read_bytes() == b"new"


from unittest.mock import AsyncMock, MagicMock, call, patch

from pandora_daemon.config import DownloadConfig
from pandora_daemon.download import DownloadManager

class TestImageExtensions:
    @pytest.mark.parametrize(
        ("data", "extension"),
        [
            (b"\xff\xd8\xffimage", ".jpg"),
            (b"\x89PNG\r\n\x1a\nimage", ".png"),
            (b"GIF89aimage", ".gif"),
            (b"RIFF\x00\x00\x00\x00WEBPimage", ".webp"),
            (b"unknown", ".jpg"),
        ],
    )
    def test_ext_from_image_bytes(self, data, extension):
        assert _ext_from_image_bytes(data) == extension



@pytest.fixture
def dl_config(tmp_path):
    return DownloadConfig(path=str(tmp_path / "downloads"), gallery_concurrency=1, page_concurrency=2)


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "downloads.json"


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    detail = MagicMock()
    detail.title = "Test Gallery"
    detail.title_jpn = "Test JPN"
    detail.pages = 3
    detail.gid = "1"
    detail.token = "t"
    detail.url = "https://ex.org/g/1/t/"
    detail.category = "Manga"
    detail.uploader = "user"
    detail.cover_url = "https://ex.org/t/cover.jpg"
    detail.tags = {}
    detail.size = "10 MB"
    detail.posted = "2026-01-01"
    detail.favorite_slot = None
    detail.rating = 4.0
    detail.rating_count = 10
    detail.favorite_count = 5
    detail.torrent_count = 0
    detail.comments = []
    detail.comments_has_more = False
    provider.get_gallery_details.return_value = detail
    return provider


@pytest.fixture
def mock_ws():
    return AsyncMock()


@pytest.fixture
def mock_image_service():
    svc = AsyncMock()
    svc.proxy_image.return_value = b"fake image bytes"
    svc.get_page_image.return_value = b"\xff\xd8\xffpage"
    svc.get_thumbnail.return_value = b"\x89PNG\r\n\x1a\nthumb"
    return svc


class TestDownloadManagerInit:
    def test_constructor_accepts_provider(self, mock_provider, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        assert mgr._provider is mock_provider
        assert mgr._image_service is mock_image_service
        assert not hasattr(mgr, "_api")

    def test_constructor_no_cache_param(self, mock_provider, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        assert not hasattr(mgr, '_cache')



class TestDebounce:
    @pytest.mark.asyncio
    async def test_mark_dirty_creates_save_task(self, mock_provider, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        mgr._mark_dirty()
        assert mgr._save_task is not None
        assert not mgr._save_task.done()
        mgr._save_task.cancel()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_debounce_and_saves(self, mock_provider, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.start()
        await mgr.submit("1", "t")
        mgr._mark_dirty()
        await mgr.shutdown()
        assert state_file.exists()
        assert mgr._save_task is None or mgr._save_task.done() or mgr._save_task.cancelled()


class TestDownloadPages:
    """Tests for _download_pages concurrent download logic."""

    @pytest.mark.asyncio
    async def test_concurrent_download_all_pages_succeed(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir=str(tmp_path / "gallery"),
        )
        pages_dir = Path(task.output_dir) / "pages"
        pages_dir.mkdir(parents=True)

        await mgr._download_pages(task)

        assert task.downloaded_pages == 3
        assert task.failed_pages == []
        assert all(task.page_states[i] == "done" for i in range(1, 4))
        mock_image_service.get_page_image.assert_has_awaits(
            [call("1", "t", page) for page in range(1, 4)],
            any_order=True,
        )

    @pytest.mark.asyncio
    async def test_concurrent_download_skips_existing_files(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir=str(tmp_path / "gallery"),
        )
        pages_dir = Path(task.output_dir) / "pages"
        pages_dir.mkdir(parents=True)
        (pages_dir / "0001.jpg").write_bytes(b"existing")
        (pages_dir / "0002.jpg").write_bytes(b"existing")

        await mgr._download_pages(task)

        assert task.page_states[1] == "done"
        assert task.page_states[2] == "done"
        assert task.page_states[3] == "done"
        assert task.downloaded_pages == 3
        mock_image_service.get_page_image.assert_awaited_once_with("1", "t", 3)

    @pytest.mark.asyncio
    async def test_concurrent_download_ignores_tmp_files(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )
        pages_dir = Path(task.output_dir) / "pages"
        pages_dir.mkdir(parents=True)
        (pages_dir / "0001.jpg.tmp").write_bytes(b"partial")

        await mgr._download_pages(task)

        assert task.page_states[1] == "done"
        assert not (pages_dir / "0001.jpg.tmp").exists()

    @pytest.mark.asyncio
    async def test_concurrent_download_broadcasts_progress(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=2, output_dir=str(tmp_path / "gallery"),
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        await mgr._download_pages(task)

        progress_calls = [
            c[0][0] for c in mock_ws.broadcast.call_args_list
            if c[0][0].get("event") == "download_progress"
        ]
        assert len(progress_calls) == 2

    @pytest.mark.asyncio
    async def test_uses_atomic_write(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        with patch("pandora_daemon.download._atomic_write") as mock_aw:
            await mgr._download_pages(task)
            mock_aw.assert_called_once()


class TestRetryBehavior:
    @pytest.mark.asyncio
    async def test_network_error_retries_and_succeeds(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        dl_config.max_retry = 2
        dl_config.retry_base_delay = 0.01
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        call_count = 0

        async def get_page_image_side_effect(gid, token, page):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderNetworkError("timeout")
            return b"\xff\xd8\xffpage"

        mock_image_service.get_page_image.side_effect = get_page_image_side_effect
        await mgr._download_pages(task)

        assert task.page_states[1] == "done"
        assert task.failed_pages == []
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_network_error_exhausts_retries(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        dl_config.max_retry = 1
        dl_config.retry_base_delay = 0.01
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_image_service.get_page_image.side_effect = ProviderNetworkError("timeout")
        await mgr._download_pages(task)

        assert task.page_states[1] == "failed"
        assert 1 in task.failed_pages

    @pytest.mark.asyncio
    async def test_provider_parse_error_retries(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        dl_config.max_retry = 1
        dl_config.retry_base_delay = 0.01
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_image_service.get_page_image.side_effect = ProviderParseError("unparseable")
        await mgr._download_pages(task)

        assert task.page_states[1] == "failed"
        assert 1 in task.failed_pages
        assert mock_image_service.get_page_image.await_count == 2

    @pytest.mark.asyncio
    async def test_unknown_exception_no_retry(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        dl_config.max_retry = 3
        dl_config.retry_base_delay = 0.01
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_image_service.get_page_image.side_effect = RuntimeError("unexpected")
        await mgr._download_pages(task)

        assert task.page_states[1] == "failed"
        assert mock_image_service.get_page_image.await_count == 1


class TestFatalExceptions:
    @pytest.mark.asyncio
    async def test_auth_error_stops_all_pages(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir=str(tmp_path / "gallery"),
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_image_service.get_page_image.side_effect = ProviderAuthenticationError("Sad Panda")
        with pytest.raises(ProviderAuthenticationError):
            await mgr._download_pages(task)

    @pytest.mark.asyncio
    async def test_image_limit_error_raises(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_image_service.get_page_image.side_effect = ProviderQuotaError("509")
        with pytest.raises(ProviderQuotaError):
            await mgr._download_pages(task)

    @pytest.mark.asyncio
    async def test_gallery_not_found_raises(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_image_service.get_page_image.side_effect = ProviderGalleryNotFoundError("removed")
        with pytest.raises(ProviderGalleryNotFoundError):
            await mgr._download_pages(task)


class TestDownloadGallery:
    @pytest.mark.asyncio
    async def test_successful_download_sets_completed(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir=str(tmp_path / "gallery"),
        )

        await mgr._download_gallery(task)

        assert task.status == "completed"
        assert task.metadata_saved is True
        assert task.cover_downloaded is True
        assert task.downloaded_thumbs == 3
        assert (Path(task.output_dir) / "thumbs" / "0001.png").is_file()
        assert (Path(task.output_dir) / "pages" / "0001.jpg").is_file()
        mock_provider.get_gallery_details.assert_awaited_once_with("1", "t")
        mock_image_service.proxy_image.assert_awaited_once_with(
            mock_provider.get_gallery_details.return_value.cover_url
        )
        mock_image_service.get_thumbnail.assert_has_awaits(
            [call("1", "t", page) for page in range(1, 4)]
        )
        mock_image_service.get_page_image.assert_has_awaits(
            [call("1", "t", page) for page in range(1, 4)],
            any_order=True,
        )

    @pytest.mark.asyncio
    async def test_download_gallery_sets_downloading_before_work(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )

        async def assert_downloading(gid, token, page):
            assert task.status == "downloading"
            return b"\x89PNG\r\n\x1a\nthumb"

        mock_image_service.get_thumbnail.side_effect = assert_downloading
        await mgr._download_gallery(task)

        assert task.status == "completed"

    @pytest.mark.asyncio
    async def test_failed_pages_sets_completed_with_errors(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        dl_config.max_retry = 0
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )

        mock_image_service.get_page_image.side_effect = ProviderNetworkError("fail")
        await mgr._download_gallery(task)

        assert task.status == "completed_with_errors"
        assert 1 in task.failed_pages

    @pytest.mark.asyncio
    async def test_auth_error_sets_failed_and_broadcasts(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )

        mock_image_service.get_page_image.side_effect = ProviderAuthenticationError("Sad Panda")
        await mgr._download_gallery(task)

        assert task.status == "failed"
        events = [c[0][0]["event"] for c in mock_ws.broadcast.call_args_list]
        assert "download_auth_failed" in events

    @pytest.mark.asyncio
    async def test_image_limit_sets_paused(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
        )

        mock_image_service.get_page_image.side_effect = ProviderQuotaError("509")
        await mgr._download_gallery(task)

        assert task.status == "paused"
        events = [c[0][0]["event"] for c in mock_ws.broadcast.call_args_list]
        assert "download_paused" in events

    @pytest.mark.asyncio
    async def test_retry_skips_metadata_and_cover(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        """When pages are retried, skip completed metadata and cover phases."""
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir=str(tmp_path / "gallery"),
            downloaded_pages=2,
            metadata_saved=True,
            cover_downloaded=True,
        )
        task.page_states = {1: "done", 2: "done", 3: "failed"}
        task.failed_pages = [3]
        pages_dir = Path(task.output_dir) / "pages"
        pages_dir.mkdir(parents=True)
        (pages_dir / "0001.jpg").write_bytes(b"ok")
        (pages_dir / "0002.jpg").write_bytes(b"ok")

        await mgr._download_gallery(task)

        assert task.status == "completed"
        mock_provider.get_gallery_details.assert_not_awaited()
        mock_image_service.proxy_image.assert_not_awaited()
        mock_image_service.get_thumbnail.assert_has_awaits(
            [call("1", "t", page) for page in range(1, 4)]
        )
        mock_image_service.get_page_image.assert_awaited_once_with("1", "t", 3)


class TestResumeRetry:
    @pytest.mark.asyncio
    async def test_resume_paused_task(self, mock_provider, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")
        task = mgr._tasks["1"]
        task.status = "paused"

        result = await mgr.resume("1")
        assert result is True
        assert task.status == "queued"

    @pytest.mark.asyncio
    async def test_resume_non_paused_returns_false(self, mock_provider, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")

        result = await mgr.resume("1")
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_nonexistent_returns_false(self, mock_provider, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        result = await mgr.resume("999")
        assert result is False

    @pytest.mark.asyncio
    async def test_retry_failed_completed_with_errors(self, mock_provider, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")
        task = mgr._tasks["1"]
        task.status = "completed_with_errors"
        task.failed_pages = [3, 5]
        task.downloaded_pages = 8

        result = await mgr.retry_failed("1")
        assert result is True
        assert task.status == "queued"

    @pytest.mark.asyncio
    async def test_retry_failed_wrong_status_returns_false(self, mock_provider, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")

        result = await mgr.retry_failed("1")
        assert result is False

    @pytest.mark.asyncio
    async def test_retry_reconciles_missing_pages_when_failed_list_is_stale(
        self, mock_provider, mock_ws, mock_image_service, dl_config, state_file
    ):
        mgr = DownloadManager(mock_provider, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")
        task = mgr._tasks["1"]
        task.status = "completed_with_errors"
        task.failed_pages = []

        result = await mgr.retry_failed("1")
        assert result is True
        assert task.status == "queued"
        assert task.page_states == {1: "pending", 2: "pending", 3: "pending"}
