# TUI Bugfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 19 bugs from the TUI audit report (`docs/tui-audit-2026-04-05.md`), grouped into 4 batches by severity.

**Architecture:** Batch-sequential fixes across 12 Rust source files. Batch 1 (CRITICAL) prevents panics/terminal corruption. Batch 2 (HIGH) adds CancellationToken-based task lifecycle and WS backoff. Batch 3 (MEDIUM) improves HTTP error handling and display correctness. Batch 4 (LOW) polishes edge cases.

**Tech Stack:** Rust, ratatui, tokio, tokio-util (new dep for CancellationToken), crossterm, reqwest, unicode-width, urlencoding

---

## File Structure

| File | Changes |
|------|---------|
| `Cargo.toml` | Add `tokio-util` dependency |
| `main.rs` | C1 panic hook, H1/H2 CancellationToken integration, H3 WS backoff, H4 preload error event, L6 favorite error event, L7 suggestion generation, L8 image_states threshold |
| `app.rs` | H1/H2 new CancellationToken fields |
| `event.rs` | H4 `PreloadFailed`, L6 `StatusMessage`, L7 generation on `SuggestionsLoaded` |
| `ui/downloads.rs` | C2 saturating_sub + early return |
| `ui/gallery_card.rs` | C3 UTF-8 safe slice, L1 unicode width |
| `ui/status_bar.rs` | M1 unicode width |
| `client.rs` | M2 URL encoding, M3/M4 error_for_status |
| `state/downloads.rs` | M5 cleanup_completed |
| `state/gallery_list.rs` | L2 clamp selected, L3 clamp scroll_offset |
| `state/search.rs` | L4 pub(crate) cursor_pos, L7 suggest_generation field |
| `config.rs` | L5 HOME fallback warning |

---

### Task 1: C1 — Panic hook for terminal restoration

**Files:**
- Modify: `pandora-tui/src/main.rs:88-93`

- [ ] **Step 1: Write the panic hook before terminal setup**

In `main.rs`, insert before line 88 (`enable_raw_mode()?;`):

```rust
// Install panic hook to restore terminal on crash
let original_hook = std::panic::take_hook();
std::panic::set_hook(Box::new(move |panic_info| {
    let _ = disable_raw_mode();
    let _ = execute!(io::stdout(), LeaveAlternateScreen);
    original_hook(panic_info);
}));
```

- [ ] **Step 2: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles without errors

- [ ] **Step 3: Commit**

```bash
git add pandora-tui/src/main.rs
git commit -m "fix(tui): C1 install panic hook to restore terminal on crash"
```

---

### Task 2: C2 — Downloads overlay u16 underflow protection

**Files:**
- Modify: `pandora-tui/src/ui/downloads.rs:6-16`

- [ ] **Step 1: Add early return guard and fix arithmetic**

Replace lines 6-16 of `draw_download_overlay`:

```rust
pub fn draw_download_overlay(frame: &mut Frame, app: &App) {
    if !app.downloads.show_overlay {
        return;
    }

    let area = frame.area();
    if area.width < 20 || area.height < 8 {
        return;
    }

    let overlay_width = (area.width * 70 / 100).min(60);
    let overlay_height = (app.downloads.tasks.len() as u16 * 2 + 4)
        .min(area.height.saturating_sub(4))
        .max(6);
    let x = area.width.saturating_sub(overlay_width) / 2;
    let y = area.height.saturating_sub(overlay_height) / 2;
    let overlay_area = Rect::new(x, y, overlay_width, overlay_height);
```

- [ ] **Step 2: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles without errors

- [ ] **Step 3: Commit**

```bash
git add pandora-tui/src/ui/downloads.rs
git commit -m "fix(tui): C2 prevent u16 underflow in downloads overlay"
```

---

### Task 3: C3 + L1 — UTF-8 safe string slice and unicode width in gallery_card

**Files:**
- Modify: `pandora-tui/src/ui/gallery_card.rs:73,81-85,89`

- [ ] **Step 1: Fix C3 — UTF-8 safe date slice (lines 81-85)**

