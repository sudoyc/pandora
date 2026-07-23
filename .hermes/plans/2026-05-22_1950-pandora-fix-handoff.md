# Pandora 修复执行文档与交接计划

> For Hermes: 这是供下一次 /new 后继续修复使用的主 handoff 文档。执行时优先采用 Hermes 主控 + OpenCode 实现 + Codex 复核的协作模式。主控必须亲自检查 diff、运行测试、保护现有 WIP，不要只信任外部 agent 的自报结果。

Date: 2026-05-22 19:50 CST
Status: completed (`d4fea6f` daemon/public-contract hardening; `69bece7` web contract alignment)
Source review: `.hermes/plans/2026-05-22_1905-pandora-full-review.md`

Goal:
- 基于已完成的全仓 read-only review，按安全性、公共契约稳定性、agent/plugin 方向一致性，系统修复 Pandora 的高优先级问题。
- 为后续“砍掉/冻结 TUI、强化 daemon/CLI、方便包装成 skill/plugin”铺平接口边界。

Architecture direction:
- 保持 `exhentai_api/` 纯无状态抓取/解析层。
- 保持 `pandora_daemon/` 为唯一有状态边界：认证、cookie、缓存、下载、DB、library、WebSocket。
- 优先把 daemon REST + CLI JSON/NDJSON 契约做干净；Hermes skill/plugin 只做薄封装，不再创建第二套状态层。
- `pandora-tui/` 当前视为 frozen/deprecated reference consumer，不继续开发；在契约测试补足前，不急着物理删除。

Tech stack:
- Python 3.12, FastAPI, httpx, aiosqlite, uv
- Optional React/Vite web frontend in `pandora-web/`
- External coding workers available: OpenCode 1.15.7, Codex CLI 0.133.0

---

## 0. 当前工作区状态与约束

### 0.1 当前未提交改动（必须保护）

运行 `git status --short --branch` 时，当前工作树已有以下未提交变更：

- `pandora-tui/Cargo.lock`
- `pandora-web/README.md`
- `pandora-web/src/App.tsx`
- `pandora-web/src/api/client.ts`
- `pandora-web/src/components/GalleryCard.tsx`
- `pandora-web/src/components/GalleryDrawer.tsx`
- `pandora-web/src/components/Reader.tsx`
- `pandora-web/src/hooks/useGalleries.ts`
- `pandora-web/src/hooks/useWebSocket.ts`
- `pandora-web/src/models.ts`
- `pandora-web/src/styles/variables.css`
- `pandora_daemon/app.py`
- 未跟踪：`.hermes/plans/2026-05-22_1905-pandora-full-review.md`

本次修复期间必须把这些改动视为 user-owned WIP，除非任务明确要求，否则不要覆盖、回滚、重排、顺手格式化、顺手重构。

### 0.2 本次允许触碰的主要目录

优先：
- `pandora_daemon/`
- `tests/pandora_daemon/`
- `docs/api_reference.md`
- `docs/architecture.md`（如需最小同步）
- `.agents/skills/pandora/SKILL.md`

尽量不要碰：
- `pandora-web/`（除非修 contract drift 必须联动）
- `pandora-tui/`（本轮不做功能修复）

### 0.3 工具策略

- 主控：Hermes
- 实现 worker：优先 OpenCode
- 独立复核：优先 Codex
- 如果 OpenCode/Codex 的结果与主控验证不一致，以主控实测为准
- 不使用 `git add .`
- 不盲目 stage 目录
- Python 一律 `uv run ...`
- 前端验证用 npm（仓库存在 `pandora-web/package-lock.json`）

---

## 1. 已确认问题清单（按优先级）

以下问题都来自已完成的代码审计和文件证据。括号内为主要证据文件。

### P0-1 `/api/image/proxy` 存在 SSRF + ExHentai cookie 外带

证据：
- `pandora_daemon/routes/browse.py:157-174`
- `pandora_daemon/image_service.py:29-39`
- `exhentai_api/client.py`（review 中已验证 client 持有认证 cookie）

现状：
- `GET /api/image/proxy?url=...` 接受任意 URL
- `ImageService.proxy_image()` 直接调用 `self._api.client.session.get(url)`
- 这会复用带 ExHentai 认证状态的共享 session

风险：
- 任意外网/内网地址 SSRF
- 将站点 cookie 发送给非预期 host
- 便于探测内网和辅助错误枚举

