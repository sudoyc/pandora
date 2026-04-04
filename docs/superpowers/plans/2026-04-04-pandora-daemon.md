# pandora-daemon Implementation Plan -- COMPLETE

> All 12 tasks implemented and passing. Extended by unified image browsing & download plan (2026-04-04). Total: 203 tests.

**Goal:** Build a FastAPI daemon that wraps `exhentai_api` as a REST + WebSocket service with download management, caching, and configuration.

**Architecture:** Single-process FastAPI app. `AppState` holds shared resources (ExhentaiAPI, DownloadManager, CacheManager, WebSocketManager). Routes grouped by domain. Download workers are asyncio tasks in the same event loop. JSON file persistence for downloads, TOML for config, disk cache for thumbnails.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, httpx, tomllib (stdlib), tomli-w, pytest, pytest-asyncio

---

## File Map

```
pandora_daemon/
├── __init__.py          # Empty package marker
├── __main__.py          # `python -m pandora_daemon` entry point
├── app.py               # create_app(), lifespan
├── config.py            # PandoraConfig dataclasses + load/save TOML
├── state.py             # AppState dataclass
├── dependencies.py      # FastAPI Depends() helpers
├── download.py          # DownloadTask + DownloadManager
├── cache.py             # CacheManager (disk thumbs + memory gallery TTL)
├── ws.py                # WebSocketManager
└── routes/
    ├── __init__.py      # Collects all routers
    ├── browse.py        # search, homepage, popular, toplist, watched, thumb proxy
    ├── gallery.py       # gallery detail, images, comments, rating, vote, torrents, archive
    ├── favorites.py     # favorites list, add, modify
    ├── downloads.py     # submit, status, cancel
    ├── user.py          # home, reset_limit, profile, tags
    └── config_routes.py # config read/update

tests/pandora_daemon/
├── __init__.py
├── test_config.py
├── test_ws.py
├── test_cache.py
├── test_download.py
├── test_routes_browse.py
├── test_routes_gallery.py
├── test_routes_favorites.py
├── test_routes_downloads.py
├── test_routes_user.py
└── test_routes_config.py
```

---

### Task 1: Project Setup and Config System

**Files:**
- Modify: `pyproject.toml`
- Create: `pandora_daemon/__init__.py`
- Create: `pandora_daemon/config.py`
- Create: `tests/pandora_daemon/__init__.py`
- Create: `tests/pandora_daemon/test_config.py`

- [ ] **Step 1: Update pyproject.toml with new dependencies**

Add FastAPI, uvicorn, tomli-w to dependencies:

```toml
[project]
name = "workspace"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "beautifulsoup4>=4.14.3",
    "httpx>=0.28.1",
    "rich>=14.3.3",
    "textual>=8.2.1",
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "tomli-w>=1.0",
]

[project.scripts]
exhentai-dl = "cli:main"

[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
]
```

- [ ] **Step 2: Install dependencies**

Run: `uv sync`
Expected: Dependencies installed successfully.

- [ ] **Step 3: Create package init files**

Create empty `pandora_daemon/__init__.py` and `tests/pandora_daemon/__init__.py`.

- [ ] **Step 4: Write the failing config tests**

```python
# tests/pandora_daemon/test_config.py
import pytest
import tomli_w
from pathlib import Path
from pandora_daemon.config import (
    PandoraConfig,
    CredentialsConfig,
    ServerConfig,
    DownloadConfig,
    CacheConfig,
    load_config,
    save_config,
)


def test_default_config():
    config = PandoraConfig()
    assert config.credentials.igneous == ""
    assert config.credentials.ipb_member_id == ""
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 7860
    assert config.download.path == "~/Downloads/pandora"
    assert config.download.concurrency == 3
    assert config.cache.thumb_dir == "~/.cache/pandora/thumbs"
    assert config.cache.thumb_max_size_mb == 500
    assert config.cache.gallery_ttl_seconds == 300


def test_load_config_creates_default(tmp_path):
    config_path = tmp_path / "config.toml"
    config = load_config(config_path)
    assert config.server.port == 7860
    assert config_path.exists()


def test_load_config_reads_existing(tmp_path):
    config_path = tmp_path / "config.toml"
    data = {
        "credentials": {"igneous": "abc", "ipb_member_id": "123"},
        "server": {"host": "0.0.0.0", "port": 9999},
        "download": {"path": "/tmp/dl", "concurrency": 5},
        "cache": {"thumb_dir": "/tmp/thumbs", "thumb_max_size_mb": 100, "gallery_ttl_seconds": 60},
    }
    config_path.write_bytes(tomli_w.dumps(data))
    config = load_config(config_path)
    assert config.credentials.igneous == "abc"
    assert config.server.port == 9999
    assert config.download.concurrency == 5


def test_load_config_partial_toml(tmp_path):
    config_path = tmp_path / "config.toml"
    data = {"server": {"port": 1234}}
    config_path.write_bytes(tomli_w.dumps(data))
    config = load_config(config_path)
    assert config.server.port == 1234
    assert config.credentials.igneous == ""  # default
    assert config.download.concurrency == 3  # default


def test_save_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config = PandoraConfig()
    config.server.port = 8080
    save_config(config, config_path)

    reloaded = load_config(config_path)
    assert reloaded.server.port == 8080


def test_config_to_dict_omits_credentials():
    config = PandoraConfig()
    config.credentials.igneous = "secret"
    d = config.to_public_dict()
    assert "credentials" not in d
    assert d["server"]["port"] == 7860
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_config.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'pandora_daemon')

- [ ] **Step 6: Implement config.py**

```python
# pandora_daemon/config.py
import tomllib
from dataclasses import dataclass, asdict
from pathlib import Path

import tomli_w


@dataclass
class CredentialsConfig:
    igneous: str = ""
    ipb_member_id: str = ""


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 7860


@dataclass
class DownloadConfig:
    path: str = "~/Downloads/pandora"
    concurrency: int = 3


@dataclass
class CacheConfig:
    thumb_dir: str = "~/.cache/pandora/thumbs"
    thumb_max_size_mb: int = 500
    gallery_ttl_seconds: int = 300


@dataclass
class PandoraConfig:
    credentials: CredentialsConfig = None
    server: ServerConfig = None
    download: DownloadConfig = None
    cache: CacheConfig = None

    def __post_init__(self):
        if self.credentials is None:
            self.credentials = CredentialsConfig()
        if self.server is None:
            self.server = ServerConfig()
        if self.download is None:
            self.download = DownloadConfig()
        if self.cache is None:
            self.cache = CacheConfig()

    def to_public_dict(self) -> dict:
        d = asdict(self)
        d.pop("credentials", None)
        return d


def load_config(path: Path) -> PandoraConfig:
    if path.exists():
        with open(path, "rb") as f:
            data = tomllib.load(f)
    else:
        data = {}

    creds = data.get("credentials", {})
    server = data.get("server", {})
    download = data.get("download", {})
    cache = data.get("cache", {})

    config = PandoraConfig(
        credentials=CredentialsConfig(**creds),
        server=ServerConfig(**server),
        download=DownloadConfig(**download),
        cache=CacheConfig(**cache),
    )

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        save_config(config, path)

    return config


