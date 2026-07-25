# 开发路线图

状态：Complete
基线：`0.2.0` / `v0.2.0`（`5f9cf3b`）
最近核对：2026-07-25

本路线图维护阶段方向、依赖和完成标准。每个阶段以可验证结果结束，不按文件数量或主观
完成度结项。动态工作包状态、命令证据和检查点只维护在
[长期开发工作计划](development/work-program.md)，避免形成第二份执行事实源。

跨轮次无人值守执行必须遵守
[长期开发约束](development/unattended-development.md)。

## 当前进度

- `UP-01` 至 `CLOSE-01` 已按工作计划记录的直接证据完成；最终统一检查为 685 个 Python
  测试、25 个 Web unit/component 测试和 5 个 Chromium browser 测试全部通过。
- readiness、下载对账/恢复、版本化机器契约、Web 日常工作流、主分支 CI、可重复 release
  candidate 和纯 Python wheel 分发均已建立。
- 隔离环境已验证旧版安装、daemon 启动、health/config/readiness/status、候选升级、计划回滚
  和候选失败后的自动恢复。
- 注释 tag `v0.2.0` 和非草稿 GitHub Release 已发布；上传后的 wheel/sdist checksum、内容、
  安装、升级和回滚均已复核。`CLOSE-01` 最终审计已完成；Optional `WRAP-01` 不影响核心
  完成判定。最终证据见 [完成报告](development/completion-report.md)。
- 2026-07-23 后未重新执行真实账号探针；当前回归和分发证据来自脱敏 fixture 与隔离状态。

## 阶段总览

| 优先级 | 阶段 | 状态 | 前置条件 |
|---|---|---|---|
| P0 | 上游会话与端点可用性 | Done | 无 |
| P1 | 下载状态与 library 一致性 | Done | P0 的错误分类稳定 |
| P1 | CI 与发布基线 | Done | CI/candidate 与 `v0.2.0` tag/release 均已完成 |
| P2 | Agent/CLI 契约版本化 | Done | P0/P1 通过 |
| P2 | Web 可维护性与完整工作流 | Done | daemon 契约稳定 |
| P3 | 分发与薄 wrapper | Done | 默认 wheel 分发已完成；wrapper 为 Optional 且保持 Gated |

## 优先级

### P0：恢复可判定的上游可用性

目标：调用方能够区分 daemon 启动成功、凭据已配置、会话有效、上游接口漂移四种状态。

范围：

- 增加只读 auth/upstream readiness 探针，不返回 cookie 或账户敏感信息。
- 复核 homepage/search/popular 的空结果原因，避免认证失败被误报为成功空列表。
- 复核用户 home endpoint；更新正确端点，或明确标记为暂不可用并返回稳定错误。
- 用当前脱敏 fixture 更新 parser/route regression tests。
- 在 deployment 和 Agent bootstrap 中加入 readiness 诊断顺序。

完成标准：

- 无效会话得到结构化 auth/upstream 错误，不再与合法空结果混淆。
- homepage、search、popular、home 至少各有一条当前 fixture 测试。
- `health` 继续保持轻量；新的 readiness 命令/接口在无凭据环境也有确定输出。
- 全量测试通过，日志和机器输出不包含凭据或完整上游响应。

### P1：下载状态与 library 一致性

目标：重启、文件丢失或历史状态迁移后，用户能诊断并恢复下载，而不是看到互相矛盾的
queue/library 状态。

范围：

- 定义 download task、磁盘目录和 library metadata 的一致性规则。
- 增加只读 reconcile/report，再提供显式 repair/forget 操作。
- 为状态文件增加 schema/version 迁移策略和损坏文件恢复测试。
- 统一 status、pages、library 的公开状态词汇和终态语义。

完成标准：

- orphan task、缺失页面、缺失 metadata 和未登记 library 都能被报告。
- 修复操作幂等、可预览、不会静默删除页面文件。
- cancel/resume/retry/restart/reconcile 有集成测试覆盖。

### P1：建立持续集成与发布基线

目标：每个主分支提交自动执行与本地相同的最低质量门槛。

范围：

- CI：Python 3.12 测试、Web lint/build、`uv lock --check`、`git diff --check`。
- 增加内部 Markdown 链接检查和 Agent JSON Schema 校验。
- 定义版本、changelog、tag 和回滚流程；先发布一个可重复构建的内部版本。
- 固化不包含凭据和真实内容的 smoke fixture。

完成标准：

- 新 clone 按文档可重复完成安装、测试、构建和 daemon health probe。
- 合并前所有必需检查自动运行，失败可定位到具体层。
- release artifact、版本号和 tag 一致，发布步骤可回滚。

### P2：收紧 Agent/CLI 契约

目标：在增加 wrapper 前，CLI/REST/WS 的机器接口达到可版本化、可恢复、可观测的程度。

范围：

- 为主要 CLI 成功响应补齐 schema，不只覆盖错误和事件。
- 统一 REST 与 CLI error code、退出码和终态映射。
- 为长任务增加 request/correlation id 和最小诊断字段。
- 明确兼容策略：新增字段、弃用字段、breaking change 和 schema version。

完成标准：

- bootstrap、search、gallery、download、library/PDF 的成功与失败路径都有 contract test。
- Agent Pack 示例能在 fixture daemon 上端到端执行。
- wrapper 不需要解析 human output 或读取 daemon 状态文件。

### P2：把 Web 提升为可维护的人类客户端

目标：先补完整日常工作流和测试，再做视觉扩展。

范围：

- 拆分 `App.tsx` 的布局、搜索、画廊和下载状态职责。
- WebSocket 重连后从 `/api/downloads` 对账，避免只依赖实时事件。
- 增加 favorites、history、downloads、library 页面和明确的空/错/重试状态。
- 修复移动端布局、键盘操作和对话框焦点管理。
- 增加 reducer/hook 单元测试与关键浏览器 smoke tests。

完成标准：

- 首页、搜索、详情、阅读、下载、恢复、本地库形成完整可重复流程。
- daemon 重启或 WS 断线后 UI 状态可恢复。
- 桌面和移动视口无内容重叠，关键流程有自动化测试。

### P3：分发与薄 wrapper

前置条件：P0/P1 完成，Agent/CLI 契约稳定至少一个发布周期。

候选工作：

- 评估 wheel、单目录运行包或 systemd 安装脚本，选择一个可维护分发方式。
- 如确有需求，创建只包装 CLI/REST/WS 的 agent plugin/toolset。
- 为 wrapper 增加超时、取消和机器错误透传，不新增状态数据库。

完成标准：

- 干净环境可以安装、启动、探测、升级和回滚。
- wrapper 与 CLI 使用同一 contract suite，不复制业务逻辑。

## 非目标

- 不恢复或继续打磨 `pandora-tui/`。
- 不让 Web/CLI/Agent 直接请求上游或持久化凭据。
- 不在没有第二站点和具体差异证据前抽象多站点 adapter。
- 不把 Rust 重写、桌面壳或公网多用户部署列为默认方向。
- 不以新增功能数量替代上游兼容、状态恢复和契约测试。

## 维护方式

- 阶段优先级或完成标准变化时更新本文件；动态状态只在 work program 中维护。
- 长期运行时只允许一个工作包为 In Progress，并在 work program 中记录检查点和直接证据。
- 新需求先归入 P0-P3；无法说明用户结果和完成标准的条目不进入路线图。
- 阶段目标和完成标准保留在本文件；完成命令、提交和 CI 证据不在这里重复维护。
- 架构方向变化先更新 [架构决策](architecture/decisions.md)，再调整路线图。
