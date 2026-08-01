# 测试与可用性验收

状态：现役

测试结果必须说明它证明了什么，也必须说明它没有证明什么。大量 fixture 测试通过不能替代
真实用户路径；一次 live 成功也不能替代可重复的单元、契约和安全回归测试。

## 证据分层

| 层级 | 回答的问题 | 默认命令 | 执行位置 |
|---|---|---|---|
| 单元与契约 | 解析、状态机、安全边界和公共数据形状是否符合定义 | `uv run --frozen python scripts/check.py` | 本地与 CI |
| 浏览器 fixture | React 交互、布局、错误状态和浏览器图片解码是否符合定义 | `npm --prefix pandora-web run test:browser` | 本地与 CI |
| 只读 live 验收 | 当前候选、凭据、网络、上游页面和 CDN 组合是否真的可用 | `npm --prefix pandora-web run test:live` | 本地发布环境 |
| 分发与回滚 | 构建物是否可安装、升级和回退 | `scripts/release.py`、`scripts/distribution_smoke.py` | 候选发布环境 |

四层证据不能互相替代：

- HTTP 200、存在 `img.src` 或空图片 body 都不等于图片可见。
- readiness 成功只证明所列上游探针，不证明 Web、图片代理或阅读器。
- fixture 浏览器测试不证明当天的上游 HTML、CDN hostname、Referer 或网络代理行为。
- live 测试缺少凭据、未执行或因环境跳过时，结论是“无证据”，不是通过。
- live 通过不能放宽私网阻断、内容签名、大小限制或 cookie 隔离等确定性安全测试。

## 图片可用标准

图片链路的验收单位是用户能看到的像素，而不是某一层函数返回。当前 live 浏览路径必须满足：

1. daemon readiness 为 `ready: true`、`session: valid`，四项检查均为 `ok`。
2. 首页返回不少于配置采样数的图库和缩略图。
3. 浏览器只请求 daemon；不能直接访问上游图片域名。
4. 多张缩略图、详情封面和阅读器首图的 `complete` 为 true，且
   `naturalWidth`、`naturalHeight` 均大于 0。
5. `/api/image/proxy` 与阅读器 page 端点没有 4xx/5xx，浏览器没有 console/page error。
6. live 流程保持只读，不提交下载、收藏、评分、评论或其他上游写操作。

浏览器 fixture 也使用真实可解码的 PNG 字节并检查非零尺寸。这样 fixture 能验证断言方法本身，
live 验收再验证真实集成链路。Live suite 还会为配置数量的缩略图生成新的等价缓存键并发
重新解码，保证每次都有一组图片请求实际穿过上游网络，而不是由热缓存掩盖首屏并发问题。

## 执行流程

代码变更阶段：

1. 用可观察失败写最窄回归测试，并确认修复前会失败。
2. 修复后运行目标测试，再运行对应 Python/Web 分组。
3. 运行完整 `scripts/check.py`；该结果记录为“确定性检查”，不能写成“线上可用”。
4. 影响上游解析、认证、网络、图片或关键 Web 路径时，再运行 live 验收。

候选发布阶段：

1. 从候选构建物完成安装、版本、启动、升级和回滚 smoke。
2. 使用只读真实会话启动候选 daemon，并确认浏览器只连接该候选。
3. 使用受控的冷图片缓存运行 live 验收；随后可用热缓存复跑稳定性，但不能只跑热缓存。
4. 同时保留确定性 CI、live 验收、artifact 校验和与回滚证据，才可解除发布门。

线上问题回归阶段：

1. 先按用户可观察结果复现，例如图片解码失败或按钮流程中断。
2. 分层记录浏览器、daemon、上游响应和网络环境，避免只修最后一条异常文本。
3. 把观察到的机制写入确定性回归，例如 CDN hostname、必要请求头、代理 fake-IP 和并发上限。
4. 用同一 live 用户路径复验，不能用新增 mock 代替原故障路径。

## Live 命令

先启动使用目标代码/构建物的 daemon。Web server 默认在 `127.0.0.1:5173` 自动启动或复用：

```bash
npm --prefix pandora-web run test:live
```

非默认 daemon 地址和采样数：

```bash
PANDORA_LIVE_DAEMON_URL=http://127.0.0.1:7860 \
PANDORA_LIVE_IMAGE_SAMPLES=5 \
npm --prefix pandora-web run test:live
```

Live trace 和失败截图可能包含真实页面内容，只能保留在本地忽略目录中，不能提交或上传到公开
CI artifact。测试和报告不得输出 cookie、完整图片 URL、图库 token 或本地配置内容。
