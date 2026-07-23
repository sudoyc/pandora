# pandora-tui Bug 修复设计文档

日期: 2026-04-06
范围: 同目录 `tui-audit-2026-04-05.md` 中 19 个 bug 的历史修复方案
状态: 已归档。`pandora-tui/` 已冻结且不再维护；本文不再作为待执行开发计划。
依据: 历史审计记录；当前优先保障 daemon/CLI/Agent Pack 契约。

> 不要继续实现本文的 TUI 修复项。若旧 TUI 暴露出 daemon API 契约问题，请把契约固化到 `tests/pandora_daemon/`，而不是维护 TUI。

---

## 概述

按审计报告的优先级分 4 个批次修复。每批次独立可提交，后续批次不依赖前序批次的代码变更（除 H1/H2 共享 CancellationToken 模式外）。

---

## 批次一：CRITICAL — 直接导致 panic 或终端损坏

### C1. 安装 panic hook 防止终端损坏

**文件:** `main.rs`
**位置:** 在 `enable_raw_mode()` (line 88) 之前插入

```rust
let original_hook = std::panic::take_hook();
std::panic::set_hook(Box::new(move |panic_info| {
    let _ = disable_raw_mode();
    let _ = execute!(io::stdout(), LeaveAlternateScreen);
    original_hook(panic_info);
}));
```

标准 ratatui 社区做法。保留原始 hook 确保 panic 信息仍然打印。

### C2. downloads overlay u16 下溢防护

**文件:** `ui/downloads.rs`
**修改:**

1. 函数开头加 early return guard:
```rust
if area.width < 20 || area.height < 8 {
    return;
}
```

2. 所有减法改为 `saturating_sub`:
```rust
let overlay_height = (app.downloads.tasks.len() as u16 * 2 + 4)
    .min(area.height.saturating_sub(4))
    .max(6);
let x = area.width.saturating_sub(overlay_width) / 2;
let y = area.height.saturating_sub(overlay_height) / 2;
```

### C3. UTF-8 安全字符串截取

**文件:** `ui/gallery_card.rs` (line 81-82)
**修改:**

```rust
let date = if self.item.posted.len() >= 10 {
    let end = self.item.posted
        .char_indices()
        .nth(10)
        .map(|(i, _)| i)
        .unwrap_or(self.item.posted.len());
    &self.item.posted[..end]
} else {
    &self.item.posted
};
```

`posted` 正常情况是 `"2024-01-15 12:00"` 纯 ASCII，`char_indices` 开销可忽略。

---

## 批次二：HIGH — 资源泄漏与稳定性

### H1 + H2. CancellationToken 统一管理页面加载和预加载

**新增依赖:** `tokio-util = "0.7"` (仅用 `CancellationToken`)

**核心设计:** 在 `App` 中新增两个 token:

```rust
// app.rs
pub page_load_cancel: CancellationToken,    // 当前页面加载
pub preload_cancel: CancellationToken,       // 当前预加载批次
```

**H1 修复 — 页面加载取消:**

`main.rs` 中 `load_page_image` 调用前:
```rust
app.page_load_cancel.cancel();
app.page_load_cancel = CancellationToken::new();
let cancel = app.page_load_cancel.clone();
```

spawn 内部用 `tokio::select!` 监听 cancel:
```rust
tokio::spawn(async move {
    tokio::select! {
        _ = cancel.cancelled() => { /* 被取消，静默退出 */ }
        result = async { /* 原有加载逻辑 */ } => {
            // 发送事件
        }
    }
});
```

**H2 修复 — 预加载取消:**

`trigger_preload` 开头:
```rust
app.preload_cancel.cancel();
app.preload_cancel = CancellationToken::new();
```

每个预加载 spawn 传入 `app.preload_cancel.child_token()`。

退出 reader 时:
```rust
app.preload_cancel.cancel();
app.page_load_cancel.cancel();
```

### H3. WebSocket 指数退避重连

**文件:** `main.rs` (lines 59-85)
**修改:**

