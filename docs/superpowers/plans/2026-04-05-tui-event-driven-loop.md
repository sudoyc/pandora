# TUI Event-Driven Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the TUI main loop from fixed-framerate polling to event-driven rendering, add gallery list generation counter, and optimize preload performance.

**Architecture:** Replace the synchronous `crossterm::event::poll()`+`read()` loop with `tokio::select!` over three async sources (terminal EventStream, mpsc channel, debounce timer). A `dirty` flag gates rendering. Image decoding moves to `spawn_blocking`. Preload concurrency is limited by a semaphore.

**Tech Stack:** Rust, ratatui, crossterm (event-stream feature), tokio, ratatui-image

---

### Task 1: Add `event-stream` feature to crossterm and update imports

**Files:**
- Modify: `pandora-tui/Cargo.toml`

- [ ] **Step 1: Add event-stream feature**

In `Cargo.toml`, change the crossterm dependency:

```toml
crossterm = { version = "0.29", features = ["event-stream"] }
```

- [ ] **Step 2: Verify it compiles**

Run: `cd pandora-tui && cargo check`
Expected: compiles with no new errors

- [ ] **Step 3: Commit**

```bash
cd pandora-tui
git add Cargo.toml Cargo.lock
git commit -m "build: enable crossterm event-stream feature"
```

### Task 2: Add `list_generation` to App and wire into GalleriesLoaded

**Files:**
- Modify: `pandora-tui/src/app.rs`
- Modify: `pandora-tui/src/event.rs`
- Modify: `pandora-tui/src/main.rs`

- [ ] **Step 1: Update AppEvent enum**

In `event.rs`, change `GalleriesLoaded` to carry a generation:

```rust
GalleriesLoaded(Result<Vec<GalleryItem>, String>, u64),
```

- [ ] **Step 2: Add `list_generation` field to App**

In `app.rs`, add field to `App` struct after `detail_generation`:

```rust
    pub detail_generation: u64,
    pub list_generation: u64,
```

In `App::new()`, initialize it:

```rust
            detail_generation: 0,
            list_generation: 0,
```

- [ ] **Step 3: Wire generation into `load_current_page()`**

In `app.rs`, at the start of `load_current_page()`, increment and capture generation:

```rust
    pub fn load_current_page(&mut self) {
        self.gallery_list.loading = true;
        self.list_generation += 1;
        let generation = self.list_generation;
        let page = self.gallery_list.current_page;
```

Then update every `AppEvent::GalleriesLoaded(...)` inside the match arms to include `generation`. For example the Homepage arm:

```rust
            PageSource::Homepage => {
                self.spawn_fetch(move |c| async move {
                    AppEvent::GalleriesLoaded(c.get_homepage().await, generation)
                });
            }
```

Apply the same pattern to all 7 arms: Homepage, Popular, Toplist, Watched, Favorites, Downloaded, Search.

- [ ] **Step 4: Update handler in `main.rs`**

In `handle_app_event()`, update both `GalleriesLoaded` arms:

```rust
        AppEvent::GalleriesLoaded(Ok(items), generation) => {
            if generation != app.list_generation {
                return; // Stale response, discard
            }
            let count = items.len();
            app.gallery_list.items = items;
            app.gallery_list.loading = false;
            app.gallery_list.selected = 0;
            app.status_msg = format!("Loaded {} galleries", count);
            app.load_selected_detail();
        }
        AppEvent::GalleriesLoaded(Err(e), generation) => {
            if generation != app.list_generation {
                return;
            }
            app.gallery_list.loading = false;
            app.status_msg = if e.contains("timed out") || e.contains("timeout") {
                "Connection timed out — check daemon".to_string()
            } else if e.contains("connect") || e.contains("Connection refused") {
                "Cannot reach daemon — is it running?".to_string()
            } else {
                format!("Load failed: {}", e)
            };
        }
```

Also update `FavoritesLoaded` handler to include generation check (it also sets gallery_list.items):

```rust
        AppEvent::FavoritesLoaded(Ok(resp)) => {
            app.gallery_list.items = resp.galleries;
            app.gallery_list.loading = false;
            app.gallery_list.selected = 0;
        }
```

Note: FavoritesLoaded is dispatched from Favorites arm of `load_current_page()` which now goes through `GalleriesLoaded` with generation. No separate change needed for FavoritesLoaded unless it's still used elsewhere. Check if it's still referenced — if not, it can be removed.

- [ ] **Step 5: Verify compilation and tests**

Run: `cargo test`
Expected: 16 tests pass, no compile errors

- [ ] **Step 6: Commit**

