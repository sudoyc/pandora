# 架构文档库

状态：现役
基线版本：`0.2.0`
最近核对：2026-07-23

## 阅读顺序

1. [系统概览](system-overview.md)：组件、依赖方向、状态、数据流和安全边界。
2. [架构决策](decisions.md)：当前实现必须遵守的长期选择。
3. [未来开发计划](../roadmap.md)：从当前状态到下一阶段的优先级和验收条件。
4. [API Reference](../api_reference.md)：具体 Python、REST、WebSocket 和 CLI 接口。
5. [Agent Pack](../agent/README.md)：机器调用契约、schema 和操作工作流。

## 维护规则

- 本目录只描述当前架构，不保存实施过程、评审对话或已完成任务清单。
- 架构图必须能映射到仓库中的真实模块；不为尚未批准的组件预留方框。
- `exhentai_api`、daemon、consumer 之间的依赖方向变化必须先记录决策。
- 具体端点和字段不在架构文档重复维护，统一链接到 API/Agent contract。
- 被替代的架构文档通过 `git mv` 放入 [`../archive/architecture/`](../archive/architecture/)。

历史设计与参考项目研究见 [文档归档](../archive/README.md)。