Replace:
```rust
        let date = if self.item.posted.len() >= 10 {
            &self.item.posted[..10]
        } else {
            &self.item.posted
        };
```

With:
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

- [ ] **Step 2: Fix L1 — unicode width for cat_label (line 73)**

Replace:
```rust
            if cat_x + cat_label.len() as u16 <= area.x + area.width {
```

With:
```rust
            if cat_x + UnicodeWidthStr::width(cat_label.as_str()) as u16 <= area.x + area.width {
```

- [ ] **Step 3: Fix L1 — unicode width for date (line 89)**

Replace:
```rust
            let pages_x = text_x + date.len() as u16 + 2;
```

With:
```rust
            let pages_x = text_x + UnicodeWidthStr::width(date) as u16 + 2;
```

- [ ] **Step 4: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles without errors

- [ ] **Step 5: Commit**

```bash
git add pandora-tui/src/ui/gallery_card.rs
git commit -m "fix(tui): C3 UTF-8 safe date slice, L1 unicode width in gallery_card"
```

---

### Task 4: Add tokio-util dependency + CancellationToken fields (H1/H2 prep)

**Files:**
- Modify: `pandora-tui/Cargo.toml:11`
- Modify: `pandora-tui/src/app.rs:1-10,53-80,83-100`

- [ ] **Step 1: Add tokio-util to Cargo.toml**

After the `tokio` line (line 11), add:
```toml
tokio-util = { version = "0.7", features = ["rt"] }
```

- [ ] **Step 2: Add CancellationToken fields to App struct**

In `app.rs`, add import at top:
```rust
use tokio_util::sync::CancellationToken;
```

Add two fields to `App` struct (after `preload_semaphore`):
```rust
    pub page_load_cancel: CancellationToken,
    pub preload_cancel: CancellationToken,
```

- [ ] **Step 3: Initialize tokens in App::new()**

In the `App::new()` constructor, add:
```rust
            page_load_cancel: CancellationToken::new(),
            preload_cancel: CancellationToken::new(),
```

- [ ] **Step 4: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles (warnings about unused fields are OK at this stage)

- [ ] **Step 5: Commit**

```bash
git add pandora-tui/Cargo.toml pandora-tui/src/app.rs
git commit -m "feat(tui): H1/H2 add tokio-util CancellationToken fields to App"
```

---

### Task 5: H1 — Page load cancellation with CancellationToken

**Files:**
- Modify: `pandora-tui/src/main.rs:502-580` (load_page_image function)

- [ ] **Step 1: Add tokio_util import to main.rs**

At the top of `main.rs`, add:
```rust
use tokio_util::sync::CancellationToken;
```

- [ ] **Step 2: Cancel old token before loading in start_page_load**

In `start_page_load` (around line 494-498), before `load_page_image(app)`:
```rust
    app.page_load_cancel.cancel();
    app.page_load_cancel = CancellationToken::new();
```

- [ ] **Step 3: Wrap load_page_image spawns with cancellation**

Modify `load_page_image` to accept and use a cancel token. Change signature:
```rust
fn load_page_image(app: &App) {
```

Add after existing variable captures (line 507):
```rust
    let cancel = app.page_load_cancel.clone();
```

Wrap the local spawn (lines 512-542) with `tokio::select!`:
```rust
    if is_local {
        tokio::spawn(async move {
            tokio::select! {
                _ = cancel.cancelled() => {}
                result = async {
                    let path = format!("page/{}", page);
                    match client.get_library_file(&gid, &path).await {
                        Ok(bytes) => {
                            let bytes_vec = bytes.to_vec();
                            match tokio::task::spawn_blocking(move || image::load_from_memory(&bytes_vec)).await {
                                Ok(Ok(img)) => {
                                    let _ = tx.send(AppEvent::PageImageLoaded { page, image: img });
                                }
                                Ok(Err(e)) => {
                                    let _ = tx.send(AppEvent::ImageError {
                                        url: format!("page:{}", page),
                                        error: e.to_string(),
                                    });
                                }
                                Err(_) => {
                                    let _ = tx.send(AppEvent::ImageError {
                                        url: format!("page:{}", page),
                                        error: "image decode task panicked".to_string(),
                                    });
                                }
                            }
                        }
                        Err(e) => {
                            let _ = tx.send(AppEvent::ImageError {
                                url: format!("page:{}", page),
                                error: e,
                            });
                        }
                    }
                } => {}
            }
        });
```

