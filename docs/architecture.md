# Pandora — 架构设计文档

> Open the box. Browse, search, and download from ExHentai.

---

## 项目定位

Pandora 是一个 ExHentai/E-Hentai 画廊浏览器与下载器，采用 daemon + 多前端架构。名字取自潘多拉之盒与 Sad Panda 的双关。

核心目标：为桌面用户提供一个本地化的、可离线浏览的画廊管理工具。daemon 作为本地服务运行，前端通过 REST/WebSocket 通信，彼此完全解耦。

---

## 分层架构

```
┌─────────────────────────────────────────────────────┐
│                    前端层 (Frontends)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ TUI      │  │ Web SPA  │  │ CLI      │           │
│  │ (Rust)   │  │ (React)  │  │ (Python) │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘           │
│       │              │              │                 │
│       └──────────────┼──────────────┘                 │
│                      │ REST + WebSocket               │
├──────────────────────┼──────────────────────────────-─┤
│                 服务层 (Daemon)                        │
│  ┌───────────────────┴────────────────────────────┐  │
│  │              pandora-daemon                     │  │
│  │         FastAPI + WebSocket + SQLite            │  │
│  └───────────────────┬────────────────────────────┘  │
│                      │ import                         │
├──────────────────────┼────────────────────────────────┤
│                 接口层 (API Library)                   │
│  ┌───────────────────┴────────────────────────────┐  │
│  │              exhentai_api                       │  │
│  │       无状态 HTTP 客户端 + HTML 解析器            │  │
│  └───────────────────┬────────────────────────────┘  │
│                      │ HTTP                           │
├──────────────────────┼────────────────────────────────┤
│                      ▼                                │
│              ExHentai / E-Hentai                      │
└───────────────────────────────────────────────────────┘
```

### 层级职责

| 层 | 职责 | 不做什么 |
|---|---|---|
| exhentai_api | HTTP 请求、HTML 解析、数据模型定义 | 无状态、无缓存、无配置、无持久化 |
| pandora-daemon | 会话管理、下载队列、图片缓存、数据库持久化、配置管理 | 不做 UI 渲染 |
| 前端 | 渲染、用户交互、调用 daemon API | 不直接请求 ExHentai |

### 为什么这样分

- **exhentai_api 无状态**：纯函数式设计，输入 cookie + 参数，输出结构化数据。可独立测试，可被任何 Python 项目复用。
- **daemon 作为中间层**：统一管理认证会话、缓存策略、下载并发、数据持久化。前端不需要关心这些复杂性。
- **前端只认 REST/WS**：前端与数据源完全解耦。换站点只需换 daemon 的 adapter，前端一行不改。

---

## 组件详解

### 1. exhentai_api — 接口层

```
exhentai_api/
├── api.py              # ExhentaiAPI — 22 个 async 方法
├── client.py           # ExhentaiClient — httpx 会话 (cookie 认证)
├── constants.py        # 基础 URL 常量
├── exceptions.py       # 异常层级
├── models/             # 17 个数据模型 (dataclass)
│   ├── gallery.py      #   GalleryListItem, GalleryDetail
│   ├── comment.py      #   GalleryComment
│   ├── favorites.py    #   FavoriteCategory, FavoritesResponse
│   ├── image.py        #   ImageDetail
│   ├── search.py       #   SearchParams (高级搜索构建器)
│   ├── tags.py         #   Tag, WatchedTag
│   └── ...             #   TopListItem, TorrentItem, ArchiveOption 等
└── parsers/            # 11 个 HTML 解析器
    ├── gallery.py      #   画廊列表页
    ├── gallery_detail.py #  画廊详情页
    ├── image.py        #   图片查看器页 + api.php 响应
    ├── favorites.py    #   收藏页
    └── ...             #   评论、种子、归档、个人资料等
```

**API 方法分组：**

