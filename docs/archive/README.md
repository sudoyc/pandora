# 文档归档

状态：Historical / Non-authoritative
最近整理：2026-07-23

本目录保存已经完成、被替代或不再符合当前方向的设计资料。文件继续保留用于追溯需求、
实现和决策背景，但不得作为当前接口或开发任务的依据。

当前权威入口见 [`../README.md`](../README.md)。

## 分类

| 目录 | 内容 |
|---|---|
| [`architecture/`](architecture/) | 被当前架构库替代的系统说明 |
| [`reference/`](reference/) | Android 参考项目等外部实现研究 |
| [`roadmaps/`](roadmaps/) | 已完成或被替代的路线图 |
| [`plans/`](plans/) | 2026-04 的详细实施计划 |
| [`specs/`](specs/) | 2026-04 的功能设计规格 |
| [`tui/`](tui/) | 已冻结 Rust TUI 的设计、审计和修复计划 |
| [`web/`](web/) | 已被当前 Web 实现和新路线图替代的早期方案 |
| [`hermes/`](hermes/) | 2026-05 已执行的 agent/CLI/Hermes 计划和交接记录 |

根目录中的 `IMPROVEMENTS.md` 与 `search_and_favorites_api.md` 是更早的专题记录，保留原名
以便 Git 历史追踪。

## 使用规则

- 归档文件中的路径、数量、命令和接口可能已经失效。
- 归档文件不接收事实同步更新；需要恢复其中的想法时，先写新的决策或路线图条目。
- 修复归档文件的安全问题或真实泄密仍然允许；普通措辞和旧链接不做持续维护。
- 从现役区归档时使用 `git mv`，并在文件顶部或本索引注明替代文档。
