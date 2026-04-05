# P2 AppState 生命周期 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `AppState` complete lifecycle management (`start()` / `shutdown()`), extract a `_build_state()` factory, and reduce `lifespan` to four lines.

**Architecture:** `AppState` gains `start(eviction_loop_coro)` which calls `downloads.start()` and creates the eviction task, and `shutdown()` which cancels the eviction task then closes all components in dependency order. A new `_build_state()` async factory in `app.py` constructs all components and returns `AppState`. The `lifespan` function becomes: build → start → yield → shutdown.

**Tech Stack:** Python asyncio, FastAPI lifespan, dataclasses

**Spec:** `docs/superpowers/specs/2026-04-05-appstate-lifecycle-design.md`

---

### Task 1: Add `start()` and `shutdown()` to AppState

**Files:**
- Modify: `pandora_daemon/state.py:1-25`
- Create: `tests/pandora_daemon/test_state.py`

- [ ] **Step 1: Write failing tests**

Create `tests/pandora_daemon/test_state.py`:

```python
"""Tests for AppState lifecycle methods."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from pandora_daemon.state import AppState


def _make_state() -> AppState:
    """Build an AppState with all-mock components."""
    downloads = MagicMock()
    downloads.start = AsyncMock()
    downloads.shutdown = AsyncMock()

    image_service = MagicMock()
    image_service.shutdown = AsyncMock()

    db = MagicMock()
    db.close = AsyncMock()

    api = MagicMock()
    api.aclose = AsyncMock()

    return AppState(
        config=MagicMock(),
        config_path=MagicMock(),
        client=MagicMock(),
        api=api,
        downloads=downloads,
        cache=MagicMock(),
        image_service=image_service,
        ws=MagicMock(),
        db=db,
        tag_database=MagicMock(),
    )


class TestAppStateStart:
    @pytest.mark.asyncio
    async def test_start_calls_downloads_start(self):
        state = _make_state()
        coro = AsyncMock()()  # a coroutine object
        await state.start(coro)
        state.downloads.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_creates_eviction_task(self):
        state = _make_state()
        started = asyncio.Event()

        async def fake_loop():
            started.set()
            await asyncio.sleep(9999)

        await state.start(fake_loop())
        await asyncio.sleep(0.01)
        assert started.is_set()
        assert state._eviction_task is not None
        assert not state._eviction_task.done()
        # cleanup
        state._eviction_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await state._eviction_task


class TestAppStateShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_order(self):
        """shutdown() calls components in correct order."""
        state = _make_state()
        order = []
        state.downloads.shutdown = AsyncMock(side_effect=lambda: order.append("downloads"))
        state.image_service.shutdown = AsyncMock(side_effect=lambda: order.append("image_service"))
        state.db.close = AsyncMock(side_effect=lambda: order.append("db"))
        state.api.aclose = AsyncMock(side_effect=lambda: order.append("api"))

        # start first so _eviction_task exists
        async def fake_loop():
            await asyncio.sleep(9999)

        await state.start(fake_loop())
        await state.shutdown()

        assert order == ["downloads", "image_service", "db", "api"]

    @pytest.mark.asyncio
    async def test_shutdown_cancels_eviction_task(self):
        state = _make_state()

        async def fake_loop():
            await asyncio.sleep(9999)

        await state.start(fake_loop())
        task = state._eviction_task
        await state.shutdown()
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_shutdown_without_start(self):
        """shutdown() works even if start() was never called."""
        state = _make_state()
        await state.shutdown()  # should not raise
        state.downloads.shutdown.assert_awaited_once()
        state.api.aclose.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_state.py -v`
Expected: FAIL — `AppState` has no `start` or `shutdown` method

- [ ] **Step 3: Implement**

Replace `pandora_daemon/state.py` with:

```python
from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from pandora_daemon.config import PandoraConfig
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager
from pandora_daemon.image_service import ImageService
from pandora_daemon.tag_database import TagDatabase
from pandora_daemon.db import PandoraDB


@dataclass
class AppState:
    config: PandoraConfig
    config_path: Path
    client: ExhentaiClient
    api: ExhentaiAPI
    downloads: DownloadManager
    cache: CacheManager
    image_service: ImageService
    ws: WebSocketManager
    db: PandoraDB
    tag_database: TagDatabase = field(default_factory=TagDatabase)
    _eviction_task: asyncio.Task[None] | None = field(
        default=None, init=False, repr=False
    )

    async def start(self, eviction_loop_coro: Any) -> None:
        """Start background tasks (downloads + cache eviction)."""
        await self.downloads.start()
        self._eviction_task = asyncio.create_task(eviction_loop_coro)

    async def shutdown(self) -> None:
        """Shut down all components in dependency order."""
        if self._eviction_task is not None:
            self._eviction_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._eviction_task
        await self.downloads.shutdown()
        await self.image_service.shutdown()
        await self.db.close()
        await self.api.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_state.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/state.py tests/pandora_daemon/test_state.py
git commit -m "feat(state): add start() and shutdown() lifecycle methods to AppState"
```

