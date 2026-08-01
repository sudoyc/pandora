# 长期无人值守开发约束

状态：Active
适用范围：Pandora 仓库的跨轮次、可自动续跑开发
最近核对：2026-07-23

本文规定长期开发如何选择工作、修改代码、验证、提交、恢复和结束。它不替代
[开发路线图](../roadmap.md)；路线图回答“为什么做、先做什么”，
[执行工作计划](work-program.md)回答“当前做到哪里”，本文回答“每一轮必须怎样做”。

## 1. 目标与完成边界

长期目标是完成当前路线图内所有**非可选**工作包，使 Pandora 从已有功能集合变成一个：

- 能区分 daemon、配置、会话和上游端点状态的本地服务；
- 能诊断并修复下载状态与磁盘库不一致的可恢复系统；
- 有持续集成、版本规则和可重复构建流程的可维护项目；
- 具有版本化 CLI/REST/WS 机器契约的可靠 Agent 后端；
- 具有完整日常工作流、恢复能力和自动化测试的可选 Web 客户端；
- 能在干净环境安装、升级和回滚的本地应用。

“补全所有内容”指完成 [执行工作计划](work-program.md) 中全部 Required 工作包，不指无边界地
增加所有可以想象的功能。新发现只有在具备复现证据、用户结果和完成标准后，才能加入工作
计划。薄 wrapper 保持条件性工作，不影响核心项目的完成判定。

## 2. 事实来源与冲突处理

按以下顺序解释项目现状：

1. 代码、测试和实际命令输出：当前行为的事实来源。
2. [系统架构](../architecture/system-overview.md)和
   [架构决策](../architecture/decisions.md)：模块边界与长期不变量。
3. [开发路线图](../roadmap.md)：阶段优先级和阶段验收标准。
4. [执行工作计划](work-program.md)：工作包状态、依赖、检查点和完成证据。
5. [goal prompt](goal-prompt.md)：启动协议，不单独定义产品事实。
6. `docs/archive/`、历史提交和本机未跟踪说明：只提供上下文，不覆盖现役文档。

发现冲突时先用测试或运行证据确认，再修正较低层级文档。跨模块方向变化必须先新增或替代
ADR，不能通过普通实现提交静默改变架构。

## 3. 不可破坏的约束

### 架构与状态

- 应用层只依赖 provider-neutral `GalleryProvider`；上游 HTTP、parser、model 和异常只属于无状态 adapter。
- `pandora-daemon` 负责确定性 provider 选择，并且是凭据、session、SQLite、缓存、下载队列和本地库的唯一状态所有者。
- CLI、Agent 和 Web 只使用 daemon REST、WebSocket 或 CLI JSON/NDJSON，不导入 adapter 或创建第二套状态层。
- `pandora-tui/` 已冻结，不做功能、重构、依赖升级或视觉维护。
- 默认保持 loopback 部署；远程绑定、认证和多用户模式不属于自治扩展范围。

### 数据与凭据

- 不读取、打印、提交或摘要本机凭据、cookie、代理密钥、真实配置内容。
- 默认测试必须使用 fixture、mock、`tmp_path` 和隔离的临时 HOME/config/cache/download 目录。
- 不把仓库根的 `downloads/`、用户下载目录、缓存或 SQLite 文件当作测试数据。
- 无人值守模式不执行评论、评分、收藏、标签修改、reset limit 等上游写操作。
- 日志、测试失败、schema 示例和提交内容不得包含公开 gallery route token 之外的认证材料或
  真实内容响应。

### 改动范围

- 一次 slice 只交付一个可独立验证的行为；不顺带清理无关代码。
- 行为修复先建立失败复现或回归测试，再做最小实现。
- 只删除本次改动造成的孤立代码；既有无关技术债进入候选工作包，不在当前 diff 中处理。
- 公共契约变化同步 API reference、Agent Pack、JSON Schema 和 contract tests。
- Python 一律通过 `uv run ...`；不得使用全局 `pip` 或隐式修改系统环境。

## 4. 自动权限与人工门