| 分组 | 方法 |
|------|------|
| 浏览 | `get_homepage`, `search`, `get_popular`, `get_toplist`, `get_watched` |
| 画廊 | `get_gallery_details`, `get_image_url`, `get_gallery_token` |
| 交互 | `comment_gallery`, `vote_comment`, `rate_gallery` |
| 收藏 | `get_favorites`, `add_favorite`, `modify_favorites` |
| 资源 | `get_torrent_list`, `get_archive_list`, `download_archive` |
| 标签 | `get_mytags`, `add_tag`, `delete_tag` |
| 用户 | `get_home_detail`, `reset_image_limit`, `get_profile` |
| 搜索 | `image_search` (SHA1) |

**异常层级：**

```
ExhentaiError
├── AuthenticationError     # cookie 无效或过期
├── ImageLimitError         # 图片配额耗尽
├── GalleryNotFoundError    # 画廊不存在
├── GalleryOffensiveError   # 画廊被标记为 offensive
├── ParseError              # HTML 结构变化导致解析失败
└── NetworkError            # 网络连接问题
```

---

### 2. pandora-daemon — 服务层

```
pandora_daemon/
├── app.py              # FastAPI 应用入口，生命周期管理
├── config.py           # TOML 配置系统
├── state.py            # AppState — 共享应用状态
├── dependencies.py     # FastAPI 依赖注入
├── db.py               # SQLite 数据库层 (aiosqlite, WAL)
├── cache.py            # 图片缓存 (SHA256, LRU 淘汰)
├── image_service.py    # 图片代理、页面 URL 解析、服务端预取
├── download.py         # 下载管理器 (离线画廊构建)
├── tag_database.py     # EhTagTranslation 中文标签数据库
├── ws.py               # WebSocket 广播管理器
├── cli.py              # CLI 入口 (pandora download/status)
└── routes/
    ├── browse.py       # 首页、搜索、热门、排行、关注、图片代理
    ├── gallery.py      # 画廊详情、评论、评分、投票、种子、归档、翻页、缩略图、预取
    ├── favorites.py    # 收藏列表、添加、修改
    ├── downloads.py    # 提交、状态、取消下载
    ├── history.py      # 浏览历史 CRUD
    ├── local_favorites.py  # 本地收藏 CRUD
    ├── bookmarks_routes.py # 阅读进度书签
    ├── quick_search.py # 快速搜索预设
    ├── filters.py      # 画廊过滤规则
    ├── config.py       # 配置读写
    ├── user.py         # 用户信息
    ├── tags.py         # 标签自动补全
    └── library.py      # 已下载画廊浏览、本地文件服务
```

#### 核心子系统

**配置系统 (`config.py`)**

```toml
# ~/.config/pandora/config.toml

[credentials]
igneous = "..."
ipb_member_id = "..."

[server]
host = "127.0.0.1"
port = 7860

[download]
path = "~/Downloads/pandora"
gallery_concurrency = 2
page_concurrency = 4
max_retry = 3
retry_base_delay = 2.0

[cache]
image_dir = "~/.cache/pandora/images"
image_max_size_mb = 2048
gallery_ttl_seconds = 300
prefetch_ahead = 3
prefetch_behind = 1
eviction_interval_seconds = 600

[network]
proxy = ""
timeout = 30
```

**数据库 (`db.py`)**

SQLite + aiosqlite，WAL 模式，版本迁移机制。6 张表：

| 表 | 用途 | 自动触发 |
|---|---|---|
| `history` | 浏览历史 (最多 200 条) | 访问画廊详情时自动写入 |
| `local_favorites` | 本地收藏 (不依赖 ExHentai 账号) | — |
| `bookmarks` | 阅读进度 | prefetch 时自动更新 |
| `quick_search` | 搜索预设 | — |
| `filter` | 过滤规则 (标题/上传者/标签) | — |
| `gallery_tags_cache` | 画廊标签缓存 (用于本地过滤) | — |

**图片缓存 (`cache.py`)**