---

### Task 2: Extract `_build_state()` and simplify `lifespan` in app.py

**Files:**
- Modify: `pandora_daemon/app.py:1-83`
- Modify: `tests/pandora_daemon/test_cache_eviction.py` (import unchanged, just verify still passes)

- [ ] **Step 1: Write failing test for `_build_state`**

Create `tests/pandora_daemon/test_app_build_state.py`:

```python
"""Tests for _build_state factory in app.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pandora_daemon.state import AppState


class TestBuildState:
    @pytest.mark.asyncio
    async def test_build_state_returns_appstate(self, tmp_path):
        """_build_state() constructs and returns an AppState."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("")

        mock_config = MagicMock()
        mock_config.credentials.igneous = "test"
        mock_config.credentials.ipb_member_id = "test"
        mock_config.cache = MagicMock()
        mock_config.download = MagicMock()

        mock_db = MagicMock()
        mock_db.initialize = AsyncMock()

        mock_tag_db = MagicMock()
        mock_tag_db.download_and_load = AsyncMock()

        with (
            patch("pandora_daemon.app.Path") as mock_path_cls,
            patch("pandora_daemon.app.load_config", return_value=mock_config),
            patch("pandora_daemon.app.PandoraDB", return_value=mock_db),
            patch("pandora_daemon.app.ExhentaiClient"),
            patch("pandora_daemon.app.ExhentaiAPI"),
            patch("pandora_daemon.app.CacheManager"),
            patch("pandora_daemon.app.ImageService"),
            patch("pandora_daemon.app.WebSocketManager"),
            patch("pandora_daemon.app.TagDatabase", return_value=mock_tag_db),
            patch("pandora_daemon.app.DownloadManager"),
        ):
            mock_path_instance = MagicMock()
            mock_path_instance.expanduser.return_value = config_path
            mock_path_instance.parent = tmp_path
            mock_path_instance.__truediv__ = lambda self, other: tmp_path / other
            mock_path_cls.return_value = mock_path_instance

            from pandora_daemon.app import _build_state

            state = await _build_state()
            assert isinstance(state, AppState)
            mock_db.initialize.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pandora_daemon/test_app_build_state.py -v`
Expected: FAIL — `cannot import name '_build_state' from 'pandora_daemon.app'`

- [ ] **Step 3: Implement — rewrite app.py**

Replace `pandora_daemon/app.py` with:

```python
import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from exhentai_api.exceptions import (
    ExhentaiError,
    AuthenticationError,
    ImageLimitError,
    GalleryNotFoundError,
    GalleryOffensiveError,
    ParseError,
    NetworkError,
)
from pandora_daemon.config import load_config
from pandora_daemon.state import AppState
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager
from pandora_daemon.image_service import ImageService
from pandora_daemon.tag_database import TagDatabase
from pandora_daemon.db import PandoraDB

logger = logging.getLogger(__name__)


async def _cache_eviction_loop(cache: CacheManager, interval: int) -> None:
    """Background loop: periodically prune expired galleries and evict images."""
    while True:
        await asyncio.sleep(interval)
        try:
            cache.prune_expired_galleries()
            await cache.evict_images()
        except Exception:
            logger.exception("Cache eviction error")


async def _build_state() -> AppState:
    """Construct all components and return an AppState."""
    config_path = Path("~/.config/pandora/config.toml").expanduser()
    config = load_config(config_path)
    db_path = config_path.parent / "pandora.db"
    db = PandoraDB(db_path)
    await db.initialize()
    client = ExhentaiClient(
        igneous=config.credentials.igneous,
        ipb_member_id=config.credentials.ipb_member_id,
    )
    api = ExhentaiAPI(client=client)
    cache = CacheManager(config.cache)
    image_service = ImageService(api=api, cache=cache, config=config.cache)
    ws = WebSocketManager()
    tag_database = TagDatabase()
    try:
        await tag_database.download_and_load()
    except Exception:
        pass  # Non-fatal: suggest will return empty results
    state_file = config_path.parent / "downloads.json"
    downloads = DownloadManager(
        api=api, config=config.download, ws=ws,
        image_service=image_service, state_file=state_file,
    )
    return AppState(
        config=config, config_path=config_path,
        client=client, api=api,
        downloads=downloads, cache=cache,
        image_service=image_service, ws=ws,
        db=db, tag_database=tag_database,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = await _build_state()
    app.state.pandora = state
    await state.start(
        _cache_eviction_loop(state.cache, state.config.cache.eviction_interval_seconds)
    )
    yield
    await state.shutdown()


def create_app() -> FastAPI:
    from pandora_daemon.routes import router
    app = FastAPI(title="pandora-daemon", lifespan=lifespan)

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request: Request, exc: AuthenticationError):
        return JSONResponse(status_code=401, content={"error": "auth", "detail": str(exc)})

    @app.exception_handler(GalleryNotFoundError)
    async def gallery_not_found_handler(request: Request, exc: GalleryNotFoundError):
        return JSONResponse(status_code=404, content={"error": "gallery_not_found", "detail": str(exc)})

    @app.exception_handler(ImageLimitError)
    async def image_limit_handler(request: Request, exc: ImageLimitError):
        return JSONResponse(status_code=429, content={"error": "image_limit", "detail": str(exc)})

    @app.exception_handler(GalleryOffensiveError)
    async def offensive_handler(request: Request, exc: GalleryOffensiveError):
        return JSONResponse(status_code=451, content={"error": "offensive", "detail": str(exc)})

    @app.exception_handler(ParseError)
    async def parse_error_handler(request: Request, exc: ParseError):
        return JSONResponse(status_code=502, content={"error": "parse", "detail": str(exc)})

    @app.exception_handler(NetworkError)
    async def network_error_handler(request: Request, exc: NetworkError):
        return JSONResponse(status_code=502, content={"error": "network", "detail": str(exc)})

    @app.exception_handler(ExhentaiError)
    async def exhentai_error_handler(request: Request, exc: ExhentaiError):
        return JSONResponse(status_code=500, content={"error": "exhentai", "detail": str(exc)})

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    app.include_router(router)
    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_app_build_state.py tests/pandora_daemon/test_cache_eviction.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS (390+ tests)

- [ ] **Step 6: Commit**

```bash
git add pandora_daemon/app.py tests/pandora_daemon/test_app_build_state.py
git commit -m "feat(app): extract _build_state() and simplify lifespan"
```

---

### Task 3: Update CLAUDE.md and IMPROVEMENTS.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `IMPROVEMENTS.md`

- [ ] **Step 1: Update IMPROVEMENTS.md**

Change the P2 AppState 生命周期 row in the priority table (line 829) from:

```
| **P2** | AppState 生命周期 (第 5 章) | 代码整洁性 | 修改 `state.py` + `app.py` | 待实施 |
```

to:

```
| **P2** | AppState 生命周期 (第 5 章) | 代码整洁性 | 修改 `state.py` + `app.py` | ✅ 已完成 |
```

- [ ] **Step 2: Update CLAUDE.md**

In the `state.py` description, update to mention lifecycle methods:

```
- `state.py` -- Shared application state (AppState dataclass with start/shutdown lifecycle, manages eviction task, includes TagDatabase, PandoraDB)
```

In the `app.py` description, update to mention `_build_state`:

```
- `app.py` -- FastAPI app factory, `_build_state()` component factory, `_cache_eviction_loop`, lifespan (build → start → yield → shutdown), exception handlers
```

In the IMPROVEMENTS ROADMAP table, update P2 status:

```
| P2 | AppState 生命周期 — `state.py` + `app.py`: start/shutdown 生命周期, _build_state 工厂 | ✅ 已完成 |
```

Update NEXT STEPS to point to P2 网络代理配置:

```
### Next: P2 网络代理配置 (IMPROVEMENTS.md 第 6 章)
- 核心改进：config.py + client.py 代理支持
- 详细设计见 `IMPROVEMENTS.md` 第 6 章
```

- [ ] **Step 3: Commit**

```bash
git add IMPROVEMENTS.md
git commit -m "docs: mark P2 AppState lifecycle as complete"
```

Note: `CLAUDE.md` is in `.gitignore` and should not be committed.