def save_config(config: PandoraConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(config)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_config.py -v`
Expected: All 6 tests PASS

- [ ] **Step 8: Commit**

```bash
git add pandora_daemon/__init__.py pandora_daemon/config.py tests/pandora_daemon/__init__.py tests/pandora_daemon/test_config.py pyproject.toml
git commit -m "feat(daemon): add config system with TOML load/save"
```

---

### Task 2: WebSocket Manager

**Files:**
- Create: `pandora_daemon/ws.py`
- Create: `tests/pandora_daemon/test_ws.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_ws.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from pandora_daemon.ws import WebSocketManager


@pytest.mark.asyncio
async def test_connect_adds_to_set():
    mgr = WebSocketManager()
    ws = AsyncMock()
    await mgr.connect(ws)
    assert ws in mgr.connections
    ws.accept.assert_awaited_once()


def test_disconnect_removes_from_set():
    mgr = WebSocketManager()
    ws = MagicMock()
    mgr.connections.add(ws)
    mgr.disconnect(ws)
    assert ws not in mgr.connections


def test_disconnect_ignores_missing():
    mgr = WebSocketManager()
    ws = MagicMock()
    mgr.disconnect(ws)  # should not raise


@pytest.mark.asyncio
async def test_broadcast_sends_to_all():
    mgr = WebSocketManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    mgr.connections = {ws1, ws2}
    event = {"event": "test", "data": 123}
    await mgr.broadcast(event)
    ws1.send_json.assert_awaited_once_with(event)
    ws2.send_json.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_broadcast_removes_disconnected():
    mgr = WebSocketManager()
    ws_ok = AsyncMock()
    ws_bad = AsyncMock()
    ws_bad.send_json.side_effect = Exception("disconnected")
    mgr.connections = {ws_ok, ws_bad}
    await mgr.broadcast({"event": "test"})
    assert ws_bad not in mgr.connections
    assert ws_ok in mgr.connections
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_ws.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement ws.py**

```python
# pandora_daemon/ws.py
from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, event: dict) -> None:
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections.discard(ws)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_ws.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/ws.py tests/pandora_daemon/test_ws.py
git commit -m "feat(daemon): add WebSocket manager"
```

---

### Task 3: Cache Manager

**Files:**
- Create: `pandora_daemon/cache.py`
- Create: `tests/pandora_daemon/test_cache.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_cache.py
import pytest
import time
from pathlib import Path
from pandora_daemon.cache import CacheManager
from pandora_daemon.config import CacheConfig


@pytest.fixture
def cache_config(tmp_path):
    return CacheConfig(
        thumb_dir=str(tmp_path / "thumbs"),
        thumb_max_size_mb=1,
        gallery_ttl_seconds=2,
    )


@pytest.fixture
def cache(cache_config):
    return CacheManager(cache_config)


# -- Thumbnail cache tests --

@pytest.mark.asyncio
async def test_thumb_miss_returns_none(cache):
    result = await cache.get_thumb("https://example.com/thumb.jpg")
    assert result is None


@pytest.mark.asyncio
async def test_thumb_put_and_get(cache):
    url = "https://example.com/thumb.jpg"
    data = b"fake image data"
    await cache.put_thumb(url, data)
    result = await cache.get_thumb(url)
    assert result == data


@pytest.mark.asyncio
async def test_thumb_eviction(tmp_path):
    config = CacheConfig(
        thumb_dir=str(tmp_path / "thumbs"),
        thumb_max_size_mb=0,  # 0 MB limit forces immediate eviction
        gallery_ttl_seconds=300,
    )
    cache = CacheManager(config)
    await cache.put_thumb("https://example.com/1.jpg", b"x" * 100)
    await cache.put_thumb("https://example.com/2.jpg", b"y" * 100)
    await cache.evict_thumbs()
    # After eviction with 0 MB limit, directory should be empty or near-empty
    thumb_dir = Path(config.thumb_dir)
    files = list(thumb_dir.iterdir()) if thumb_dir.exists() else []
    assert len(files) == 0


# -- Gallery detail cache tests --

def test_gallery_cache_miss(cache):
    result = cache.get_gallery("999", "xyz")
    assert result is None


def test_gallery_cache_put_and_get(cache):
    from unittest.mock import MagicMock
    detail = MagicMock()
    detail.gid = "123"
    detail.token = "abc"
    cache.put_gallery(detail)
    result = cache.get_gallery("123", "abc")
    assert result is detail


def test_gallery_cache_ttl_expiry(cache):
    from unittest.mock import MagicMock
    detail = MagicMock()
    detail.gid = "123"
    detail.token = "abc"
    cache.put_gallery(detail)
    # Manually expire it
    cache._gallery_cache["123:abc"] = (detail, time.time() - 1)
    result = cache.get_gallery("123", "abc")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_cache.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement cache.py**

```python
# pandora_daemon/cache.py
import hashlib
import time
from pathlib import Path

from pandora_daemon.config import CacheConfig


class CacheManager:
    def __init__(self, config: CacheConfig):
        self._config = config
        self._thumb_dir = Path(config.thumb_dir)
        self._thumb_dir.mkdir(parents=True, exist_ok=True)
        self._max_bytes = config.thumb_max_size_mb * 1024 * 1024
        self._ttl = config.gallery_ttl_seconds
        self._gallery_cache: dict[str, tuple] = {}  # key -> (detail, expires_at)

    def _thumb_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()
        return self._thumb_dir / f"{h}.jpg"

    async def get_thumb(self, url: str) -> bytes | None:
        path = self._thumb_path(url)
        if path.exists():
            path.stat()  # update access time for LRU
            return path.read_bytes()
        return None

    async def put_thumb(self, url: str, data: bytes) -> None:
        path = self._thumb_path(url)
        path.write_bytes(data)

    async def evict_thumbs(self) -> None:
        if not self._thumb_dir.exists():
            return
        files = sorted(self._thumb_dir.iterdir(), key=lambda p: p.stat().st_atime)
        total = sum(f.stat().st_size for f in files)
        while total > self._max_bytes and files:
            oldest = files.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink()

    def get_gallery(self, gid: str, token: str) -> object | None:
        key = f"{gid}:{token}"
        entry = self._gallery_cache.get(key)
        if entry is None:
            return None
        detail, expires_at = entry
        if time.time() > expires_at:
            del self._gallery_cache[key]
            return None
        return detail

    def put_gallery(self, detail) -> None:
        key = f"{detail.gid}:{detail.token}"
        self._gallery_cache[key] = (detail, time.time() + self._ttl)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_cache.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/cache.py tests/pandora_daemon/test_cache.py
git commit -m "feat(daemon): add cache manager with disk thumbs and memory TTL"
```

---

### Task 4: Download Manager

**Files:**
- Create: `pandora_daemon/download.py`
- Create: `tests/pandora_daemon/test_download.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_download.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pandora_daemon.download import DownloadManager, DownloadTask
from pandora_daemon.config import DownloadConfig


@pytest.fixture
def download_config(tmp_path):
    return DownloadConfig(
        path=str(tmp_path / "downloads"),
        concurrency=2,
    )


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "downloads.json"


@pytest.fixture
def mock_api():
    api = AsyncMock()
    detail = MagicMock()
    detail.title = "Test Gallery"
    detail.pages = 3
    detail.preview_pages = 1
    detail.preview_urls = [
        "https://exhentai.org/s/abc/123-1",
        "https://exhentai.org/s/def/123-2",
        "https://exhentai.org/s/ghi/123-3",
    ]
    detail.gid = "123"
    detail.token = "abc"
    detail.url = "https://exhentai.org/g/123/abc/"
    api.get_gallery_details.return_value = detail
    return api


@pytest.fixture
def mock_ws():
    return AsyncMock()


# -- DownloadTask model tests --

def test_download_task_creation():
    task = DownloadTask(
        gid="123", token="abc", title="Test",
        total_pages=10, output_dir="/tmp/test",
    )
    assert task.status == "queued"
    assert task.downloaded_pages == 0
    assert task.error == ""
    assert task.created_at != ""


def test_download_task_to_dict():
    task = DownloadTask(
        gid="123", token="abc", title="Test",
        total_pages=10, output_dir="/tmp/test",
    )
    d = task.to_dict()
    assert d["gid"] == "123"
    assert d["status"] == "queued"
    assert "created_at" in d


# -- DownloadManager tests --

@pytest.mark.asyncio
async def test_submit_creates_task(mock_api, mock_ws, download_config, state_file):
    mgr = DownloadManager(api=mock_api, config=download_config, ws=mock_ws, state_file=state_file)
    task = await mgr.submit("123", "abc")
    assert task.gid == "123"
    assert task.title == "Test Gallery"
    assert task.total_pages == 3
    assert task.status == "queued"
    mock_ws.broadcast.assert_awaited()


@pytest.mark.asyncio
async def test_submit_duplicate_rejected(mock_api, mock_ws, download_config, state_file):
    mgr = DownloadManager(api=mock_api, config=download_config, ws=mock_ws, state_file=state_file)
    await mgr.submit("123", "abc")
    with pytest.raises(ValueError, match="already"):
        await mgr.submit("123", "abc")


@pytest.mark.asyncio
async def test_status_returns_all_tasks(mock_api, mock_ws, download_config, state_file):
    mgr = DownloadManager(api=mock_api, config=download_config, ws=mock_ws, state_file=state_file)
    await mgr.submit("123", "abc")
    tasks = mgr.status()
    assert len(tasks) == 1
    assert tasks[0].gid == "123"


@pytest.mark.asyncio
async def test_cancel_marks_cancelled(mock_api, mock_ws, download_config, state_file):
    mgr = DownloadManager(api=mock_api, config=download_config, ws=mock_ws, state_file=state_file)
    await mgr.submit("123", "abc")
    result = await mgr.cancel("123")
    assert result is True
    assert mgr.status()[0].status == "cancelled"
    mock_ws.broadcast.assert_awaited()


@pytest.mark.asyncio
async def test_cancel_nonexistent(mock_api, mock_ws, download_config, state_file):
    mgr = DownloadManager(api=mock_api, config=download_config, ws=mock_ws, state_file=state_file)
    result = await mgr.cancel("999")
    assert result is False


@pytest.mark.asyncio
async def test_save_and_load_state(mock_api, mock_ws, download_config, state_file):
    mgr = DownloadManager(api=mock_api, config=download_config, ws=mock_ws, state_file=state_file)
    await mgr.submit("123", "abc")
    mgr._save_state()
    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["gid"] == "123"


@pytest.mark.asyncio
async def test_load_state_requeues_pending(mock_api, mock_ws, download_config, state_file):
    state_data = {
        "tasks": [
            {
                "gid": "456", "token": "def", "title": "Pending Gallery",
                "status": "queued", "total_pages": 5, "downloaded_pages": 0,
                "output_dir": "/tmp/test", "error": "", "created_at": "2026-04-04T12:00:00",
                "preview_urls": [],
            }
        ]
    }
    state_file.write_text(json.dumps(state_data))
    mgr = DownloadManager(api=mock_api, config=download_config, ws=mock_ws, state_file=state_file)
    mgr._load_state()
    assert len(mgr._tasks) == 1
    assert mgr._tasks["456"].status == "queued"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_download.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement download.py**

```python
# pandora_daemon/download.py
import asyncio
import json
import re
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from pandora_daemon.config import DownloadConfig


@dataclass
class DownloadTask:
    gid: str
    token: str
    title: str
    total_pages: int
    output_dir: str
    status: str = "queued"
    downloaded_pages: int = 0
    error: str = ""
    created_at: str = ""
    preview_urls: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)


class DownloadManager:
    def __init__(self, api, config: DownloadConfig, ws, state_file: Path):
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
        self._load_state()
        # Re-queue pending/downloading tasks
        for task in self._tasks.values():
            if task.status in ("queued", "downloading"):
                task.status = "queued"
                await self._queue.put(task.gid)
        for _ in range(self._config.concurrency):
            worker = asyncio.create_task(self._worker())
            self._workers.append(worker)

    async def shutdown(self) -> None:
        for w in self._workers:
            w.cancel()
        for w in self._workers:
            try:
                await w
            except asyncio.CancelledError:
                pass
        self._save_state()

    async def submit(self, gid: str, token: str) -> DownloadTask:
        if gid in self._tasks and self._tasks[gid].status in ("queued", "downloading"):
            raise ValueError(f"Download {gid} already in queue")

        detail = await self._api.get_gallery_details(gid, token)
        title = detail.title or "Unknown"
        folder = f"{gid}-{_sanitize_filename(title)}"
        output_dir = str(self._download_path / folder)

        # Collect all preview URLs including extra preview pages
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

        task = DownloadTask(
            gid=gid, token=token, title=title,
            total_pages=detail.pages, output_dir=output_dir,
            preview_urls=preview_urls,
        )
        self._tasks[gid] = task
        await self._queue.put(gid)
        self._save_state()
        await self._ws.broadcast({
            "event": "download_queued",
            "gid": gid, "title": title, "total_pages": detail.pages,
        })
        return task

    async def cancel(self, gid: str) -> bool:
        task = self._tasks.get(gid)
        if not task or task.status not in ("queued", "downloading"):
            return False
        task.status = "cancelled"
        self._cancelled.add(gid)
        self._save_state()
        await self._ws.broadcast({"event": "download_cancelled", "gid": gid})
        return True

    def status(self) -> list[DownloadTask]:
        return list(self._tasks.values())

    async def _worker(self) -> None:
        while True:
            gid = await self._queue.get()
            task = self._tasks.get(gid)
            if not task or task.status == "cancelled":
                self._queue.task_done()
                continue

            task.status = "downloading"
            self._save_state()

            try:
                os.makedirs(task.output_dir, exist_ok=True)
                from exhentai_api.parsers.image import parse_image_viewer

                for i, viewer_url in enumerate(task.preview_urls, 1):
                    if gid in self._cancelled:
                        break
                    if i <= task.downloaded_pages:
                        continue  # skip already downloaded

                    html = await self._api.client.get_html(viewer_url)
                    image_url, _ = parse_image_viewer(html)

                    if image_url:
                        ext = ".jpg"
                        if ".png" in image_url.lower():
                            ext = ".png"
                        elif ".gif" in image_url.lower():
                            ext = ".gif"

                        filepath = os.path.join(task.output_dir, f"{i:04d}{ext}")
                        async with self._api.client.session.stream("GET", image_url) as resp:
                            resp.raise_for_status()
                            with open(filepath, "wb") as f:
                                async for chunk in resp.aiter_bytes(8192):
                                    f.write(chunk)

                    task.downloaded_pages = i
                    self._save_state()
                    await self._ws.broadcast({
                        "event": "download_progress",
                        "gid": gid, "page": i, "total_pages": task.total_pages,
                    })

                if gid not in self._cancelled:
                    task.status = "completed"
                    self._save_state()
                    await self._ws.broadcast({
                        "event": "download_complete",
                        "gid": gid, "path": task.output_dir,
                    })
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                self._save_state()
                await self._ws.broadcast({
                    "event": "download_error",
                    "gid": gid, "error": str(e),
                })
            finally:
                self._queue.task_done()

    def _save_state(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"tasks": [t.to_dict() for t in self._tasks.values()]}
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text())
            for t in data.get("tasks", []):
                task = DownloadTask(
                    gid=t["gid"], token=t["token"], title=t["title"],
                    total_pages=t["total_pages"], output_dir=t["output_dir"],
                    status=t["status"], downloaded_pages=t["downloaded_pages"],
                    error=t["error"], created_at=t["created_at"],
                    preview_urls=t.get("preview_urls", []),
                )
                self._tasks[task.gid] = task
        except (json.JSONDecodeError, KeyError):
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_download.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/download.py tests/pandora_daemon/test_download.py
git commit -m "feat(daemon): add download manager with queue, persistence, and WebSocket events"
```

---

### Task 5: App State, Dependencies, Lifespan, and Entry Point

**Files:**
- Create: `pandora_daemon/state.py`
- Create: `pandora_daemon/dependencies.py`
- Create: `pandora_daemon/app.py`
- Create: `pandora_daemon/routes/__init__.py`
- Create: `pandora_daemon/__main__.py`

This task wires everything together. Since these modules are thin glue, they are grouped in one task.

- [ ] **Step 1: Create state.py**

```python
# pandora_daemon/state.py
from dataclasses import dataclass
from pathlib import Path

from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from pandora_daemon.config import PandoraConfig
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager


@dataclass
class AppState:
    config: PandoraConfig
    config_path: Path
    client: ExhentaiClient
    api: ExhentaiAPI
    downloads: DownloadManager
    cache: CacheManager
    ws: WebSocketManager
```

- [ ] **Step 2: Create dependencies.py**

```python
# pandora_daemon/dependencies.py
from fastapi import Request, Depends

from pandora_daemon.state import AppState
from exhentai_api.api import ExhentaiAPI
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager


def get_state(request: Request) -> AppState:
    return request.app.state.pandora


def get_api(state: AppState = Depends(get_state)) -> ExhentaiAPI:
    return state.api


def get_downloads(state: AppState = Depends(get_state)) -> DownloadManager:
    return state.downloads


def get_cache(state: AppState = Depends(get_state)) -> CacheManager:
    return state.cache


def get_ws(state: AppState = Depends(get_state)) -> WebSocketManager:
    return state.ws
```

- [ ] **Step 3: Create routes/__init__.py (empty for now, routes added in later tasks)**

```python
# pandora_daemon/routes/__init__.py
from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 4: Create app.py**

```python
# pandora_daemon/app.py
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from pandora_daemon.config import load_config
from pandora_daemon.state import AppState
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_path = Path("~/.config/pandora/config.toml").expanduser()
    config = load_config(config_path)

    client = ExhentaiClient(
        igneous=config.credentials.igneous,
        ipb_member_id=config.credentials.ipb_member_id,
    )
    api = ExhentaiAPI(client=client)
    cache = CacheManager(config.cache)
    ws = WebSocketManager()
    state_file = config_path.parent / "downloads.json"
    downloads = DownloadManager(api=api, config=config.download, ws=ws, state_file=state_file)

    state = AppState(
        config=config, config_path=config_path,
        client=client, api=api,
        downloads=downloads, cache=cache, ws=ws,
    )
    app.state.pandora = state

    await downloads.start()
    yield
    await downloads.shutdown()
    await api.aclose()


def create_app() -> FastAPI:
    from pandora_daemon.routes import router
    app = FastAPI(title="pandora-daemon", lifespan=lifespan)
    app.include_router(router)
    return app
```

- [ ] **Step 5: Create __main__.py**

```python
# pandora_daemon/__main__.py
import uvicorn
from pandora_daemon.config import load_config
from pathlib import Path


def main():
    config_path = Path("~/.config/pandora/config.toml").expanduser()
    config = load_config(config_path)
    from pandora_daemon.app import create_app
    app = create_app()
    uvicorn.run(app, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Verify the module is importable**

Run: `uv run python -c "from pandora_daemon.app import create_app; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add pandora_daemon/state.py pandora_daemon/dependencies.py pandora_daemon/app.py pandora_daemon/routes/__init__.py pandora_daemon/__main__.py
git commit -m "feat(daemon): add app state, dependencies, lifespan, and entry point"
```

---

### Task 6: Browse Routes

**Files:**
- Create: `pandora_daemon/routes/browse.py`
- Modify: `pandora_daemon/routes/__init__.py`
- Create: `tests/pandora_daemon/test_routes_browse.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_routes_browse.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from pandora_daemon.routes.browse import router
from pandora_daemon.state import AppState
from pandora_daemon.config import PandoraConfig, CacheConfig


def _make_app(mock_api, mock_cache=None):
    app = FastAPI()
    app.include_router(router)

    state = MagicMock(spec=AppState)
    state.api = mock_api
    state.cache = mock_cache or MagicMock()
    app.state.pandora = state
    return app


def _make_gallery_item(gid="1", title="Test"):
    item = MagicMock()
    item.gid = gid
    item.token = "abc"
    item.title = title
    item.category = "Manga"
    item.uploader = "user"
    item.thumb_url = "https://ex.com/t.jpg"
    item.posted = "2026-01-01"
    item.rating = 4.5
    item.pages = 20
    item.rated = False
    item.thumb_width = 250
    item.thumb_height = 356
    item.url = f"https://exhentai.org/g/{gid}/abc/"
    return item


def test_homepage():
    mock_api = AsyncMock()
    mock_api.get_homepage.return_value = [_make_gallery_item()]
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/homepage")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["gid"] == "1"


def test_search():
    mock_api = AsyncMock()
    mock_api.search.return_value = [_make_gallery_item(gid="2", title="Found")]
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/search", params={"keyword": "test", "page": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    mock_api.search.assert_awaited_once()


def test_popular():
    mock_api = AsyncMock()
    mock_api.get_popular.return_value = [_make_gallery_item()]
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/popular")
    assert resp.status_code == 200


def test_toplist():
    mock_api = AsyncMock()
    item = MagicMock()
    item.gid = "1"
    item.token = "abc"
    item.title = "Top"
    item.category = "Manga"
    item.uploader = "user"
    item.thumb_url = "https://ex.com/t.jpg"
    item.posted = "2026-01-01"
    mock_api.get_toplist.return_value = [item]
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/toplist", params={"tl": "15"})
    assert resp.status_code == 200
    mock_api.get_toplist.assert_awaited_once_with("15")


def test_watched():
    mock_api = AsyncMock()
    mock_api.get_watched.return_value = []
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/watched", params={"page": 2})
    assert resp.status_code == 200
    mock_api.get_watched.assert_awaited_once_with(page=2)


def test_thumb_proxy_cached():
    mock_api = AsyncMock()
    mock_cache = AsyncMock()
    mock_cache.get_thumb.return_value = b"fake-image-bytes"
    app = _make_app(mock_api, mock_cache)
    client = TestClient(app)
    resp = client.get("/api/thumb", params={"url": "https://ex.com/t.jpg"})
    assert resp.status_code == 200
    assert resp.content == b"fake-image-bytes"


def test_thumb_proxy_fetches_on_miss():
    mock_api = AsyncMock()
    mock_response = AsyncMock()
    mock_response.content = b"downloaded-image"
    mock_response.raise_for_status = MagicMock()
    mock_api.client.session.get.return_value = mock_response
    mock_cache = AsyncMock()
    mock_cache.get_thumb.return_value = None
    app = _make_app(mock_api, mock_cache)
    client = TestClient(app)
    resp = client.get("/api/thumb", params={"url": "https://ex.com/t.jpg"})
    assert resp.status_code == 200
    mock_cache.put_thumb.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_browse.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement routes/browse.py**

```python
# pandora_daemon/routes/browse.py
from dataclasses import asdict
from fastapi import APIRouter, Depends, Query, Response

from exhentai_api.api import ExhentaiAPI
from exhentai_api.models.search import SearchParams
from pandora_daemon.dependencies import get_api, get_cache, get_state
from pandora_daemon.cache import CacheManager

router = APIRouter(prefix="/api", tags=["browse"])


def _gallery_item_to_dict(item) -> dict:
    return {
        "gid": item.gid, "token": item.token, "title": item.title,
        "category": item.category, "uploader": item.uploader,
        "thumb_url": item.thumb_url, "posted": item.posted,
        "rating": item.rating, "pages": item.pages,
        "rated": item.rated,
        "thumb_width": item.thumb_width, "thumb_height": item.thumb_height,
        "url": item.url,
    }


def _toplist_item_to_dict(item) -> dict:
    return {
        "gid": item.gid, "token": item.token, "title": item.title,
        "category": item.category, "uploader": item.uploader,
        "thumb_url": item.thumb_url, "posted": item.posted,
    }


@router.get("/homepage")
async def homepage(api: ExhentaiAPI = Depends(get_api)):
    items = await api.get_homepage()
    return [_gallery_item_to_dict(g) for g in items]


@router.get("/search")
async def search(
    keyword: str = "",
    page: int = 0,
    min_rating: int | None = None,
    category: int | None = None,
    api: ExhentaiAPI = Depends(get_api),
):
    params = SearchParams(f_search=keyword)
    if category is not None:
        params.f_cats = category
    if min_rating is not None:
        params.advsearch = True
        params.f_sr = True
        params.f_srdd = min_rating
    items = await api.search(params, page=page)
    return [_gallery_item_to_dict(g) for g in items]


@router.get("/popular")
async def popular(api: ExhentaiAPI = Depends(get_api)):
    items = await api.get_popular()
    return [_gallery_item_to_dict(g) for g in items]


@router.get("/toplist")
async def toplist(tl: str = "15", api: ExhentaiAPI = Depends(get_api)):
    items = await api.get_toplist(tl)
    return [_toplist_item_to_dict(g) for g in items]


@router.get("/watched")
async def watched(page: int = 0, api: ExhentaiAPI = Depends(get_api)):
    items = await api.get_watched(page=page)
    return [_gallery_item_to_dict(g) for g in items]


@router.get("/thumb")
async def thumb_proxy(
    url: str,
    api: ExhentaiAPI = Depends(get_api),
    cache: CacheManager = Depends(get_cache),
):
    data = await cache.get_thumb(url)
    if data is None:
        resp = await api.client.session.get(url)
        resp.raise_for_status()
        data = resp.content
        await cache.put_thumb(url, data)
    return Response(content=data, media_type="image/jpeg")
```

- [ ] **Step 4: Update routes/__init__.py to include browse router**

```python
# pandora_daemon/routes/__init__.py
from fastapi import APIRouter
from pandora_daemon.routes.browse import router as browse_router

router = APIRouter()
router.include_router(browse_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_routes_browse.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/routes/browse.py pandora_daemon/routes/__init__.py tests/pandora_daemon/test_routes_browse.py
git commit -m "feat(daemon): add browse routes (homepage, search, popular, toplist, watched, thumb)"
```

---

### Task 7: Gallery Routes

**Files:**
- Create: `pandora_daemon/routes/gallery.py`
- Modify: `pandora_daemon/routes/__init__.py`
- Create: `tests/pandora_daemon/test_routes_gallery.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_routes_gallery.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from pandora_daemon.routes.gallery import router
from pandora_daemon.state import AppState


def _make_app(mock_api, mock_cache=None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.api = mock_api
    state.cache = mock_cache or MagicMock()
    state.cache.get_gallery = MagicMock(return_value=None)
    app.state.pandora = state
    return app


def _make_detail():
    d = MagicMock()
    d.gid = "123"
    d.token = "abc"
    d.title = "Test"
    d.title_jpn = "テスト"
    d.category = "Manga"
    d.uploader = "user"
    d.cover_url = "https://ex.com/cover.jpg"
    d.tags = {"parody": ["fate"]}
    d.pages = 10
    d.size = "50 MB"
    d.posted = "2026-01-01"
    d.favorite_slot = None
    d.preview_pages = 1
    d.preview_urls = []
    d.rating = 4.5
    d.rating_count = 100
    d.favorite_count = 50
    d.torrent_count = 2
    d.torrent_url = ""
    d.archive_url = ""
    d.parent_url = None
    d.newer_versions = []
    d.comments = []
    d.comments_has_more = False
    d.api_uid = "uid1"
    d.api_key = "key1"
    d.url = "https://exhentai.org/g/123/abc/"
    return d


def test_gallery_detail():
    mock_api = AsyncMock()
    mock_api.get_gallery_details.return_value = _make_detail()
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/gallery/123/abc")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gid"] == "123"
    assert data["title"] == "Test"


def test_gallery_detail_uses_cache():
    mock_api = AsyncMock()
    cached = _make_detail()
    mock_cache = MagicMock()
    mock_cache.get_gallery.return_value = cached
    app = _make_app(mock_api, mock_cache)
    client = TestClient(app)
    resp = client.get("/api/gallery/123/abc")
    assert resp.status_code == 200
    mock_api.get_gallery_details.assert_not_awaited()


def test_comment_gallery():
    mock_api = AsyncMock()
    comment = MagicMock()
    comment.id = 1
    comment.user = "user"
    comment.comment = "Great!"
    comment.score = 0
    comment.time = "2026-01-01"
    comment.is_uploader = False
    comment.vote_up_able = True
    comment.vote_down_able = True
    comment.vote_up_ed = False
    comment.vote_down_ed = False
    comment.editable = False
    comment.last_edited = ""
    mock_api.comment_gallery.return_value = [comment]
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.post("/api/gallery/123/abc/comment", json={"comment": "Great!"})
    assert resp.status_code == 200
    mock_api.comment_gallery.assert_awaited_once_with("123", "abc", "Great!", edit_id=None)


def test_rate_gallery():
    mock_api = AsyncMock()
    result = MagicMock()
    result.rating = 4.5
    result.rating_count = 101
    mock_api.rate_gallery.return_value = result
    # Need gallery detail for api_uid/api_key
    detail = _make_detail()
    mock_api.get_gallery_details.return_value = detail
    mock_cache = MagicMock()
    mock_cache.get_gallery.return_value = detail
    app = _make_app(mock_api, mock_cache)
    client = TestClient(app)
    resp = client.post("/api/gallery/123/abc/rate", json={"rating": 8})
    assert resp.status_code == 200
    data = resp.json()
    assert data["rating"] == 4.5


def test_torrents():
    mock_api = AsyncMock()
    t = MagicMock()
    t.name = "test.torrent"
    t.url = "https://ex.com/t"
    t.size = "100 MB"
    t.seeds = 5
    t.peers = 2
    t.downloads = 50
    t.posted = "2026-01-01"
    t.uploader = "user"
    mock_api.get_torrent_list.return_value = [t]
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/gallery/123/abc/torrents")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_archive():
    mock_api = AsyncMock()
    data = MagicMock()
    data.original = MagicMock()
    data.original.url = "https://ex.com/a"
    data.original.size = "200 MB"
    data.original.cost = "100 GP"
    data.resample = MagicMock()
    data.resample.url = "https://ex.com/b"
    data.resample.size = "50 MB"
    data.resample.cost = "20 GP"
    data.funds = "1000 GP"
    mock_api.get_archive_list.return_value = data
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/gallery/123/abc/archive")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_gallery.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement routes/gallery.py**

```python
# pandora_daemon/routes/gallery.py
from dataclasses import asdict
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from exhentai_api.api import ExhentaiAPI
from pandora_daemon.dependencies import get_api, get_cache, get_state
from pandora_daemon.cache import CacheManager
from pandora_daemon.state import AppState

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


def _detail_to_dict(d) -> dict:
    return {
        "gid": d.gid, "token": d.token, "title": d.title,
        "title_jpn": d.title_jpn, "category": d.category,
        "uploader": d.uploader, "cover_url": d.cover_url,
        "tags": d.tags, "pages": d.pages, "size": d.size,
        "posted": d.posted, "favorite_slot": d.favorite_slot,
        "preview_pages": d.preview_pages,
        "rating": d.rating, "rating_count": d.rating_count,
        "favorite_count": d.favorite_count, "torrent_count": d.torrent_count,
        "comments": [
            {
                "id": c.id, "user": c.user, "comment": c.comment,
                "score": c.score, "time": c.time,
                "is_uploader": c.is_uploader,
                "vote_up_able": c.vote_up_able, "vote_down_able": c.vote_down_able,
                "vote_up_ed": c.vote_up_ed, "vote_down_ed": c.vote_down_ed,
                "editable": c.editable, "last_edited": c.last_edited,
            }
            for c in d.comments
        ],
        "comments_has_more": d.comments_has_more,
        "api_uid": d.api_uid, "api_key": d.api_key,
        "url": d.url,
    }


def _comment_to_dict(c) -> dict:
    return {
        "id": c.id, "user": c.user, "comment": c.comment,
        "score": c.score, "time": c.time,
        "is_uploader": c.is_uploader,
        "vote_up_able": c.vote_up_able, "vote_down_able": c.vote_down_able,
        "vote_up_ed": c.vote_up_ed, "vote_down_ed": c.vote_down_ed,
        "editable": c.editable, "last_edited": c.last_edited,
    }


def _torrent_to_dict(t) -> dict:
    return {
        "name": t.name, "url": t.url, "size": t.size,
        "seeds": t.seeds, "peers": t.peers,
        "downloads": t.downloads, "posted": t.posted,
        "uploader": t.uploader,
    }


def _archive_to_dict(a) -> dict:
    result = {"funds": a.funds}
    if a.original:
        result["original"] = {"url": a.original.url, "size": a.original.size, "cost": a.original.cost}
    if a.resample:
        result["resample"] = {"url": a.resample.url, "size": a.resample.size, "cost": a.resample.cost}
    return result


async def _get_detail(gid: str, token: str, api: ExhentaiAPI, cache: CacheManager):
    cached = cache.get_gallery(gid, token)
    if cached is not None:
        return cached
    detail = await api.get_gallery_details(gid, token)
    cache.put_gallery(detail)
    return detail


@router.get("/{gid}/{token}")
async def gallery_detail(
    gid: str, token: str,
    api: ExhentaiAPI = Depends(get_api),
    cache: CacheManager = Depends(get_cache),
):
    detail = await _get_detail(gid, token, api, cache)
    return _detail_to_dict(detail)


class CommentBody(BaseModel):
    comment: str
    edit_id: Optional[int] = None


@router.post("/{gid}/{token}/comment")
async def comment_gallery(
    gid: str, token: str, body: CommentBody,
    api: ExhentaiAPI = Depends(get_api),
):
    comments = await api.comment_gallery(gid, token, body.comment, edit_id=body.edit_id)
    return [_comment_to_dict(c) for c in comments]


class RateBody(BaseModel):
    rating: int


@router.post("/{gid}/{token}/rate")
async def rate_gallery(
    gid: str, token: str, body: RateBody,
    api: ExhentaiAPI = Depends(get_api),
    cache: CacheManager = Depends(get_cache),
):
    detail = await _get_detail(gid, token, api, cache)
    result = await api.rate_gallery(detail.api_uid, detail.api_key, int(gid), token, body.rating)
    return {"rating": result.rating, "rating_count": result.rating_count}


class VoteCommentBody(BaseModel):
    comment_id: int
    vote: int


@router.post("/{gid}/{token}/vote_comment")
async def vote_comment(
    gid: str, token: str, body: VoteCommentBody,
    api: ExhentaiAPI = Depends(get_api),
    cache: CacheManager = Depends(get_cache),
):
    detail = await _get_detail(gid, token, api, cache)
    result = await api.vote_comment(
        detail.api_uid, detail.api_key, int(gid), token, body.comment_id, body.vote,
    )
    return {"comment_id": result.comment_id, "comment_score": result.comment_score, "comment_vote": result.comment_vote}


@router.get("/{gid}/{token}/torrents")
async def torrents(gid: str, token: str, api: ExhentaiAPI = Depends(get_api)):
    items = await api.get_torrent_list(gid, token)
    return [_torrent_to_dict(t) for t in items]


@router.get("/{gid}/{token}/archive")
async def archive(gid: str, token: str, api: ExhentaiAPI = Depends(get_api)):
    data = await api.get_archive_list(gid, token)
    return _archive_to_dict(data)
```

- [ ] **Step 4: Update routes/__init__.py**

```python
# pandora_daemon/routes/__init__.py
from fastapi import APIRouter
from pandora_daemon.routes.browse import router as browse_router
from pandora_daemon.routes.gallery import router as gallery_router

router = APIRouter()
router.include_router(browse_router)
router.include_router(gallery_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_routes_gallery.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/routes/gallery.py pandora_daemon/routes/__init__.py tests/pandora_daemon/test_routes_gallery.py
git commit -m "feat(daemon): add gallery routes (detail, comment, rate, vote, torrents, archive)"
```

---

### Task 8: Favorites Routes

**Files:**
- Create: `pandora_daemon/routes/favorites.py`
- Modify: `pandora_daemon/routes/__init__.py`
- Create: `tests/pandora_daemon/test_routes_favorites.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_routes_favorites.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from pandora_daemon.routes.favorites import router
from pandora_daemon.state import AppState


def _make_app(mock_api):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.api = mock_api
    app.state.pandora = state
    return app


def test_get_favorites():
    mock_api = AsyncMock()
    fav_resp = MagicMock()
    cat = MagicMock()
    cat.slot = 0
    cat.name = "Favorites 0"
    cat.count = 5
    fav_resp.categories = [cat]
    gallery = MagicMock()
    gallery.gid = "1"
    gallery.token = "abc"
    gallery.title = "Fav Gallery"
    gallery.category = "Manga"
    gallery.uploader = "user"
    gallery.thumb_url = "https://ex.com/t.jpg"
    gallery.posted = "2026-01-01"
    gallery.rating = 4.0
    gallery.pages = 10
    gallery.rated = False
    gallery.thumb_width = 250
    gallery.thumb_height = 356
    gallery.url = "https://exhentai.org/g/1/abc/"
    fav_resp.galleries = [gallery]
    mock_api.get_favorites.return_value = fav_resp
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/favorites", params={"slot": 0, "page": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["categories"]) == 1
    assert len(data["galleries"]) == 1
    mock_api.get_favorites.assert_awaited_once()


def test_add_favorite():
    mock_api = AsyncMock()
    mock_api.add_favorite.return_value = "OK"
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.post("/api/favorites", json={"gid": "1", "token": "abc", "slot": 2, "note": "good"})
    assert resp.status_code == 200
    mock_api.add_favorite.assert_awaited_once_with("1", "abc", favcat=2, favnote="good")


def test_modify_favorites():
    mock_api = AsyncMock()
    mock_api.modify_favorites.return_value = "OK"
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.request("DELETE", "/api/favorites", json={"gids": ["1", "2"], "action": "delete"})
    assert resp.status_code == 200
    mock_api.modify_favorites.assert_awaited_once_with(["1", "2"], "delete")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_favorites.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement routes/favorites.py**

```python
# pandora_daemon/routes/favorites.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from exhentai_api.api import ExhentaiAPI
from pandora_daemon.dependencies import get_api

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


def _gallery_item_to_dict(item) -> dict:
    return {
        "gid": item.gid, "token": item.token, "title": item.title,
        "category": item.category, "uploader": item.uploader,
        "thumb_url": item.thumb_url, "posted": item.posted,
        "rating": item.rating, "pages": item.pages,
        "rated": item.rated,
        "thumb_width": item.thumb_width, "thumb_height": item.thumb_height,
        "url": item.url,
    }


@router.get("")
async def get_favorites(
    slot: int = -1,
    page: int = 0,
    keyword: str = "",
    sn: bool = False,
    st: bool = False,
    sf: bool = False,
    api: ExhentaiAPI = Depends(get_api),
):
    resp = await api.get_favorites(favcat=slot, page=page, keyword=keyword, sn=sn, st=st, sf=sf)
    return {
        "categories": [{"slot": c.slot, "name": c.name, "count": c.count} for c in resp.categories],
        "galleries": [_gallery_item_to_dict(g) for g in resp.galleries],
    }


class AddFavoriteBody(BaseModel):
    gid: str
    token: str
    slot: int = 0
    note: str = ""


@router.post("")
async def add_favorite(body: AddFavoriteBody, api: ExhentaiAPI = Depends(get_api)):
    result = await api.add_favorite(body.gid, body.token, favcat=body.slot, favnote=body.note)
    return {"result": result}


class ModifyFavoritesBody(BaseModel):
    gids: list[str]
    action: str


@router.delete("")
async def modify_favorites(body: ModifyFavoritesBody, api: ExhentaiAPI = Depends(get_api)):
    result = await api.modify_favorites(body.gids, body.action)
    return {"result": result}
```

- [ ] **Step 4: Update routes/__init__.py**

```python
# pandora_daemon/routes/__init__.py
from fastapi import APIRouter
from pandora_daemon.routes.browse import router as browse_router
from pandora_daemon.routes.gallery import router as gallery_router
from pandora_daemon.routes.favorites import router as favorites_router

router = APIRouter()
router.include_router(browse_router)
router.include_router(gallery_router)
router.include_router(favorites_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_routes_favorites.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/routes/favorites.py pandora_daemon/routes/__init__.py tests/pandora_daemon/test_routes_favorites.py
git commit -m "feat(daemon): add favorites routes (list, add, modify)"
```

---

### Task 9: Downloads Routes

**Files:**
- Create: `pandora_daemon/routes/downloads.py`
- Modify: `pandora_daemon/routes/__init__.py`
- Create: `tests/pandora_daemon/test_routes_downloads.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_routes_downloads.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from pandora_daemon.routes.downloads import router
from pandora_daemon.state import AppState
from pandora_daemon.download import DownloadTask


def _make_app(mock_downloads):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.downloads = mock_downloads
    app.state.pandora = state
    return app


def test_submit_download():
    mock_dl = AsyncMock()
    task = DownloadTask(gid="123", token="abc", title="Test", total_pages=10, output_dir="/tmp/dl")
    mock_dl.submit.return_value = task
    app = _make_app(mock_dl)
    client = TestClient(app)
    resp = client.post("/api/downloads", json={"gid": "123", "token": "abc"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["gid"] == "123"
    assert data["status"] == "queued"


def test_submit_download_duplicate():
    mock_dl = AsyncMock()
    mock_dl.submit.side_effect = ValueError("already in queue")
    app = _make_app(mock_dl)
    client = TestClient(app)
    resp = client.post("/api/downloads", json={"gid": "123", "token": "abc"})
    assert resp.status_code == 409


def test_get_downloads():
    mock_dl = MagicMock()
    task = DownloadTask(gid="123", token="abc", title="Test", total_pages=10, output_dir="/tmp/dl")
    mock_dl.status.return_value = [task]
    app = _make_app(mock_dl)
    client = TestClient(app)
    resp = client.get("/api/downloads")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1


def test_cancel_download():
    mock_dl = AsyncMock()
    mock_dl.cancel.return_value = True
    app = _make_app(mock_dl)
    client = TestClient(app)
    resp = client.delete("/api/downloads/123")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_cancel_nonexistent():
    mock_dl = AsyncMock()
    mock_dl.cancel.return_value = False
    app = _make_app(mock_dl)
    client = TestClient(app)
    resp = client.delete("/api/downloads/999")
    assert resp.status_code == 200
    assert resp.json()["success"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_downloads.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement routes/downloads.py**

```python
# pandora_daemon/routes/downloads.py
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
    try:
        task = await downloads.submit(body.gid, body.token)
        return task.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("")
async def list_downloads(downloads: DownloadManager = Depends(get_downloads)):
    tasks = downloads.status()
    return [t.to_dict() for t in tasks]


@router.delete("/{gid}")
async def cancel_download(gid: str, downloads: DownloadManager = Depends(get_downloads)):
    result = await downloads.cancel(gid)
    return {"success": result}
```

- [ ] **Step 4: Update routes/__init__.py**

```python
# pandora_daemon/routes/__init__.py
from fastapi import APIRouter
from pandora_daemon.routes.browse import router as browse_router
from pandora_daemon.routes.gallery import router as gallery_router
from pandora_daemon.routes.favorites import router as favorites_router
from pandora_daemon.routes.downloads import router as downloads_router

router = APIRouter()
router.include_router(browse_router)
router.include_router(gallery_router)
router.include_router(favorites_router)
router.include_router(downloads_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_routes_downloads.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/routes/downloads.py pandora_daemon/routes/__init__.py tests/pandora_daemon/test_routes_downloads.py
git commit -m "feat(daemon): add download routes (submit, status, cancel)"
```

---

### Task 10: User Routes

**Files:**
- Create: `pandora_daemon/routes/user.py`
- Modify: `pandora_daemon/routes/__init__.py`
- Create: `tests/pandora_daemon/test_routes_user.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_routes_user.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from pandora_daemon.routes.user import router
from pandora_daemon.state import AppState


def _make_app(mock_api):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.api = mock_api
    app.state.pandora = state
    return app


def test_get_home():
    mock_api = AsyncMock()
    home = MagicMock()
    home.image_used = 100
    home.image_total = 5000
    home.reset_cost = 1000
    mock_api.get_home_detail.return_value = home
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/home")
    assert resp.status_code == 200
    data = resp.json()
    assert data["image_used"] == 100


def test_reset_limit():
    mock_api = AsyncMock()
    home = MagicMock()
    home.image_used = 0
    home.image_total = 5000
    home.reset_cost = 1000
    mock_api.reset_image_limit.return_value = home
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.post("/api/home/reset_limit")
    assert resp.status_code == 200


def test_get_profile():
    mock_api = AsyncMock()
    profile = MagicMock()
    profile.display_name = "TestUser"
    profile.avatar_url = "https://ex.com/avatar.jpg"
    mock_api.get_profile.return_value = profile
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/profile")
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "TestUser"


def test_get_tags():
    mock_api = AsyncMock()
    tag = MagicMock()
    tag.id = 1
    tag.name = "artist:test"
    tag.watched = True
    tag.hidden = False
    tag.color = ""
    tag.weight = 0
    mock_api.get_mytags.return_value = [tag]
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.get("/api/tags")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_add_tag():
    mock_api = AsyncMock()
    mock_api.add_tag.return_value = []
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.post("/api/tags", json={"name": "artist:test", "watched": True})
    assert resp.status_code == 200
    mock_api.add_tag.assert_awaited_once()


def test_delete_tag():
    mock_api = AsyncMock()
    mock_api.delete_tag.return_value = []
    app = _make_app(mock_api)
    client = TestClient(app)
    resp = client.delete("/api/tags/42")
    assert resp.status_code == 200
    mock_api.delete_tag.assert_awaited_once_with(42)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_user.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement routes/user.py**

```python
# pandora_daemon/routes/user.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from exhentai_api.api import ExhentaiAPI
from pandora_daemon.dependencies import get_api

router = APIRouter(prefix="/api", tags=["user"])


def _home_to_dict(h) -> dict:
    return {
        "image_used": h.image_used,
        "image_total": h.image_total,
        "reset_cost": h.reset_cost,
    }


def _profile_to_dict(p) -> dict:
    return {
        "display_name": p.display_name,
        "avatar_url": p.avatar_url,
    }


def _tag_to_dict(t) -> dict:
    return {
        "id": t.id, "name": t.name,
        "watched": t.watched, "hidden": t.hidden,
        "color": t.color, "weight": t.weight,
    }


@router.get("/home")
async def get_home(api: ExhentaiAPI = Depends(get_api)):
    detail = await api.get_home_detail()
    return _home_to_dict(detail)


@router.post("/home/reset_limit")
async def reset_limit(api: ExhentaiAPI = Depends(get_api)):
    detail = await api.reset_image_limit()
    return _home_to_dict(detail)


@router.get("/profile")
async def get_profile(api: ExhentaiAPI = Depends(get_api)):
    profile = await api.get_profile()
    return _profile_to_dict(profile)


@router.get("/tags")
async def get_tags(api: ExhentaiAPI = Depends(get_api)):
    tags = await api.get_mytags()
    return [_tag_to_dict(t) for t in tags]


class AddTagBody(BaseModel):
    name: str
    watched: bool = False
    hidden: bool = False
    color: str = ""
    weight: int = 0


@router.post("/tags")
async def add_tag(body: AddTagBody, api: ExhentaiAPI = Depends(get_api)):
    tags = await api.add_tag(body.name, watched=body.watched, hidden=body.hidden, color=body.color, weight=body.weight)
    return [_tag_to_dict(t) for t in tags]


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, api: ExhentaiAPI = Depends(get_api)):
    tags = await api.delete_tag(tag_id)
    return [_tag_to_dict(t) for t in tags]
```

- [ ] **Step 4: Update routes/__init__.py**

```python
# pandora_daemon/routes/__init__.py
from fastapi import APIRouter
from pandora_daemon.routes.browse import router as browse_router
from pandora_daemon.routes.gallery import router as gallery_router
from pandora_daemon.routes.favorites import router as favorites_router
from pandora_daemon.routes.downloads import router as downloads_router
from pandora_daemon.routes.user import router as user_router

router = APIRouter()
router.include_router(browse_router)
router.include_router(gallery_router)
router.include_router(favorites_router)
router.include_router(downloads_router)
router.include_router(user_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_routes_user.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/routes/user.py pandora_daemon/routes/__init__.py tests/pandora_daemon/test_routes_user.py
git commit -m "feat(daemon): add user routes (home, profile, tags)"
```

---

### Task 11: Config Routes and WebSocket Endpoint

**Files:**
- Create: `pandora_daemon/routes/config_routes.py`
- Modify: `pandora_daemon/routes/__init__.py`
- Create: `tests/pandora_daemon/test_routes_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_routes_config.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from pathlib import Path

from pandora_daemon.routes.config_routes import router
from pandora_daemon.state import AppState
from pandora_daemon.config import PandoraConfig


def _make_app(config=None, config_path=None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.config = config or PandoraConfig()
    state.config_path = config_path or Path("/tmp/config.toml")
    state.ws = MagicMock()
    app.state.pandora = state
    return app, state


def test_get_config():
    app, state = _make_app()
    state.config.credentials.igneous = "secret"
    client = TestClient(app)
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "credentials" not in data
    assert data["server"]["port"] == 7860


def test_update_config(tmp_path):
    config_path = tmp_path / "config.toml"
    app, state = _make_app(config_path=config_path)
    client = TestClient(app)
    with patch("pandora_daemon.routes.config_routes.save_config") as mock_save:
        resp = client.put("/api/config", json={"server": {"port": 9999}})
        assert resp.status_code == 200
        assert state.config.server.port == 9999
        mock_save.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_config.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement routes/config_routes.py**

```python
# pandora_daemon/routes/config_routes.py
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from pandora_daemon.dependencies import get_state
from pandora_daemon.state import AppState
from pandora_daemon.config import save_config

router = APIRouter(tags=["config"])


@router.get("/api/config")
async def get_config(state: AppState = Depends(get_state)):
    return state.config.to_public_dict()


@router.put("/api/config")
async def update_config(body: dict, state: AppState = Depends(get_state)):
    config = state.config
    if "server" in body:
        for k, v in body["server"].items():
            if hasattr(config.server, k):
                setattr(config.server, k, v)
    if "download" in body:
        for k, v in body["download"].items():
            if hasattr(config.download, k):
                setattr(config.download, k, v)
    if "cache" in body:
        for k, v in body["cache"].items():
            if hasattr(config.cache, k):
                setattr(config.cache, k, v)
    save_config(config, state.config_path)
    return config.to_public_dict()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, state: AppState = Depends(get_state)):
    await state.ws.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        state.ws.disconnect(ws)
```

- [ ] **Step 4: Update routes/__init__.py (final version)**

```python
# pandora_daemon/routes/__init__.py
from fastapi import APIRouter
from pandora_daemon.routes.browse import router as browse_router
from pandora_daemon.routes.gallery import router as gallery_router
from pandora_daemon.routes.favorites import router as favorites_router
from pandora_daemon.routes.downloads import router as downloads_router
from pandora_daemon.routes.user import router as user_router
from pandora_daemon.routes.config_routes import router as config_router

router = APIRouter()
router.include_router(browse_router)
router.include_router(gallery_router)
router.include_router(favorites_router)
router.include_router(downloads_router)
router.include_router(user_router)
router.include_router(config_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_routes_config.py -v`
Expected: All 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/routes/config_routes.py pandora_daemon/routes/__init__.py tests/pandora_daemon/test_routes_config.py
git commit -m "feat(daemon): add config routes, WebSocket endpoint, and wire all routes"
```

---

### Task 12: Error Handling and Full Integration Test

**Files:**
- Modify: `pandora_daemon/app.py` (add error handler)
- Create: `tests/pandora_daemon/test_integration.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_integration.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from pathlib import Path

from pandora_daemon.app import create_app
from pandora_daemon.state import AppState
from pandora_daemon.config import PandoraConfig
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager


@pytest.fixture
def mock_state(tmp_path):
    config = PandoraConfig()
    config_path = tmp_path / "config.toml"
    mock_api = AsyncMock()
    mock_client = AsyncMock()
    mock_api.client = mock_client

    cache_config = config.cache
    cache_config.thumb_dir = str(tmp_path / "thumbs")
    cache = CacheManager(cache_config)
    ws = WebSocketManager()
    state_file = tmp_path / "downloads.json"
    downloads = DownloadManager(api=mock_api, config=config.download, ws=ws, state_file=state_file)

    state = AppState(
        config=config, config_path=config_path,
        client=mock_client, api=mock_api,
        downloads=downloads, cache=cache, ws=ws,
    )
    return state, mock_api


def _make_test_app(mock_state):
    state, mock_api = mock_state
    from pandora_daemon.routes import router
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.exception_handler(RuntimeError)
    async def sad_panda_handler(request: Request, exc: RuntimeError):
        if "Sad Panda" in str(exc):
            return JSONResponse(status_code=401, content={"detail": str(exc)})
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    app.include_router(router)
    app.state.pandora = state
    return app


def test_homepage_returns_galleries(mock_state):
    state, mock_api = mock_state
    item = MagicMock()
    item.gid = "1"
    item.token = "abc"
    item.title = "Test"
    item.category = "Manga"
    item.uploader = "user"
    item.thumb_url = "https://ex.com/t.jpg"
    item.posted = "2026-01-01"
    item.rating = 4.5
    item.pages = 20
    item.rated = False
    item.thumb_width = 250
    item.thumb_height = 356
    item.url = "https://exhentai.org/g/1/abc/"
    mock_api.get_homepage.return_value = [item]
    app = _make_test_app(mock_state)
    client = TestClient(app)
    resp = client.get("/api/homepage")
    assert resp.status_code == 200
    assert resp.json()[0]["title"] == "Test"


def test_sad_panda_returns_401(mock_state):
    state, mock_api = mock_state
    mock_api.get_homepage.side_effect = RuntimeError("Sad Panda: You do not have permission")
    app = _make_test_app(mock_state)
    client = TestClient(app)
    resp = client.get("/api/homepage")
    assert resp.status_code == 401


def test_search_passes_params(mock_state):
    state, mock_api = mock_state
    mock_api.search.return_value = []
    app = _make_test_app(mock_state)
    client = TestClient(app)
    resp = client.get("/api/search", params={"keyword": "fate", "page": 2, "min_rating": 4})
    assert resp.status_code == 200
    call_args = mock_api.search.call_args
    params = call_args[0][0]  # first positional arg is SearchParams
    assert params.f_search == "fate"
    assert params.f_sr is True
    assert params.f_srdd == 4
    assert call_args[1]["page"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_integration.py -v`
Expected: FAIL (sad panda handler not in routes)

- [ ] **Step 3: Add error handler to app.py**

Add to `create_app()` in `pandora_daemon/app.py`:

```python
# pandora_daemon/app.py
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from pandora_daemon.config import load_config
from pandora_daemon.state import AppState
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_path = Path("~/.config/pandora/config.toml").expanduser()
    config = load_config(config_path)

    client = ExhentaiClient(
        igneous=config.credentials.igneous,
        ipb_member_id=config.credentials.ipb_member_id,
    )
    api = ExhentaiAPI(client=client)
    cache = CacheManager(config.cache)
    ws = WebSocketManager()
    state_file = config_path.parent / "downloads.json"
    downloads = DownloadManager(api=api, config=config.download, ws=ws, state_file=state_file)

    state = AppState(
        config=config, config_path=config_path,
        client=client, api=api,
        downloads=downloads, cache=cache, ws=ws,
    )
    app.state.pandora = state

    await downloads.start()
    yield
    await downloads.shutdown()
    await api.aclose()


def create_app() -> FastAPI:
    from pandora_daemon.routes import router
    app = FastAPI(title="pandora-daemon", lifespan=lifespan)

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError):
        if "Sad Panda" in str(exc):
            return JSONResponse(status_code=401, content={"detail": str(exc)})
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    app.include_router(router)
    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_integration.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All existing tests PASS + all new daemon tests PASS

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/app.py tests/pandora_daemon/test_integration.py
git commit -m "feat(daemon): add error handling and integration tests"
```

---

## Verification

After all tasks are complete:

1. Run full test suite: `uv run pytest tests/ -v` — all tests should pass
2. Verify daemon starts: `uv run python -m pandora_daemon` — should bind to localhost:7860 (will fail to connect to ExHentai without credentials, which is expected)
3. Verify API docs: open `http://localhost:7860/docs` — FastAPI auto-generated Swagger UI should show all endpoints

## Spec Coverage Checklist

| Spec Section | Task |
|-------------|------|
| 1. Configuration | Task 1 |
| 2. Application State | Task 5 |
| 3. Application Lifespan | Task 5 |
| 4. Dependencies | Task 5 |
| 5.1 Browse Routes | Task 6 |
| 5.2 Gallery Routes | Task 7 |
| 5.3 Favorites Routes | Task 8 |
| 5.4 Downloads Routes | Task 9 |
| 5.5 User Routes | Task 10 |
| 5.6 Config Routes | Task 11 |
| 5.7 Thumbnails | Task 6 |
| 6. Download Manager | Task 4 |
| 7. Cache Manager | Task 3 |
| 8. WebSocket Manager | Task 2 |
| 9. Entry Point | Task 5 |
| 10. Error Handling | Task 12 |
| 11. Dependencies (pyproject) | Task 1 |
| 12. Testing Strategy | All tasks (TDD) |
