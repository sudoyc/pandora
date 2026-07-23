# 架构决策记录

状态：现役
最近整理：2026-07-23

本文件记录当前已经接受的长期决策。新决策使用新的编号；已实施的历史决策不静默删除，
需要改变时追加一条 `Superseded` 记录并说明替代关系。

| ID | 状态 | 决策 | 主要理由 | 重新评估条件 |
|---|---|---|---|---|
| ADR-001 | Accepted | `exhentai_api` 保持无状态 | parser/client 可独立测试和复用，上游变化集中处理 | 出现无法由调用参数表达的上游协议状态 |
| ADR-002 | Accepted | daemon 是唯一有状态边界 | 避免凭据、缓存、队列、书签和 library 多份事实来源 | daemon 被拆成多个独立进程且有明确状态协议 |
| ADR-003 | Accepted | REST/WS + CLI JSON/NDJSON 是公共机器契约 | 便于测试、脚本和 agent 使用，避免解析 UI 文本 | 引入正式版本化 RPC 且迁移成本可控 |
| ADR-004 | Accepted | Agent Pack 是 agent 文档源，wrapper 必须薄 | 防止工具专属实现复制业务逻辑和状态 | Agent Pack 无法表达必要能力，且已有具体失败证据 |
| ADR-005 | Accepted | Web 是可选 consumer；Rust TUI 冻结 | 资源集中在 daemon/CLI 可靠性，保留历史参考而不继续分叉 | 明确的用户需求、维护者和验收预算重新出现 |
| ADR-006 | Accepted | 内部 model 与公共 DTO 分离 | 防止 token、本地路径和抓取辅助数据泄露或固化为契约 | 无；新增公共字段仍需显式评审 |
| ADR-007 | Accepted | 本地优先并默认只绑定 loopback | daemon 持有凭据和本地文件能力，不应默认暴露公网 | 增加认证、TLS、权限模型和远程部署需求 |
| ADR-008 | Accepted | 历史设计统一归档，不与当前文档并列 | 保留决策上下文，同时避免旧计划被误执行 | 无；归档内容需要恢复时先形成新决策 |

## 决策约束

### 状态写入

只有 daemon 可以写入 Pandora 配置、SQLite、下载状态、缓存和离线库。CLI、Web、Agent
通过公开接口请求变更，不直接操作这些文件。

### consumer 边界

CLI、Web、Agent wrapper 不导入 `exhentai_api` 执行用户工作流，不直接保存凭据，不创建
独立下载队列或 library 索引。复杂选择属于 agent/UI，业务事实属于 daemon。

### 公共数据

公开字段遵循最小必要原则。增加字段前先判断它是稳定用户概念还是 daemon 实现细节；
后者保留在内部 model。所有机器契约变化必须有测试和文档共同落地。

### 历史实现

`pandora-tui/` 和 [`docs/archive/`](../archive/README.md) 不代表当前方向。修复公共契约时以
Python contract tests 为依据，不为了兼容冻结 consumer 恢复已移除的敏感字段。