```rust
let mut backoff = Duration::from_secs(3);
const MAX_BACKOFF: Duration = Duration::from_secs(60);

loop {
    match connect_async(&ws_url).await {
        Ok((ws_stream, _)) => {
            backoff = Duration::from_secs(3); // 连接成功，重置退避
            let _ = tx_ws.send(AppEvent::WsReconnected);
            // ... 读消息循环 ...
        }
        Err(_) => {
            let _ = tx_ws.send(AppEvent::WsDisconnected);
        }
    }
    tokio::time::sleep(backoff).await;
    backoff = (backoff * 2).min(MAX_BACKOFF);
}
```

同时保存 `JoinHandle`，main loop break 后 `.abort()`。

### H4. 预加载失败清理 pending_pages

**文件:** `main.rs` (lines 654-665)
**修改:**

预加载 spawn 中，错误分支发送事件:
```rust
Err(e) => {
    let _ = tx.send(AppEvent::PreloadFailed { page: p });
}
```

新增 `AppEvent::PreloadFailed { page: usize }`，handler 中:
```rust
AppEvent::PreloadFailed { page } => {
    app.pending_pages.remove(&page);
}
```

---

## 批次三：MEDIUM — 显示正确性与错误处理

### M1. status_bar 使用 Unicode 宽度

**文件:** `ui/status_bar.rs` (line 44)
**修改:**

```rust
use unicode_width::UnicodeWidthStr;
let padding = width.saturating_sub(left.width() + right.width());
```

`unicode-width` 已是项目依赖。

### M2. URL 路径段编码

**文件:** `client.rs` (6 处 format! 调用)
**修改:**

```rust
use urlencoding::encode;
format!("{}/api/gallery/{}/{}", self.base_url, encode(gid), encode(token))
```

`urlencoding` 已是项目依赖。对所有 `format!` 中直接插入 gid/token 的位置统一修改。

### M3 + M4. HTTP 响应状态码检查

**文件:** `client.rs` (所有请求方法)
**修改:**

在每个 `.json()` 或 `.bytes()` 调用前加:
```rust
let resp = resp.error_for_status().map_err(|e| e.to_string())?;
```

涉及方法: `get_homepage`, `search`, `get_popular`, `get_toplist`, `get_watched`, `get_gallery_detail`, `get_page_image`, `get_favorites`, `add_favorite`, `proxy_image`, `get_library`, `get_downloads`, `submit_download`, `cancel_download`, `suggest_tags`, `get_config`, `update_config` 等。

`proxy_image` (line 267-278) 同理，在 `.bytes()` 前检查。

### M5. 下载任务自动清理

**文件:** `state/downloads.rs`
**修改:**

在 `handle_ws_event` 中，`download_complete` 后记录完成时间。新增清理逻辑:

```rust
pub fn cleanup_completed(&mut self) {
    self.tasks.retain(|t| {
        !matches!(t.status, DownloadStatus::Completed | DownloadStatus::Failed)
            || t.completed_at.map_or(true, |t| t.elapsed().unwrap_or_default() < Duration::from_secs(300))
    });
    // 硬上限: 保留最近 50 个已完成任务
    // ... 或者更简单: 只保留最近 50 个
}
```

在每次 WS 事件处理后调用 `cleanup_completed()`。

---

## 批次四：LOW — 边缘情况与打磨

### L1. gallery_card 坐标用 Unicode 宽度

**文件:** `ui/gallery_card.rs` (lines 73, 89)
**修改:** `.len()` → `.width()` (同 M1 模式)

### L2. items 替换后 clamp selected

**文件:** `state/gallery_list.rs`
**修改:** 在 `FavoritesLoaded` 和 `DownloadsRefreshed` handler 中，替换 items 后:
```rust
self.selected = self.selected.min(self.items.len().saturating_sub(1));
```

### L3. scroll_offset clamp

**文件:** `state/gallery_list.rs` (lines 47-56)
**修改:** `adjust_scroll` 末尾加:
```rust
self.scroll_offset = self.scroll_offset.min(self.items.len().saturating_sub(1));
```

### L4. cursor_pos 改为 pub(crate)

**文件:** `state/search.rs` (line 22)
**修改:** `pub cursor_pos` → `pub(crate) cursor_pos`