Apply the same `tokio::select!` pattern to the online spawn (lines 545-580).

- [ ] **Step 4: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles without errors

- [ ] **Step 5: Commit**

```bash
git add pandora-tui/src/main.rs
git commit -m "fix(tui): H1 cancel stale page loads with CancellationToken"
```

---

### Task 6: H2 — Cancel preload tasks on navigation/exit

**Files:**
- Modify: `pandora-tui/src/main.rs:603-668` (preload_adjacent_pages)
- Modify: `pandora-tui/src/main.rs:308-314` (exit reader key handler)

- [ ] **Step 1: Cancel old preloads at start of preload_adjacent_pages**

At the top of `preload_adjacent_pages` (after the function signature), add:
```rust
    app.preload_cancel.cancel();
    app.preload_cancel = CancellationToken::new();
```

- [ ] **Step 2: Wrap each preload spawn with child token**

For each spawn in the preload loop, clone a child token and wrap with `tokio::select!`:

Local preload spawn (lines 636-653):
```rust
        let cancel = app.preload_cancel.child_token();
        tokio::spawn(async move {
            tokio::select! {
                _ = cancel.cancelled() => {}
                _ = async {
                    let _permit = sem.acquire().await;
                    // ... existing local preload logic ...
                } => {}
            }
        });
```

Online preload spawn (lines 654-665) — same pattern, plus send `PreloadFailed` on error:
```rust
        let cancel = app.preload_cancel.child_token();
        tokio::spawn(async move {
            tokio::select! {
                _ = cancel.cancelled() => {}
                _ = async {
                    let _permit = sem.acquire().await;
                    match client.get_page_image(&gid, &token, p).await {
                        Ok(resp) => {
                            match resp.bytes().await {
                                Ok(bytes) => {
                                    let bytes_vec = bytes.to_vec();
                                    match tokio::task::spawn_blocking(move || image::load_from_memory(&bytes_vec)).await {
                                        Ok(Ok(img)) => {
                                            let _ = tx.send(AppEvent::PageImageLoaded { page: p, image: img });
                                        }
                                        _ => {
                                            let _ = tx.send(AppEvent::PreloadFailed { page: p });
                                        }
                                    }
                                }
                                Err(_) => {
                                    let _ = tx.send(AppEvent::PreloadFailed { page: p });
                                }
                            }
                        }
                        Err(_) => {
                            let _ = tx.send(AppEvent::PreloadFailed { page: p });
                        }
                    }
                } => {}
            }
        });
```

- [ ] **Step 3: Cancel tokens on reader exit (lines 308-314)**

In `handle_key_read`, the `Esc | Char('h')` branch, add after `app.pending_pages.clear()`:
```rust
            app.preload_cancel.cancel();
            app.page_load_cancel.cancel();
```

- [ ] **Step 4: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles without errors

- [ ] **Step 5: Commit**

```bash
git add pandora-tui/src/main.rs
git commit -m "fix(tui): H2 cancel preload tasks on navigation/exit, H4 send PreloadFailed on error"
```

---

### Task 7: H3 — WebSocket exponential backoff reconnection

**Files:**
- Modify: `pandora-tui/src/main.rs:56-86` (WS spawn block)
- Modify: `pandora-tui/src/main.rs:167-171` (cleanup section)

- [ ] **Step 1: Add backoff logic and save JoinHandle**

Replace the WS spawn block (lines 56-86) with:

```rust
    // WebSocket background connection
    let ws_handle = {
        let ws_url = app.client.ws_url();
        let tx_ws = tx.clone();
        tokio::spawn(async move {
            use futures_util::StreamExt;
            use tokio_tungstenite::connect_async;

            let mut backoff = Duration::from_secs(3);
            const MAX_BACKOFF: Duration = Duration::from_secs(60);

            loop {
                match connect_async(&ws_url).await {
                    Ok((ws_stream, _)) => {
                        backoff = Duration::from_secs(3);
                        let _ = tx_ws.send(AppEvent::WsReconnected);
                        let (_, mut read) = ws_stream.split();
                        while let Some(msg) = read.next().await {
                            match msg {
                                Ok(tokio_tungstenite::tungstenite::Message::Text(text)) => {
                                    if let Ok(ev) = serde_json::from_str::<crate::models::WsEvent>(&text) {
                                        let _ = tx_ws.send(AppEvent::WsEvent(ev));
                                    }
                                }
                                Err(_) => break,
                                _ => {}
                            }
                        }
                        let _ = tx_ws.send(AppEvent::WsDisconnected);
                    }
                    Err(_) => {
                        let _ = tx_ws.send(AppEvent::WsDisconnected);
                    }
                }
                tokio::time::sleep(backoff).await;
                backoff = (backoff * 2).min(MAX_BACKOFF);
            }
        })
    };
```

- [ ] **Step 2: Abort WS task on exit**

After the main loop `break` (line 167 area), before `disable_raw_mode()`, add:
```rust
    ws_handle.abort();
```

- [ ] **Step 3: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles without errors

- [ ] **Step 4: Commit**

```bash
git add pandora-tui/src/main.rs
git commit -m "fix(tui): H3 WebSocket exponential backoff reconnection"
```

---

### Task 8: Event enum updates (H4 + L6 + L7)

**Files:**
- Modify: `pandora-tui/src/event.rs`
- Modify: `pandora-tui/src/main.rs` (handle_app_event)

- [ ] **Step 1: Add new event variants**

In `event.rs`, add these variants to `AppEvent`:

```rust
    PreloadFailed { page: u32 },
    StatusMessage(String),
```

Change `SuggestionsLoaded` to carry a generation:
```rust
    SuggestionsLoaded(Result<Vec<TagSuggestion>, String>, u64),
```

- [ ] **Step 2: Add handlers in handle_app_event**

In `main.rs` `handle_app_event`, add handlers:

```rust
        AppEvent::PreloadFailed { page } => {
            app.pending_pages.remove(&page);
        }
        AppEvent::StatusMessage(msg) => {
            app.status_msg = msg;
        }
```

Update `SuggestionsLoaded` handler (lines 715-721):
```rust
        AppEvent::SuggestionsLoaded(Ok(suggestions), gen) => {
            if gen == app.search.suggest_generation {
                app.search.suggestions = suggestions;
                app.search.selected_suggestion = None;
            }
        }
        AppEvent::SuggestionsLoaded(Err(_), _) => {
            app.search.suggestions.clear();
        }
```

- [ ] **Step 3: Fix L6 — favorite error uses StatusMessage**

In `main.rs` lines 257-264, replace:
```rust
                    if let Err(e) = client.add_favorite(&gid, &token, 0).await {
                        let _ = tx.send(AppEvent::ImageError {
                            url: String::new(),
                            error: e,
                        });
                    }
```

With:
```rust
                    if let Err(e) = client.add_favorite(&gid, &token, 0).await {
                        let _ = tx.send(AppEvent::StatusMessage(format!("收藏失败: {}", e)));
                    }
```

- [ ] **Step 4: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles without errors

- [ ] **Step 5: Commit**

```bash
git add pandora-tui/src/event.rs pandora-tui/src/main.rs
git commit -m "fix(tui): H4 PreloadFailed event, L6 StatusMessage event, L7 suggestion generation"
```

---

### Task 9: M1 — Status bar unicode width

**Files:**
- Modify: `pandora-tui/src/ui/status_bar.rs:1,44`

- [ ] **Step 1: Add import and fix width calculation**

Add import at top:
```rust
use unicode_width::UnicodeWidthStr;
```

Replace line 44:
```rust
    let padding = width.saturating_sub(left.len() + right.len());
```

With:
```rust
    let padding = width.saturating_sub(UnicodeWidthStr::width(left.as_str()) + UnicodeWidthStr::width(right.as_str()));
```

- [ ] **Step 2: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles without errors

- [ ] **Step 3: Commit**

