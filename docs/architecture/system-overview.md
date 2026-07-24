# 系统架构概览

状态：现役
基线版本：`0.2.0`
最近核对：2026-07-23

## 1. 目标

Pandora 是一个本地运行的画廊浏览、检索、下载和离线库服务。当前设计目标是：

- 让上游 HTTP/HTML 变化被隔离在无状态 Python 库中。
- 让认证、缓存、数据库、下载队列和本地文件只由一个 daemon 管理。
- 为 CLI、Agent Pack 和可选 Web UI 提供稳定、可测试的 REST/WS 契约。
- 默认绑定 loopback，避免把本地凭据和文件能力暴露为公网服务。
- 优先保证机器调用、恢复能力和契约稳定，再扩展人类 UI。

当前不追求：恢复 Rust TUI、创建第二套状态层、让 consumer 直接访问上游、
多站点抽象或无依据地重写 daemon。

## 2. 系统上下文

```text
                         machine / human consumers
                 +-------------+-------------+-------------+
                 | Python CLI  | Agent Pack  | React Web  |
                 +------+------+------+------+------+------+
                        |             |             |
                        +-------------+-------------+
                                      |
                              REST + WebSocket
                                      |
                         +------------v------------+
                         |      pandora-daemon      |
                         | FastAPI / SQLite / files |
                         +------------+------------+
                                      |
                               Python imports
                                      |
                         +------------v------------+
                         |       exhentai_api       |
                         | HTTP / parsing / models  |
                         +------------+------------+
                                      |
                                  upstream HTTP
```

依赖只能向下：consumer 调 daemon，daemon 调 `exhentai_api`。consumer 不得绕过
daemon，`exhentai_api` 也不得反向依赖配置、数据库或 UI。

## 3. 分层职责

| 层 | 仓库位置 | 拥有的职责 | 明确不拥有 |
|---|---|---|---|
| 上游接口库 | `exhentai_api/` | HTTP client、HTML/JSON parser、领域 model、上游异常 | 配置、缓存、数据库、队列、UI |
| 本地服务 | `pandora_daemon/` | 凭据和 session、REST/WS、SQLite、缓存、下载、本地库、配置 | UI 渲染、agent 决策 |
| CLI | `pandora_daemon/cli.py` | daemon 的人类和 JSON/NDJSON 客户端 | 直接抓取、持久化副本 |
| Agent Pack | `docs/agent/` | 机器契约、schema、工作流、故障处理 | 业务状态、第二套控制平面 |
| Web | `pandora-web/` | 可选的人类浏览界面，只消费 REST/WS | 上游请求、服务端状态 |
| 历史 TUI | `pandora-tui/` | 冻结的 consumer 参考 | 新功能和常规维护 |

## 4. daemon 组成

| 子系统 | 主要模块 | 说明 |
|---|---|---|
| 应用生命周期 | `app.py`, `state.py`, `dependencies.py` | 构造共享 `AppState`，按依赖顺序启动和关闭资源 |
| 配置 | `config.py`, `routes/config_routes.py` | TOML 配置、公开字段白名单和校验 |
| 数据库 | `db.py` | SQLite/WAL；历史、本地收藏、书签、搜索、过滤和标签缓存 |
| 图片缓存 | `cache.py` | URL 哈希文件缓存、详情 TTL、容量淘汰 |
| 图片服务 | `image_service.py` | 受限图片代理、页面解析、预取、缩略图裁剪 |
| 下载 | `download.py`, `routes/downloads.py` | 队列、并发、重试、原子文件写入、恢复和公开状态 |
| 本地库/PDF | `routes/library.py`, `pdf_export.py` | 扫描已下载内容、受限文件服务、PDF 导出 |
| 标签库 | `tag_database.py`, `routes/tags.py` | 翻译标签缓存、状态、刷新和建议 |
| 实时事件 | `ws.py` | WebSocket 连接管理与事件广播 |
| HTTP 路由 | `routes/` | 浏览、详情、收藏、用户状态和本地数据接口 |

具体端点和字段见 [API Reference](../api_reference.md)。

## 5. 状态所有权

