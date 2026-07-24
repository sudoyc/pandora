# Pandora 长期开发工作计划

状态：In Progress
范围：当前路线图全部 Required 工作包
最近核对：2026-07-25

本文是长期开发的可执行队列和跨轮次检查点。阶段方向和优先级以
[开发路线图](../roadmap.md)为准，执行方式以
[无人值守开发约束](unattended-development.md)为准。

## 1. 当前检查点

| 字段 | 当前值 |
|---|---|
| Program | In Progress |
| Active work package | None（等待 `REL-02` 人工门） |
| Next work package | `REL-02`（Gated） |
| Last completed work package | `DIST-02` |
| Blockers | None；`REL-02` 尚未人工放行 |
| Source baseline | `fdca102`; 2026-07-23 文档与运行盘点 |
| Last full Python evidence | 685 passed（2026-07-25；本地统一检查，implementation `497cb5c`） |
| Last Web evidence | 25 unit/component + 5 Chromium browser passed；lint/build passed（2026-07-25；本地统一检查，implementation `497cb5c`） |

维护规则：开始工作时只把一个工作包改为 `In Progress`；完成时填写实际证据和 commit，并更新
下一项。详细过程保留在提交历史或阶段完成报告，不在本文件堆积逐命令日志。

## 2. 功能补全范围

| 能力 | 目标结果 | 对应工作包 |
|---|---|---|
| 上游可用性 | daemon 存活、凭据配置、会话有效、端点/parser 漂移可区分 | `UP-01` - `UP-04` |
| 下载恢复 | 状态文件、页面目录、metadata、library 可报告、迁移、修复 | `DL-01` - `DL-04` |
| 工程基线 | 本地统一检查、CI、版本、构建、发布和回滚流程可重复 | `CI-01`, `CI-02`, `REL-01`, `REL-02` |
| 机器契约 | 成功/失败 schema、兼容规则、诊断关联和 Agent E2E 完整 | `CT-01` - `CT-04` |
| Web 工作流 | 搜索、详情、阅读、下载恢复、收藏、历史、本地库可测试 | `WEB-01` - `WEB-05` |
| 分发 | 干净环境可安装、启动、升级和回滚 | `DIST-01`, `DIST-02` |
| 薄 wrapper | 只有真实 consumer 需求出现后才实现 | `WRAP-01`（Optional） |

## 3. 执行顺序

状态值：`Queued`、`Ready`、`In Progress`、`Blocked`、`Gated`、`Done`、`Dropped`。

