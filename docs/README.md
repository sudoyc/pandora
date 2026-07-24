# Pandora 文档库

状态：现役
最近整理：2026-07-23

本目录把当前设计、稳定契约、操作手册和历史材料分开维护。新成员先读
[架构入口](architecture/README.md)，再按任务进入对应文档。

## 当前文档

| 主题 | 权威文档 | 何时更新 |
|---|---|---|
| 系统边界与状态所有权 | [architecture/system-overview.md](architecture/system-overview.md) | 模块职责、依赖方向、持久化边界变化时 |
| 已接受的架构决策 | [architecture/decisions.md](architecture/decisions.md) | 出现新的跨模块长期约束时 |
| 开发优先级与完成标准 | [roadmap.md](roadmap.md) | 阶段开始、完成、取消或重新排序时 |
| 长期无人值守开发约束 | [development/unattended-development.md](development/unattended-development.md) | 自治权限、检查点、验证或停机规则变化时 |
| 长期执行队列与状态 | [development/work-program.md](development/work-program.md) | 工作包开始、完成、阻塞或依赖变化时 |
| 版本、构建与回滚 | [development/release-process.md](development/release-process.md) | 版本、artifact、候选发布或回滚规则变化时 |
| 长期 goal prompt | [development/goal-prompt.md](development/goal-prompt.md) | 启动协议或默认授权变化时 |
| Python、REST、WebSocket、CLI 接口 | [api_reference.md](api_reference.md) | 公共接口或数据形状变化时 |
| 部署与运行 | [deployment.md](deployment.md) | 配置、启动、服务管理或诊断方式变化时 |
| Python 库用法 | [exhentai_api_usage.md](exhentai_api_usage.md) | `exhentai_api` 公共 API 变化时 |
| Agent 机器契约与工作流 | [agent/README.md](agent/README.md) | agent 可见命令、事件、schema 或流程变化时 |
| Hermes 打包约定 | [hermes_integration.md](hermes_integration.md) | Hermes consumer 形态变化时 |
| Web 当前能力 | [../pandora-web/README.md](../pandora-web/README.md) | Web 功能或开发方式变化时 |

## 文档类型

- **Architecture**：描述当前系统必须保持的边界和依赖方向。
- **Decision**：记录已经接受、会长期影响实现的设计选择。
- **Contract**：描述调用方可以依赖的公共行为，必须与测试同步。
- **Runbook**：描述部署、操作和故障恢复流程。
- **Roadmap**：描述尚未完成的工作及其验收标准，不作为当前行为说明。
- **Archive**：只保留历史上下文，不再指导实现，统一放在 [archive/](archive/README.md)。

## 权威性规则

1. 可执行行为以代码和测试为事实来源；文档与其不一致时，差异本身就是缺陷。
2. 跨模块边界以架构文档和决策记录为约束，不能只在实现提交中隐式改变。
3. Agent 可见行为以 `docs/agent/`、JSON Schema 和 contract tests 为准。
4. `docs/archive/` 与历史 Git 提交只用于追溯，不覆盖当前文档。
5. 同一主题只保留一个现役入口；旧版本完成后立即归档。
6. 长期执行中，路线图维护阶段优先级，work program 只维护工作包状态和完成证据。

## 变更检查表

- 修改模块职责或依赖方向：更新系统概览，并追加或替代一条架构决策。
- 修改 REST/WS/CLI 公共行为：同步 API reference、Agent Pack、schema 和 contract tests。
- 修改配置、状态目录或启动方式：同步 deployment 文档。
- 完成路线图阶段：记录验证结果，更新阶段状态，把一次性计划移入 archive。
- 长期自治工作：同步 work program 检查点；权限、验证或停机策略变化时同步约束和 prompt。
- 归档文档：保留 Git 历史，添加归档说明，修复所有现役文档引用。
- 提交前：运行 Python 测试、相关前端/构建检查、`git diff --check` 和本地链接检查。
