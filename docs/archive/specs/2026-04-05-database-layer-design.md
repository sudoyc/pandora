# P0: 数据库层设计 ✅ 已完成

> 日期：2026-04-05  
> 完成日期：2026-04-05  
> 范围：`pandora_daemon/db.py`（新建）、`pandora_daemon/routes/`（新增 + 修改）、`pandora_daemon/state.py`（修改）、`pandora_daemon/app.py`（修改）、`pandora_daemon/dependencies.py`（修改）  
> 依赖：P0 异常体系（已完成）

---

## 1. 问题

Pandora 没有本地数据库。浏览历史、阅读进度、本地收藏、搜索偏好在 daemon 重启后全部丢失。

## 2. 技术选型

- SQLite via `aiosqlite`（异步，无 ORM）
- 文件位置：`~/.config/pandora/pandora.db`
- 迁移：`PRAGMA user_version` + 手动版本号

## 3. 实施分批

整个数据库层拆为 3 批 subagent 并行实现：

| 批次 | 内容 | subagent |
|------|------|----------|
| A | `db.py` 核心（初始化 + 迁移 + 6 张表 CRUD） | subagent-A |
| B | 新增 REST 路由（history / bookmarks / local_favorites / quick_search / filter） | subagent-B（依赖 A） |
| C | 集成（AppState + lifespan + dependencies + 自动触发 + gallery_tags_cache 路由） | subagent-C（依赖 A） |

## 4. 表结构（6 张表）

### 4.1 history

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
    read_page  INTEGER NOT NULL DEFAULT 0,
    time       INTEGER NOT NULL
);
CREATE INDEX idx_history_time ON history(time DESC);
```

### 4.2 local_favorites

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
    time       INTEGER NOT NULL
);
CREATE INDEX idx_local_fav_time ON local_favorites(time DESC);
```

### 4.3 bookmarks

```sql
CREATE TABLE bookmarks (
    gid        TEXT PRIMARY KEY,
    token      TEXT NOT NULL,
    title      TEXT NOT NULL,
    thumb_url  TEXT NOT NULL DEFAULT '',
    page       INTEGER NOT NULL,
    total      INTEGER NOT NULL DEFAULT 0,
    time       INTEGER NOT NULL
);
CREATE INDEX idx_bookmarks_time ON bookmarks(time DESC);
```

### 4.4 quick_search

```sql
CREATE TABLE quick_search (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    keyword    TEXT NOT NULL DEFAULT '',
    category   INTEGER,
    min_rating INTEGER,
    page_from  INTEGER,
    page_to    INTEGER,
    time       INTEGER NOT NULL
);
```

### 4.5 filter

```sql
CREATE TABLE filter (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    mode       INTEGER NOT NULL,
    text       TEXT NOT NULL,
    enabled    INTEGER NOT NULL DEFAULT 1
);
```

过滤模式常量：
```python
FILTER_TITLE = 0
FILTER_UPLOADER = 1
FILTER_TAG = 2
FILTER_TAG_NAMESPACE = 3
```

### 4.6 gallery_tags_cache

```sql
CREATE TABLE gallery_tags_cache (
    gid         TEXT PRIMARY KEY,
    tags_json   TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);
```

## 5. db.py 门面接口