| ID | Required | 状态 | 依赖 | 工作结果 | 直接完成证据 |
|---|---|---|---|---|---|
| `UP-01` | Yes | Done | - | 定义 auth/session/upstream/parse/network 状态和稳定错误分类 | 契约说明、异常映射测试、无敏感字段测试 |
| `UP-02` | Yes | Done | `UP-01` | homepage/search/popular/home 使用当前脱敏 fixture，合法空列表不与失败混淆 | 四类 fixture regression tests 和 parser/route 目标测试 |
| `UP-03` | Yes | Done | `UP-01`, `UP-02` | 提供独立、只读、无凭据也有确定输出的 readiness REST/CLI 机器接口 | route/CLI/schema tests；失败类别和退出语义测试 |
| `UP-04` | Yes | Done | `UP-03` | 部署和 Agent bootstrap 使用统一诊断顺序 | fixture daemon smoke、deployment/Agent Pack/skill 同步 |
| `DL-01` | Yes | Done | `UP-04` | 定义 task、状态文件、磁盘页面、metadata、library 的一致性规则并提供只读报告 | orphan/missing/unregistered fixture matrix；REST/CLI report tests |
| `DL-02` | Yes | Done | `DL-01` | 下载状态有 schema version、原子迁移和损坏文件恢复 | 旧版本迁移、未知版本、截断/损坏文件测试 |
| `DL-03` | Yes | Done | `DL-01`, `DL-02` | 提供显式 dry-run repair/forget，幂等且不静默删除页面 | preview/apply/idempotency/no-delete tests 和机器契约 |
| `DL-04` | Yes | Done | `DL-03` | cancel/resume/retry/restart/reconcile 状态和终态词汇一致 | 生命周期集成测试、重启恢复 smoke、文档同步 |
| `CI-01` | Yes | Done | - | 建立一个本地统一检查入口，覆盖锁文件、Markdown 链接、Agent schema、Python 和 Web | 干净 clone 可执行；每个失败能定位具体检查 |
| `CI-02` | Yes | Done | `CI-01` | 主分支 CI 使用与本地一致的检查，不依赖凭据或真实内容 | workflow 配置、fixture-only run、分层 job 结果 |
| `REL-01` | Yes | Done | `CI-02`, `CT-01` | 统一版本/changelog/tag/构建/回滚规则并产出内部 release candidate | 版本一致性检查、artifact build/install dry-run、回滚 runbook |
| `CT-01` | Yes | Done | `UP-04`, `DL-04` | 定义 REST/CLI/WS 版本兼容、错误码、退出码和弃用策略 | 决策/contract 文档、错误矩阵 contract tests |
| `CT-02` | Yes | Done | `CT-01` | 主要成功响应都有 JSON Schema 并由真实 serializer fixture 校验 | health/readiness/search/gallery/download/library/tag schema tests |
| `CT-03` | Yes | Done | `CT-01` | 长任务具有 request/correlation id 和最小诊断字段，日志可关联且不泄密 | REST/CLI/WS 关联测试、日志脱敏测试 |
| `CT-04` | Yes | Done | `CT-02`, `CT-03` | Agent Pack 关键工作流能在 fixture daemon 端到端执行 | bootstrap/search/gallery/download/library/PDF 成功和失败 E2E |
| `WEB-01` | Yes | Done | `CT-02` | 建立 Web unit/component/browser 测试基线，覆盖已有 feed/detail/reader/WS reducer | 可重复 test script、现有行为基线测试、lint/build |
| `WEB-02` | Yes | Done | `WEB-01` | 拆分 `App.tsx` 职责，形成 typed API/error 层和稳定 view state | 组件/hook tests；无契约复制；lint/build |
| `WEB-03` | Yes | Done | `WEB-02`, `DL-04` | 初始加载、WS 重连、daemon 重启后下载状态从 REST 对账恢复 | disconnect/reconnect/restart browser tests |
| `WEB-04` | Yes | Done | `WEB-02`, `CT-02` | favorites、history、downloads、library 页面与本地阅读形成完整流程 | 各页空/错/重试/component tests 和关键 E2E |
| `WEB-05` | Yes | Done | `WEB-03`, `WEB-04` | 桌面/移动端无重叠，键盘和对话框焦点可用 | 多视口截图检查、键盘/焦点 browser tests、lint/build |
| `DIST-01` | Yes | Done | `REL-01`, `CT-04`, `WEB-05` | 用 ADR 选择一种维护成本可控的分发方式并构建 artifact | ADR、可重复 build、artifact 内容/版本检查 |
| `DIST-02` | Yes | Done | `DIST-01` | 隔离环境完成安装、启动、health/readiness、升级和回滚 | clean-environment scripted smoke 和失败恢复记录 |
| `REL-02` | Yes | Gated | `DIST-02` | 经人工放行后创建内部 tag/release，版本、tag 和 artifact 完全一致 | 远端 tag/release、artifact 校验和、安装 smoke、回滚点 |
| `WRAP-01` | No | Gated | `CT-04`, `DIST-02` | 有真实需求时创建只包装 CLI/REST/WS 的薄 consumer | 需求证据、同一 contract suite、无第二状态层 |
| `CLOSE-01` | Yes | Queued | 除自身外全部 Required | 逐条审计路线图、文档、测试、构建、分发和遗留项 | 最终 HEAD 全门槛通过、完成报告、干净且已同步的 Git 状态 |

## 4. 阶段验收补充

### P0 上游可用性

- readiness 不能把一次具体上游页面成功硬编码为所有能力成功。
- 合法空列表、未配置凭据、会话失效、网络失败、parser 漂移、端点移除必须可分别断言。
- 新错误对人类保持简洁，对机器保持稳定；服务端日志不得记录 cookie 或完整页面。

### P1 下载一致性与工程基线

- reconcile 默认只读；所有修复先 preview，再显式 apply。
- 现有页面文件优先保留，损坏状态文件隔离备份，不以删除来制造一致。
- CI 不需要真实账户、网络内容或本机路径；本地和 CI 使用同一个检查入口。
- release 工作先证明可构建、可安装、可回滚；实际 tag/release 由 `REL-02` 承担，未放行时
  长期目标保持未完成。