目标修复：
- `image/proxy` 改为严格受限的公共图片代理，而不是任意 URL fetcher
- 不复用带认证 cookie 的 session
- 仅允许预期图片 host / CDN host
- 禁止 localhost / RFC1918 / link-local / metadata / 非 allowlist redirect
- 错误响应改为稳定、安全、低泄露

建议改动文件：
- `pandora_daemon/image_service.py`
- `pandora_daemon/routes/browse.py`
- 如有必要：`pandora_daemon/config.py`（仅当你决定增加 allowlist 配置；否则先 hardcode 最小 allowlist）
- `tests/pandora_daemon/test_image_service.py`
- `tests/pandora_daemon/test_routes_browse.py`

### P0-2 gallery detail 对外暴露 `api_uid` / `api_key`

证据：
- `pandora_daemon/routes/gallery.py:62-87`
- `pandora_daemon/routes/gallery.py:160-183`
- `tests/pandora_daemon/test_agent_contracts.py:75-133`

现状：
- `_detail_to_dict()` 把 `api_uid` 和 `api_key` 返回给公共 REST 客户端
- 但这些字段只应该在 daemon 内部用于 `rate_gallery` / `vote_comment`

风险：
- 浏览器端、agent transcript、日志可能拿到不必要的敏感字段
- 破坏“daemon 内部状态 vs 公共契约”边界

目标修复：
- `GET /api/gallery/{gid}/{token}` 的公共返回中移除 `api_uid` / `api_key`
- 内部缓存对象继续保留，供 daemon server-side 调用使用
- 同步更新 contract tests / CLI redaction assumptions / 文档

建议改动文件：
- `pandora_daemon/routes/gallery.py`
- `tests/pandora_daemon/test_routes_gallery.py`
- `tests/pandora_daemon/test_agent_contracts.py`
- 如有必要：`pandora-web/src/models.ts`（仅在当前 WIP 允许且确实依赖时最小联动）

### P1-1 downloads 公共状态暴露过多内部字段

证据：
- `pandora_daemon/download.py:36-63`
- `pandora_daemon/routes/downloads.py`
- `pandora_daemon/download.py:421-427`（WS complete 事件）
- `tests/pandora_daemon/test_agent_contracts.py:136-193`

现状：
- `DownloadTask.to_dict()` 直接 `asdict(self)`，包括：
  - `token`
  - `output_dir`
  - `viewer_urls`
  - `thumb_urls`
  - `thumb_sprites`
- `download_complete` WS 事件包含 `path`

风险：
- 对外暴露 gallery token、本地路径、抓取内部状态
- 不利于后续 agent/plugin 稳定契约设计

目标修复：
- 新增 public serializer，区分：
  - 内部持久化/运行态对象
  - REST/WS 对外 DTO
- 默认对外只暴露必要状态摘要：
  - gid/title/status/total_pages/downloaded_pages/downloaded_thumbs/cover_downloaded/metadata_saved/error/created_at/failed_pages/page_states（视接口需要可进一步收窄）
- `output_dir` 不再出现在公共 REST / WS 事件
- `token`、`viewer_urls`、`thumb_urls`、`thumb_sprites` 不再出现在公共 REST / WS 事件
- 如需 library 路径，应通过专门 library API 获取，而不是下载状态顺带泄露

建议改动文件：
- `pandora_daemon/download.py`
- `pandora_daemon/routes/downloads.py`
- `pandora_daemon/cli.py`（如 CLI 当前依赖某些字段）
- `tests/pandora_daemon/test_download.py`
- `tests/pandora_daemon/test_routes_downloads.py`
- `tests/pandora_daemon/test_agent_contracts.py`
- `tests/pandora_daemon/test_cli.py`
- `tests/pandora_daemon/test_ws.py`

### P1-2 history / bookmarks / local_favorites 直接返回 `token`

证据：
- `pandora_daemon/db.py:28-65, 166-247`
- `pandora_daemon/routes/history.py:12-25`
- `pandora_daemon/routes/bookmarks_routes.py:12-27`
- `pandora_daemon/routes/local_favorites.py:26-39`

现状：
- DB schema 存储 token
- 路由直接返回 `SELECT *` 的结果
- 于是 history / bookmarks / local_favorites 公共接口会带 token

判断：
- 这比 `gallery list`/`search results` 中出现 token 更敏感，因为这些是本地持久化私有状态接口，不应无理由暴露完整 gallery token

目标修复：
- 为 history / bookmarks / local favorites 新建 public serializer
- 默认去掉 `token`
- 如果某一 consumer 的确需要恢复 gallery 链接，可考虑单独返回 `url` 或通过详情接口再次解析，而不是长期在这些接口中暴露 token
- 同步更新相应 tests