| 操作 | 默认 | 条件 |
|---|---|---|
| 读取和修改仓库内代码、测试、文档 | 允许 | 遵守工作包边界和用户已有改动 |
| 运行 fixture 测试、lint、build、临时目录 smoke | 允许 | 不读取真实凭据和业务数据 |
| 创建小而完整的本地提交 | 允许 | 精确暂存，通过适用门槛 |
| 推送当前跟踪分支 | 由 goal prompt 授权 | 远端未分叉，禁止 force push |
| 安装锁文件声明的仓库本地依赖 | 允许 | 使用 `uv` 或项目现有 npm lockfile |
| 只读真实上游探针 | 禁止 | 需要操作者明确开启，并使用脱敏输出 |
| 上游写操作或真实下载 | 禁止 | 需要针对该操作的明确指令 |
| 修改真实配置、下载库、缓存或数据库 | 禁止 | 只能操作隔离 fixture 状态 |
| 破坏性迁移、自动删文件、重写 Git 历史 | 禁止 | 必须人工审查和明确授权 |
| 创建/推送 tag、发布 release/package | 禁止 | 可完成 dry-run；实际发布必须人工放行 |

人工门只阻塞依赖它的工作包。记录原因后，应继续执行其他依赖已满足且文件不冲突的工作包。

## 5. 工作包状态机

工作状态只在 [执行工作计划](work-program.md) 中维护：

```text
Queued -> Ready -> In Progress -> Done
                    |             ^
                    +-> Blocked --+
Queued/Ready -> Gated -> Ready
Queued/Ready/In Progress -> Dropped (必须记录决策依据)
```

规则：

- 同一时间最多一个 `In Progress` 工作包。
- 只有依赖全部 `Done` 的工作包可以进入 `Ready`。
- `Done` 必须带命令、测试、构建、运行结果或归档报告等直接证据；提交哈希本身不是充分证据。
- `Blocked` 必须写清阻塞事实、已尝试动作和解除条件，不得只写“需要更多时间”。
- `Gated` 表示等待人工权限或产品条件，不是假完成。
- 新缺陷使用 `BUG-YYYYMMDD-NN`，先映射到现有阶段；安全、凭据泄露和数据损坏问题可以抢占。

## 6. 工作选择算法

每次续跑按固定顺序选择：

1. 读取最新用户指令、Git 状态和工作计划检查点。
2. 若存在 `In Progress`，继续完成它，不另开工作包。
3. 若该工作包被外部条件阻塞，记录 `Blocked`，不要反复执行同一失败动作。
4. 从依赖已完成的工作中选择优先级最高的 `Ready` 项；同级按工作计划顺序。
5. 当前工作区有用户改动时，选择不触碰相同文件的工作；没有隔离工作时才停下说明冲突。
6. 没有 `Ready` 项时，重新检查依赖和 `Blocked/Gated` 解除条件；只有所有剩余项都不可推进时才停。

不得因为某个任务困难而跳到更显眼的 Web 或包装功能。P0、P1 的可靠性和恢复工作优先于新 UI。

## 7. 单个 slice 的执行循环

### 7.1 预检

1. 执行 `git status --short --branch`，记录已有修改，不覆盖非本轮工作。
2. 有跟踪远端时执行 fetch 并确认没有分叉；无法确认远端或已经分叉时按 Git 门处理。
3. 阅读工作包涉及的代码、测试、契约和最近提交，不根据文件名猜实现。
4. 把用户结果改写成一个可失败的验收条件，并列出目标测试和包级检查。
5. 将工作包设为 `In Progress`，更新当前检查点；最迟随第一个实现提交持久化该状态。

### 7.2 实现

1. 对行为缺陷先写最窄回归测试并确认它以预期原因失败。
2. 实现满足该测试的最小改动，保持既有架构和风格。
3. 运行目标测试；失败时定位根因，不通过放宽断言、跳过测试或吞异常制造绿灯。
4. 检查完整 diff，移除仅由本次改动产生的临时代码、调试输出和生成物。
5. 更新受影响的契约和文档，不复制另一个事实源。

### 7.3 验收与检查点

1. 先运行目标检查，再运行工作包级检查；达到阶段边界时运行全量检查。
2. 记录实际命令和结果。未运行、环境不具备和失败必须分开写，不能统称“通过”。
3. 精确暂存实现文件，创建功能内聚的 implementation commit，并取得实际 commit 哈希。
4. 将工作包改为 `Done`，在完成记录中填写该哈希和实际验证结果，提升下一个依赖已满足的
   工作包为 `Ready`，再创建一个小型 checkpoint commit。
