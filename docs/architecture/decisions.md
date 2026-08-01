# 架构决策记录

状态：现役
最近整理：2026-08-02

本文件记录当前已经接受的长期决策。新决策使用新的编号；已实施的历史决策不静默删除，
需要改变时追加一条 `Superseded` 记录并说明替代关系。

| ID | 状态 | 决策 | 主要理由 | 重新评估条件 |
|---|---|---|---|---|
| ADR-001 | Superseded by ADR-011 | 独立 `exhentai_api` 保持无状态 | 该约束已并入 provider adapter 边界，原独立顶层包不再存在 | 见 ADR-011 |
| ADR-002 | Accepted | daemon 是唯一有状态边界 | 避免凭据、缓存、队列、书签和 library 多份事实来源 | daemon 被拆成多个独立进程且有明确状态协议 |
| ADR-003 | Accepted | REST/WS + CLI JSON/NDJSON 是公共机器契约 | 便于测试、脚本和 agent 使用，避免解析 UI 文本 | 引入正式版本化 RPC 且迁移成本可控 |
| ADR-004 | Accepted | Agent Pack 是 agent 文档源，wrapper 必须薄 | 防止工具专属实现复制业务逻辑和状态 | Agent Pack 无法表达必要能力，且已有具体失败证据 |
| ADR-005 | Accepted | Web 是可选 consumer；Rust TUI 冻结 | 资源集中在 daemon/CLI 可靠性，保留历史参考而不继续分叉 | 明确的用户需求、维护者和验收预算重新出现 |
| ADR-006 | Accepted | 内部 model 与公共 DTO 分离 | 防止 token、本地路径和抓取辅助数据泄露或固化为契约 | 无；新增公共字段仍需显式评审 |
| ADR-007 | Accepted | 本地优先并默认只绑定 loopback | daemon 持有凭据和本地文件能力，不应默认暴露公网 | 增加认证、TLS、权限模型和远程部署需求 |
| ADR-008 | Accepted | 历史设计统一归档，不与当前文档并列 | 保留决策上下文，同时避免旧计划被误执行 | 无；归档内容需要恢复时先形成新决策 |
| ADR-009 | Accepted | REST/CLI/WS 使用独立 major 的机器契约版本 | 应用发布版本不能表达 consumer 兼容性；跨 surface 的字段、错误和退出语义需要同一边界 | 引入正式版本化 RPC，或现有 v1 必须发生破坏性变化 |
| ADR-010 | Accepted | 经验证的纯 Python wheel 是唯一默认运行分发，并安装到隔离 venv | 复用现有 Python 3.12、entry point、artifact 校验和回滚流程，保持跨平台且不新增打包器 | Python/uv 前置条件成为主要采用障碍，或出现必须离线自包含部署的证据 |
| ADR-011 | Accepted | 应用层只依赖 `GalleryProvider`；上游 client/parser/model 归属各自 adapter | 替换 provider 不改路由、下载、缓存、数据库或公共 v1；具体上游变化集中在 adapter | 两个真实 adapter 无法共享现有契约，且失败证据表明需要扩展 provider-neutral 领域模型 |

## 决策约束

### 状态写入

只有 daemon 可以写入 Pandora 配置、SQLite、下载状态、缓存和离线库。CLI、Web、Agent
通过公开接口请求变更，不直接操作这些文件。

### Provider 边界

路由、应用状态、图片服务和下载管理器只接收 `GalleryProvider` 及 provider-neutral model/error。
内置 adapter 位于 `pandora_daemon/providers/<provider-id>/`，其包元数据声明 `PROVIDER_ID` 和
惰性 factory target；默认 registry 只确定性发现仓库内置包，不加载第三方 entry point。测试或
组合根可以显式注入 `ProviderRegistry`，不需要修改应用层。

默认 provider 保留既有 `pandora.db`、`downloads.json` 和 library 路径。其他 provider 的数据库、
下载状态和 library 使用 provider-qualified workspace，防止切换 provider 时共享不兼容状态。
adapter 内的 upstream model 不是 REST/CLI/WS v1，也不是 consumer 可导入的公共边界。

### consumer 边界

CLI、Web、Agent wrapper 不导入 provider adapter 或其 upstream 实现执行用户工作流，不直接保存
凭据，不创建独立下载队列或 library 索引。复杂选择属于 agent/UI，业务事实属于 daemon。

### 公共数据

公开字段遵循最小必要原则。增加字段前先判断它是稳定用户概念还是 daemon 实现细节；
后者保留在内部 model。所有机器契约变化必须有测试和文档共同落地。

### 机器契约版本

`GET /api/health` 公告独立于应用版本的 `contract_version`。同一 major 内只允许在明确可扩展
对象增加可选字段；既有字段语义/类型、HTTP 错误映射、CLI 退出码和 WebSocket 终态分类保持
稳定。破坏性变化必须启用新的 major 和并行迁移入口。弃用项需声明替代方案，不污染机器
stdout，至少跨越后续一个 minor release，并且只能在新的机器契约 major 中移除。详细规则以
[Agent Contract](../agent/contract.md#machine-contract-versioning) 为准。

### 默认运行分发

默认运行 artifact 是 `pandora-VERSION-py3-none-any.whl`，使用
[`scripts/release.py`](../../scripts/release.py) 从受控 sdist 构建并校验。安装目标是独立的
Python 3.12 venv；`pandora` 和 `pandora-daemon` 是稳定入口。wheel 只发布 `pandora_daemon` 顶层
包树，provider 实现嵌套其中；sdist 用于可追溯构建和源码回滚，不是第二条默认运行安装路径。
wheel 不捆绑可选 Web、冻结 TUI、凭据或 daemon 运行状态。

单目录可执行包当前不采用，因为它需要新的冻结工具、按操作系统构建和额外运行时兼容矩阵；
systemd 安装脚本也不作为分发，因为它只覆盖 Linux，并会对主机路径和服务状态执行写操作。
systemd 仍可作为 wheel 安装后的部署配方。若 Python/uv 前置条件或在线解析依赖成为有复现证据的
用户阻塞，再评估自包含 artifact，而不是同时维护多条默认路径。

### 历史实现

`pandora-tui/` 和 [`docs/archive/`](../archive/README.md) 不代表当前方向。修复公共契约时以
Python contract tests 为依据，不为了兼容冻结 consumer 恢复已移除的敏感字段。