```bash
git add src/app.rs src/event.rs src/main.rs
git commit -m "fix: add list_generation counter to prevent stale gallery list"
```

### Task 3: Add preload semaphore and `spawn_blocking` for image decode

**Files:**
- Modify: `pandora-tui/src/app.rs`
- Modify: `pandora-tui/src/main.rs`

- [ ] **Step 1: Add constants to `main.rs`**

At the top of `main.rs`, after the `use` block:

```rust
const PRELOAD_WINDOW_LOCAL: u32 = 10;
const PRELOAD_WINDOW_ONLINE: u32 = 3;
const PRELOAD_CONCURRENT: usize = 3;
const RENDER_BURST_FRAMES: u8 = 2;
```

- [ ] **Step 2: Add semaphore to App**

In `app.rs`, add import:

```rust
use std::sync::Arc;
use tokio::sync::Semaphore;
```

Add field to `App`:

```rust
    pub preload_semaphore: Arc<Semaphore>,
```

Initialize in `App::new()`:

```rust
            preload_semaphore: Arc::new(Semaphore::new(3)),
```

- [ ] **Step 3: Refactor `request_thumbnail()` to use `spawn_blocking` for decode**

In `app.rs`, update `request_thumbnail()`:

```rust
    pub fn request_thumbnail(&mut self, url: String) {
        if self.image_cache.contains(&url)
            || self.failed_images.contains(&url)
            || self.pending_images.contains(&url)
        {
            return;
        }
        self.pending_images.insert(url.clone());
        let tx = self.tx.clone();
        let client = self.client.clone();
        tokio::spawn(async move {
            match client.proxy_image(&url).await {
                Ok(bytes) => {
                    let url_clone = url.clone();
                    match tokio::task::spawn_blocking(move || {
                        image::load_from_memory(&bytes)
                    }).await {
                        Ok(Ok(img)) => {
                            let _ = tx.send(AppEvent::ThumbnailLoaded { url, image: img });
                        }
                        Ok(Err(e)) => {
                            let _ = tx.send(AppEvent::ImageError {
                                url,
                                error: e.to_string(),
                            });
                        }
                        Err(e) => {
                            let _ = tx.send(AppEvent::ImageError {
                                url: url_clone,
                                error: e.to_string(),
                            });
                        }
                    }
                }
                Err(e) => {
                    let _ = tx.send(AppEvent::ImageError { url, error: e });
                }
            }
        });
    }
```

Apply the same `spawn_blocking` pattern to `request_gallery_thumb()`.

- [ ] **Step 4: Refactor `load_page_image()` in `main.rs` to use `spawn_blocking`**

For both the local and online branches, replace direct `image::load_from_memory(&bytes)` calls with:

```rust
                    match tokio::task::spawn_blocking(move || {
                        image::load_from_memory(&bytes)
                    }).await {
                        Ok(Ok(img)) => {
                            let _ = tx.send(AppEvent::PageImageLoaded { page, image: img });
                        }
                        Ok(Err(e)) => {
                            let _ = tx.send(AppEvent::ImageError {
                                url: format!("page:{}", page),
                                error: e.to_string(),
                            });
                        }
                        Err(_) => {}
                    }
```

- [ ] **Step 5: Add semaphore to `preload_adjacent_pages()`**

In `main.rs`, update `preload_adjacent_pages()` to use constants and semaphore:

```rust
fn preload_adjacent_pages(app: &mut App) {
    let page = app.reader.current_page;
    let total = app.reader.total_pages;
    let is_local = app.reader.is_local;
    let gid = app.reader.gid.clone();
    let token = app.reader.token.clone();

    let (behind, ahead) = if is_local {
        (PRELOAD_WINDOW_LOCAL, PRELOAD_WINDOW_LOCAL)
    } else {
        (PRELOAD_WINDOW_ONLINE, PRELOAD_WINDOW_ONLINE)
    };
    let start = page.saturating_sub(behind).max(1);
    let end = (page + ahead).min(total);

    // Priority order: N+1, N-1, N+2, N-2, ...
    let mut pages_to_load: Vec<u32> = Vec::new();
    for delta in 1..=ahead.max(behind) {
        if page + delta <= end {
            pages_to_load.push(page + delta);
        }
        if delta <= behind && page > delta && page - delta >= start {
            pages_to_load.push(page - delta);
        }
    }

    for p in pages_to_load {
        let cache_key = format!("page:{}:{}", gid, p);
        if app.page_cache.contains(&cache_key) || app.pending_pages.contains(&p) {
            continue;
        }
        app.pending_pages.insert(p);

        let tx = app.tx.clone();
        let client = app.client.clone();
        let gid = gid.clone();
        let token = token.clone();
        let sem = app.preload_semaphore.clone();

        if is_local {
            tokio::spawn(async move {
                let _permit = sem.acquire().await;
                let path = format!("page/{}", p);
                if let Ok(bytes) = client.get_library_file(&gid, &path).await {
                    if let Ok(Ok(img)) = tokio::task::spawn_blocking(move || {
                        image::load_from_memory(&bytes)
                    }).await {
                        let _ = tx.send(AppEvent::PageImageLoaded { page: p, image: img });
                    }
                }
            });
        } else {
            tokio::spawn(async move {
                let _permit = sem.acquire().await;
                if let Ok(resp) = client.get_page_image(&gid, &token, p).await {
                    if let Ok(bytes) = resp.bytes().await {
                        if let Ok(Ok(img)) = tokio::task::spawn_blocking(move || {
                            image::load_from_memory(&bytes)
                        }).await {
                            let _ = tx.send(AppEvent::PageImageLoaded { page: p, image: img });
                        }
                    }
                }
            });
        }
    }
}
```

