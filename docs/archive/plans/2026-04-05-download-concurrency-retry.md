# P1: 下载并发+重试 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 download.py 从串行下载改为并发下载，加入即时重试、原子写入、异常分类处理和 debounce 状态保存。

**Architecture:** 在现有 DownloadManager 上原地改造。页面下载用 `asyncio.gather` + `Semaphore(page_concurrency)` 并发，单页失败时就地指数退避重试。用临时文件+原子重命名保证断点续传安全。不可恢复异常（Auth/ImageLimit/NotFound）通过 `asyncio.Event` 中止信号停止所有并发页面。

**Tech Stack:** Python 3.12, asyncio, aiofiles (已有), PIL (已有), FastAPI

**Spec:** `docs/superpowers/specs/2026-04-05-download-concurrency-retry-design.md`

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `pandora_daemon/config.py` | 修改 | `DownloadConfig` 拆分 concurrency 为 gallery/page，新增 max_retry/retry_base_delay |
| `pandora_daemon/download.py` | 重构 | 并发下载、即时重试、原子写入、debounce 保存、image_service 集成 |
| `pandora_daemon/routes/downloads.py` | 修改 | 新增 retry/resume/pages 三个端点 |
| `pandora_daemon/app.py` | 修改 | DownloadManager 构造参数变更 |
| `tests/pandora_daemon/test_config.py` | 修改 | 新增配置字段测试 |
| `tests/pandora_daemon/test_download.py` | 修改 | 更新 fixture 适配新签名 |
| `tests/pandora_daemon/test_download_concurrency.py` | 新建 | 并发下载、重试、异常处理、debounce 测试 |
| `tests/pandora_daemon/test_routes_downloads.py` | 修改 | 新增 3 个端点测试 |

---

### Task 1: DownloadConfig 拆分 + 向后兼容

**Files:**
- Modify: `pandora_daemon/config.py:34-39` (DownloadConfig)
- Modify: `pandora_daemon/config.py:73-91` (to_public_dict)
- Modify: `pandora_daemon/config.py:93-101` (_to_dict)
- Modify: `pandora_daemon/config.py:131-136` (load_config download section)
- Test: `tests/pandora_daemon/test_config.py`

- [ ] **Step 1: Write failing tests for new config fields**

在 `tests/pandora_daemon/test_config.py` 的 `TestDefaultConfig` 类中替换 `test_default_download_config`，并新增向后兼容测试：

```python
# 替换 TestDefaultConfig.test_default_download_config (line 32)
def test_default_download_config(self):
    cfg = DownloadConfig()
    assert cfg.path == "~/Downloads/pandora"
    assert cfg.gallery_concurrency == 2
    assert cfg.page_concurrency == 4
    assert cfg.max_retry == 3
    assert cfg.retry_base_delay == 2.0
```

在 `TestLoadConfig` 类末尾新增：

```python
def test_load_config_backward_compat_concurrency(self, tmp_path):
    """Old 'concurrency' field maps to gallery_concurrency."""
    config_path = tmp_path / "config.toml"
    data = {"download": {"concurrency": 5, "path": "~/dl"}}
    config_path.write_bytes(tomli_w.dumps(data).encode())
    cfg = load_config(config_path)
    assert cfg.download.gallery_concurrency == 5
    assert cfg.download.page_concurrency == 4  # default

def test_load_config_new_fields(self, tmp_path):
    """New fields load correctly."""
    config_path = tmp_path / "config.toml"
    data = {"download": {
        "gallery_concurrency": 1, "page_concurrency": 8,
        "max_retry": 5, "retry_base_delay": 1.0,
    }}
    config_path.write_bytes(tomli_w.dumps(data).encode())
    cfg = load_config(config_path)
    assert cfg.download.gallery_concurrency == 1
    assert cfg.download.page_concurrency == 8
    assert cfg.download.max_retry == 5
    assert cfg.download.retry_base_delay == 1.0
```

在 `TestToPublicDict` 类末尾新增：

```python
def test_to_public_dict_contains_new_download_fields(self):
    cfg = PandoraConfig()
    d = cfg.to_public_dict()
    dl = d["download"]
    assert "gallery_concurrency" in dl
    assert "page_concurrency" in dl
    assert "max_retry" in dl
    assert "retry_base_delay" in dl
    assert "concurrency" not in dl
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_config.py -v -k "download_config or backward_compat or new_fields or new_download_fields"`
Expected: FAIL — `DownloadConfig` has no `gallery_concurrency` attribute

- [ ] **Step 3: Implement DownloadConfig changes**

修改 `pandora_daemon/config.py`:

1. `DownloadConfig` (line 34-39) 替换为：

```python
@dataclass
class DownloadConfig:
    """Download manager settings."""

    path: str = "~/Downloads/pandora"
    gallery_concurrency: int = 2
    page_concurrency: int = 4
    max_retry: int = 3
    retry_base_delay: float = 2.0
```