- 文件名：`SHA256(URL)` 无扩展名
- 淘汰策略：LRU，默认上限 2GB
- 后台淘汰循环：可配置间隔（默认 600s）
- 异步文件 I/O：`run_in_executor`

**下载管理器 (`download.py`)**

离线画廊构建器，下载产物结构：

```
~/Downloads/pandora/{gid}/
├── metadata.json       # 画廊元数据
├── cover.jpg           # 封面
├── thumbs/             # 缩略图 (CSS sprite 裁剪)
│   ├── 1.jpg
│   └── ...
└── pages/              # 全尺寸页面
    ├── 1.jpg
    └── ...
```

特性：
- 并发控制：`asyncio.Semaphore` (画廊级 + 页面级)
- 重试：指数退避 (可配置 base delay)
- 原子写入：临时文件 + rename
- 状态保存：debounce 防抖
- 异常驱动状态机：completed / completed_with_errors / paused / failed

**WebSocket (`ws.py`)**

实时下载事件广播：

```
事件类型: queued → started → page_done (×N) → thumb_done (×N)
         → cover_done → completed / completed_with_errors / paused / failed
```

每个事件携带 `gid`, `event`, 以及可选的 `page`, `total`, `path`, `error`, `title`, `phase` 字段。

**标签数据库 (`tag_database.py`)**

- 数据源：EhTagTranslation (GitHub)，约 15K 条中英文标签
- 搜索：子串匹配，前缀优先排序
- 缓存：本地 JSON 文件，自动从 GitHub 下载更新

**图片服务 (`image_service.py`)**

- 图片代理：统一缓存入口，前端不直接请求 ExHentai
- 页面 URL 解析：调用 `exhentai_api.get_image_url` 获取真实图片地址
- 服务端预取：`asyncio.Semaphore(4)` 控制并发，后台预加载邻近页面
- CSS sprite 裁剪：ExHentai 缩略图以 sprite sheet 形式返回，daemon 裁剪为单张

---

### 3. 前端层

#### CLI (`pandora_daemon/cli.py`)

```bash
pandora download <url>    # 提交下载任务
pandora dl <url>          # 同上 (别名)
pandora status            # 查看下载状态
```

轻量级命令行工具，直接调用 daemon REST API。

#### TUI (`pandora-tui/`, Rust)

状态：已挂起。详见 `docs/tui-visual-design.md`。

技术栈：ratatui + ratatui-image + tokio + reqwest

三个模式：Browse (三栏画廊浏览) → Read (双栏大图阅读) → Search (覆盖层搜索)

#### Web (`pandora-web/`, React + TypeScript)

状态：开发中。

技术栈：React 19 + Vite + TypeScript + Tailwind + Radix UI + SWR

---

## REST API 概览

daemon 暴露 30+ 个 REST 端点 + 1 个 WebSocket 端点，全部监听 `localhost:7860`。

| 分组 | 端点 | 说明 |
|------|------|------|
| 浏览 | `GET /api/homepage, /search, /popular, /toplist, /watched` | 画廊列表 |
| 画廊 | `GET /api/gallery/{gid}/{token}` | 详情 (自动记录历史) |
| 翻页 | `GET .../image/{page}`, `POST .../prefetch` | 图片 URL + 服务端预取 (自动更新书签) |
| 缩略图 | `GET .../thumb/{page}` | CSS sprite 裁剪后的单张缩略图 |
| 交互 | `POST .../comment, .../rate, .../vote-comment` | 评论、评分、投票 |
| 收藏 | `GET/POST /api/favorites`, `DELETE .../favorites/{gid}` | ExHentai 收藏 |
| 下载 | `GET/POST /api/downloads`, `DELETE .../downloads/{gid}` | 下载管理 |
| 本地库 | `GET /api/library`, `.../library/{gid}/page/{page}` | 已下载画廊浏览 |
| 历史 | `GET/DELETE /api/history` | 浏览历史 |
| 本地收藏 | `GET/POST/DELETE /api/local-favorites` | 不依赖账号的本地收藏 |
| 书签 | `GET/DELETE /api/bookmarks` | 阅读进度 |
| 快速搜索 | `GET/POST/DELETE /api/quick-search` | 搜索预设 |
| 过滤 | `GET/POST/PUT/DELETE /api/filters` | 过滤规则 |
| 配置 | `GET/PUT /api/config` | 运行时配置读写 |
| 标签 | `GET /api/tags/suggest?q=...` | 中文标签自动补全 |
| 图片代理 | `GET /api/image/proxy?url=...` | 统一图片代理 |
| WebSocket | `WS /ws` | 实时下载进度事件 |