- [ ] **Step 6: Eliminate page image clone in handler**

In `handle_app_event()` in `main.rs`, update `PageImageLoaded`:

```rust
        AppEvent::PageImageLoaded { page, image } => {
            app.pending_pages.remove(&page);
            if page == app.reader.current_page {
                // Current page: display directly, also cache
                app.page_image_state = None;
                app.reader.loading = false;
                app.reader.loading_progress = None;
                let cache_key = format!("page:{}:{}", app.reader.gid, page);
                app.page_cache.put(cache_key, image.clone());
                app.page_image = Some(image);
            } else {
                // Preloaded page: cache only, no clone
                let cache_key = format!("page:{}:{}", app.reader.gid, page);
                app.page_cache.put(cache_key, image);
            }
        }
```

Note: current page still needs a clone (one copy in page_cache, one in page_image for rendering). Preloaded pages do not clone — they move directly into cache.

- [ ] **Step 7: Verify compilation and tests**

Run: `cargo test`
Expected: 16 tests pass

- [ ] **Step 8: Commit**

```bash
git add src/app.rs src/main.rs
git commit -m "perf: spawn_blocking for image decode, semaphore for preload concurrency"
```

### Task 4: Rewrite main loop to event-driven `tokio::select!`

**Files:**
- Modify: `pandora-tui/src/main.rs`
- Modify: `pandora-tui/src/app.rs`

- [ ] **Step 1: Remove `suggest_debounce` from App**

In `app.rs`, remove the field:

```rust
    // DELETE: pub suggest_debounce: Option<Instant>,
```

And remove from `App::new()`:

```rust
    // DELETE: suggest_debounce: None,
```

The debounce timer will live as a local variable in the main loop instead.

- [ ] **Step 2: Rewrite the main loop in `main.rs`**

Replace everything from `// Terminal setup` through the `loop { ... }` and `// Cleanup` section. The new main function body after the WebSocket spawn block:

```rust
    // Terminal setup
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // Async terminal event stream
    let mut term_events = crossterm::event::EventStream::new();

    // Render state
    let mut dirty = true; // Draw initial frame
    let mut render_burst: u8 = 0;

    // Debounce state for search suggestions
    let mut suggest_deadline: Option<tokio::time::Instant> = None;

    loop {
        // Render if dirty
        if dirty {
            terminal.draw(|frame| {
                ui::draw(frame, &mut app);
            })?;
            dirty = false;
            if render_burst > 0 {
                render_burst -= 1;
                dirty = true;
            }
        }

        if app.should_quit {
            break;
        }

        // Block until an event arrives
        tokio::select! {
            maybe_event = futures_util::StreamExt::next(&mut term_events) => {
                if let Some(Ok(event)) = maybe_event {
                    match event {
                        Event::Key(key) if key.kind == KeyEventKind::Press => {
                            handle_key(&mut app, key.code, key.modifiers);
                            dirty = true;
                        }
                        Event::Resize(_, _) => {
                            dirty = true;
                        }
                        _ => {}
                    }
                }
            }
            Some(app_event) = rx.recv() => {
                let is_image_event = matches!(
                    app_event,
                    AppEvent::ThumbnailLoaded { .. } | AppEvent::PageImageLoaded { .. }
                );
                handle_app_event(&mut app, app_event);
                dirty = true;
                if is_image_event {
                    render_burst = RENDER_BURST_FRAMES;
                }
            }
            _ = async {
                match suggest_deadline {
                    Some(deadline) => tokio::time::sleep_until(deadline).await,
                    None => std::future::pending::<()>().await,
                }
            }, if suggest_deadline.is_some() => {
                suggest_deadline = None;
                request_suggestions(&app);
            }
        }

        // Check if a keystroke scheduled a suggestion debounce
        if app.suggest_debounce.is_some() {
            suggest_deadline = Some(tokio::time::Instant::now() + Duration::from_millis(150));
            app.suggest_debounce = None;
        }
    }

    // Cleanup
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    Ok(())
```