建议改动文件：
- `pandora_daemon/routes/history.py`
- `pandora_daemon/routes/bookmarks_routes.py`
- `pandora_daemon/routes/local_favorites.py`
- 如有需要：新增 serializer helper 模块
- `tests/pandora_daemon/test_routes_history.py`
- `tests/pandora_daemon/test_routes_bookmarks.py`
- `tests/pandora_daemon/test_routes_local_favorites.py`

### P1-3 `PUT /api/config` 更新边界过宽，缺少结构化校验

证据：
- `pandora_daemon/routes/config_routes.py:47-63`
- `tests/pandora_daemon/test_routes_config.py:143-227`

现状：
- `body: dict`
- 直接 `hasattr + setattr`
- 未知字段被静默忽略
- 没有值域校验、类型约束、只读/需重启字段划分

风险：
- 容易写入坏配置
- 允许本地关键运行参数被随意持久化
- 未来一旦 daemon 边界变化，风险进一步放大

目标修复：
- 使用 Pydantic 请求模型替代裸 `dict`
- 只允许有限、明确的 public mutable fields
- 对类型和值域做校验
- 未知字段返回 422，而不是静默忽略
- 视情况把 `server.host/port` 这类字段从 live public update 中移除，或至少显式标记

建议改动文件：
- `pandora_daemon/routes/config_routes.py`
- `tests/pandora_daemon/test_routes_config.py`
- `tests/pandora_daemon/test_agent_contracts.py`（如 contract 有变化）
- `docs/api_reference.md`

### P1-4 异常响应把内部错误文本直接暴露给客户端

证据：
- `pandora_daemon/app.py:130-136`
- `pandora_daemon/routes/browse.py:160-164`
- `pandora_daemon/routes/gallery.py:204-209`

现状：
- generic exception handler / route-level 502 直接返回 `str(e)`

风险：
- 泄露内部网络信息、路径、下游错误文本、解析细节
- 配合 SSRF 更危险

目标修复：
- 对外统一稳定 error envelope
- 详细异常只打服务端日志
- route-level `HTTPException` 不再拼接底层异常全文

建议改动文件：
- `pandora_daemon/app.py`
- `pandora_daemon/routes/browse.py`
- `pandora_daemon/routes/gallery.py`
- `tests/pandora_daemon/test_exception_handlers.py`
- `tests/pandora_daemon/test_routes_browse.py`
- `tests/pandora_daemon/test_routes_gallery.py`

### P1-5 cancel 后重新 submit/resume/retry 同 gid 可能被 `_cancelled` 静默吞掉

证据：
- `pandora_daemon/download.py:79`
- `pandora_daemon/download.py:146-177`
- `pandora_daemon/download.py:224-226`

现状：
- `cancel()` 会把 gid 放进 `_cancelled`
- worker 遇到 gid in `_cancelled` 直接跳过
- `submit()/resume()/retry_failed()` 未显式清掉 `_cancelled`

目标修复：
- fresh submit/resume/retry 时显式移除 `_cancelled` 中对应 gid
- 或重构为 task-instance 级取消状态
- 先做最小正确修复，不做大规模架构翻新

建议改动文件：
- `pandora_daemon/download.py`
- `tests/pandora_daemon/test_download.py`
- `tests/pandora_daemon/test_routes_downloads.py`

### P1-6 `.agents/skills/pandora/SKILL.md` frontmatter YAML 解析错误

证据：
- `.agents/skills/pandora/SKILL.md:3`

现状：
- `description:` 行包含冒号但未整体加引号，导致 YAML parse 失败

目标修复：
- 修正 frontmatter quoting
- 顺手检查 frontmatter 其他字段合法性

建议改动文件：
- `.agents/skills/pandora/SKILL.md`

### P2-1 web feed 分页行为与 daemon 实际能力漂移

证据：
- `pandora_daemon/routes/browse.py:69-73, 131-154`
- `tests/pandora_daemon/test_routes_browse.py`
- 审计结论：web `homepage` / `popular` load-more 假设与真实 API 不一致

现状：
- `homepage` 无 `page` 参数
- `popular` 也非分页接口
- 但前端逻辑把它们当可累积 feed 使用

目标修复：
二选一，优先选择最小正确方案：
- 方案 A：前端去掉不真实的 load more
- 方案 B：真的给 daemon / upstream 加分页能力（不推荐本轮）