```bash
git add pandora-tui/src/ui/status_bar.rs
git commit -m "fix(tui): M1 use unicode width in status bar"
```

---

### Task 10: M2 + M3 + M4 — URL encoding and HTTP status checks in client.rs

**Files:**
- Modify: `pandora-tui/src/client.rs`

- [ ] **Step 1: M3/M4 — Add error_for_status() to all request methods**

For every method that calls `.json()` or `.bytes()`, insert `let resp = resp.error_for_status().map_err(|e| e.to_string())?;` before the deserialization call.

Methods to modify (line numbers are approximate):
- `get_homepage` (line 43): before `.json()`
- `search` (line 66): before `.json()`
- `get_popular` (line 75): before `.json()`
- `get_toplist` (line 84): before `.json()`
- `get_watched` (line 93): before `.json()`
- `get_gallery_detail` (line 108): before `.json()`
- `get_favorites` (line 127): before `.json()`
- `add_favorite` (line 142): before `.json()`
- `submit_download` (line 157): before `.json()`
- `get_downloads` (line 172): before `.json()`
- `cancel_download` (line 186): before checking status
- `suggest_tags` (line 203): before `.json()`
- `get_config` (line 212): before `.json()`
- `update_config` (line 222): before `.json()`
- `get_library` (line 233): before `.json()`
- `get_library_file` (line 244): before `.bytes()`
- `proxy_image` (line 277): before `.bytes()`
- `get_page_image`: returns Response directly, no change needed

Pattern for each:
```rust
// Before:
resp.json().await.map_err(|e| e.to_string())
// After:
let resp = resp.error_for_status().map_err(|e| e.to_string())?;
resp.json().await.map_err(|e| e.to_string())
```

- [ ] **Step 2: M2 — URL encode gid/token in path segments**

Add `use urlencoding::encode;` (already imported for search).

For these methods, encode gid and token in the URL format string:
- `get_gallery_detail`: `format!("{}/api/gallery/{}/{}", self.base_url, encode(gid), encode(token))`
- `add_favorite`: same pattern
- `submit_download`: same pattern
- `cancel_download`: encode gid
- `get_page_image`: same pattern (gid + token)

Note: `gid` and `token` are normally safe ASCII, so this is purely defensive.

- [ ] **Step 3: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles without errors

- [ ] **Step 4: Commit**

```bash
git add pandora-tui/src/client.rs
git commit -m "fix(tui): M2 URL-encode path segments, M3/M4 check HTTP status codes"
```

---

### Task 11: M5 — Download task cleanup + L2/L3 — List state clamping

**Files:**
- Modify: `pandora-tui/src/state/downloads.rs`
- Modify: `pandora-tui/src/state/gallery_list.rs`
- Modify: `pandora-tui/src/main.rs` (DownloadsRefreshed, FavoritesLoaded handlers)

- [ ] **Step 1: M5 — Add cleanup_completed to DownloadState**

In `state/downloads.rs`, add after `update_from_ws`:

```rust
    pub fn cleanup_completed(&mut self) {
        // Keep max 50 completed/error tasks
        let mut done_count = self.tasks.iter()
            .filter(|t| t.status == "complete" || t.status == "error")
            .count();
        if done_count > 50 {
            self.tasks.retain(|t| {
                if (t.status == "complete" || t.status == "error") && done_count > 50 {
                    done_count -= 1;
                    false
                } else {
                    true
                }
            });
        }
    }
```

- [ ] **Step 2: Call cleanup after WS event handling**

In `main.rs`, in the `AppEvent::WsEvent` handler (line 790-801), add after `update_from_ws`:
```rust
            app.downloads.cleanup_completed();
```

- [ ] **Step 3: L2 — Clamp selected after items replacement**

In `main.rs`, in `AppEvent::DownloadsRefreshed(Ok(tasks))` handler (line 777-778), add:
```rust
        AppEvent::DownloadsRefreshed(Ok(tasks)) => {
            app.downloads.tasks = tasks;
            // L2: already handled by FavoritesLoaded below
        }
```

In `AppEvent::FavoritesLoaded(Ok(resp))` handler (lines 781-785), it already sets `selected = 0` — this is correct.