- [ ] **Step 3: Wait — keep `suggest_debounce` on App for keystroke signaling**

Actually, the search key handler sets `app.suggest_debounce = Some(Instant::now())` to signal that a suggestion request should be debounced. We need to keep this as a simple `bool` flag instead.

In `app.rs`, change the field:

```rust
    pub suggest_pending: bool,
```

Initialize in `App::new()`:

```rust
    suggest_pending: false,
```

In `main.rs`, update the search key handler — replace all `app.suggest_debounce = Some(Instant::now())` with:

```rust
    app.suggest_pending = true;
```

And update the check after `select!`:

```rust
        if app.suggest_pending {
            suggest_deadline = Some(tokio::time::Instant::now() + Duration::from_millis(150));
            app.suggest_pending = false;
        }
```

- [ ] **Step 4: Update imports in `main.rs`**

Replace the existing import block:

```rust
use std::io;
use std::time::Duration;

use crossterm::{
    event::{Event, KeyCode, KeyEventKind, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::prelude::*;
use ratatui_image::picker::Picker;
use tokio::sync::mpsc;

use app::{App, AppMode, PageSource};
use client::DaemonClient;
use event::AppEvent;
```

Note: removed `std::time::Instant` (no longer used in main), removed `crossterm::event::{self as ct_event}`, added `Event` directly.

- [ ] **Step 5: Remove unused `AppEvent` variants**

In `event.rs`, remove `Key(KeyEvent)` and `Tick` variants — they're no longer used:

```rust
pub enum AppEvent {
    // ── Daemon responses ──
    GalleriesLoaded(Result<Vec<GalleryItem>, String>, u64),
    DetailLoaded(Result<GalleryDetail, String>, u64),
    FavoritesLoaded(Result<FavoritesResponse, String>),
    SuggestionsLoaded(Result<Vec<TagSuggestion>, String>),
    DownloadSubmitted(Result<DownloadTask, String>),
    DownloadsRefreshed(Result<Vec<DownloadTask>, String>),

    // ── Image events ──
    ThumbnailLoaded { url: String, image: DynamicImage },
    PageImageLoaded { page: u32, image: DynamicImage },
    PageImageProgress { page: u32, received: u64, total: u64 },
    ImageError { url: String, error: String },

    // ── WebSocket events ──
    WsEvent(WsEvent),
    WsDisconnected,
    WsReconnected,
}
```

Remove the `use crossterm::event::KeyEvent;` import if `Key` variant is gone.

- [ ] **Step 6: Remove `Tick` and `Key` handlers from `handle_app_event()`**

In `main.rs`, remove:

```rust
        AppEvent::Tick => {}
        AppEvent::Key(_) => {}
```

- [ ] **Step 7: Verify compilation and tests**

Run: `cargo test`
Expected: 16 tests pass, no compile errors

- [ ] **Step 8: Commit**

```bash
git add src/main.rs src/app.rs src/event.rs Cargo.toml
git commit -m "refactor: event-driven main loop with tokio::select!, dirty flag, render burst"
```

### Task 5: Final verification

**Files:** none (testing only)

- [ ] **Step 1: Run full test suite**

Run: `cargo test`
Expected: 16 tests pass

- [ ] **Step 2: Build release**

Run: `cargo build --release`
Expected: compiles successfully

- [ ] **Step 3: Manual smoke test checklist**

Run the release binary against a running daemon and verify:
- [ ] Idle CPU near 0% when sitting on a gallery detail (check with `top` or `htop`)
- [ ] Key presses respond instantly (j/k navigation, / search)
- [ ] Images render fully after loading (cover, thumbs, reader pages)
- [ ] Fast source switching (1→6→1) shows correct list, no stale data
- [ ] Downloaded gallery reader loads pages from local files
- [ ] Search suggestion debounce works (type fast, only one request after pause)
- [ ] WebSocket reconnection works (restart daemon, TUI reconnects)

- [ ] **Step 4: Commit any fixes from smoke testing**

## Verification

- All 16 existing tests pass unchanged
- Spec requirements covered: event-driven loop (Task 4), generation counter (Task 2), preload perf (Task 3)
- No new files created, no daemon changes