建议：
- 本轮只做 contract 收敛，不扩 feature
- 如果碰前端，仅做最小联动并避免踩已有 WIP

建议改动文件：
- 若联动：`pandora-web/src/hooks/useGalleries.ts`
- 文档：`docs/api_reference.md`

### P2-2 文档与公共契约测试需要同步

重点：
- `docs/api_reference.md`
- `tests/pandora_daemon/test_agent_contracts.py`
- 如 CLI 有 machine contract 变化：`tests/pandora_daemon/test_cli.py`

---

## 2. 推荐执行顺序

### Phase 1: 安全边界和公共契约收口

1. 修 `image/proxy` SSRF + cookie 外带
2. 从 gallery detail 移除 `api_uid/api_key`
3. 收紧 downloads public serializer 与 WS 事件
4. 收紧 history/bookmarks/local_favorites public serializer
5. 收紧 config update 请求模型与校验
6. 收紧错误响应暴露
7. 修 download cancel/resubmit 状态 bug
8. 修 repo-local Pandora skill YAML

### Phase 2: 契约对齐与最小联动

9. 同步 agent contract tests / CLI tests / docs
10. 处理 web homepage/popular 非真实分页 drift（如需要，仅最小改动）

### Phase 3: 方向性整理（本轮可只记录 TODO）

11. 明确 TUI 为 frozen/deprecated，并把其隐式契约提升到 tests/docs
12. 再讨论是否物理删除 `pandora-tui/`
13. 再讨论 skill/plugin 包装形式

---

## 3. 推荐的 agent 协作模式

### 3.1 角色分工

Hermes 主控负责：
- 读取本 handoff 文档
- 保护现有 dirty repo WIP
- 选择每个 phase 的边界
- 启动 OpenCode/Codex
- 亲自检查 diff、读取关键文件、运行测试
- 决定是否继续下一阶段

OpenCode 负责：
- 实现 bounded coding task
- 按明确文件边界改代码
- 在单个 phase 内完成相关测试修复

Codex 负责：
- 对 OpenCode 产出的 diff 做独立 review
- 查 contract/backward-compat/security/test gap
- 必要时接手小范围补丁，但不要和 OpenCode 同时编辑同一批文件

### 3.2 推荐执行模式

每个 phase：
1. Hermes 记录当前 `git status --short --branch`
2. Hermes 给 OpenCode 一个明确、有限的 task prompt
3. OpenCode 完成实现
4. Hermes 回读关键 diff + 运行 targeted tests
5. Hermes 给 Codex 一个“只审不改” prompt
6. Codex review 后，如有必要：
   - Hermes 自己做最小修补，或
   - 再给 OpenCode/Codex 一个极小修复任务
7. Hermes 再跑 targeted tests
8. Phase 通过后再进入下一 phase

### 3.3 不要做的事

- 不要让 OpenCode 自己决定大范围重构
- 不要让 OpenCode/Codex 触碰 `pandora-web/` 现有 WIP，除非 prompt 明确授权
- 不要让两个 agent 同时写同一批文件
- 不要在 dirty repo 里 `git add .`
- 不要只看 agent 自报“tests passed”，必须自己跑

---

## 4. 分阶段实施任务（可直接照着派工）

### Task Group A: SSRF / image proxy hardening

Objective:
- 把 `/api/image/proxy` 从“任意 URL 代理”改成“受限图片代理”

Expected files:
- Modify: `pandora_daemon/image_service.py`
- Modify: `pandora_daemon/routes/browse.py`
- Modify/Add tests: `tests/pandora_daemon/test_image_service.py`
- Modify/Add tests: `tests/pandora_daemon/test_routes_browse.py`

Acceptance criteria:
- 非 allowlist host 返回 400/403，而不是尝试请求
- 不复用带认证 cookie 的 session
- 跳转到非 allowlist host 也失败
- 失败响应不回显底层异常全文
- 现有正常图片代理测试和新增安全测试都通过

Suggested verification:
- `uv run pytest tests/pandora_daemon/test_image_service.py tests/pandora_daemon/test_routes_browse.py -q`

### Task Group B: gallery detail / download / local-state public serializers

Objective:
- 清理不该对外暴露的字段

