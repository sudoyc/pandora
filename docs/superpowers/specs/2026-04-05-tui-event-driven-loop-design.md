# TUI Event-Driven Loop Redesign

**Date:** 2026-04-05
**Scope:** pandora-tui only (no daemon changes)

## Problem

The TUI main loop runs at a fixed 50ms tick rate (20 FPS), redrawing unconditionally every frame. This causes:

1. **Wasted CPU** — idle reading burns cycles on redundant redraws
2. **Unresponsive preloading** — ±10 local preload spawns 20 concurrent tasks; `image::load_from_memory()` blocks tokio worker threads; main loop drains all events per frame, cloning megabytes of pixel data synchronously
3. **Stale gallery list** — fast page-source switching can overwrite current list with a late response from the previous source (no generation counter like detail loading has)

## Design

### 1. Event-Driven Main Loop

Replace the poll-timeout-draw loop with `tokio::select!` blocking on three event sources:

```
loop {
    if dirty {
        terminal.draw()?;
        dirty = false;
        if render_burst > 0 {
            render_burst -= 1;
            dirty = true;
        }
    }

    tokio::select! {
        Some(event) = term_events.next() => {
            handle_terminal_event(event);
            dirty = true;
        }
        Some(event) = rx.recv() => {
            handle_app_event(event);
            dirty = true;
        }
        _ = debounce_sleep(), if debounce_active => {
            fire_suggestion_request();
            debounce_active = false;
        }
    }
}
```

**Key behaviors:**
- No events → `select!` blocks, zero CPU
- `dirty: bool` — set by any event handler, controls whether `draw()` is called
- `render_burst: u8` — set to 2 when an image loads; forces 2 extra consecutive redraws so ratatui-image's StatefulProtocol completes kitty/sixel transmission; then stops
- crossterm `EventStream` (async) replaces synchronous `poll()` + `read()`
- Debounce timer for search suggestions replaces the current `Instant`-based check in the tick section

**Dependency:** crossterm `event-stream` feature (adds `EventStream` type).

### 2. Gallery List Generation Counter

Same pattern as the existing `detail_generation`:

- `App` gets `list_generation: u64`
- `load_current_page()` increments it, passes the value into the spawned closure
- `AppEvent::GalleriesLoaded` carries a `u64` generation field
- Handler compares: mismatch → discard the response

Prevents stale data from overwriting the current list when the user switches sources rapidly.

### 3. Preload Performance

**Concurrent preload limiting:**
- `App` gets `preload_semaphore: Arc<tokio::sync::Semaphore>` with 3 permits
- Each preload task acquires a permit before starting, releases on completion
- Preload window unchanged: ±10 local, ±3 online (hardcoded constants for now)

**Image decode offload:**
- All `image::load_from_memory()` calls move to `tokio::task::spawn_blocking`
- Pattern: `tokio::spawn` does network I/O → gets bytes → `spawn_blocking` decodes → sends event through channel
- Applies to: page load, preload, thumbnail load

**Eliminate page image clone:**
- `PageImageLoaded` handler: if current page → move image into `page_image` (no clone); otherwise → move into `page_cache`
- A `DynamicImage` lives in exactly one place, never duplicated

### 4. File Changes

| File | Change |
|------|--------|
| `Cargo.toml` | Add `event-stream` to crossterm features |
| `main.rs` | Rewrite main loop to `select!`; add `dirty`, `render_burst`; single `recv()` replaces drain loop; debounce via `tokio::time::sleep` future; all decode calls use `spawn_blocking`; generation check on `GalleriesLoaded` |
| `app.rs` | Add `list_generation: u64`, `preload_semaphore: Arc<Semaphore>` |
| `event.rs` | `GalleriesLoaded(Result<Vec<GalleryItem>, String>, u64)` — add generation |

No new files. No daemon changes. No UI rendering changes.

### 5. Constants

```rust
const PRELOAD_WINDOW_LOCAL: u32 = 10;
const PRELOAD_WINDOW_ONLINE: u32 = 3;
const PRELOAD_CONCURRENT: usize = 3;
const RENDER_BURST_FRAMES: u8 = 2;
```

### 6. Testing

- Existing 16 tests must pass unchanged (they test models, state, config — not the main loop)
- Manual verification: idle CPU near 0%, preload doesn't block key input, fast source-switching shows correct list, image renders fully after load