| 状态 | 默认位置 | 所有者 | 对 consumer 的暴露方式 |
|---|---|---|---|
| 凭据与运行配置 | `~/.config/pandora/config.toml` | daemon | 仅返回去凭据、去代理内容的公开配置 |
| SQLite 数据 | `~/.config/pandora/pandora.db` | daemon | 专用 REST/CLI 接口 |
| 下载队列快照 | `~/.config/pandora/downloads.json` | daemon | 公开 download DTO，不含 token/本地路径 |
| 图片缓存 | `~/.cache/pandora/images` | daemon | 受限图片/页面接口 |
| 标签数据库缓存 | `~/.cache/pandora/tags` | daemon | status/refresh/suggest 接口 |
| 离线画廊 | `download.path`，默认 `~/Downloads/pandora` | daemon | library API 和 PDF export |
| Web 临时视图状态 | 浏览器内存/`localStorage` | Web | 不成为业务事实来源 |

consumer 不应直接编辑 daemon 状态文件。需要修复或迁移时，应由 daemon/CLI 提供
显式操作并保持原子写入。

## 6. 关键数据流

### 启动与探测

```text
load config -> initialize SQLite -> create upstream client/cache/tag DB/download manager
            -> start workers and eviction loop -> expose health/config/readiness/status
```

`health.auth_configured` 只表示凭据字段已配置，不表示上游会话已验证。`readiness` 通过
homepage、search、popular 和 home 四个只读检查分别报告 auth/session/upstream/parse/network
状态；未配置完整凭据时不请求上游。

### 浏览与详情

```text
consumer -> daemon route -> cache/database policy -> exhentai_api -> upstream
         <- public serializer <- parsed domain model <- response
```

上游 parser model 可以包含 daemon 内部工作字段，公共 serializer 只返回调用方所需字段。
访问详情时可由 daemon 记录历史，consumer 不直接写数据库。

### 下载与恢复

```text
submit -> reject active duplicate -> fetch detail -> persist task -> queue worker
       -> metadata -> cover -> thumbnails -> pages -> terminal state
       -> REST status + WebSocket progress events
```

页面文件和状态文件使用临时文件加 rename。终态包括 `completed`、
`completed_with_errors`、`failed`、`paused` 和 `cancelled`；Agent watcher 的退出语义见
[Agent Contract](../agent/contract.md)。

只读一致性报告以 daemon 已载入的 task 注册表为状态事实源，对照 `download.path` 下的
metadata 和页面文件；它不重新实现 library 索引、不返回本地路径，也不执行修复。

## 7. 公共契约

- REST 是请求/响应和资源操作接口；WebSocket 只承载实时事件。
- CLI 是 daemon 客户端，不是第二个业务实现；机器调用优先 JSON/NDJSON。
- WebSocket discriminator 固定为 `event`，不是 `type`。
- 公共 gallery/download/local-state DTO 不返回 daemon-only secret、抓取辅助字段或本地路径。
- Agent Pack 是 agent 可见契约的权威文档；Hermes skill 只做薄封装。
- 翻译标签使用显式 `status -> refresh? -> suggest -> agent choose -> search` 流程，
  daemon 不代替 agent 做歧义决策。

## 8. 安全边界

- 默认监听 `127.0.0.1`；改变绑定地址需要重新评估认证和文件访问边界。
- 凭据只进入 daemon 的上游 client，不进入公开配置、事件、日志示例或 Agent Pack。
- 图片代理只允许预期 host 和安全重定向，并使用不携带认证 cookie 的独立请求路径。
- 公共异常返回稳定、低泄露的错误；详细堆栈仅记录在服务端。
- library 文件服务必须验证 `gid` 和相对路径，不能越过下载根目录。
- 配置更新使用结构化模型和字段白名单，不接受任意 `dict` 写入。

## 9. 质量门槛

当前变更至少运行：

```bash
uv run python -m pytest -q
git diff --check
```

Web 变更追加：

```bash
cd pandora-web
npm run lint
npm run build
```

公共契约变化还必须同步 API reference、Agent Pack、JSON Schema 和 contract tests。
TUI 已冻结，不纳入默认功能开发验证。

## 10. 当前约束

- 上游是 HTML 驱动接口，页面或认证行为变化会造成 parser/endpoint 漂移。
- `health` 保持轻量；上游会话和四项页面能力由显式 `readiness` 探针验证。
- Web 仍是可选 WIP，缺少重连后的下载状态对账、完整页面和自动化 UI 测试。
- 仓库尚无持续集成和正式 release/tag 流程。
- 历史下载状态与磁盘 library 可能失配，缺少正式 reconcile/repair 工作流。

这些事项的处理顺序和验收标准见 [开发路线图](../roadmap.md)。