Expected files:
- Modify: `pandora_daemon/routes/gallery.py`
- Modify: `pandora_daemon/download.py`
- Modify: `pandora_daemon/routes/downloads.py`
- Modify: `pandora_daemon/routes/history.py`
- Modify: `pandora_daemon/routes/bookmarks_routes.py`
- Modify: `pandora_daemon/routes/local_favorites.py`
- Modify/Add tests:
  - `tests/pandora_daemon/test_agent_contracts.py`
  - `tests/pandora_daemon/test_routes_gallery.py`
  - `tests/pandora_daemon/test_routes_downloads.py`
  - `tests/pandora_daemon/test_routes_history.py`
  - `tests/pandora_daemon/test_routes_bookmarks.py`
  - `tests/pandora_daemon/test_routes_local_favorites.py`
  - `tests/pandora_daemon/test_ws.py`
  - `tests/pandora_daemon/test_cli.py`（如 CLI 依赖收缩后的 shape）

Acceptance criteria:
- gallery detail 不再暴露 `api_uid/api_key`
- downloads REST/WS 不再暴露 `token/output_dir/viewer_urls/thumb_urls/thumb_sprites`
- history/bookmarks/local_favorites 不再暴露 `token`
- 公共契约测试更新到新的安全 shape

Suggested verification:
- `uv run pytest tests/pandora_daemon/test_agent_contracts.py tests/pandora_daemon/test_routes_gallery.py tests/pandora_daemon/test_routes_downloads.py tests/pandora_daemon/test_routes_history.py tests/pandora_daemon/test_routes_bookmarks.py tests/pandora_daemon/test_routes_local_favorites.py tests/pandora_daemon/test_ws.py tests/pandora_daemon/test_cli.py -q`

### Task Group C: config update validation + error surface tightening

Objective:
- 收紧 `/api/config` 更新边界，并统一更安全的错误输出

Expected files:
- Modify: `pandora_daemon/routes/config_routes.py`
- Modify: `pandora_daemon/app.py`
- Modify: `pandora_daemon/routes/browse.py`
- Modify: `pandora_daemon/routes/gallery.py`
- Modify/Add tests:
  - `tests/pandora_daemon/test_routes_config.py`
  - `tests/pandora_daemon/test_exception_handlers.py`
  - `tests/pandora_daemon/test_routes_browse.py`
  - `tests/pandora_daemon/test_routes_gallery.py`

Acceptance criteria:
- `PUT /api/config` 使用明确 request model
- 未知字段 / 非法值明确报错
- 错误响应不再直接拼接底层异常全文
- health/config 的 safe public contract 不回退

Suggested verification:
- `uv run pytest tests/pandora_daemon/test_routes_config.py tests/pandora_daemon/test_exception_handlers.py tests/pandora_daemon/test_routes_browse.py tests/pandora_daemon/test_routes_gallery.py -q`

### Task Group D: download cancel/resubmit bug + repo skill YAML

Objective:
- 修运行态 bug，清理 repo skill 可读性问题

Expected files:
- Modify: `pandora_daemon/download.py`
- Modify: `tests/pandora_daemon/test_download.py`
- Modify: `tests/pandora_daemon/test_routes_downloads.py`
- Modify: `.agents/skills/pandora/SKILL.md`

Acceptance criteria:
- cancel 后 fresh submit/resume/retry 可正常继续
- 增加对应 regression tests
- Pandora repo-local skill frontmatter 可被 YAML 解析

Suggested verification:
- `uv run pytest tests/pandora_daemon/test_download.py tests/pandora_daemon/test_routes_downloads.py -q`
- 如有 skill validator，可再跑；没有的话至少人工复读 frontmatter

### Task Group E: docs / contract sync + optional minimal web alignment

Objective:
- 把 docs/tests/可选前端行为同步到真实契约

Expected files:
- Modify: `docs/api_reference.md`
- Optional minimal modify: `pandora-web/src/hooks/useGalleries.ts`
- Optional minimal modify: `pandora-web/src/models.ts`
- 相关 tests 如需增加/更新

Acceptance criteria:
- 文档不再暗示 homepage/popular 是真实分页 feed
- 如联动 web，则行为与 daemon 实际能力一致
- 不扩大到 UI 重做

Suggested verification:
- `uv run pytest tests/pandora_daemon/test_agent_contracts.py tests/pandora_daemon/test_cli.py -q`
- `npm --prefix pandora-web run build`
- `npm --prefix pandora-web run lint`

---

## 5. 给 OpenCode 的推荐 prompt 模板

在每个 task group 开始前，Hermes 先记录 dirty state，然后给 OpenCode 一个严格边界 prompt。

模板：