2. `to_public_dict` (line 73-91) 中 download 部分替换为：

```python
"download": {
    "path": self.download.path,
    "gallery_concurrency": self.download.gallery_concurrency,
    "page_concurrency": self.download.page_concurrency,
    "max_retry": self.download.max_retry,
    "retry_base_delay": self.download.retry_base_delay,
},
```

3. `load_config` (line 131-136) download 部分替换为：

```python
dl_data = data.get("download", {})
gallery_concurrency = dl_data.get("gallery_concurrency",
                                   dl_data.get("concurrency", 2))
download = DownloadConfig(
    path=dl_data.get("path", "~/Downloads/pandora"),
    gallery_concurrency=gallery_concurrency,
    page_concurrency=dl_data.get("page_concurrency", 4),
    max_retry=dl_data.get("max_retry", 3),
    retry_base_delay=dl_data.get("retry_base_delay", 2.0),
)
```

- [ ] **Step 4: Fix existing tests that reference old `concurrency` field**

`tests/pandora_daemon/test_download.py` line 20 的 fixture：

```python
# 旧
return DownloadConfig(path=str(tmp_path / "downloads"), concurrency=2)
# 新
return DownloadConfig(path=str(tmp_path / "downloads"), gallery_concurrency=2)
```

`tests/pandora_daemon/test_config.py` 中所有引用 `concurrency` 的现有测试也需要更新为 `gallery_concurrency`。

- [ ] **Step 5: Run all tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_config.py tests/pandora_daemon/test_download.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/config.py tests/pandora_daemon/test_config.py tests/pandora_daemon/test_download.py
git commit -m "feat(config): split concurrency into gallery/page, add retry params"
```

---

### Task 2: DownloadTask 新增字段 + _atomic_write 辅助函数

**Files:**
- Modify: `pandora_daemon/download.py:26-50` (DownloadTask)
- Modify: `pandora_daemon/download.py` (新增 `_atomic_write`)
- Test: `tests/pandora_daemon/test_download_concurrency.py` (新建)

- [ ] **Step 1: Write failing tests**

新建 `tests/pandora_daemon/test_download_concurrency.py`：

```python
"""Tests for download concurrency, retry, and atomic write."""
from __future__ import annotations

from pathlib import Path

import pytest

from pandora_daemon.download import DownloadTask, _atomic_write


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
        # JSON converts int keys to str — this is expected
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_download_concurrency.py -v`
Expected: FAIL — `_atomic_write` not found, `page_states` not in DownloadTask

- [ ] **Step 3: Add page_states and failed_pages to DownloadTask**

在 `pandora_daemon/download.py` 的 `DownloadTask` dataclass 中，在 `thumb_sprites` 字段后追加：

```python
    page_states: dict[int, str] = field(default_factory=dict)
    failed_pages: list[int] = field(default_factory=list)
