# Pandora 长期无人值守开发 Goal Prompt

状态：Active
最近核对：2026-07-23

将下面整个代码块作为长期 goal 的初始 prompt。它与
[无人值守开发约束](unattended-development.md)和
[执行工作计划](work-program.md)配套使用；不要只复制其中一个片段。

```text
你正在 Pandora 仓库中执行一个可跨轮次自动续跑的长期开发目标。

最终目标：按照 docs/development/work-program.md 的依赖和优先级，完成其中全部
Required 工作包，并用 docs/development/unattended-development.md 规定的直接证据完成
CLOSE-01 审计。不要把“写了计划”“测试没有发现问题”或“完成了一部分”当作目标完成。

本次长期工作的默认授权：
- 可以读取和修改仓库内代码、测试、文档和构建配置。
- 可以使用 fixture、mock 和隔离临时目录运行测试、lint、build 与 smoke。
- 可以按功能创建小提交，并在远端未分叉时 push 当前跟踪分支。
- 不允许 force push、重写他人提交、覆盖已有用户改动或盲目暂存目录。
- 不允许读取/输出真实凭据，不允许使用真实业务下载目录或数据库做测试。
- 不允许真实上游写操作、真实下载、破坏性迁移、tag、release 或 package publish。
- 只读真实上游探针默认关闭；缺少新 fixture 时先推进不依赖它的工作包并记录人工门。

每次开始或自动续跑都执行以下协议：

1. 先确认仓库根目录，读取最新用户消息，然后读取：
   - docs/development/unattended-development.md
   - docs/development/work-program.md
   - docs/roadmap.md
   - docs/architecture/system-overview.md
   - docs/architecture/decisions.md
   - docs/agent/safety.md
   - .agents/skills/pandora/SKILL.md
2. 执行 git status --short --branch；有跟踪远端时 fetch 并确认没有分叉。再查看相关代码、
   测试和最近提交。当前文件和外部状态始终比旧对话记忆可靠；已有改动一律视为用户工作，
   不得回滚。
3. 若工作计划存在 In Progress 项，继续该项。否则选择依赖已 Done 的最高优先级 Ready
   项；同级按文档顺序。除安全、凭据泄露或数据损坏外，不跳过 P0/P1 去做 UI。
4. 把本轮限制为一个可独立验证的 slice：先写清用户结果、失败复现、目标检查和包级检查，
   然后把工作计划检查点更新为 In Progress。不要只回复计划，立即开始执行。
5. 行为变更先增加最窄回归测试并确认它以预期原因失败，再实现最小修复。文档或 CI 工作
   先建立可重复的失败检查。不要通过放宽断言、skip、吞异常或手写假输出获得通过。
6. 使用现有架构：应用层只依赖 provider-neutral `GalleryProvider`，上游实现保持在无状态 adapter；
   daemon 是唯一持久状态层；CLI/Agent/Web 只消费 REST/WS/CLI 机器契约；pandora-tui 冻结。Python 命令一律通过 uv run。
7. 先跑目标测试，再跑工作包级检查；阶段边界运行 uv run python -m pytest -q 和
   git diff --check。Web 变更运行其测试、npm run lint、npm run build，并按约束做浏览器
   smoke。契约变化同步 API reference、Agent Pack、schema 和 contract tests。
8. 回读完整 diff，确认没有凭据、真实内容、下载文件、缓存、数据库、生成目录或无关重构。
   只精确暂存本 slice 文件，提交一个可回滚的 implementation commit。禁止 git add . 和
   git add -A。
9. 工作包全部验收后，取得实际 implementation commit 哈希；再把工作包改为 Done，在完成
   记录中写实际命令、结果和哈希，提升下一个依赖已满足的项目为 Ready，创建一个小型
   checkpoint commit。不要在尚未生成的 commit 内预填自身哈希。
10. push 前再次 fetch 并确认是快进关系，然后一次推送 implementation 与 checkpoint commits。
    远端分叉时不自动 rebase/merge/force，也不继续堆叠新功能提交。记录程序级 Git 阻塞，
    留下干净检查点后暂停，等待操作者决定合并方式。
11. 推送成功后继续循环，不等待“继续”指令。

阻塞处理：
- 单个工作包需要真实凭据、上游探针、发布权限、破坏性数据操作或冲突文件时，记录阻塞
  事实、已尝试动作和解除条件，转向下一 Ready 项。
- 同一个失败动作不要无变化地反复执行。先定位、缩小复现、选择其他证据或转向独立工作。
- 新发现必须有复现证据、用户结果和完成标准；使用 BUG-YYYYMMDD-NN，并映射到现有阶段。
- 只有所有剩余 Required 项都被外部条件阻塞时才暂停整个长期目标。

完成判定：
- 对 work-program 中每个 Required 项逐项查验直接证据，不能用窄测试证明宽目标。
- 在最终 HEAD 重跑 Python、Web、文档/schema/lock、构建安装和回滚检查。
- 核对 REST/WS/CLI、Agent Pack、schema、API reference、路线图与实现一致。
- 逐项归类 TODO/FIXME、失败测试、未提交文件、Blocked/Gated 项和已知缺陷。
- 生成完成报告，保持工作区干净；允许 push 时确认本地 HEAD 与远端一致。
- 只有 CLOSE-01 和全部 Required 工作包确有证据完成，才将长期 goal 标记 complete。
  `REL-02` 的实际 tag/release 未获授权时保持 Gated，长期 goal 保持未完成；Optional
  `WRAP-01` 可以继续 Gated。真实账号探针未执行时明确记录，不得声称已经执行。

现在先执行预检并领取 UP-01；如果仓库状态已经变化，以最新 work-program 和依赖为准。
```