```text
You are implementing a bounded fix in the Pandora repository.

Repository: /home/ycyc/code/projects/pandora

Important constraints:
- Existing dirty files are user-owned WIP. Do not touch or reformat them unless explicitly listed in scope.
- Do not edit/stage/commit any files outside the allowed list.
- Do not use broad refactors.
- Keep changes minimal, contract-focused, and test-backed.
- Use uv for Python commands.
- After changes, run the requested targeted tests.

Out-of-scope existing WIP that must not be touched unless explicitly listed:
- pandora-tui/Cargo.lock
- pandora-web/README.md
- pandora-web/src/App.tsx
- pandora-web/src/api/client.ts
- pandora-web/src/components/GalleryCard.tsx
- pandora-web/src/components/GalleryDrawer.tsx
- pandora-web/src/components/Reader.tsx
- pandora-web/src/hooks/useGalleries.ts
- pandora-web/src/hooks/useWebSocket.ts
- pandora-web/src/models.ts
- pandora-web/src/styles/variables.css
- pandora_daemon/app.py

Task:
<粘贴某一个 Task Group 的 objective + acceptance criteria>

Allowed files:
<明确列出可编辑文件>

Verification to run:
<明确列出 pytest / npm 命令>

Report back with:
1. files changed
2. key contract/security decisions
3. test commands run and results
4. any blockers or follow-up risks
```

说明：
- 如果某个 task group 必须改 `pandora_daemon/app.py` 或某个 web WIP 文件，就把它从 out-of-scope 移到 allowed files，单独明确授权。

---

## 6. 给 Codex 的推荐复核 prompt 模板

```text
Review the Pandora diff for this bounded fix. Prefer finding contract regressions, security gaps, test blind spots, and over-exposed public fields. Do not make code changes unless explicitly asked.

Repository: /home/ycyc/code/projects/pandora

Review focus:
- public REST/WS/CLI contract correctness
- secret/token/path exposure
- SSRF / unsafe fetch behavior
- backward-compat where intentional
- tests actually covering the new behavior
- accidental edits to out-of-scope dirty files

Files intended to change:
<列出本 phase 预期文件>

Out-of-scope dirty files that should remain untouched:
- pandora-tui/Cargo.lock
- pandora-web/README.md
- pandora-web/src/App.tsx
- pandora-web/src/api/client.ts
- pandora-web/src/components/GalleryCard.tsx
- pandora-web/src/components/GalleryDrawer.tsx
- pandora-web/src/components/Reader.tsx
- pandora-web/src/hooks/useGalleries.ts
- pandora-web/src/hooks/useWebSocket.ts
- pandora-web/src/models.ts
- pandora-web/src/styles/variables.css
- pandora_daemon/app.py

Output format:
- Critical issues
- Important issues
- Minor issues
- Verdict: APPROVED or REQUEST_CHANGES
```

---

## 7. 主控每个 phase 的固定验证步骤

每个 phase 结束后，Hermes 主控至少执行：

```bash
git status --short --branch
git diff --stat
uv run pytest <该 phase 对应测试> -q
```

跨多个 phase 或准备收尾时再执行：

```bash
uv run pytest tests/pandora_daemon -q
npm --prefix pandora-web run build
npm --prefix pandora-web run lint
```

如果有 staged 内容，额外执行：

```bash
git diff --cached --check
git diff --cached --stat
```

---

## 8. 本轮不做的事

- 不把 `pandora-tui/` 直接删除
- 不做 web UI 重构
- 不新建 Hermes 插件/toolset 包装层
- 不把所有序列化逻辑一次性重写成复杂 schema framework
- 不做 daemon supervisor / installer / packaging overhaul

---

## 9. 完成定义

本 handoff 对应的修复工作，完成标准为：

1. P0/P1 问题全部修完并有 regression tests
2. 公共 REST/WS/CLI contract 不再暴露多余敏感字段
3. `/api/image/proxy` 不再是任意 URL SSRF 面
4. `PUT /api/config` 不再接受无结构裸 dict 任意写配置
5. download cancel/resubmit bug 有测试覆盖
6. repo-local Pandora skill 可被正常解析
7. docs 与 tests 至少同步到新的真实契约
8. 现有 user-owned WIP 未被误改

---

## 10. 建议的首次实施切片

如果下一次 /new 只想先做一个最值回票价的切片，推荐：

Slice 1:
- Task Group A（SSRF）
- Task Group B 中的 gallery detail / download serializer 收口

原因：
- 安全收益最高
- 最符合“为 skill/plugin 做薄接口”的方向
- 能最快把最脏的公共边界收紧
