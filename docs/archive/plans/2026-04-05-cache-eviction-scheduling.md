# P1 缓存淘汰调度 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up the existing `evict_images()` and `prune_expired_galleries()` methods via a background asyncio loop, with configurable interval.

**Architecture:** A module-level `_cache_eviction_loop` coroutine in `app.py` runs every `eviction_interval_seconds` (default 600), calling `prune_expired_galleries()` then `evict_images()`. Exceptions are caught and logged. The task is created in `lifespan` before yield and cancelled after yield.

**Tech Stack:** Python asyncio, FastAPI lifespan, logging

**Spec:** `docs/superpowers/specs/2026-04-05-cache-eviction-scheduling-design.md`

---

### Task 1: Add `eviction_interval_seconds` to CacheConfig

**Files:**
- Modify: `pandora_daemon/config.py:46-53` (CacheConfig dataclass)
- Modify: `pandora_daemon/config.py:89-96` (to_public_dict cache section)
- Modify: `pandora_daemon/config.py:149-156` (load_config cache parsing)
- Test: `tests/pandora_daemon/test_config.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/pandora_daemon/test_config.py` class `TestDefaultConfig`:

```python
def test_default_cache_eviction_interval(self):
    cache = CacheConfig()
    assert cache.eviction_interval_seconds == 600
```

Add to class `TestLoadConfig`:

```python
def test_load_config_custom_eviction_interval(self, tmp_path):
    config_path = tmp_path / "config.toml"
    data = {"cache": {"eviction_interval_seconds": 120}}
    config_path.write_bytes(tomli_w.dumps(data).encode())
    cfg = load_config(config_path)
    assert cfg.cache.eviction_interval_seconds == 120
```

Add to class `TestToPublicDict`:

```python
def test_to_public_dict_contains_eviction_interval(self):
    cfg = PandoraConfig()
    d = cfg.to_public_dict()
    assert "eviction_interval_seconds" in d["cache"]
    assert d["cache"]["eviction_interval_seconds"] == 600
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_config.py::TestDefaultConfig::test_default_cache_eviction_interval tests/pandora_daemon/test_config.py::TestLoadConfig::test_load_config_custom_eviction_interval tests/pandora_daemon/test_config.py::TestToPublicDict::test_to_public_dict_contains_eviction_interval -v`
Expected: FAIL — `CacheConfig` has no `eviction_interval_seconds` attribute

- [ ] **Step 3: Implement**

In `pandora_daemon/config.py`, add field to `CacheConfig` (line 53):

```python
@dataclass
class CacheConfig:
    """Cache settings."""

    image_dir: str = "~/.cache/pandora/images"
    image_max_size_mb: int = 2048
    gallery_ttl_seconds: int = 300
    prefetch_ahead: int = 3
    prefetch_behind: int = 1
    eviction_interval_seconds: int = 600
```

In `to_public_dict` cache section (around line 91), add the new field:

```python
"cache": {
    "image_dir": self.cache.image_dir,
    "image_max_size_mb": self.cache.image_max_size_mb,
    "gallery_ttl_seconds": self.cache.gallery_ttl_seconds,
    "prefetch_ahead": self.cache.prefetch_ahead,
    "prefetch_behind": self.cache.prefetch_behind,
    "eviction_interval_seconds": self.cache.eviction_interval_seconds,
},
```

In `load_config` cache parsing (around line 149), add:

```python
cache = CacheConfig(
    image_dir=cache_data.get("image_dir", "~/.cache/pandora/images"),
    image_max_size_mb=cache_data.get("image_max_size_mb", 2048),
    gallery_ttl_seconds=cache_data.get("gallery_ttl_seconds", 300),
    prefetch_ahead=cache_data.get("prefetch_ahead", 3),
    prefetch_behind=cache_data.get("prefetch_behind", 1),
    eviction_interval_seconds=cache_data.get("eviction_interval_seconds", 600),
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/config.py tests/pandora_daemon/test_config.py
git commit -m "feat(config): add eviction_interval_seconds to CacheConfig"
```

---

### Task 2: Add `_cache_eviction_loop` to app.py and wire into lifespan

**Files:**
- Modify: `pandora_daemon/app.py:1-59` (add import, loop function, lifespan changes)
- Create: `tests/pandora_daemon/test_cache_eviction.py`

- [ ] **Step 1: Write failing tests**

Create `tests/pandora_daemon/test_cache_eviction.py`:

```python
"""Tests for cache eviction loop in app.py."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pandora_daemon.app import _cache_eviction_loop


class TestCacheEvictionLoop:
    @pytest.mark.asyncio
    async def test_calls_prune_then_evict(self):
        """Loop calls prune_expired_galleries then evict_images each cycle."""
        cache = MagicMock()
        cache.prune_expired_galleries = MagicMock()
        cache.evict_images = AsyncMock()

        call_order = []
        cache.prune_expired_galleries.side_effect = lambda: call_order.append("prune")
        cache.evict_images.side_effect = lambda: call_order.append("evict")

        task = asyncio.create_task(_cache_eviction_loop(cache, interval=0))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert cache.prune_expired_galleries.call_count >= 1
        assert cache.evict_images.call_count >= 1
        # Verify ordering: each prune is followed by evict
        for i in range(0, len(call_order) - 1, 2):
            assert call_order[i] == "prune"
            assert call_order[i + 1] == "evict"

    @pytest.mark.asyncio
    async def test_exception_resilience(self):
        """If evict_images raises, the loop continues running."""
        cache = MagicMock()
        cache.prune_expired_galleries = MagicMock()
        call_count = 0

        async def evict_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("disk error")

        cache.evict_images = AsyncMock(side_effect=evict_side_effect)

        task = asyncio.create_task(_cache_eviction_loop(cache, interval=0))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Loop survived the first exception and ran again
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_cancel_exits_cleanly(self):
        """Cancelling the task raises CancelledError, no other exception."""
        cache = MagicMock()
        cache.prune_expired_galleries = MagicMock()
        cache.evict_images = AsyncMock()

        task = asyncio.create_task(_cache_eviction_loop(cache, interval=9999))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_cache_eviction.py -v`
Expected: FAIL — `cannot import name '_cache_eviction_loop' from 'pandora_daemon.app'`

- [ ] **Step 3: Implement `_cache_eviction_loop`**

In `pandora_daemon/app.py`, add imports at top (after existing imports):

```python
import asyncio
import contextlib
import logging

logger = logging.getLogger(__name__)
```

Add the loop function before `lifespan`:

```python
async def _cache_eviction_loop(cache: CacheManager, interval: int) -> None:
    """Background loop: periodically prune expired galleries and evict images."""
    while True:
        await asyncio.sleep(interval)
        try:
            cache.prune_expired_galleries()
            await cache.evict_images()
        except Exception:
            logger.exception("Cache eviction error")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_cache_eviction.py -v`
Expected: ALL PASS

- [ ] **Step 5: Wire into lifespan**

In `pandora_daemon/app.py`, modify the `lifespan` function. After `await downloads.start()` (line 54), add:

```python
    eviction_task = asyncio.create_task(
        _cache_eviction_loop(cache, config.cache.eviction_interval_seconds)
    )
```

After `yield` (line 55→56), before `await db.close()`, add:

```python
    eviction_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await eviction_task
```

The full lifespan should look like:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
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
    downloads = DownloadManager(api=api, config=config.download, ws=ws, image_service=image_service, state_file=state_file)
    state = AppState(
        config=config, config_path=config_path,
        client=client, api=api,
        downloads=downloads, cache=cache, image_service=image_service, ws=ws,
        db=db, tag_database=tag_database,
    )
    app.state.pandora = state
    await downloads.start()
    eviction_task = asyncio.create_task(
        _cache_eviction_loop(cache, config.cache.eviction_interval_seconds)
    )
    yield
    eviction_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await eviction_task
    await db.close()
    await downloads.shutdown()
    await image_service.shutdown()
    await api.aclose()
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add pandora_daemon/app.py tests/pandora_daemon/test_cache_eviction.py
git commit -m "feat(app): add cache eviction loop with configurable interval"
```

---

### Task 3: Update CLAUDE.md and IMPROVEMENTS.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `IMPROVEMENTS.md`

- [ ] **Step 1: Update IMPROVEMENTS.md**

Mark P1 缓存淘汰调度 as ✅ 已完成:

```
| P1 | 缓存淘汰调度 — `cache.py` + `app.py`: 定时 LRU 淘汰, 磁盘空间管理 | ✅ 已完成 |
```

- [ ] **Step 2: Update CLAUDE.md**

In the `cache.py` description, add mention of eviction scheduling:

```
- `cache.py` -- Unified image cache (SHA256(URL), LRU eviction, 2GB default, async file I/O via run_in_executor) + in-memory gallery detail cache (TTL). Background eviction loop (configurable interval, default 600s)
```

In `app.py` description, add eviction task:

```
- `app.py` -- FastAPI app factory, lifespan (init/shutdown), exception handlers, background cache eviction task
```

In `CacheConfig` or config section, mention the new field if there's a relevant spot.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md IMPROVEMENTS.md
git commit -m "docs: mark P1 cache eviction scheduling as complete"
```