5. 再次确认 staged/unstaged 状态和远端关系，一次推送 implementation 与 checkpoint commits。

一个工作包可以包含多个 slice/commit，但每个 commit 都必须处于可测试状态。最后用 checkpoint
commit 记录实现提交和证据，避免在同一个 commit 中记录自身未知哈希；下一轮必须能仅凭仓库恢复
上下文。

## 8. 验证层级

| 变更 | 最低目标检查 | 包级或阶段检查 |
|---|---|---|
| 文档/Prompt | 内部链接、JSON 语法、`git diff --check` | 文档检查器落地后使用统一入口 |
| Provider adapter | 对应 parser/client fixture tests | `uv run python -m pytest pandora_daemon/providers/exhentai/upstream/tests -q` |
| daemon/CLI | 对应 route/service/CLI tests | `uv run python -m pytest tests/pandora_daemon -q` |
| 下载状态 | download、concurrency、route integration tests | 重启/迁移/损坏 fixture 场景 + Python 全量测试 |
| Agent 契约 | contract test + 相关 schema 校验 | fixture daemon 端到端工作流 |
| Web | 相关 unit/component test | `npm run lint`、`npm run build` 和关键浏览器 smoke |
| 分发 | build/install 的隔离环境 smoke | 安装、启动、探测、升级、回滚全流程 |

Python 阶段边界统一运行：

```bash
uv run python -m pytest -q
git diff --check
```

Web 变更在 `pandora-web/` 运行现有 `lint`、`build`，测试框架落地后必须追加测试命令。真实上游
成功不能替代 fixture 回归测试，历史的“521 passed”也不能替代本轮新输出。

## 9. Git 与远端规则

- 不使用 `git add .`、`git add -A` 或整目录盲目暂存；逐文件暂存并复核 staged diff。
- 不使用 `reset --hard`、强制 checkout、强推、重写他人提交或自动删除用户改动。
- 提交按可回滚功能切分，使用 `feat:`、`fix:`、`test:`、`docs:`、`ci:`、`build:` 等现有风格。
- 推送前先 fetch 并确认目标远端没有非快进分叉；发生分叉时记录程序级阻塞，不自动
  rebase/merge 猜意图，也不继续堆叠新的功能提交。
- 测试失败的中间状态可以保留在工作区检查点，但不得推送为已完成工作包。
- 下载内容、缓存、数据库、凭据、`node_modules`、`dist`、Rust `target` 和临时报告不得进入提交。

## 10. 阻塞、恢复与停机

以下情况记录后停止当前工作包：

- 需要人工门权限；
- 所需事实只能从不可用的真实上游或凭据获得；
- 用户改动与目标文件重叠且无法隔离；
- 依赖服务持续不可用；
- 需求会推翻 Accepted ADR，但没有足够证据形成替代决策。

恢复时从 Git 状态、`In Progress` 工作包和当前检查点开始，先重跑最近的目标测试。不要依赖上轮
对话记忆，也不要重新执行已经有证据的探索。若同一阻塞持续存在，转向其他 Ready 工作包。
远端分叉是程序级 Git 门：保存干净检查点后暂停整个程序，等待操作者决定合并方式。

## 11. 最终完成审计

只有同时满足以下条件，长期 goal 才能标记完成：

- 工作计划中所有 Required 工作包为 `Done`，不存在 `In Progress` 或未解释的 `Blocked`。
- 路线图每个阶段的原始完成标准都有直接证据，不能用更窄测试代替。
- Python 全量测试、Web 测试/lint/build、文档链接/schema、锁文件和分发 smoke 均使用最终 HEAD 通过。
- 新 clone 或隔离环境完成安装、启动、health/readiness、核心 fixture 工作流和回滚验证。
- 公共 REST/WS/CLI 契约、Agent Pack、schema、API reference 和实现一致。
- `TODO/FIXME`、失败测试、未提交文件和已知缺陷已逐项归类，不存在被沉默遗漏的目标内工作。
- 工作区干净；允许推送时本地 HEAD 与远端一致；完成报告记录命令、结果、提交和剩余人工门。

实际 release/tag 是 Required 人工门；未获授权时必须保持对应工作包 `Gated`，长期 goal 不能
标记完成。真实账号探针若不是验收必需项可以保持人工门；可选 wrapper 不影响核心完成判定。