```python
class PandoraDB:
    def __init__(self, db_path: Path): ...
    async def initialize(self) -> None: ...
    async def close(self) -> None: ...

    # ── history ──
    async def put_history(self, gallery) -> None: ...
    async def get_history(self, limit=50, offset=0) -> list[dict]: ...
    async def delete_history(self, gid: str) -> None: ...
    async def clear_history(self) -> None: ...

    # ── local_favorites ──
    async def add_local_favorite(self, gallery) -> None: ...
    async def remove_local_favorite(self, gid: str) -> None: ...
    async def get_local_favorites(self, limit=50, offset=0) -> list[dict]: ...
    async def is_local_favorite(self, gid: str) -> bool: ...

    # ── bookmarks ──
    async def update_bookmark(self, gid, token, title, thumb_url, page, total) -> None: ...
    async def get_bookmark(self, gid: str) -> dict | None: ...
    async def get_bookmarks(self, limit=50, offset=0) -> list[dict]: ...
    async def delete_bookmark(self, gid: str) -> None: ...

    # ── quick_search ──
    async def add_quick_search(self, name, keyword="", category=None, min_rating=None, page_from=None, page_to=None) -> int: ...
    async def get_quick_searches(self) -> list[dict]: ...
    async def delete_quick_search(self, id: int) -> None: ...

    # ── filter ──
    async def add_filter(self, mode: int, text: str) -> int: ...
    async def get_filters(self) -> list[dict]: ...
    async def toggle_filter(self, id: int) -> None: ...
    async def delete_filter(self, id: int) -> None: ...
    async def apply_filters(self, galleries: list[dict]) -> list[dict]: ...

    # ── gallery_tags_cache ──
    async def get_cached_tags(self, gid: str) -> dict | None: ...
    async def put_cached_tags(self, gid: str, tags: dict) -> None: ...

    # ── migration ──
    async def _migrate(self, current_version: int) -> None: ...
```

`put_history` 和 `add_local_favorite` 接受 `GalleryListItem` 或 `GalleryDetail`，通过 duck typing 读取 `gid`, `token`, `title`, `category` 等字段。

`apply_filters` 逻辑：
- mode 0 (TITLE): `text.lower() in gallery["title"].lower()`
- mode 1 (UPLOADER): `text.lower() == gallery["uploader"].lower()`
- mode 2 (TAG): 查 gallery_tags_cache，检查 tags 中是否包含 `text`
- mode 3 (TAG_NAMESPACE): 查 gallery_tags_cache，检查是否有 `text` 命名空间的标签
- 只应用 `enabled=1` 的规则
- 匹配任一规则的画廊被过滤掉（不返回）

## 6. REST 路由（16 个）

### 6.1 新建 `routes/history.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/history` | 获取浏览历史，query: `limit`, `offset` |
| DELETE | `/api/history/{gid}` | 删除单条历史 |
| DELETE | `/api/history` | 清空全部历史 |

### 6.2 新建 `routes/local_favorites.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/local-favorites` | 获取本地收藏，query: `limit`, `offset` |
| POST | `/api/local-favorites` | 添加本地收藏，body: `{gid, token}` → 先通过 API 获取 detail |
| DELETE | `/api/local-favorites/{gid}` | 删除本地收藏 |

### 6.3 新建 `routes/bookmarks_routes.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/bookmarks` | 获取阅读进度列表，query: `limit`, `offset` |
| GET | `/api/bookmarks/{gid}` | 获取单个书签 |
| DELETE | `/api/bookmarks/{gid}` | 删除书签 |

### 6.4 新建 `routes/quick_search.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/quick-search` | 获取快速搜索列表 |
| POST | `/api/quick-search` | 添加，body: `{name, keyword?, category?, min_rating?, page_from?, page_to?}` |
| DELETE | `/api/quick-search/{id}` | 删除 |

### 6.5 新建 `routes/filters.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/filters` | 获取过滤规则列表 |
| POST | `/api/filters` | 添加，body: `{mode, text}` |
| PUT | `/api/filters/{id}` | 切换启用/禁用 |
| DELETE | `/api/filters/{id}` | 删除 |

## 7. 集成修改

### 7.1 AppState 新增字段

```python
@dataclass
class AppState:
    # ... 现有字段 ...
    db: PandoraDB
```

### 7.2 dependencies.py 新增

```python
def get_db(state: AppState = Depends(get_state)) -> PandoraDB:
    return state.db
```

### 7.3 app.py lifespan 修改

