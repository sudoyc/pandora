# Pandora 架构改进设计文档

> 本文档描述 Pandora 项目当前缺失的功能模块和需要改进的设计。  
> 预期读者：负责实现的 Claude Code 实例。请配合 `ARCHITECTURE.md` (EhViewer 参考架构) 一起阅读。

---

## 目录

1. [数据库层设计](#1-数据库层设计)
2. [下载系统改进](#2-下载系统改进)
3. [异常体系设计](#3-异常体系设计)
4. [缓存淘汰调度](#4-缓存淘汰调度)
5. [AppState 生命周期](#5-appstate-生命周期)
6. [网络代理配置](#6-网络代理配置)
7. [杂项修正](#7-杂项修正)
8. [实施优先级](#8-实施优先级)

---

## 1. 数据库层设计

### 1.1 现状问题

Pandora 目前**没有任何本地数据库**。用户的浏览历史、收藏、阅读进度、搜索偏好等数据在 daemon 重启后全部丢失。下载状态虽然用 `downloads.json` 做了文件持久化，但缺少结构化查询能力。

### 1.2 技术选型

- **数据库**：SQLite (通过 `aiosqlite` 异步访问)
- **文件位置**：`~/.config/pandora/pandora.db`
- **迁移方式**：手动版本号 + SQL 迁移脚本 (参考 EhViewer 的 `upgradeDB()` 模式)
- **不使用 ORM**：项目规模不大，直接用 SQL 更清晰，避免引入 SQLAlchemy 等重依赖

### 1.3 新建文件

```
pandora_daemon/
  db.py          # 数据库门面类 (类似 EhViewer 的 EhDB.java)
```

### 1.4 表结构设计

#### 1.4.1 history (浏览历史)

用户每次打开一个画廊详情时，daemon 自动记录一条浏览历史。

```sql
CREATE TABLE history (
    gid        TEXT PRIMARY KEY,
    token      TEXT NOT NULL,
    title      TEXT NOT NULL,
    title_jpn  TEXT,
    category   TEXT NOT NULL DEFAULT '',
    uploader   TEXT NOT NULL DEFAULT '',
    thumb_url  TEXT NOT NULL DEFAULT '',
    posted     TEXT NOT NULL DEFAULT '',
    rating     REAL NOT NULL DEFAULT 0.0,
    pages      INTEGER NOT NULL DEFAULT 0,
    read_page  INTEGER NOT NULL DEFAULT 0,   -- 上次阅读到第几页
    time       INTEGER NOT NULL               -- unix 时间戳
);
CREATE INDEX idx_history_time ON history(time DESC);
```

**触发点**：`GET /api/gallery/{gid}/{token}` 路由成功返回时，自动 upsert 一条记录。

**上限管理**：保留最近 200 条 (可配置)，超出时删除最旧记录。

#### 1.4.2 local_favorites (本地收藏)

（虽然我感觉电脑端的本地收藏和下载库重合了）

不依赖服务端的本地收藏功能。用户可以在断网状态下管理收藏。

```sql
CREATE TABLE local_favorites (
    gid        TEXT PRIMARY KEY,
    token      TEXT NOT NULL,
    title      TEXT NOT NULL,
    title_jpn  TEXT,
    category   TEXT NOT NULL DEFAULT '',
    uploader   TEXT NOT NULL DEFAULT '',
    thumb_url  TEXT NOT NULL DEFAULT '',
    posted     TEXT NOT NULL DEFAULT '',
    rating     REAL NOT NULL DEFAULT 0.0,
    pages      INTEGER NOT NULL DEFAULT 0,
    time       INTEGER NOT NULL               -- 收藏时间
);
CREATE INDEX idx_local_fav_time ON local_favorites(time DESC);
```

#### 1.4.3 bookmarks (阅读进度书签)

记录每个画廊的阅读位置，用户下次打开可以从上次位置继续。

```sql
CREATE TABLE bookmarks (
    gid        TEXT PRIMARY KEY,
    token      TEXT NOT NULL,
    title      TEXT NOT NULL,
    thumb_url  TEXT NOT NULL DEFAULT '',
    page       INTEGER NOT NULL,              -- 阅读到的页码
    total      INTEGER NOT NULL DEFAULT 0,    -- 画廊总页数
    time       INTEGER NOT NULL               -- 最后阅读时间
);
CREATE INDEX idx_bookmarks_time ON bookmarks(time DESC);
```

**触发点**：前端调用 `POST /api/gallery/{gid}/{token}/prefetch` 上报当前页码时，自动更新书签。

#### 1.4.4 quick_search (快速搜索)

保存用户常用的搜索条件组合，一键调出。

```sql
CREATE TABLE quick_search (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,                 -- 显示名称
    keyword    TEXT NOT NULL DEFAULT '',       -- 搜索关键词
    category   INTEGER,                       -- 分类掩码 (f_cats)
    min_rating INTEGER,                       -- 最低评分
    page_from  INTEGER,                       -- 起始页数
    page_to    INTEGER,                       -- 结束页数
    time       INTEGER NOT NULL               -- 创建时间
);
```

#### 1.4.5 filter (过滤规则)

本地过滤画廊列表结果，可按标题、上传者、标签过滤。

```sql
CREATE TABLE filter (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    mode       INTEGER NOT NULL,              -- 0=标题, 1=上传者, 2=标签, 3=标签命名空间
    text       TEXT NOT NULL,                 -- 过滤文本
    enabled    INTEGER NOT NULL DEFAULT 1     -- 1=启用, 0=禁用
);
```

**过滤模式**：

```python
FILTER_TITLE = 0           # 标题包含 text 则过滤
FILTER_UPLOADER = 1        # 上传者匹配 text 则过滤
FILTER_TAG = 2             # 包含指定标签则过滤
FILTER_TAG_NAMESPACE = 3   # 包含指定命名空间的标签则过滤
```

#### 1.4.6 gallery_tags_cache (画廊标签缓存)

缓存画廊的标签信息到本地，减少重复请求。

```sql
CREATE TABLE gallery_tags_cache (
    gid         TEXT PRIMARY KEY,
    tags_json   TEXT NOT NULL,                -- JSON 序列化的 Dict[str, List[str]]
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);
```

### 1.5 db.py 门面接口设计

```python
class PandoraDB:
    """数据库门面类，封装所有 DAO 操作。"""

    def __init__(self, db_path: Path): ...
    async def initialize(self) -> None: ...
    async def close(self) -> None: ...

    # ── 浏览历史 ─────────────────────────────────
    async def put_history(self, gallery: GalleryListItem | GalleryDetail) -> None: ...
    async def get_history(self, limit: int = 50, offset: int = 0) -> list[dict]: ...
    async def delete_history(self, gid: str) -> None: ...
    async def clear_history(self) -> None: ...

    # ── 本地收藏 ─────────────────────────────────
    async def add_local_favorite(self, gallery: GalleryListItem | GalleryDetail) -> None: ...
    async def remove_local_favorite(self, gid: str) -> None: ...
    async def get_local_favorites(self, limit: int = 50, offset: int = 0) -> list[dict]: ...
    async def search_local_favorites(self, query: str) -> list[dict]: ...
    async def is_local_favorite(self, gid: str) -> bool: ...

    # ── 阅读进度 ─────────────────────────────────
    async def update_bookmark(self, gid: str, token: str, title: str,
                              thumb_url: str, page: int, total: int) -> None: ...
    async def get_bookmark(self, gid: str) -> dict | None: ...
    async def get_bookmarks(self, limit: int = 50, offset: int = 0) -> list[dict]: ...
    async def delete_bookmark(self, gid: str) -> None: ...

    # ── 快速搜索 ─────────────────────────────────
    async def add_quick_search(self, name: str, keyword: str = "",
                               category: int | None = None,
                               min_rating: int | None = None) -> int: ...
    async def get_quick_searches(self) -> list[dict]: ...
    async def delete_quick_search(self, id: int) -> None: ...

    # ── 过滤规则 ─────────────────────────────────
    async def add_filter(self, mode: int, text: str) -> int: ...
    async def get_filters(self) -> list[dict]: ...
    async def toggle_filter(self, id: int) -> None: ...
    async def delete_filter(self, id: int) -> None: ...
    async def apply_filters(self, galleries: list[dict]) -> list[dict]: ...

    # ── 画廊标签缓存 ─────────────────────────────
    async def get_cached_tags(self, gid: str) -> dict | None: ...
    async def put_cached_tags(self, gid: str, tags: dict) -> None: ...

    # ── 迁移 ─────────────────────────────────────
    async def _migrate(self, current_version: int) -> None: ...
```

### 1.6 数据库版本迁移

```python
SCHEMA_VERSION = 1

async def _migrate(self, current_version: int) -> None:
    """逐版本执行迁移 SQL。"""
    migrations = {
        0: [  # 初始 schema
            CREATE_HISTORY_SQL,
            CREATE_LOCAL_FAVORITES_SQL,
            CREATE_BOOKMARKS_SQL,
            CREATE_QUICK_SEARCH_SQL,
            CREATE_FILTER_SQL,
            CREATE_GALLERY_TAGS_CACHE_SQL,
        ],
        # 未来新增:
        # 1: ["ALTER TABLE history ADD COLUMN ...", ...],
    }
    for version in range(current_version, SCHEMA_VERSION):
        for sql in migrations[version]:
            await self._db.execute(sql)
    await self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    await self._db.commit()
```

### 1.7 需要新增的 REST 路由

在 `pandora_daemon/routes/` 下新增文件或在现有文件中追加：

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/history` | GET | 获取浏览历史 (分页) |
| `/api/history/{gid}` | DELETE | 删除单条历史 |
| `/api/history` | DELETE | 清空历史 |
| `/api/local-favorites` | GET | 获取本地收藏 (分页) |
| `/api/local-favorites` | POST | 添加本地收藏 |
| `/api/local-favorites/{gid}` | DELETE | 删除本地收藏 |
| `/api/bookmarks` | GET | 获取阅读进度列表 |
| `/api/bookmarks/{gid}` | GET | 获取单个书签 |
| `/api/bookmarks/{gid}` | DELETE | 删除书签 |
| `/api/quick-search` | GET | 获取快速搜索列表 |
| `/api/quick-search` | POST | 添加快速搜索 |
| `/api/quick-search/{id}` | DELETE | 删除快速搜索 |
| `/api/filters` | GET | 获取过滤规则列表 |
| `/api/filters` | POST | 添加过滤规则 |
| `/api/filters/{id}` | PUT | 切换启用/禁用 |
| `/api/filters/{id}` | DELETE | 删除过滤规则 |

### 1.8 自动触发逻辑

需要在现有路由中嵌入数据库写入：

| 触发位置 | 动作 |
|----------|------|
| `routes/gallery.py: get_gallery_detail()` | 调用 `db.put_history(detail)` |
| `routes/gallery.py: prefetch_pages()` | 调用 `db.update_bookmark(gid, token, ..., current_page, total)` |
| `routes/browse.py: get_homepage/search/...` | 返回前调用 `db.apply_filters(results)` |

### 1.9 集成到 AppState

```python
@dataclass
class AppState:
    # ... 现有字段 ...
    db: PandoraDB           # 新增
```

在 `app.py` 的 `lifespan` 中：

```python
db_path = config_path.parent / "pandora.db"
db = PandoraDB(db_path)
await db.initialize()
# ... 创建 state 时传入 db ...
# yield
await db.close()  # shutdown 时关闭
```

---

## 2. 下载系统改进

### 2.1 现状问题

当前 `pandora_daemon/download.py` 的核心问题：

1. **页面下载串行**：`_download_gallery` 中 for 循环逐页下载，无并发
2. **失败页跳过不重试**：page 下载失败只 `except: pass`，整个画廊仍标记 `completed`，实际缺页
3. **状态保存过频**：每下完一页就全量序列化 `_save_state()`，1000 页画廊写 1000 次 JSON
4. **缺少页面级状态追踪**：无法知道哪些页成功、哪些失败、哪些未开始

### 2.2 新增页面级状态

在 `DownloadTask` 中增加页面级追踪：

```python
@dataclass
class DownloadTask:
    # ... 现有字段 ...

    # 新增：页面级状态
    page_states: dict[int, str] = field(default_factory=dict)
    # key: 页码 (1-based), value: "pending" | "downloading" | "done" | "failed"
    failed_pages: list[int] = field(default_factory=list)  # 失败页列表，用于重试
```

### 2.3 并发下载设计

将串行 for 循环改为 Semaphore 控制的并发下载：

```python
async def _download_pages(self, task: DownloadTask) -> None:
    """并发下载全部页面图片。"""
    semaphore = asyncio.Semaphore(self._config.concurrency)

    async def _download_one_page(idx: int, viewer_url: str) -> None:
        page_num = idx + 1
        # 检查是否已下载 (断点续传)
        pages_dir = Path(task.output_dir) / "pages"
        existing = list(pages_dir.glob(f"{page_num:04d}.*"))
        if existing:
            task.page_states[page_num] = "done"
            return

        async with semaphore:
            if task.gid in self._cancelled:
                return
            task.page_states[page_num] = "downloading"
            try:
                html = await self._api.client.get_html(viewer_url)
                image_url, _ = parse_image_viewer(html)
                if not image_url:
                    task.page_states[page_num] = "failed"
                    task.failed_pages.append(page_num)
                    return
                data = await self._fetch_image(image_url)
                ext = _ext_from_url(image_url)
                (pages_dir / f"{page_num:04d}{ext}").write_bytes(data)
                task.page_states[page_num] = "done"
                task.downloaded_pages += 1
            except Exception as exc:
                task.page_states[page_num] = "failed"
                task.failed_pages.append(page_num)

            await self._ws.broadcast({
                "event": "download_progress", "gid": task.gid,
                "phase": "pages", "page": page_num, "total": task.total_pages,
            })

    # 并发执行全部页面下载
    coros = [
        _download_one_page(idx, url)
        for idx, url in enumerate(task.preview_urls)
    ]
    await asyncio.gather(*coros)
```

### 2.4 失败重试机制

在 `_download_gallery` 完成后检查 `failed_pages`，执行重试：

```python
MAX_RETRY = 2

async def _download_gallery(self, task: DownloadTask) -> None:
    # ... metadata, cover, thumbs 阶段 (保持不变) ...

    # pages 阶段：并发下载
    await self._download_pages(task)

    # 重试失败页
    for attempt in range(MAX_RETRY):
        if not task.failed_pages:
            break
        retry_pages = task.failed_pages.copy()
        task.failed_pages.clear()
        for page_num in retry_pages:
            idx = page_num - 1
            if idx < len(task.preview_urls):
                await self._download_one_page(task, idx, task.preview_urls[idx])

    # 最终状态判定
    if task.failed_pages:
        task.status = "completed_with_errors"
        task.error = f"{len(task.failed_pages)} pages failed: {task.failed_pages[:10]}"
    else:
        task.status = "completed"
```

### 2.5 状态保存优化

用 debounce 替代每页写入：

```python
class DownloadManager:
    def __init__(self, ...):
        # ... 现有 ...
        self._save_dirty = False
        self._save_task: asyncio.Task | None = None

    def _mark_dirty(self) -> None:
        """标记状态为脏，启动延迟保存。"""
        self._save_dirty = True
        if self._save_task is None or self._save_task.done():
            self._save_task = asyncio.create_task(self._debounced_save())

    async def _debounced_save(self) -> None:
        """延迟 5 秒后保存，合并多次写入。"""
        await asyncio.sleep(5)
        if self._save_dirty:
            self._save_state()
            self._save_dirty = False
```

将 `_download_gallery` 和 `_worker` 中所有 `self._save_state()` 替换为 `self._mark_dirty()`。仅在以下关键节点保留即时保存：

- `submit()` — 新任务入队
- `cancel()` — 用户取消
- `shutdown()` — daemon 关闭
- 任务最终状态变更 (completed / failed)

### 2.6 新增下载状态值

```python
# 当前状态
"queued" | "downloading" | "completed" | "failed" | "cancelled"

# 新增
"completed_with_errors"   # 部分页面下载失败
"retrying"                # 正在重试失败页
```

### 2.7 新增 REST 端点

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/downloads/{gid}/retry` | POST | 重试失败页面 |
| `/api/downloads/{gid}/status` | GET | 获取详细页面级状态 |

---

## 3. 异常体系设计

### 3.1 现状问题

`exhentai_api/` 中所有错误都是裸 `Exception` 或 `ValueError`。daemon 的 `app.py` 只做了一个简单的字符串匹配 (`"Sad Panda" in str(exc)`)。下载管理器无法区分"该重试"和"该放弃"的错误。

### 3.2 自定义异常层级

在 `exhentai_api/` 下新建 `exceptions.py`：

```python
class ExhentaiError(Exception):
    """所有 exhentai_api 异常的基类。"""
    pass

class AuthenticationError(ExhentaiError):
    """认证失败。Sad Panda 或 Cookie 过期。
    
    处理方式：不重试，提示用户重新登录。
    """
    pass

class ImageLimitError(ExhentaiError):
    """HTTP 509 图片查看限额耗尽。
    
    处理方式：暂停下载，等待限额恢复或提示用户 reset_image_limit()。
    """
    pass

class GalleryNotFoundError(ExhentaiError):
    """画廊不存在或已被删除 (kokomade / pining / unavailable)。
    
    处理方式：永久失败，不重试。
    """
    pass

class GalleryOffensiveError(ExhentaiError):
    """攻击性内容警告，需要用户确认。
    
    处理方式：提示用户确认后重试。
    """
    pass

class ParseError(ExhentaiError):
    """HTML/JSON 解析失败，可能是网站结构变更。
    
    处理方式：可重试 1-2 次，持续失败则报告。
    """
    pass

class NetworkError(ExhentaiError):
    """网络请求失败 (超时、连接重置等)。
    
    处理方式：指数退避重试。
    """
    pass
```

### 3.3 在 API 层抛出异常

修改 `exhentai_api/client.py` 和各 parser，在检测到特定响应时抛出对应异常：

| 检测条件 | 抛出异常 |
|----------|----------|
| 响应包含 `sadpanda.jpg` | `AuthenticationError("Sad Panda")` |
| 响应包含 `kokomade.jpg` | `GalleryNotFoundError("Gallery removed")` |
| 响应包含 "This gallery has been removed" | `GalleryNotFoundError(...)` |
| 响应包含 "offensive content" | `GalleryOffensiveError(...)` |
| HTTP 状态码 509 | `ImageLimitError("Image limit exceeded")` |
| HTML 解析结果为空 / 缺少关键元素 | `ParseError(...)` |
| httpx.TimeoutException / ConnectError | 包装为 `NetworkError(...)` |

### 3.4 daemon 层异常处理

修改 `app.py` 的 exception handler：

```python
from exhentai_api.exceptions import (
    AuthenticationError, ImageLimitError, GalleryNotFoundError,
    GalleryOffensiveError, ParseError, NetworkError,
)

@app.exception_handler(AuthenticationError)
async def auth_error_handler(request, exc):
    return JSONResponse(status_code=401, content={"error": "auth", "detail": str(exc)})

@app.exception_handler(GalleryNotFoundError)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"error": "gallery_not_found", "detail": str(exc)})

@app.exception_handler(ImageLimitError)
async def limit_handler(request, exc):
    return JSONResponse(status_code=429, content={"error": "image_limit", "detail": str(exc)})

@app.exception_handler(GalleryOffensiveError)
async def offensive_handler(request, exc):
    return JSONResponse(status_code=451, content={"error": "offensive", "detail": str(exc)})

@app.exception_handler(ParseError)
async def parse_handler(request, exc):
    return JSONResponse(status_code=502, content={"error": "parse", "detail": str(exc)})

@app.exception_handler(NetworkError)
async def network_handler(request, exc):
    return JSONResponse(status_code=502, content={"error": "network", "detail": str(exc)})
```

### 3.5 下载管理器的重试策略

在 `DownloadManager._download_gallery` 中根据异常类型决定行为：

```python
except AuthenticationError:
    task.status = "failed"
    task.error = "认证失败，请检查 Cookie 配置"
    # 不重试

except ImageLimitError:
    task.status = "paused"
    task.error = "图片限额耗尽，等待恢复"
    # 重新入队，延迟重试

except GalleryNotFoundError:
    task.status = "failed"
    task.error = "画廊已被删除"
    # 永久失败，不重试

except NetworkError:
    task.page_states[page_num] = "failed"
    task.failed_pages.append(page_num)
    # 稍后重试该页

except ParseError:
    task.page_states[page_num] = "failed"
    task.failed_pages.append(page_num)
    # 重试 1-2 次
```

---

## 4. 缓存淘汰调度

### 4.1 现状问题

`CacheManager.evict_images()` 方法已实现，但**从未被调用过**。缓存会无限增长直到磁盘满。

另外 `evict_images()` 每次调用都遍历全部文件做 `stat()`，文件多时很慢。

### 4.2 改进方案

#### 4.2.1 定时淘汰任务

在 `app.py` 的 `lifespan` 中启动后台定时任务：

```python
async def _cache_eviction_loop(cache: CacheManager):
    """每 10 分钟检查一次缓存大小，超限则淘汰。"""
    while True:
        await asyncio.sleep(600)
        try:
            await cache.evict_images()
        except Exception:
            pass

# 在 lifespan 中:
eviction_task = asyncio.create_task(_cache_eviction_loop(cache))
# yield
eviction_task.cancel()
```

#### 4.2.2 写入时触发淘汰

在 `CacheManager.put_image()` 中追加大小检查：

```python
async def put_image(self, url: str, data: bytes) -> None:
    path = self._image_path(url)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, path.write_bytes, data)
    self._current_size += len(data)
    if self._current_size > self._max_bytes:
        asyncio.create_task(self.evict_images())  # 后台淘汰，不阻塞写入
```

#### 4.2.3 运行时大小跟踪

在 `CacheManager.__init__` 中初始化当前缓存大小，避免每次 evict 都全量 stat：

```python
def __init__(self, config: CacheConfig) -> None:
    # ... 现有 ...
    self._current_size = self._calculate_dir_size()

def _calculate_dir_size(self) -> int:
    """启动时计算一次缓存总大小。"""
    if not self._image_dir.exists():
        return 0
    return sum(f.stat().st_size for f in self._image_dir.iterdir() if f.is_file())
```

#### 4.2.4 gallery detail 缓存清理

已有 `prune_expired_galleries()` 方法但从未调用。与缓存淘汰任务合并，在同一个定时循环中调用：

```python
async def _cache_eviction_loop(cache: CacheManager):
    while True:
        await asyncio.sleep(600)
        try:
            cache.prune_expired_galleries()  # 清理过期画廊缓存
            await cache.evict_images()       # 淘汰磁盘图片缓存
        except Exception:
            pass
```

---

## 5. AppState 生命周期

### 5.1 现状问题

`AppState` 是纯 dataclass，没有统一的 shutdown 方法。清理逻辑分散在 `app.py` 的 `lifespan` 中。

### 5.2 改进方案

给 `AppState` 增加生命周期方法：

```python
@dataclass
class AppState:
    # ... 现有字段 ...
    db: PandoraDB                  # 新增

    async def shutdown(self) -> None:
        """统一关闭所有子组件。"""
        await self.downloads.shutdown()
        await self.image_service.shutdown()
        await self.db.close()
        await self.api.aclose()
```

简化 `app.py` 的 lifespan：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    state = await _build_state()  # 构建所有组件
    app.state.pandora = state
    await state.downloads.start()
    yield
    await state.shutdown()        # 一行清理
```

---

## 6. 网络代理配置

### 6.1 现状

`ExhentaiClient` 直接创建 httpx.AsyncClient，无代理配置。PC 用户经常需要通过代理访问。

### 6.2 改进方案

#### 6.2.1 config.toml 新增 network section

```toml
[network]
proxy = ""                  # 例如 "http://127.0.0.1:7890" 或 "socks5://..."
timeout = 30                # 请求超时 (秒)
```

#### 6.2.2 新增 NetworkConfig

在 `config.py` 中：

```python
@dataclass
class NetworkConfig:
    proxy: str = ""
    timeout: int = 30
```

在 `PandoraConfig` 中新增字段：

```python
@dataclass
class PandoraConfig:
    # ... 现有 ...
    network: NetworkConfig = field(default_factory=NetworkConfig)
```

#### 6.2.3 传递给 ExhentaiClient

修改 `exhentai_api/client.py`，让 `ExhentaiClient.__init__` 接受可选的 proxy 和 timeout 参数：

```python
class ExhentaiClient:
    def __init__(self, igneous="", ipb_member_id="",
                 proxy: str = "", timeout: int = 30):
        transport_kwargs = {}
        if proxy:
            transport_kwargs["proxy"] = proxy
        self.session = httpx.AsyncClient(
            cookies=cookies,
            timeout=timeout,
            **transport_kwargs,
        )
```

修改 `app.py` 中的初始化：

```python
client = ExhentaiClient(
    igneous=config.credentials.igneous,
    ipb_member_id=config.credentials.ipb_member_id,
    proxy=config.network.proxy,
    timeout=config.network.timeout,
)
```

---

## 7. 杂项修正

### 7.1 变量命名：preview_urls → viewer_urls

**位置**：`exhentai_api/models/gallery.py:50`、`download.py` 全文、`image_service.py` 全文

**问题**：`GalleryDetail.preview_urls` 实际存储的是 viewer page URL（形如 `/s/xxx/gid-page`），不是预览图 URL。与 `thumb_urls` (真正的预览缩略图 URL) 容易混淆。

**改进**：重命名为 `viewer_urls`。这是一个全局 rename，涉及：

| 文件 | 需要修改的内容 |
|------|---------------|
| `exhentai_api/models/gallery.py` | `preview_urls` → `viewer_urls` |
| `exhentai_api/parsers/gallery_detail.py` | 解析结果赋值 |
| `pandora_daemon/download.py` | 多处引用 `task.preview_urls` |
| `pandora_daemon/image_service.py` | `detail.preview_urls` |
| `pandora_daemon/routes/gallery.py` | 序列化 |
| `pandora-tui/src/models.rs` | Rust 端对应字段 |
| 测试文件 | 所有断言 |

### 7.2 图片获取逻辑统一

**问题**：`download.py` 的 `_fetch_image()` 和 `image_service.py` 的 `proxy_image()` 功能重复。

**改进**：`DownloadManager` 应该依赖 `ImageService` 获取图片，而不是自己实现一套。

```python
class DownloadManager:
    def __init__(self, api, config, ws, cache, image_service, state_file):
        # ... 新增 image_service 参数 ...
        self._image_service = image_service

    async def _fetch_image(self, url: str) -> bytes:
        return await self._image_service.proxy_image(url)
```

删除 `DownloadManager._fetch_image` 中直接访问 `self._api.client.session` 和 `self._cache` 的代码。

同步修改 `app.py` 中 DownloadManager 的构造，传入 `image_service` 参数。

---

## 8. 实施优先级

| 优先级 | 任务 | 原因 | 预估改动 | 状态 |
|--------|------|------|----------|------|
| **P0** | 数据库层 (第 1 章) | 用户数据完全丢失，核心功能缺失 | 新增 `db.py` + 6 张表 + 16 个路由 | ✅ 已完成 |
| **P0** | 异常体系 (第 3 章) | 下载管理器无法正确处理错误 | 新增 `exceptions.py` + 修改 client/parser/app.py | ✅ 已完成 |
| **P1** | 下载并发+重试 (第 2 章) | 下载速度慢、失败页丢失 | 修改 `download.py` | ✅ 已完成 |
| **P1** | 缓存淘汰调度 (第 4 章) | 缓存无限增长 | 修改 `config.py` + `app.py` | ✅ 已完成 |
| **P2** | AppState 生命周期 (第 5 章) | 代码整洁性 | 修改 `state.py` + `app.py` | ✅ 已完成 |
| **P2** | 网络代理配置 (第 6 章) | 用户便利性 | 修改 `config.py` + `client.py` | ⏭ 跳过 |
| **P3** | 杂项修正 (第 7 章) | 代码质量 | 全局 rename + 逻辑统一 | 待实施 |

### 实施顺序建议

```
P0: 异常体系 → 数据库层
     ↓ (异常是数据库和下载的基础依赖)
P1: 下载并发+重试 → 缓存淘汰
     ↓
P2: AppState 生命周期 → 网络代理
     ↓
P3: 杂项修正 (rename + 逻辑统一)
```

先做异常体系是因为：数据库操作和下载系统的错误处理都依赖正确的异常分类。没有异常分类，下载重试逻辑无法正确实现。