### P2 契约与 Web

- Schema 必须校验由实际 serializer/route 产生的 fixture，不只校验手写示例。
- 新增字段遵循兼容策略；删除或改义字段必须经过 breaking-change 流程。
- Web 不直接访问上游，不持久化 daemon 业务状态；断线恢复以 REST 快照对账。
- 浏览器验收至少覆盖一个桌面和一个移动视口，不接受内容重叠或焦点丢失。

### P3 分发

- 只选择一种默认分发方式，不同时维护多个未经验证的安装路径。
- 安装 smoke 必须在隔离环境执行，不能因开发 checkout 已有依赖而误判成功。
- wrapper 不属于默认完成范围；没有真实 consumer 和维护者时保持 `Gated`。

## 5. 新发现处理

新问题先记录复现证据，再按以下规则处理：

1. 凭据泄露、目录逃逸、数据丢失或不可逆损坏：新增 P0 bug，抢占当前工作。
2. 阻塞当前工作包完成：建立 `BUG-YYYYMMDD-NN` 并作为该包依赖。
3. 属于后续阶段：附加到对应工作包，不扩大当前 slice。
4. 只有代码洁癖、没有用户结果或无法验收：不进入 Required 队列。
5. 推翻架构决策：先形成 ADR 证据，未通过前保持 `Gated`。

## 6. 工作包完成记录

每个 Done 项追加一行；命令写实际执行内容，不能填写计划命令。