### L5. HOME 未设置时使用 dirs crate

**文件:** `config.rs` (lines 50-53)

**设计决策:** 不引入 `dirs` crate（避免新依赖），改为打印警告:
```rust
fn dirs_home() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            eprintln!("WARNING: HOME not set, using current directory for config");
            PathBuf::from(".")
        })
}
```

### L6. 收藏失败发送正确事件

**文件:** `main.rs` (lines 257-264)
**修改:**

新增 `AppEvent::StatusMessage(String)`，替代错误使用的 `ImageError`:
```rust
Err(e) => {
    let _ = tx.send(AppEvent::StatusMessage(format!("收藏失败: {}", e)));
}
```

Handler 中设置 `app.status_msg`，不污染 `failed_images`。

### L7. 搜索建议 generation 计数器

**文件:** `main.rs`, `state/search.rs`, `event.rs`
**修改:**

`SearchState` 新增 `pub suggest_generation: u64`。请求时递增并传入 spawn，`SuggestionsLoaded` 事件携带 generation，handler 中比对丢弃过期结果。

### L8. image_states 清理阈值对齐

**文件:** `main.rs` (lines 727-730)
**修改:** 阈值从 300 降到 `image_cache.cap() + 20`（即 220）。

---

## 新增依赖

| Crate | 版本 | 用途 | 批次 |
|-------|------|------|------|
| `tokio-util` | `0.7` | `CancellationToken` (H1, H2) | 批次二 |

其余修复使用已有依赖: `unicode-width`, `urlencoding`, `crossterm`, `tokio`。

---

## 设计决策

1. **CancellationToken vs AbortHandle**: 选择 CancellationToken。AbortHandle 会在 await 点强制终止任务，可能导致资源未释放。CancellationToken 是协作式取消，任务在 `select!` 中优雅退出。

2. **L5 不引入 dirs crate**: 仅为一个 fallback 场景引入新依赖不值得。打印警告足够。

3. **M5 清理策略**: 选择时间 + 硬上限双重策略。5 分钟后自动移除已完成任务，同时保留最近 50 个防止突发大量下载时信息丢失。

4. **H3 退避上限 60s**: 平衡用户体验（不想等太久）和服务器压力。daemon 通常是本地的，60s 足够。

5. **批次独立性**: 批次一（CRITICAL）完全独立。批次二的 H1/H2 共享 CancellationToken 模式应一起实施。批次三/四各项独立。

---

## 测试策略

TUI 测试受限于终端渲染和异步运行时，现有 16 个测试主要覆盖 state 逻辑。

**可单元测试的修复:**
- C2: 构造小 `Rect`，验证不 panic
- L2/L3: 构造 `GalleryListState`，替换 items 后验证 selected/scroll_offset 被 clamp
- M5: 构造 `DownloadState`，添加已完成任务，调用 cleanup 验证移除
- L7: 模拟 generation 计数器逻辑

**需手动验证的修复:**
- C1: 故意 panic 后检查终端是否恢复
- C3: 构造含非 ASCII posted 的数据，验证不 panic
- H1/H2: 快速翻页 + 退出 reader，观察任务是否被取消
- H3: 停止 daemon，观察 TUI 重连行为
- M1/L1: 使用中文内容验证对齐
- M2/M3/M4: daemon 返回错误时验证错误信息可读

---

## 文件修改清单

| 文件 | 修改项 |
|------|--------|
| `main.rs` | C1, H1, H2, H3, H4, L6, L7, L8 |
| `app.rs` | H1, H2 (新增 CancellationToken 字段) |
| `event.rs` | H4, L6, L7 (新增事件变体) |
| `ui/downloads.rs` | C2 |
| `ui/gallery_card.rs` | C3, L1 |
| `ui/status_bar.rs` | M1 |
| `client.rs` | M2, M3, M4 |
| `state/downloads.rs` | M5 |
| `state/gallery_list.rs` | L2, L3 |
| `state/search.rs` | L4, L7 |
| `config.rs` | L5 |
| `Cargo.toml` | H1/H2 (tokio-util) |
