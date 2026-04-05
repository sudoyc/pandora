# P2 AppState 生命周期 — 设计文档

**日期:** 2026-04-05
**状态:** 已批准
**范围:** pandora-daemon AppState 生命周期管理

## 背景

`AppState` 是纯 dataclass，没有生命周期方法。所有组件的启动和关闭逻辑散落在 `app.py` 的 `lifespan` 函数中，包括 `downloads.start()`、eviction task 的创建/取消、以及四个组件的 shutdown 调用。随着后台任务增多，lifespan 会越来越臃肿。

## 方案选择

| 方案 | 描述 | 结论 |
|------|------|------|
| A AppState 全管 | `start()` 启动后台任务，`shutdown()` 统一关闭 | ✅ 采用 |
| B 仅 shutdown | AppState 只管关闭，eviction task 留在 lifespan | ❌ 半吊子，lifespan 仍需管理后台任务 |
| C 不改 | 维持现状 | ❌ 随功能增长 lifespan 会膨胀 |

选择 A 的理由：AppState 已经持有所有组件引用，让它管理完整生命周期是自然的职责归属。lifespan 简化为 build → start → yield → shutdown 四行。

## 设计

### 1. state.py — 新增生命周期方法

`AppState` 新增字段和方法：

```python
from __future__ import annotations
import asyncio
import contextlib

@dataclass
class AppState:
    # ... 现有字段 ...
    _eviction_task: asyncio.Task | None = field(default=None, init=False, repr=False)

    async def start(self, eviction_loop_coro) -> None:
        """启动后台任务。"""
        await self.downloads.start()
        self._eviction_task = asyncio.create_task(eviction_loop_coro)

    async def shutdown(self) -> None:
        """统一关闭所有子组件。顺序：后台任务 → 业务组件 → 底层连接。"""
        if self._eviction_task is not None:
            self._eviction_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._eviction_task
        await self.downloads.shutdown()
        await self.image_service.shutdown()
        await self.db.close()
        await self.api.aclose()
```

`start()` 接收 eviction loop 协程而非自己构造，因为 `_cache_eviction_loop` 是 `app.py` 的模块级函数，不属于 AppState 的职责。

shutdown 顺序：
1. 取消 eviction task（停止后台调度）
2. `downloads.shutdown()`（停止下载 worker）
3. `image_service.shutdown()`（取消 prefetch 任务）
4. `db.close()`（关闭数据库连接）
5. `api.aclose()`（关闭 HTTP 客户端）

### 2. app.py — 提取 `_build_state()` + 简化 lifespan

新增模块级工厂函数：

```python
async def _build_state() -> AppState:
    """构建所有组件，返回 AppState。"""
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
        pass
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
```

lifespan 简化为：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    state = await _build_state()
    app.state.pandora = state
    await state.start(
        _cache_eviction_loop(state.cache, state.config.cache.eviction_interval_seconds)
    )
    yield
    await state.shutdown()
```

### 3. `_cache_eviction_loop` — 不改

保持为 `app.py` 的模块级协程，签名和实现不变。

### 4. dependencies.py — 不改

`get_state()` 等依赖注入函数不受影响，`AppState` 的公开字段没有变化。

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `pandora_daemon/state.py` | 新增 `_eviction_task` 字段、`start()` 和 `shutdown()` 方法 |
| `pandora_daemon/app.py` | 提取 `_build_state()`，简化 `lifespan` |

## 测试计划

| 测试 | 验证点 |
|------|--------|
| `test_appstate_start_calls_downloads_and_creates_task` | `start()` 调用 `downloads.start()` 并创建 eviction task |
| `test_appstate_shutdown_order` | `shutdown()` 按正确顺序调用所有组件的关闭方法 |
| `test_appstate_shutdown_cancels_eviction_task` | `shutdown()` 取消 eviction task 且不抛异常 |
| `test_appstate_shutdown_without_start` | 未调用 `start()` 时 `shutdown()` 不报错（`_eviction_task` 为 None） |
| `test_build_state_returns_appstate` | `_build_state()` 返回正确构造的 AppState |
| `test_lifespan_integration` | lifespan 正确调用 start/shutdown |