```python
db_path = config_path.parent / "pandora.db"
db = PandoraDB(db_path)
await db.initialize()
# ... state = AppState(..., db=db)
# yield
await db.close()
```

### 7.4 自动触发

| 触发位置 | 动作 |
|----------|------|
| `routes/gallery.py: get_gallery_detail()` 成功返回后 | `await db.put_history(detail)` |
| `routes/gallery.py: prefetch_pages()` | `await db.update_bookmark(gid, token, detail.title, detail.cover_url, body.current_page, detail.pages)` |

自动触发用 `asyncio.create_task` 包装，失败不影响主请求。

### 7.5 路由注册

在 `routes/__init__.py` 中 include 新路由：
```python
from .history import router as history_router
from .local_favorites import router as local_favorites_router
from .bookmarks_routes import router as bookmarks_router
from .quick_search import router as quick_search_router
from .filters import router as filters_router
```

## 8. 依赖新增

`pyproject.toml` 添加 `aiosqlite`。

## 9. 测试计划

### 9.1 db.py 单元测试 (`tests/pandora_daemon/test_db.py`)

使用 `:memory:` SQLite 数据库，测试每个 CRUD 方法：

| 测试组 | 用例数 | 覆盖 |
|--------|--------|------|
| 初始化 + 迁移 | 3 | 表创建、版本号、重复初始化幂等 |
| history CRUD | 5 | put/get/delete/clear/上限淘汰 |
| local_favorites CRUD | 5 | add/get/remove/is_favorite/重复添加幂等 |
| bookmarks CRUD | 4 | update/get_one/get_list/delete |
| quick_search CRUD | 3 | add/get/delete |
| filter CRUD + apply | 6 | add/get/toggle/delete/apply_title/apply_tag |
| gallery_tags_cache | 3 | put/get/不存在返回 None |

共约 29 个测试。

### 9.2 路由集成测试 (`tests/pandora_daemon/test_routes_*.py`)

用 FastAPI TestClient + mock db，测试每个路由的 HTTP 状态码和响应格式。

### 9.3 自动触发测试

验证 `get_gallery_detail` 调用后 `db.put_history` 被调用。
验证 `prefetch_pages` 调用后 `db.update_bookmark` 被调用。

## 10. 文件变更清单

| 文件 | 操作 | 预估行数 |
|------|------|----------|
| `pandora_daemon/db.py` | 新建 | ~350 行 |
| `pandora_daemon/routes/history.py` | 新建 | ~40 行 |
| `pandora_daemon/routes/local_favorites.py` | 新建 | ~50 行 |
| `pandora_daemon/routes/bookmarks_routes.py` | 新建 | ~40 行 |
| `pandora_daemon/routes/quick_search.py` | 新建 | ~40 行 |
| `pandora_daemon/routes/filters.py` | 新建 | ~50 行 |
| `pandora_daemon/routes/__init__.py` | 修改 | +10 行 |
| `pandora_daemon/state.py` | 修改 | +2 行 |
| `pandora_daemon/app.py` | 修改 | +6 行 |
| `pandora_daemon/dependencies.py` | 修改 | +4 行 |
| `pandora_daemon/routes/gallery.py` | 修改 | +10 行 |
| `pyproject.toml` | 修改 | +1 行 |
| `tests/pandora_daemon/test_db.py` | 新建 | ~400 行 |
| `tests/pandora_daemon/test_routes_history.py` | 新建 | ~60 行 |
| `tests/pandora_daemon/test_routes_local_favorites.py` | 新建 | ~60 行 |
| `tests/pandora_daemon/test_routes_bookmarks.py` | 新建 | ~50 行 |
| `tests/pandora_daemon/test_routes_quick_search.py` | 新建 | ~50 行 |
| `tests/pandora_daemon/test_routes_filters.py` | 新建 | ~60 行 |
| `tests/pandora_daemon/test_auto_triggers.py` | 新建 | ~40 行 |