- [ ] **Step 4: L3 — Clamp scroll_offset in adjust_scroll**

In `state/gallery_list.rs`, at the end of `adjust_scroll` (after line 55), add:
```rust
        // L3: clamp scroll_offset to valid range
        if !self.items.is_empty() {
            self.scroll_offset = self.scroll_offset.min(self.items.len() - 1);
        } else {
            self.scroll_offset = 0;
        }
```

- [ ] **Step 5: Build and verify**

Run: `cd pandora-tui && cargo build 2>&1 | head -20`
Expected: compiles without errors

- [ ] **Step 6: Commit**

```bash
git add pandora-tui/src/state/downloads.rs pandora-tui/src/state/gallery_list.rs pandora-tui/src/main.rs
git commit -m "fix(tui): M5 download cleanup, L2/L3 clamp selected/scroll_offset"
```

---

### Task 12: L4 + L5 + L7 + L8 — Remaining LOW fixes

**Files:**
- Modify: `pandora-tui/src/state/search.rs:22` (L4)
- Modify: `pandora-tui/src/state/search.rs` (L7 — add suggest_generation field)
- Modify: `pandora-tui/src/config.rs:49-52` (L5)
- Modify: `pandora-tui/src/main.rs` (L7 — request_suggestions, L8 — image_states threshold)

- [ ] **Step 1: L4 — Change cursor_pos visibility**

In `state/search.rs` line 22, replace:
```rust
    pub cursor_pos: usize,
```
With:
```rust
    pub(crate) cursor_pos: usize,
```

- [ ] **Step 2: L7 — Add suggest_generation field**

In `state/search.rs`, add to `SearchState`:
```rust
    pub suggest_generation: u64,
```

In the `reset` method, add:
```rust
        self.suggest_generation = 0;
```

- [ ] **Step 3: L7 — Increment generation in request_suggestions**

In `main.rs`, in `request_suggestions` function, increment and capture generation:
```rust
fn request_suggestions(app: &App) {
    let keyword = app.search.extract_last_keyword();
    if keyword.is_empty() { return; }
    let keyword = keyword.to_string();
    let tx = app.tx.clone();
    let client = app.client.clone();
    let gen = app.search.suggest_generation;
    tokio::spawn(async move {
        let result = client.suggest_tags(&keyword).await;
        let _ = tx.send(AppEvent::SuggestionsLoaded(result, gen));
    });
}
```

Note: The generation must be incremented when the user types (in the search key handler where `suggest_pending` is set). Add `app.search.suggest_generation += 1;` there.

- [ ] **Step 4: L5 — HOME fallback warning**

In `config.rs`, replace `dirs_home` (lines 49-53):
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

- [ ] **Step 5: L8 — Lower image_states cleanup threshold**

In `main.rs`, in the `ThumbnailLoaded` handler (line 727), replace:
```rust
            if app.image_states.len() > 300 {
```
With:
```rust
            if app.image_states.len() > 220 {
```

- [ ] **Step 6: Build and run tests**

Run: `cd pandora-tui && cargo test 2>&1`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add pandora-tui/src/state/search.rs pandora-tui/src/config.rs pandora-tui/src/main.rs
git commit -m "fix(tui): L4 cursor_pos pub(crate), L5 HOME warning, L7 suggest generation, L8 lower cleanup threshold"
```

---

### Task 13: Final build + full test run

**Files:** None (verification only)

- [ ] **Step 1: Full build**

Run: `cd pandora-tui && cargo build 2>&1`
Expected: compiles without errors or warnings

- [ ] **Step 2: Run all tests**

Run: `cd pandora-tui && cargo test 2>&1`
Expected: all 16+ tests pass

- [ ] **Step 3: Verify no regressions in daemon tests**

Run: `cd /home/ycyc/code/project/pandora && uv run pytest tests/ -x -q 2>&1 | tail -5`
Expected: 407 passed (daemon tests unaffected by TUI changes)

- [ ] **Step 4: Final commit if any cleanup needed**

```bash
git add -A && git status
# Only commit if there are changes
```