```

- [ ] **Step 4: Add _atomic_write function**

在 `pandora_daemon/download.py` 的 `_sanitize_filename` 函数后追加：

```python
def _atomic_write(path: Path, data: bytes) -> None:
    """Write via temp file + rename to prevent partial writes on crash."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(data)
    tmp_path.rename(path)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_download_concurrency.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/download.py tests/pandora_daemon/test_download_concurrency.py
git commit -m "feat(download): add page_states, failed_pages fields and _atomic_write"
```

---

### Task 3: DownloadManager 签名变更 + image_service 集成 + debounce

**Files:**
- Modify: `pandora_daemon/download.py:53-67` (构造函数)
- Modify: `pandora_daemon/download.py:68-77` (start)
- Modify: `pandora_daemon/download.py:79-84` (shutdown)
- Modify: `pandora_daemon/download.py:348-358` (_fetch_image)
- Modify: `pandora_daemon/app.py:46` (构造调用)
- Test: `tests/pandora_daemon/test_download_concurrency.py`
- Modify: `tests/pandora_daemon/test_download.py` (fixture 适配)

- [ ] **Step 1: Write failing tests for debounce and image_service**

在 `tests/pandora_daemon/test_download_concurrency.py` 追加 fixtures 和测试：

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from pandora_daemon.config import DownloadConfig
from pandora_daemon.download import DownloadManager


@pytest.fixture
def dl_config(tmp_path):
    return DownloadConfig(path=str(tmp_path / "downloads"), gallery_concurrency=1, page_concurrency=2)


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "downloads.json"


@pytest.fixture
def mock_api():
    api = AsyncMock()
    detail = MagicMock()
    detail.title = "Test Gallery"
    detail.title_jpn = "Test JPN"
    detail.pages = 3
    detail.preview_pages = 1
    detail.preview_urls = ["https://ex.org/s/a/1-1", "https://ex.org/s/b/1-2", "https://ex.org/s/c/1-3"]
    detail.thumb_urls = ["https://ex.org/t/1.jpg", "https://ex.org/t/2.jpg", "https://ex.org/t/3.jpg"]
    detail.thumb_sprites = []
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
    api.get_gallery_details.return_value = detail
    return api


@pytest.fixture
def mock_ws():
    return AsyncMock()


@pytest.fixture
def mock_image_service():
    svc = AsyncMock()
    svc.proxy_image.return_value = b"fake image bytes"
    return svc


class TestDownloadManagerInit:
    def test_constructor_accepts_image_service(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        assert mgr._image_service is mock_image_service

    def test_constructor_no_cache_param(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        """DownloadManager no longer accepts cache as a parameter."""
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        assert not hasattr(mgr, '_cache')


class TestFetchImage:
    @pytest.mark.asyncio
    async def test_fetch_image_uses_image_service(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        result = await mgr._fetch_image("https://example.com/img.jpg")
        mock_image_service.proxy_image.assert_awaited_once_with("https://example.com/img.jpg")
        assert result == b"fake image bytes"


class TestDebounce:
    @pytest.mark.asyncio
    async def test_mark_dirty_creates_save_task(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        mgr._mark_dirty()
        assert mgr._save_task is not None
        assert not mgr._save_task.done()
        mgr._save_task.cancel()

    @pytest.mark.asyncio
    async def test_debounced_save_writes_after_delay(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")
        mgr._mark_dirty()
        # State file already exists from submit's immediate save
        state_file.unlink()
        assert not state_file.exists()
        # Wait for debounce (5s) — use shorter sleep in test by patching
        await asyncio.sleep(6)
        assert state_file.exists()
        if mgr._save_task and not mgr._save_task.done():
            mgr._save_task.cancel()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_debounce_and_saves(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.start()
        await mgr.submit("1", "t")
        mgr._mark_dirty()
        await mgr.shutdown()
        assert state_file.exists()
        assert mgr._save_task is None or mgr._save_task.done() or mgr._save_task.cancelled()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_download_concurrency.py::TestDownloadManagerInit -v`
Expected: FAIL — DownloadManager signature mismatch

- [ ] **Step 3: Modify DownloadManager constructor**

替换 `pandora_daemon/download.py` line 56-66 的 `__init__`：

```python
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
```

- [ ] **Step 4: Replace _fetch_image**

替换 `pandora_daemon/download.py` 的 `_fetch_image` 方法 (line 348-358)：

```python
    async def _fetch_image(self, url: str) -> bytes:
        """Fetch image bytes via ImageService (cache-first)."""
        return await self._image_service.proxy_image(url)
```

- [ ] **Step 5: Add debounce methods**

在 `_save_state` 方法前追加：

```python
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
```

- [ ] **Step 6: Update start() to use gallery_concurrency**

替换 `start()` 中 `for _ in range(self._config.concurrency):` 为：

```python
        for _ in range(self._config.gallery_concurrency):
```

- [ ] **Step 7: Update shutdown() to cancel debounce**

替换 `shutdown()` 方法：

```python
    async def shutdown(self) -> None:
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
        self._save_state()
```

- [ ] **Step 8: Update app.py constructor call**

替换 `pandora_daemon/app.py` line 46：

```python
    # 旧
    downloads = DownloadManager(api=api, config=config.download, ws=ws, cache=cache, state_file=state_file)
    # 新
    downloads = DownloadManager(api=api, config=config.download, ws=ws, image_service=image_service, state_file=state_file)
```

- [ ] **Step 9: Update existing test fixtures**

`tests/pandora_daemon/test_download.py` — 所有使用 `DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)` 的地方改为 `DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)`。

将 `mock_cache` fixture 替换为：

```python
@pytest.fixture
def mock_image_service():
    svc = AsyncMock()
    svc.proxy_image.return_value = b"fake image bytes"
    return svc
```

更新所有测试函数签名，将 `mock_cache` 参数替换为 `mock_image_service`。

- [ ] **Step 10: Run all tests**

Run: `uv run pytest tests/pandora_daemon/test_download.py tests/pandora_daemon/test_download_concurrency.py -v`
Expected: ALL PASS

- [ ] **Step 11: Commit**

```bash
git add pandora_daemon/download.py pandora_daemon/app.py tests/pandora_daemon/test_download.py tests/pandora_daemon/test_download_concurrency.py
git commit -m "refactor(download): replace cache with image_service, add debounce save"
```

---

### Task 4: 并发页面下载 + 即时重试 (_download_pages)

**Files:**
- Modify: `pandora_daemon/download.py` (新增 `_download_pages` 方法，替换 `_download_gallery` 中的串行页面循环)
- Test: `tests/pandora_daemon/test_download_concurrency.py`

这是最核心的改动。`_download_pages` 用 `asyncio.gather` + `Semaphore` 并发下载，每页失败时就地指数退避重试。

- [ ] **Step 1: Write failing tests for concurrent download**

在 `tests/pandora_daemon/test_download_concurrency.py` 追加：

```python
from exhentai_api.exceptions import (
    AuthenticationError, ImageLimitError, GalleryNotFoundError,
    NetworkError, ParseError,
)


class TestDownloadPages:
    """Tests for _download_pages concurrent download logic."""

    @pytest.mark.asyncio
    async def test_concurrent_download_all_pages_succeed(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1", "https://ex.org/s/b/1-2", "https://ex.org/s/c/1-3"],
        )
        pages_dir = Path(task.output_dir) / "pages"
        pages_dir.mkdir(parents=True)

        # Mock: get_html returns HTML, parse_image_viewer extracts URL
        mock_api.client.get_html = AsyncMock(return_value="<html><img id='img' src='https://ex.org/img/1.jpg'></html>")
        with patch("pandora_daemon.download.parse_image_viewer", return_value=("https://ex.org/img/1.jpg", None)):
            await mgr._download_pages(task)

        assert task.downloaded_pages == 3
        assert task.failed_pages == []
        assert all(task.page_states[i] == "done" for i in range(1, 4))

    @pytest.mark.asyncio
    async def test_concurrent_download_skips_existing_files(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1", "https://ex.org/s/b/1-2", "https://ex.org/s/c/1-3"],
        )
        pages_dir = Path(task.output_dir) / "pages"
        pages_dir.mkdir(parents=True)
        # Pre-create page 1 and 2
        (pages_dir / "0001.jpg").write_bytes(b"existing")
        (pages_dir / "0002.jpg").write_bytes(b"existing")

        mock_api.client.get_html = AsyncMock(return_value="<html></html>")
        with patch("pandora_daemon.download.parse_image_viewer", return_value=("https://ex.org/img/3.jpg", None)):
            await mgr._download_pages(task)

        # Only page 3 should have been downloaded
        assert task.page_states[1] == "done"
        assert task.page_states[2] == "done"
        assert task.page_states[3] == "done"
        # get_html called only once (for page 3)
        assert mock_api.client.get_html.await_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_download_ignores_tmp_files(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        """Leftover .tmp files should not count as completed."""
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
        )
        pages_dir = Path(task.output_dir) / "pages"
        pages_dir.mkdir(parents=True)
        # Create a .tmp file — should be cleaned up and re-downloaded
        (pages_dir / "0001.jpg.tmp").write_bytes(b"partial")

        mock_api.client.get_html = AsyncMock(return_value="<html></html>")
        with patch("pandora_daemon.download.parse_image_viewer", return_value=("https://ex.org/img/1.jpg", None)):
            await mgr._download_pages(task)

        assert task.page_states[1] == "done"
        assert not (pages_dir / "0001.jpg.tmp").exists()

    @pytest.mark.asyncio
    async def test_concurrent_download_broadcasts_progress(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=2, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1", "https://ex.org/s/b/1-2"],
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_api.client.get_html = AsyncMock(return_value="<html></html>")
        with patch("pandora_daemon.download.parse_image_viewer", return_value=("https://ex.org/img/1.jpg", None)):
            await mgr._download_pages(task)

        # Should have broadcast progress for each page
        progress_calls = [
            c[0][0] for c in mock_ws.broadcast.call_args_list
            if c[0][0].get("event") == "download_progress"
        ]
        assert len(progress_calls) == 2

    @pytest.mark.asyncio
    async def test_uses_atomic_write(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_api.client.get_html = AsyncMock(return_value="<html></html>")
        with patch("pandora_daemon.download.parse_image_viewer", return_value=("https://ex.org/img/1.jpg", None)):
            with patch("pandora_daemon.download._atomic_write") as mock_aw:
                await mgr._download_pages(task)
                mock_aw.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_download_concurrency.py::TestDownloadPages -v`
Expected: FAIL — `_download_pages` method not found

- [ ] **Step 3: Implement _download_pages**

在 `pandora_daemon/download.py` 中，在 `_download_gallery` 方法前新增：

```python
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
```

新增 import（文件顶部）：

```python
from exhentai_api.exceptions import (
    AuthenticationError, ImageLimitError, GalleryNotFoundError,
    NetworkError, ParseError,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_download_concurrency.py::TestDownloadPages -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/download.py tests/pandora_daemon/test_download_concurrency.py
git commit -m "feat(download): concurrent page download with semaphore and inline retry"
```

---

### Task 5: 异常分类重试测试

**Files:**
- Test: `tests/pandora_daemon/test_download_concurrency.py`

这些测试验证 `_download_pages` 对不同异常类型的处理行为。实现已在 Task 4 完成，这里补充异常路径测试。

- [ ] **Step 1: Write exception handling tests**

在 `tests/pandora_daemon/test_download_concurrency.py` 追加：

```python
class TestRetryBehavior:
    """Tests for inline retry on NetworkError/ParseError."""

    @pytest.mark.asyncio
    async def test_network_error_retries_and_succeeds(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        """NetworkError on first attempt, succeeds on second."""
        dl_config.max_retry = 2
        dl_config.retry_base_delay = 0.01  # fast for tests
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        call_count = 0
        async def get_html_side_effect(url):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NetworkError("timeout")
            return "<html></html>"

        mock_api.client.get_html = AsyncMock(side_effect=get_html_side_effect)
        with patch("pandora_daemon.download.parse_image_viewer", return_value=("https://ex.org/img/1.jpg", None)):
            await mgr._download_pages(task)

        assert task.page_states[1] == "done"
        assert task.failed_pages == []
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_network_error_exhausts_retries(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        """NetworkError on all attempts → page marked failed."""
        dl_config.max_retry = 1
        dl_config.retry_base_delay = 0.01
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_api.client.get_html = AsyncMock(side_effect=NetworkError("timeout"))
        await mgr._download_pages(task)

        assert task.page_states[1] == "failed"
        assert 1 in task.failed_pages

    @pytest.mark.asyncio
    async def test_parse_error_retries(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        dl_config.max_retry = 1
        dl_config.retry_base_delay = 0.01
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_api.client.get_html = AsyncMock(return_value="<html></html>")
        # parse_image_viewer returns None → raises ParseError internally
        with patch("pandora_daemon.download.parse_image_viewer", return_value=(None, None)):
            await mgr._download_pages(task)

        assert task.page_states[1] == "failed"
        assert 1 in task.failed_pages

    @pytest.mark.asyncio
    async def test_unknown_exception_no_retry(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        dl_config.max_retry = 3
        dl_config.retry_base_delay = 0.01
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_api.client.get_html = AsyncMock(side_effect=RuntimeError("unexpected"))
        await mgr._download_pages(task)

        assert task.page_states[1] == "failed"
        # Should only have been called once (no retry for unknown exceptions)
        assert mock_api.client.get_html.await_count == 1


class TestFatalExceptions:
    """Tests for exceptions that stop all concurrent downloads."""

    @pytest.mark.asyncio
    async def test_auth_error_stops_all_pages(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1", "https://ex.org/s/b/1-2", "https://ex.org/s/c/1-3"],
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_api.client.get_html = AsyncMock(side_effect=AuthenticationError("Sad Panda"))
        with pytest.raises(AuthenticationError):
            await mgr._download_pages(task)

    @pytest.mark.asyncio
    async def test_image_limit_error_raises(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_api.client.get_html = AsyncMock(side_effect=ImageLimitError("509"))
        with pytest.raises(ImageLimitError):
            await mgr._download_pages(task)

    @pytest.mark.asyncio
    async def test_gallery_not_found_raises(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
        )
        Path(task.output_dir, "pages").mkdir(parents=True)

        mock_api.client.get_html = AsyncMock(side_effect=GalleryNotFoundError("removed"))
        with pytest.raises(GalleryNotFoundError):
            await mgr._download_pages(task)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_download_concurrency.py::TestRetryBehavior tests/pandora_daemon/test_download_concurrency.py::TestFatalExceptions -v`
Expected: ALL PASS (implementation already done in Task 4)

- [ ] **Step 3: Commit**

```bash
git add tests/pandora_daemon/test_download_concurrency.py
git commit -m "test(download): add retry and fatal exception tests for _download_pages"
```

---

### Task 6: _download_gallery 改造 + _worker 异常处理

**Files:**
- Modify: `pandora_daemon/download.py:170-322` (_worker + _download_gallery)
- Test: `tests/pandora_daemon/test_download_concurrency.py`

改造 `_download_gallery` 使用新的 `_download_pages`，并根据异常类型设置任务状态。改造 `_worker` 处理新状态。所有 `write_bytes` 调用改为 `_atomic_write`。

- [ ] **Step 1: Write failing tests for _download_gallery**

在 `tests/pandora_daemon/test_download_concurrency.py` 追加：

```python
class TestDownloadGallery:
    @pytest.mark.asyncio
    async def test_successful_download_sets_completed(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
            thumb_urls=["https://ex.org/t/1.jpg"],
        )

        mock_api.client.get_html = AsyncMock(return_value="<html></html>")
        with patch("pandora_daemon.download.parse_image_viewer", return_value=("https://ex.org/img/1.jpg", None)):
            await mgr._download_gallery(task)

        assert task.status == "completed"
        assert task.metadata_saved is True
        assert task.cover_downloaded is True

    @pytest.mark.asyncio
    async def test_failed_pages_sets_completed_with_errors(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        dl_config.max_retry = 0
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
            thumb_urls=[],
        )

        mock_api.client.get_html = AsyncMock(side_effect=NetworkError("fail"))
        await mgr._download_gallery(task)

        assert task.status == "completed_with_errors"
        assert 1 in task.failed_pages

    @pytest.mark.asyncio
    async def test_auth_error_sets_failed_and_pauses_all(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
            thumb_urls=[],
        )

        mock_api.client.get_html = AsyncMock(side_effect=AuthenticationError("Sad Panda"))
        await mgr._download_gallery(task)

        assert task.status == "failed"
        # Check broadcast includes auth_failed event
        events = [c[0][0]["event"] for c in mock_ws.broadcast.call_args_list]
        assert "download_auth_failed" in events

    @pytest.mark.asyncio
    async def test_image_limit_sets_paused(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=1, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1"],
            thumb_urls=[],
        )

        mock_api.client.get_html = AsyncMock(side_effect=ImageLimitError("509"))
        await mgr._download_gallery(task)

        assert task.status == "paused"
        events = [c[0][0]["event"] for c in mock_ws.broadcast.call_args_list]
        assert "download_paused" in events

    @pytest.mark.asyncio
    async def test_is_retry_skips_metadata_cover_thumbs(
        self, mock_api, mock_ws, mock_image_service, dl_config, state_file, tmp_path
    ):
        """When task has failed_pages and downloaded_pages > 0, skip early phases."""
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir=str(tmp_path / "gallery"),
            preview_urls=["https://ex.org/s/a/1-1", "https://ex.org/s/b/1-2", "https://ex.org/s/c/1-3"],
            thumb_urls=[],
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

        mock_api.client.get_html = AsyncMock(return_value="<html></html>")
        with patch("pandora_daemon.download.parse_image_viewer", return_value=("https://ex.org/img/3.jpg", None)):
            await mgr._download_gallery(task)

        assert task.status == "completed"
        # get_gallery_details should NOT have been called (is_retry mode)
        mock_api.get_gallery_details.assert_not_awaited()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_download_concurrency.py::TestDownloadGallery -v`
Expected: FAIL — current _download_gallery doesn't handle exceptions this way

- [ ] **Step 3: Rewrite _download_gallery**

替换 `pandora_daemon/download.py` 的 `_download_gallery` 方法 (line 207-322)。新增 `_pause_all_tasks` 方法。

新的 `_download_gallery`：

```python
    async def _download_gallery(self, task: DownloadTask) -> None:
        """Download complete gallery: metadata, cover, thumbs, pages."""
        is_retry = bool(task.failed_pages) and task.downloaded_pages > 0
        task.status = "downloading"
        output_dir = Path(task.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            if not is_retry:
                # Fetch gallery detail for metadata and cover
                detail = await self._api.get_gallery_details(task.gid, task.token)

                # Phase 1: metadata
                if not task.metadata_saved:
                    self._write_metadata(detail, str(output_dir))
                    task.metadata_saved = True
                    self._save_state()

                # Phase 2: cover
                if not task.cover_downloaded:
                    if detail.cover_url:
                        try:
                            cover_data = await self._fetch_image(detail.cover_url)
                            ext = _ext_from_url(detail.cover_url)
                            _atomic_write(output_dir / f"cover{ext}", cover_data)
                        except Exception:
                            pass
                    task.cover_downloaded = True
                    await self._ws.broadcast({"event": "download_progress", "gid": task.gid, "phase": "cover"})
                    self._save_state()

                # Phase 3: thumbs
                thumbs_dir = output_dir / "thumbs"
                thumbs_dir.mkdir(exist_ok=True)
                sprite_cache: dict[str, bytes] = {}
                for idx in range(len(task.thumb_sprites or task.thumb_urls)):
                    if task.gid in self._cancelled:
                        task.status = "cancelled"
                        self._save_state()
                        return
                    page_num = idx + 1
                    existing = [f for f in thumbs_dir.glob(f"{page_num:04d}.*")
                                if not f.name.endswith(".tmp")]
                    if existing:
                        task.downloaded_thumbs = page_num
                        continue
                    try:
                        sprite = task.thumb_sprites[idx] if task.thumb_sprites else None
                        if sprite and sprite.get("width", 0) > 0:
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
                                _atomic_write(thumbs_dir / f"{page_num:04d}{ext}", data)
                        elif idx < len(task.thumb_urls):
                            thumb_url = task.thumb_urls[idx]
                            data = await self._fetch_image(thumb_url)
                            ext = _ext_from_url(thumb_url)
                            _atomic_write(thumbs_dir / f"{page_num:04d}{ext}", data)
                    except Exception:
                        pass
                    task.downloaded_thumbs = page_num
                    await self._ws.broadcast({
                        "event": "download_progress", "gid": task.gid,
                        "phase": "thumbs", "page": page_num, "total": task.total_pages,
                    })
                    self._mark_dirty()

            # Phase 4: pages — concurrent download with inline retry
            await self._download_pages(task)

            # Final status
            if task.failed_pages:
                task.status = "completed_with_errors"
                task.error = f"{len(task.failed_pages)} pages failed: {task.failed_pages[:10]}"
            else:
                task.status = "completed"

            await self._ws.broadcast(
                {"event": "download_complete", "gid": task.gid, "path": task.output_dir}
            )

        except AuthenticationError as e:
            task.status = "failed"
            task.error = str(e)
            await self._ws.broadcast(
                {"event": "download_auth_failed", "gid": task.gid, "error": str(e)}
            )
            await self._pause_all_tasks()

        except ImageLimitError as e:
            task.status = "paused"
            task.error = str(e)
            await self._ws.broadcast(
                {"event": "download_paused", "gid": task.gid, "reason": "image_limit"}
            )

        except GalleryNotFoundError as e:
            task.status = "failed"
            task.error = str(e)
            await self._ws.broadcast(
                {"event": "download_error", "gid": task.gid, "error": str(e)}
            )

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            await self._ws.broadcast(
                {"event": "download_error", "gid": task.gid, "error": str(e)}
            )

        self._save_state()
```

新增 `_pause_all_tasks` 方法（在 `_download_gallery` 后）：

```python
    async def _pause_all_tasks(self) -> None:
        """Pause all queued/downloading tasks on AuthenticationError."""
        for t in self._tasks.values():
            if t.status in ("queued", "downloading"):
                t.status = "paused"
                await self._ws.broadcast(
                    {"event": "download_paused", "gid": t.gid, "reason": "auth_failed"}
                )
        self._save_state()
```

- [ ] **Step 4: Update _worker to remove redundant exception handling**

替换 `_worker` 方法 (line 170-205)：

```python
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

            try:
                await self._download_gallery(task)
            except asyncio.CancelledError:
                if task.status == "downloading":
                    task.status = "queued"
                    self._save_state()
                self._queue.task_done()
                return

            self._queue.task_done()
```

注意：`_download_gallery` 现在内部处理所有异常并设置 task.status，所以 worker 不再需要 `except Exception` 分支。

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/pandora_daemon/test_download_concurrency.py tests/pandora_daemon/test_download.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/download.py tests/pandora_daemon/test_download_concurrency.py
git commit -m "feat(download): rewrite _download_gallery with exception-driven status and _pause_all_tasks"
```

---

### Task 7: resume + retry_failed 方法

**Files:**
- Modify: `pandora_daemon/download.py` (新增 `resume`, `retry_failed` 方法)
- Test: `tests/pandora_daemon/test_download_concurrency.py`

- [ ] **Step 1: Write failing tests**

在 `tests/pandora_daemon/test_download_concurrency.py` 追加：

```python
class TestResumeRetry:
    @pytest.mark.asyncio
    async def test_resume_paused_task(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")
        task = mgr._tasks["1"]
        task.status = "paused"

        result = await mgr.resume("1")
        assert result is True
        assert task.status == "queued"

    @pytest.mark.asyncio
    async def test_resume_non_paused_returns_false(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")

        result = await mgr.resume("1")
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_nonexistent_returns_false(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        result = await mgr.resume("999")
        assert result is False

    @pytest.mark.asyncio
    async def test_retry_failed_completed_with_errors(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")
        task = mgr._tasks["1"]
        task.status = "completed_with_errors"
        task.failed_pages = [3, 5]
        task.downloaded_pages = 8

        result = await mgr.retry_failed("1")
        assert result is True
        assert task.status == "queued"

    @pytest.mark.asyncio
    async def test_retry_failed_wrong_status_returns_false(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")

        result = await mgr.retry_failed("1")
        assert result is False

    @pytest.mark.asyncio
    async def test_retry_failed_no_failed_pages_returns_false(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.submit("1", "t")
        task = mgr._tasks["1"]
        task.status = "completed_with_errors"
        task.failed_pages = []

        result = await mgr.retry_failed("1")
        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_download_concurrency.py::TestResumeRetry -v`
Expected: FAIL — `resume` and `retry_failed` methods not found

- [ ] **Step 3: Implement resume and retry_failed**

在 `pandora_daemon/download.py` 的 `cancel` 方法后追加：

```python
    async def resume(self, gid: str) -> bool:
        """Resume a paused task."""
        task = self._tasks.get(gid)
        if task is None or task.status != "paused":
            return False
        task.status = "queued"
        await self._queue.put(gid)
        self._save_state()
        return True

    async def retry_failed(self, gid: str) -> bool:
        """Retry failed pages of a completed_with_errors task."""
        task = self._tasks.get(gid)
        if task is None or task.status != "completed_with_errors":
            return False
        if not task.failed_pages:
            return False
        task.status = "queued"
        await self._queue.put(gid)
        self._save_state()
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_download_concurrency.py::TestResumeRetry -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/download.py tests/pandora_daemon/test_download_concurrency.py
git commit -m "feat(download): add resume and retry_failed methods"
```

---

### Task 8: REST 端点 (retry / resume / pages)

**Files:**
- Modify: `pandora_daemon/routes/downloads.py`
- Test: `tests/pandora_daemon/test_routes_downloads.py`

- [ ] **Step 1: Write failing tests**

在 `tests/pandora_daemon/test_routes_downloads.py` 追加：

```python
class TestRetryDownload:
    def test_retry_completed_with_errors_returns_200(self):
        mock_downloads = MagicMock()
        mock_downloads.retry_failed = AsyncMock(return_value=True)
        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.post("/api/downloads/123/retry")
        assert response.status_code == 200
        assert response.json() == {"success": True}
        mock_downloads.retry_failed.assert_called_once_with("123")

    def test_retry_not_found_returns_404(self):
        mock_downloads = MagicMock()
        mock_downloads.retry_failed = AsyncMock(return_value=False)
        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.post("/api/downloads/999/retry")
        assert response.status_code == 404


class TestResumeDownload:
    def test_resume_paused_returns_200(self):
        mock_downloads = MagicMock()
        mock_downloads.resume = AsyncMock(return_value=True)
        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.post("/api/downloads/123/resume")
        assert response.status_code == 200
        assert response.json() == {"success": True}
        mock_downloads.resume.assert_called_once_with("123")

    def test_resume_not_paused_returns_404(self):
        mock_downloads = MagicMock()
        mock_downloads.resume = AsyncMock(return_value=False)
        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.post("/api/downloads/123/resume")
        assert response.status_code == 404


class TestGetPageStatus:
    def test_get_pages_returns_200(self):
        mock_downloads = MagicMock()
        task = _make_task(gid="123", total_pages=10, downloaded_pages=5)
        task.page_states = {1: "done", 2: "done", 3: "failed"}
        task.failed_pages = [3]
        mock_downloads.status = MagicMock(return_value=[task])
        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.get("/api/downloads/123/pages")
        assert response.status_code == 200
        data = response.json()
        assert data["gid"] == "123"
        assert data["total_pages"] == 10
        assert data["downloaded_pages"] == 5
        assert data["failed_pages"] == [3]
        assert "page_states" in data

    def test_get_pages_not_found_returns_404(self):
        mock_downloads = MagicMock()
        mock_downloads.status = MagicMock(return_value=[])
        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.get("/api/downloads/999/pages")
        assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_downloads.py::TestRetryDownload tests/pandora_daemon/test_routes_downloads.py::TestResumeDownload tests/pandora_daemon/test_routes_downloads.py::TestGetPageStatus -v`
Expected: FAIL — endpoints don't exist

- [ ] **Step 3: Add endpoints to routes/downloads.py**

在 `pandora_daemon/routes/downloads.py` 的 `cancel_download` 函数后追加：

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_routes_downloads.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/routes/downloads.py tests/pandora_daemon/test_routes_downloads.py
git commit -m "feat(routes): add retry, resume, and page status endpoints"
```

---

### Task 9: 全量测试 + 清理

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 2: Fix any remaining issues**

如果有测试失败，根据错误信息修复。常见问题：
- 旧测试中仍引用 `concurrency` 而非 `gallery_concurrency`
- 旧测试中仍传 `mock_cache` 而非 `mock_image_service`
- `to_public_dict` / `_to_dict` 中字段名不匹配

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: fix remaining test compatibility issues"
```

---

### Task 10: 更新文档

**Files:**
- Modify: `CLAUDE.md` (更新 REST API 表、WebSocket 事件、DownloadConfig 描述)
- Modify: `IMPROVEMENTS.md` (标记 P1 下载并发+重试为已完成)

- [ ] **Step 1: Update CLAUDE.md**

在 REST API 表中追加：

```
POST /api/downloads/{gid}/retry          Retry failed pages
POST /api/downloads/{gid}/resume         Resume paused download
GET  /api/downloads/{gid}/pages          Page-level status detail
```

在 WebSocket Events 中追加：

```json
{"event": "download_paused", "gid": "123", "reason": "image_limit"}
{"event": "download_auth_failed", "gid": "123", "error": "..."}
```

更新 download.py 描述，提及并发下载、即时重试、原子写入。

- [ ] **Step 2: Update IMPROVEMENTS.md**

将 P1 下载并发+重试的状态从 `⬜ 待实施` 改为 `✅ 已完成`。

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md IMPROVEMENTS.md
git commit -m "docs: update CLAUDE.md and IMPROVEMENTS.md for P1 download concurrency+retry"
```
