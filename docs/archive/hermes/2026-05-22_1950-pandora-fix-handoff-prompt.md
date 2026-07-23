# Pandora /new 修复交接 Prompt

> Status: archived. The handoff was completed in `d4fea6f`; the remaining Web contract alignment was completed in `69bece7`.

把下面整段复制到新的 `/new` 会话里即可：

```text
你现在在仓库 `/home/ycyc/code/projects/pandora` 中工作。

先读这些文件，然后开始执行，不要先空谈：
1. `/home/ycyc/code/projects/pandora/CLAUDE.md`
2. `/home/ycyc/code/projects/pandora/.hermes/plans/2026-05-22_1905-pandora-full-review.md`
3. `/home/ycyc/code/projects/pandora/.hermes/plans/2026-05-22_1950-pandora-fix-handoff.md`

任务目标：
- 根据 handoff 文档，开始修复 Pandora 的安全和公共契约问题
- 优先支持项目从 daemon + CLI 向 agent/skill/plugin 友好接口演进
- `pandora-tui/` 视为 frozen/deprecated reference consumer；本轮不要继续投入 TUI 开发，也不要现在就直接删除它

必须遵守：
- 当前仓库是 dirty repo，先执行 `git status --short --branch` 记录现状
- 现有 dirty files 视为 user-owned WIP，除非某个 phase 明确授权，不要触碰：
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
- 不要 `git add .`
- 不要盲目 stage 目录
- Python 命令一律 `uv run ...`
- 先做 P0/P1，不做大而全重构

协作要求：
- 你可以协调 OpenCode 和 Codex
- 推荐模式：Hermes 主控 + OpenCode 实现 + Codex 独立复核
- 主控必须自己读 diff、自己跑测试，不要只信任外部 agent 自报结果
- 不要让 OpenCode/Codex 同时编辑同一批文件

执行顺序：
1. 先创建一个简短 todo / phase plan
2. 先做 Phase 1 / Slice 1：
   - `/api/image/proxy` SSRF + cookie 外带修复
   - `gallery detail` 和 `downloads` 的公共字段收口
3. 每个小阶段都要：
   - 调用 OpenCode 做有边界的实现
   - 主控回读关键文件和 diff
   - 跑对应 targeted tests
   - 再调用 Codex 做 review
   - 如有必要再补小修
4. 阶段完成后再决定是否继续下一个阶段

本轮优先修的具体问题：
- `/api/image/proxy` 当前会接受任意 URL，并复用带 ExHentai cookies 的 session，存在 SSRF + cookie 外带风险
- `GET /api/gallery/{gid}/{token}` 不应再暴露 `api_uid` / `api_key`
- downloads 的 REST/WS 状态不应再暴露 `token`、`output_dir`、`viewer_urls`、`thumb_urls`、`thumb_sprites`
- history / bookmarks / local_favorites 不应直接返回 `token`
- `PUT /api/config` 不能继续用无结构裸 dict + setattr 方式随意更新配置
- error responses 不应继续直接拼接底层异常全文
- download cancel 后重新 submit/resume/retry 的 `_cancelled` 逻辑要修
- `.agents/skills/pandora/SKILL.md` frontmatter YAML 要修正

请先做这些动作：
1. 读取 handoff 文档和关键源文件
2. 记录 git 状态
3. 建立 todo
4. 开始第一个 bounded phase（优先 SSRF 修复）
5. 立即调用 OpenCode 或其他合适工具开工，不要只输出计划

建议的第一批验证命令（按需分阶段跑）：
- `uv run pytest tests/pandora_daemon/test_image_service.py tests/pandora_daemon/test_routes_browse.py -q`
- `uv run pytest tests/pandora_daemon/test_agent_contracts.py tests/pandora_daemon/test_routes_gallery.py tests/pandora_daemon/test_routes_downloads.py tests/pandora_daemon/test_ws.py tests/pandora_daemon/test_cli.py -q`
- `uv run pytest tests/pandora_daemon/test_routes_history.py tests/pandora_daemon/test_routes_bookmarks.py tests/pandora_daemon/test_routes_local_favorites.py -q`
- `uv run pytest tests/pandora_daemon/test_routes_config.py tests/pandora_daemon/test_exception_handlers.py -q`
- `uv run pytest tests/pandora_daemon/test_download.py tests/pandora_daemon/test_routes_downloads.py -q`
- 最后再视情况跑：`uv run pytest tests/pandora_daemon -q`

输出风格：
- 简洁汇报：结论 → 变更 → 验证
- 但在真正开始前必须先用工具行动
```
