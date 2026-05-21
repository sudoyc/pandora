# Pandora — 架构设计文档

> Open the box. Browse, search, and download from ExHentai.

---

## 项目定位

Pandora 是一个 ExHentai/E-Hentai 画廊浏览器与下载器，当前优先方向是稳定的 daemon + CLI + Hermes agent/plugin 契约。名字取自潘多拉之盒与 Sad Panda 的双关。

核心目标：通过本地 daemon 提供认证、缓存、下载、数据库与图片代理能力；CLI/Hermes 使用稳定 JSON/NDJSON 契约自动化操作。Web 是可选人类 UI，`pandora-tui/` 已归档冻结。

---

## 分层架构

```
┌─────────────────────────────────────────────────────┐
│          消费层 (Consumers / Agent Workflows)         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ CLI      │  │ Hermes   │  │ Web SPA  │           │
│  │ (Python) │  │ skill/tool│ │ (React)  │           │
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
| 消费层 | CLI JSON/NDJSON、Hermes 自动化、可选 Web UI | 不直接请求 ExHentai |

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
├── cli.py              # CLI 入口 (daemon-backed JSON/NDJSON)
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
事件类型: download_queued → download_progress (cover/thumbs/pages)
         → download_complete / download_error / download_cancelled
         → download_paused / download_auth_failed
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

### 3. 消费层

#### CLI (`pandora_daemon/cli.py`)

```bash
pandora download <url>              # 兼容旧入口：提交并用 rich/websocket 监控
pandora dl <url>                    # 同上 (别名)
pandora download add <url|gid> [token]
pandora download list --json
pandora download watch [gid] --ndjson
pandora download cancel <gid>
pandora download resume <gid>
pandora download retry <gid>
pandora download pages <gid>
pandora health --json
pandora config --json
pandora status --json
pandora search "keyword" --page 0 --json
pandora gallery <url|gid> [token] --json
pandora library list --json
pandora tags suggest "artist" --json
pandora favorites list --json
pandora popular --json
```

轻量级命令行工具，直接调用 daemon REST API；优先服务 agent/Hermes/脚本化场景，因此新增命令默认支持 JSON/NDJSON 输出。

#### TUI (`pandora-tui/`, Rust, 已归档冻结)

状态：已归档冻结，不再维护，不做功能改进或视觉打磨。保留目录仅作为历史实现和 REST/WebSocket consumer 参考；接口信心由 Python contract tests 维护。

技术栈：ratatui + ratatui-image + tokio + reqwest

核心能力：浏览、搜索、详情、在线/本地阅读、图片缓存与预载、WebSocket 下载进度、Library API 离线浏览。

#### Web (`pandora-web/`, React + TypeScript)

状态：开发中但已接入真实 daemon 契约。已有 Vite/React 骨架、gallery feed、搜索/热门/关注切换、detail drawer、daemon page API reader、WebSocket 下载进度 hook；下一步重点是拆分 `App.tsx`、扩展 typed API client、补齐 favorites/history/downloads/library 视图。详见 `pandora-web/README.md`。

技术栈：React 19 + Vite + TypeScript + Radix UI + SWR + Vanilla CSS variables

---

## REST API 概览

daemon 暴露 30+ 个 REST 端点 + 1 个 WebSocket 端点，全部监听 `localhost:7860`。

| 分组 | 端点 | 说明 |
|------|------|------|
| 浏览 | `GET /api/homepage, /search, /popular, /toplist, /watched` | 画廊列表 |
| 画廊 | `GET /api/gallery/{gid}/{token}` | 详情 (自动记录历史) |
| 翻页 | `GET .../page/{page}`, `POST .../prefetch` | 图片字节 + 服务端预取 (自动更新书签) |
| 缩略图 | `GET .../thumb/{page}` | CSS sprite 裁剪后的单张缩略图 |
| 交互 | `POST .../comment, .../rate, .../vote_comment` | 评论、评分、投票 |
| 收藏 | `GET/POST/DELETE /api/favorites` | ExHentai 收藏 |
| 下载 | `GET/POST /api/downloads`, `DELETE .../downloads/{gid}`, `POST .../{gid}/resume`, `POST .../{gid}/retry`, `GET .../{gid}/pages` | 下载管理 |
| 本地库 | `GET /api/library`, `GET /api/library/{gid}/file?path=...` | 已下载画廊浏览、本地文件服务 |
| 历史 | `GET/DELETE /api/history` | 浏览历史 |
| 本地收藏 | `GET/POST/DELETE /api/local-favorites` | 不依赖账号的本地收藏 |
| 书签 | `GET/DELETE /api/bookmarks` | 阅读进度 |
| 快速搜索 | `GET/POST/DELETE /api/quick-search` | 搜索预设 |
| 过滤 | `GET/POST/PUT/DELETE /api/filters` | 过滤规则 |
| 配置 | `GET /api/health`, `GET/PUT /api/config` | 健康检查、运行时配置读写 |
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
                                  → WS 广播 "download_queued"
                                  → 异步下载循环:
                                      1. 获取画廊详情 → 保存 metadata.json
                                      2. 下载封面 → WS download_progress phase=cover
                                      3. 并发下载缩略图 → WS download_progress phase=thumbs
                                      4. 并发下载页面 → WS download_progress phase=pages
                                      5. WS download_complete / download_complete_with_errors
                                         / download_paused / download_auth_failed
                                         / download_error / download_cancelled
前端监听 ← WS /ws ← 实时进度事件
```

### 离线浏览

```
前端请求 → GET /api/library → daemon 扫描下载目录
         → GET /api/library/{gid}/file?path=page/{page} → 直接读取本地文件
```

---

## 技术选型

| 组件 | 技术 | 选型理由 |
|------|------|---------|
| API 库 | Python + httpx + BeautifulSoup | 快速开发，HTML 解析生态成熟 |
| Daemon | FastAPI + aiosqlite + aiofiles | 异步原生，自动 OpenAPI 文档，轻量 |
| 数据库 | SQLite (WAL) | 单用户场景，零部署成本，嵌入式 |
| 缓存 | 文件系统 (SHA256) | 简单可靠，重启不丢失，可配置上限 |
| TUI | Rust + ratatui + tokio | 已归档冻结，仅历史参考 |
| Web | React + TypeScript + Vite | 生态成熟，开发效率高 |
| CLI | Python (复用 daemon 依赖) | 最小实现成本 |

---

## 代码规模

当前工作区约 15K 行代码（不含 `.git`、依赖目录、构建产物与缓存目录；具体数值以 `uvx pygount --format=summary` 为准）：

| 语言 | 文件 | 代码行 |
|------|------|--------|
| Python | 104+ | ~8K+ |
| Rust | 21 | ~2K+ |
| TS/TSX | 10+ | ~1K+ |
| 其他配置/脚本/文档 | 若干 | 持续变化 |
| **合计** | 240+ | ~15K |

测试数量以当前 `uv run pytest`、`cargo test` 输出为准；README 不再固化易漂移的测试总数。

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