完整端点文档见 `docs/api_reference.md`。

---

## 数据流

### 在线浏览

```
用户操作 → 前端 → REST GET → daemon
                              ├→ 检查缓存 → 命中 → 返回
                              └→ 未命中 → exhentai_api → ExHentai
                                          ├→ 写入缓存
                                          ├→ 写入数据库 (历史/书签)
                                          └→ 返回前端
```

### 图片加载

```
前端请求图片 → GET /api/image/proxy?url=...
               → daemon 检查磁盘缓存 (SHA256)
               → 未命中 → httpx 下载 → 写入缓存 → 返回字节流
```

### 下载流程

```
前端提交 → POST /api/downloads → daemon 入队
                                  → WS 广播 "queued"
                                  → 异步下载循环:
                                      1. 获取画廊详情 → 保存 metadata.json
                                      2. 下载封面 → WS "cover_done"
                                      3. 并发下载页面 → WS "page_done" (×N)
                                      4. 并发下载缩略图 → WS "thumb_done" (×N)
                                      5. WS "completed" / "failed"
前端监听 ← WS /ws ← 实时进度事件
```

### 离线浏览

```
前端请求 → GET /api/library → daemon 扫描下载目录
         → GET /api/library/{gid}/page/{page} → 直接读取本地文件
```

---

## 技术选型

| 组件 | 技术 | 选型理由 |
|------|------|---------|
| API 库 | Python + httpx + BeautifulSoup | 快速开发，HTML 解析生态成熟 |
| Daemon | FastAPI + aiosqlite + aiofiles | 异步原生，自动 OpenAPI 文档，轻量 |
| 数据库 | SQLite (WAL) | 单用户场景，零部署成本，嵌入式 |
| 缓存 | 文件系统 (SHA256) | 简单可靠，重启不丢失，可配置上限 |
| TUI | Rust + ratatui + tokio | 性能，跨平台单二进制 |
| Web | React + TypeScript + Vite | 生态成熟，开发效率高 |
| CLI | Python (复用 daemon 依赖) | 最小实现成本 |

---

## 代码规模

| 组件 | 行数 | 语言 |
|------|------|------|
| exhentai_api | ~1,750 | Python |
| pandora-daemon | ~3,000 | Python |
| pandora-tui | ~3,250 | Rust |
| pandora-web | ~150 | TypeScript (开发中) |
| 测试 | ~6,500 | Python |
| **合计** | **~14,650** | — |

测试覆盖：407 pytest + 16 cargo test = 423 个测试。

---

## 可扩展性

### 多站点适配

当前架构天然支持多站点扩展：

```
exhentai_api  ──┐
nhentai_api   ──┼── SiteAdapter trait/protocol ── daemon ── 前端
hitomi_api    ──┘
```

daemon 的 REST API 是站点无关的（画廊列表、详情、翻页、下载），只需为每个站点实现一个 adapter。前端完全不需要修改。

### 分发

当前状态：需要 Python 环境 + `uv` 才能运行 daemon。

可能的改进路径：
- 短期：PyInstaller / Nuitka 打包为单文件可执行程序
- 长期：Rust 重写 daemon，编译为静态链接二进制
- 桌面体验：tray app 包装 (daemon + 自动拉起浏览器)