| ID | 完成日期 | Commit | 验证证据 | 备注 |
|---|---|---|---|---|
| `UP-01` | 2026-07-24 | `5484566` | `uv run python -m pytest tests/exhentai_api/test_api.py tests/exhentai_api/test_api_new.py tests/exhentai_api/test_exceptions.py tests/exhentai_api/test_client_exceptions.py tests/pandora_daemon/test_exception_handlers.py -q`（86 passed）；`uv run python -m pytest tests/pandora_daemon -q`（420 passed）；`uv run python -m pytest -q`（543 passed）；`git diff --check`（passed） | REST/Agent/schema 契约同步；响应和日志脱敏测试通过 |
| `CI-01` | 2026-07-24 | `cdace52` | 隔离 clone（初始无 `.venv`、`node_modules`、`dist`）执行 `uv run --frozen python scripts/check.py`：Python/Web lock、Markdown links、5 个 Agent schema、549 tests、Web lint/build、`git diff --check` 全部 passed | 失败阶段标签回归测试 6 passed；生产依赖 `npm audit --omit=dev` 为 0 vulnerabilities |
| `CI-02` | 2026-07-24 | `208a799` | `uv run --frozen python -m pytest tests/tools/test_repo_checks.py -q`（10 passed）；`uv run --frozen python scripts/check.py`（553 passed，全部阶段 passed）；GitHub Actions `30095287193` 的 Repository contracts、Python 3.12、Web 三个 job 全部 success 且 annotations 均为 0 | workflow 仅授予 `contents: read`；测试禁止凭据和实网上游引用；5 个 npm 告警仅来自开发工具依赖 |
| `UP-02` | 2026-07-24 | `3838b19` | `uv run --frozen python -m pytest tests/exhentai_api/test_current_upstream_fixtures.py tests/exhentai_api/test_parser_gallery.py tests/exhentai_api/test_parser_home.py -q`（9 passed）；`uv run --frozen python -m pytest tests/exhentai_api -q`（128 passed）；`uv run --frozen python -m pytest tests/pandora_daemon/test_routes_browse.py tests/pandora_daemon/test_routes_user.py tests/pandora_daemon/test_exception_handlers.py -q`（48 passed）；`uv run --frozen python scripts/check.py`（558 passed，全部阶段 passed）；GitHub Actions `30097455729` 三个 job 全部 success | 四类 fixture 脱敏与凭据泄漏扫描通过；原始响应临时目录已删除；未执行上游写操作 |
| `UP-03` | 2026-07-24 | `6752bdf` | `uv run --frozen python -m pytest tests/pandora_daemon/test_routes_readiness.py tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_agent_contracts.py -q -k readiness`（12 passed）；`uv run --frozen python -m pytest tests/exhentai_api -q`（129 passed）；`uv run --frozen python -m pytest tests/pandora_daemon -q`（432 passed）；`uv run --frozen python scripts/check.py`（571 passed，全部阶段 passed）；GitHub Actions `30098470051` 三个 job 全部 success | 无凭据不请求上游；四项只读探针、核心失败分类、超时、schema、脱敏和 CLI exit 0/1 均有直接测试 |
| `UP-04` | 2026-07-24 | `247b576` | `uv run --frozen python -m pytest tests/pandora_daemon/test_bootstrap_smoke.py tests/pandora_daemon/test_agent_contracts.py -q`（17 passed）；`uv run --frozen python -m pytest tests/pandora_daemon -q`（434 passed）；`uv run --frozen python scripts/check.py`（573 passed，全部阶段 passed）；GitHub Actions `30099122066` 三个 job 全部 success | fixture daemon 按 health/config/readiness/status 顺序执行且不请求上游；deployment、Agent Pack、skill 和活跃 agent 指引已同步；凭据泄漏检查通过 |
| `DL-01` | 2026-07-24 | `30bbf3a` | `uv run --frozen python -m pytest tests/pandora_daemon/test_download_consistency.py tests/pandora_daemon/test_routes_downloads.py tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_agent_contracts.py -q`（104 passed）；`uv run --frozen python -m pytest tests/pandora_daemon -q`（442 passed）；`uv run --frozen python scripts/check.py`（581 passed，全部阶段 passed）；GitHub Actions `30100089972` 三个 job 全部 success | fixture matrix 覆盖 orphan task、缺页、缺失/无效 metadata、未登记 library、旧下载根目录与正常活动 task；报告只读且不返回 token/本地路径 |
| `DL-02` | 2026-07-24 | `f32ed19` | `uv run --frozen python -m pytest tests/pandora_daemon/test_download_state.py tests/pandora_daemon/test_download.py tests/pandora_daemon/test_download_concurrency.py tests/pandora_daemon/test_download_consistency.py tests/pandora_daemon/test_integration.py tests/pandora_daemon/test_app_lifespan.py -q`（75 passed）；`uv run --frozen python -m pytest tests/pandora_daemon -q`（449 passed）；`uv run --frozen python scripts/check.py`（588 passed，全部阶段 passed）；GitHub Actions `30100798591` 三个 job 全部 success | v1 envelope、旧映射原子迁移、唯一损坏备份、部分 task 恢复和未知版本启动中止均有直接测试；cookie 值泄漏检查通过 |
| `DL-03` | 2026-07-24 | `8658150` | `uv run --frozen python -m pytest tests/pandora_daemon/test_download_recovery.py tests/pandora_daemon/test_download_consistency.py tests/pandora_daemon/test_download_state.py tests/pandora_daemon/test_download.py tests/pandora_daemon/test_download_concurrency.py tests/pandora_daemon/test_routes_downloads.py tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_agent_contracts.py tests/pandora_daemon/test_integration.py tests/pandora_daemon/test_app_lifespan.py -q`（198 passed）；`uv run --frozen python -m pytest tests/pandora_daemon -q`（471 passed）；`uv run --frozen python scripts/check.py`（610 passed，全部阶段 passed）；GitHub Actions `30101762205` 三个 job 全部 success | repair/forget 默认 preview、显式 apply、重复 apply no-op、活动 task 保护、重启持久化和 library 文件逐字节不变均有直接测试；cookie 值泄漏检查通过 |
| `DL-04` | 2026-07-25 | `9ce9592` | `uv run --frozen python -m pytest tests/pandora_daemon/test_download_lifecycle.py tests/pandora_daemon/test_download.py tests/pandora_daemon/test_download_state.py tests/pandora_daemon/test_download_concurrency.py tests/pandora_daemon/test_download_recovery.py tests/pandora_daemon/test_download_consistency.py tests/pandora_daemon/test_routes_downloads.py tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_agent_contracts.py tests/pandora_daemon/test_integration.py tests/pandora_daemon/test_app_lifespan.py -q`（214 passed）；`uv run --frozen python -m pytest tests/pandora_daemon -q`（487 passed）；`uv run --frozen python scripts/check.py`（626 passed，全部阶段 passed）；GitHub Actions `30103571183` 三个 job 全部 success | cancel/resume/retry/restart/reconcile、恢复 task 缺页、公共状态词汇和暂停保护均有直接测试；Web lint/build 与本地 Vite HTTP smoke 通过；`cookie.txt` 保持 ignored/0600 且未读取 |
| `CT-01` | 2026-07-25 | `3417ba0` | `uv run --frozen python -m pytest tests/pandora_daemon/test_machine_contract.py tests/pandora_daemon/test_exception_handlers.py tests/pandora_daemon/test_routes_config.py tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_agent_contracts.py -q`（156 passed）；`uv run --frozen python -m pytest tests/pandora_daemon -q`（510 passed）；`uv run --frozen python scripts/check.py`（649 passed，全部阶段 passed）；GitHub Actions `30104524589` 三个 job 全部 success | 独立 machine contract major、v1 兼容/破坏/弃用规则、REST/CLI/WS 错误与退出矩阵、WS 提前关闭失败语义均有直接测试；Agent Pack、schema、API reference、ADR 和 skill 已同步 |
| `REL-01` | 2026-07-25 | `69c91fc` | `uv run --frozen python -m pytest tests/tools/test_release.py tests/tools/test_repo_checks.py tests/pandora_daemon/test_routes_config.py -q`（36 passed）；`uv run --frozen python -m pytest -q`（654 passed）；`uv run --frozen python scripts/release.py candidate --tag v0.2.0 --out-dir TEMP_DIR`（sdist→wheel、内容/版本校验、临时 Python 3.12 安装和 CLI smoke passed）；独立重建 `cmp` passed，wheel SHA-256 `2d2a92c8f5e2185175ea2ccfbc2864dfa35ccf51de11394fd28a4a3d796cda8c`，sdist SHA-256 `fb980d1c53a5ce2c43a22f9424de7f8dda26d7191a8334f3bf7952466c6a4006`；`uv run --frozen python scripts/check.py`（654 passed，全部阶段 passed）；GitHub Actions `30105806033` 三个 job 全部 success | `pyproject.toml` 为版本源，lock/changelog/tag 规则进入 CI；sdist 从基线 10693 项收敛到 64 项且排除 Web 生成物、冻结 TUI、测试/归档和本地敏感状态；实际 tag/release 仍由 `REL-02` 人工门控制 |
| `CT-02` | 2026-07-25 | `5654218` | `uv run --frozen python -m pytest tests/pandora_daemon/test_success_response_schemas.py tests/pandora_daemon/test_routes_readiness.py tests/pandora_daemon/test_routes_config.py tests/pandora_daemon/test_routes_gallery.py tests/pandora_daemon/test_routes_downloads.py tests/pandora_daemon/test_routes_library.py tests/pandora_daemon/test_routes_tags.py tests/pandora_daemon/test_agent_contracts.py -q`（120 passed）；`uv run --frozen python -m pytest tests/pandora_daemon -q`（518 passed）；`uv run --frozen python -m pytest -q`（661 passed）；`uv run --frozen python -m scripts.repo_checks`（Markdown/schema passed）；`uv run --frozen python scripts/check.py`（661 passed，全部阶段 passed）；GitHub Actions `30106897849` 三个 job 全部 success | 新增 health、gallery detail、download task/list/pages/consistency、library list、tag suggest/status schema；readiness/search 既有 schema 纳入真实 route fixture 校验；Agent Contract、API reference 和 Pandora skill 已同步 |
| `CT-03` | 2026-07-25 | `73279c3` | `uv run --frozen python -m pytest tests/pandora_daemon/test_diagnostics.py tests/pandora_daemon/test_machine_contract.py tests/pandora_daemon/test_agent_contracts.py tests/pandora_daemon/test_success_response_schemas.py tests/pandora_daemon/test_routes_downloads.py tests/pandora_daemon/test_routes_library.py tests/pandora_daemon/test_download_lifecycle.py tests/pandora_daemon/test_download_state.py tests/pandora_daemon/test_cli.py -q`（190 passed）；`uv run --frozen python -m pytest tests/pandora_daemon -q`（526 passed）；`uv run --frozen python -m pytest -q`（669 passed）；`uv run --frozen python -m scripts.repo_checks`（Markdown/schema passed）；`uv run --frozen python scripts/check.py`（669 passed，全部阶段 passed）；GitHub Actions `30108961803` 三个 job 全部 success | REST header、CLI、下载持久状态、WS 和 PDF hook 使用可关联 ID；旧 v1 task 自动补写；动态路径、token、密码、标题、本地路径和异常文本不进入诊断日志；`cookie.txt` 未读取且未暂存 |
| `CT-04` | 2026-07-25 | `0168120` | `uv run --frozen python -m pytest tests/pandora_daemon/test_agent_workflows_e2e.py tests/pandora_daemon/test_bootstrap_smoke.py tests/pandora_daemon/test_agent_contracts.py tests/pandora_daemon/test_machine_contract.py -q`（50 passed）；`uv run --frozen python -m pytest tests/pandora_daemon -q`（532 passed）；`uv run --frozen python -m pytest -q`（675 passed）；`uv run --frozen python scripts/check.py`（675 passed，全部阶段 passed）；GitHub Actions `30110103154` 三个 job 全部 success | fixture CLI 经真实 parser、ASGI route、serializer/error handler 和 schema 覆盖 bootstrap、search、gallery、download NDJSON、library 与 PDF 成功/失败；未请求上游、未读取凭据或真实业务状态 |
| `WEB-01` | 2026-07-25 | `84d9cae` | `uv run --frozen python -m pytest tests/tools/test_repo_checks.py -q`（11 passed）；`npm run test:unit`（4 files、5 tests passed）；`npm run test:browser`（1 Chromium smoke passed）；`npm run lint`、`npm run build`（passed）；`uv run --frozen python scripts/check.py`（676 passed，全部阶段 passed）；`npm audit --omit=dev`（0 vulnerabilities）；Playwright 1280x800 fixture 截图检查（reader 全视口、drawer/sidebar 层级正确、console 0 errors）；GitHub Actions `30111555658` 三个 job 全部 success | Vitest/Testing Library/jsdom 和系统浏览器 Playwright 基线覆盖 feed、search、detail、reader、WS reducer；统一 Web 检查已接入 unit/browser/lint/build；修复 reader 在 modal 外不可点击及 sidebar 覆盖问题 |
| `WEB-02` | 2026-07-25 | `aec111d` | `npm run test:unit`（6 files、11 tests passed）；`npm run test:browser`（1 Chromium smoke passed，覆盖 feed→search/history→Browse→detail→reader）；`npm run lint`、`npm run build`（passed）；`uv run --frozen python scripts/check.py`（676 passed，全部阶段 passed）；Playwright 1280x800 fixture 截图检查（搜索/历史布局正常、reader 全视口、console 0 errors）；GitHub Actions `30112311546` 三个 job 全部 success | `App.tsx` 收敛为 43 行组合层；sidebar、search/header、feed、download panel 分离；判别联合消除 mode/query 无效组合；通用 `ApiError/apiGet` 保持 daemon 契约单一来源 |
| `WEB-03` | 2026-07-25 | `365fdc8` | `npm run test:unit`（6 files、13 tests passed）；`npm run test:browser`（2 Chromium tests passed，覆盖初始 REST 快照、WS 事件、500ms 重连和 daemon restart 对账）；`npm run lint`、`npm run build`（passed）；`uv run --frozen python scripts/check.py`（676 passed，全部阶段 passed）；`npm audit --omit=dev`（0 vulnerabilities）；Playwright 1280x800 fixture 截图检查（下载面板/进度条布局正常、console/page errors 0）；GitHub Actions `30113164369` 的 Repository contracts、Python 3.12、Web 三个 job 全部 success | REST 快照为权威状态，WS 事件在快照请求期间重放；重连采用 500ms 起、上限 5s 的指数退避；旧 daemon 状态可被新快照替换 |
| `WEB-04` | 2026-07-25 | `3a1a508` | `npm run test:unit`（7 files、23 tests passed，覆盖 workspace loading/empty/error/retry、favorites 分类、downloads live state 和本地 reader）；`npm run test:browser`（3 Chromium tests passed，覆盖 feed→reader、daemon restart 和四页面导航→本地阅读）；`npm run lint`、`npm run build`（passed）；`uv run --frozen python scripts/check.py`（676 passed，全部阶段 passed）；`npm audit --omit=dev`（0 vulnerabilities）；Playwright 1280x800 与 390x844 fixture 截图检查（无横向溢出或导航/内容重叠、console/page errors 0）；GitHub Actions `30114679940` 三个 job 全部 success | favorites/history/downloads/library 只消费 daemon REST；Library 直接使用本地文件端点；共享状态壳明确区分 loading、成功空列表、失败和 retry |
| `WEB-05` | 2026-07-25 | `5538b0b` | `npm run test:unit`（7 files、25 tests passed）；`npm run test:browser`（5 Chromium tests passed，覆盖 1280x800/390x844 布局边界、键盘打开、Reader 焦点循环、分层 Escape 和焦点恢复）；`npm run lint`、`npm run build`（passed）；`uv run --frozen python scripts/check.py`（676 passed，全部阶段 passed）；`npm audit --omit=dev`（0 vulnerabilities）；Playwright 1280x800 与 390x844 fixture 的 browse/drawer/reader 截图检查（无横向溢出、区域/控件重叠或 console/page errors）；GitHub Actions `30115683011` 三个 job 全部 success | 移动搜索改为纵向布局，长标题可断行；抽屉关闭控件在 loading/error 状态始终可用；Reader 自动聚焦、捕获 Tab/Escape 并恢复触发点焦点 |
| `DIST-01` | 2026-07-25 | `f9fb7e3` | `uv run --frozen python -m pytest tests/tools/test_release.py tests/tools/test_repo_checks.py -q`（16 passed）；两次执行 `uv run --frozen python scripts/release.py candidate --tag v0.2.0 --out-dir TEMP_DIR`（sdist→wheel、内容/版本/entry point 校验、临时 Python 3.12 安装和 CLI smoke passed）；`uv run --frozen python scripts/release.py verify --dist-dir TEMP_DIR`、独立 wheel `cmp`（passed）；wheel SHA-256 `c942ce844af72b9b48ce9d41530849026deaa71686e64b972934a376c6c9aa33`，sdist SHA-256 `310b7a9343866098517fb00ce440a9fe17c3bee4de6bf9961ef53ef82b5295d1`；`uv run --frozen python scripts/check.py`（677 passed，全部阶段 passed）；GitHub Actions `30116361699` 三个 job 全部 success | ADR-010 选择纯 Python wheel + 隔离 venv 为唯一默认运行分发；sdist 仅作构建/回滚伴随物；verifier 固定 Python 3.12 下限与两个 console entry point，排除 Web/TUI/凭据和运行状态 |
| `DIST-02` | 2026-07-25 | `497cb5c` | `uv run --frozen python -m pytest tests/tools -q`（24 passed）；`0.1.0` 临时旧版 wheel → 已验证 `0.2.0` wheel → `0.1.0` 计划回滚 smoke 退出 0，三阶段 health/config/readiness/status、contract `1` 和隔离状态保持均通过；损坏 `0.3.0` wheel smoke 退出 1 且 `automatic_rollback_recovered: true`；`uv run --frozen python scripts/check.py`（685 passed，全部阶段 passed）；`npm audit --omit=dev`（0 vulnerabilities）；GitHub Actions `30117478268` 三个 job 全部 success | 临时 HOME/config/cache/download/venv 与空 tag fixture 避免凭据和上游访问；输出不含子进程日志、配置或临时路径；`cookie.txt` 未读取且未暂存；真实状态降级仍须配对备份，`REL-02` 保持人工门 |

## 7. 阻塞与人工门记录

| ID | 首次发现 | 阻塞事实 | 已尝试 | 解除条件 | 可并行的下一项 |
|---|---|---|---|---|---|
| `UP-02` | 2026-07-24 | 仓库只有早期合成 `gallery_list.html`/`home.html`，没有 2026-07-23 探针对应的 homepage/search/popular/home 脱敏 fixture；实网上游探针默认关闭 | 检查 `tests/` fixture 清单及相关 Git 历史；文档所述 `../reference_project/` 在当前工作区不存在；未执行实网请求 | 提供四类当前脱敏 fixture，或明确授权只读实网上游探针并允许保存脱敏 fixture（2026-07-24 已解除） | None |
| `REL-02` | 2026-07-25 | 实际 tag/release/package publish 需要操作者明确放行 | `DIST-01` artifact 构建/校验和与 `DIST-02` 安装、升级、回滚及失败恢复均已验证；未创建 tag/release | 明确授予 `REL-02` 发布门，并复核当前 main、CI、版本与 artifact 校验和 | None |
