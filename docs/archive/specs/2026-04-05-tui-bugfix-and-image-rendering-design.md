# TUI Bugfix & Image Rendering Design

Date: 2026-04-05
Status: Approved

## Overview

Fix all identified issues in pandora-tui and integrate ratatui-image for real image rendering. Also add daemon-side Library API for browsing downloaded galleries.

## Issues Catalog

| # | Issue | Root Cause | Severity |
|---|-------|-----------|----------|
| 1 | "Detail error: error decoding response body" | `Comment.score` is `int` in daemon, `Option<String>` in Rust | P0 |
| 2 | Detail deserialization fails even without comments | `_detail_to_dict` missing `thumb_urls` field | P0 |
| 3 | Cannot enter reader mode | Consequence of #1/#2 — `detail` is always `None` | P0 |
| 4 | Thumbnails/cover/reader all show placeholders | ratatui-image not integrated, only text placeholders | P1 |
| 5 | Selected gallery highlight too subtle | `Rgb(40,40,60)` background barely visible | P1 |
| 6 | Title overflows card boundary | `chars().count()` doesn't account for CJK double-width | P1 |
| 7 | Category badge colors hard to read | White text on light backgrounds (Artist CG, Game CG, Western) | P1 |
| 8 | Search suggestions don't scroll | No scroll offset, selected item goes off-screen | P1 |
| 9 | Search category filter logic inverted | TUI sends EXCLUDE mask, daemon treats as INCLUDE then re-inverts | P1 |
| 10 | Toplist/Watched/Favorites don't display | Toplist returns `TopListItem` not `GalleryItem`; others need investigation | P2 |
| 11 | Downloaded galleries not implemented | `PageSource::Downloaded` is a stub | P2 |

## Fix Design

### 1. Daemon-Side Fixes

#### 1.1 `_detail_to_dict` — add missing `thumb_urls`

In `pandora_daemon/routes/gallery.py`, add `"thumb_urls": d.thumb_urls` to `_detail_to_dict()`.

#### 1.2 Toplist endpoint returns GalleryItem format

Current `/api/toplist` returns `TopListItem` (`{type, name, link}`). Change it to parse `link` URLs into `(gid, token)`, fetch gallery list items, and return them in `GalleryItem` format. This keeps all frontends simple.

Alternative: accept that toplist is a different data shape. But this complicates every frontend. Daemon conversion is preferred.

**Implementation**: Toplist entries contain links to galleries. The daemon can batch-fetch gallery metadata (or at minimum, parse the toplist page which already shows gallery cards) to return standard `GalleryItem` dicts. If the existing `get_toplist` parser extracts `GalleryListItem`-compatible data from the HTML, we can use that directly. Otherwise, fallback to returning a simplified item with just gid/token/title extracted from the link.

> **Decision**: Check if the exhentai toplist HTML page actually renders gallery cards (with thumbnails, ratings, etc). If yes, parse them as `GalleryListItem`. If no (just ranked links), return a minimal `GalleryItem` with empty/default fields for thumb_url, rating, etc.

#### 1.3 Library API

New route module `pandora_daemon/routes/library.py`:

```
GET /api/library
```
Scans `config.download.path` for subdirectories containing `metadata.json`. Returns list of gallery metadata dicts (same fields as metadata.json content, which mirrors GalleryDetail fields).

```
GET /api/library/{gid}/file?path=cover|thumb/{page}|page/{page}
```
Serves local files from the download directory. The `path` parameter specifies what to serve:
- `cover` → finds `cover.*` in the gallery directory
- `thumb/3` → finds `thumbs/0003.*`
- `page/3` → finds `pages/0003.*`

Returns raw image bytes with appropriate Content-Type.

**Gallery directory lookup**: Find subdirectory matching `{gid}-*` pattern in download path.

### 2. Rust TUI Model Fixes

#### 2.1 Comment.score type

Change `score: Option<String>` to `score: i64` in `models.rs`.

#### 2.2 Defensive deserialization

Add `#[serde(default)]` to `GalleryDetail` fields that might be missing from daemon responses, particularly `thumb_urls`, `comments`, and string fields that might not always be present. This prevents hard failures when the daemon response evolves.

#### 2.3 TopListItem

No new model needed if daemon converts to GalleryItem format (see 1.2).

#### 2.4 DownloadedGalleryMeta

Already exists in models.rs. Reuse for `/api/library` responses.

### 3. Search Fixes

#### 3.1 Category bitmask semantics

The chain is:
- TUI: `excluded_categories` (bits set = EXCLUDE)
- Daemon `browse.py`: `params.f_cats = category` (treats value as INCLUDE mask)
- `SearchParams.to_dict()`: inverts f_cats to get EXCLUDE mask for exhentai

**Fix**: In TUI `category_bitmask()`, invert the excluded mask to produce an INCLUDE mask before sending:

```rust
pub fn category_bitmask(&self) -> Option<u32> {
    if self.excluded_categories == 0 {
        None  // no filtering
    } else {
        Some((!self.excluded_categories) & 1023)  // invert to INCLUDE
    }
}
```

#### 3.2 Suggestion scroll

Add `suggestion_scroll_offset: usize` to `SearchState`. When `selected_suggestion` moves beyond visible area, adjust offset. In `draw_suggestions()`, skip items before offset.

### 4. UI Rendering Fixes

#### 4.1 Title truncation with unicode-width

Add `unicode-width` crate to Cargo.toml. Replace `chars().count()` with `UnicodeWidthStr::width()` in `gallery_card.rs` truncation logic. Truncate based on display columns, not character count.

#### 4.2 Category color pairs

Replace single background color with (foreground, background) pairs:

| Category | Background | Foreground |
|----------|-----------|------------|
| Doujinshi | Red | White |
| Manga | Yellow | Black |
| Artist CG | Rgb(200,150,0) | Black |
| Game CG | Green | Black |
| Western | Rgb(140,200,60) | Black |
| Non-H | Blue | White |
| Image Set | Magenta | White |
| Cosplay | LightMagenta | Black |
| Asian Porn | DarkGray | White |
| Misc | Gray | Black |

Key principle: dark backgrounds get white/light text; light backgrounds get black text.

#### 4.3 Selected gallery highlight

- Left side: add `▶ ` prefix indicator (bright cyan or yellow)
- Background: `Rgb(50, 50, 80)` (more visible than current `Rgb(40, 40, 60)`)
- Optional: bright left border bar using `│` character

#### 4.4 ratatui-image integration

Three render points need real image rendering:

**Cover** (`info_panel.rs`):
- `app.request_thumbnail(cover_url)` to load cover into image_cache
- Retrieve `DynamicImage` from cache, create `StatefulImage`, render with `StatefulWidget` using kitty protocol
- Fallback: if terminal doesn't support kitty, show `[Cover]` text

**Thumbnails** (`thumb_grid.rs`):
- Already calls `request_thumbnail()` and loads into `image_cache`
- Replace text placeholder with `StatefulImage` render per cell
- Each cell gets its own `ImageState` (stored alongside or keyed by URL)

**Reader** (`reader.rs`):
- `page_image: Option<DynamicImage>` already populated
- Replace `[Page image rendered here]` with `StatefulImage` render
- Image should scale to fit the viewer area while preserving aspect ratio

**Implementation approach**:
- Use `ratatui_image::protocol::StatefulProtocol` with `Picker::from_query_stdio()` to auto-detect terminal capabilities
- Store a `Picker` in `App` struct, initialized at startup
- Each image render point creates a `StatefulImage` from `DynamicImage` and renders it
- Need `ImageState` per render location (stored in App or per-widget state)

**Dependencies**: `ratatui-image` 10.x already in Cargo.toml. May need to enable `crossterm` feature.

### 5. Additional Fixes

#### 5.1 Watched/Favorites error handling

These should work with the same `GalleryItem` format once the serde issues are fixed. If they still fail, it's likely a daemon auth issue. Add better error messages showing HTTP status codes.

#### 5.2 WebSocket integration

The WS connection is scaffolded but not wired into the main loop. Add `tokio-tungstenite` connect in a background task that sends `WsEvent` through the channel. This enables real-time download progress in the TUI.

## Out of Scope

- GIF/animated image rendering (post-v1)
- Search debounce (minor, can be done later)
- Favorites management UI (per v1 scope decision)
- Advanced search fields beyond category + min_rating

## File Change Summary

### Daemon (Python)
- `pandora_daemon/routes/gallery.py` — add `thumb_urls` to `_detail_to_dict`
- `pandora_daemon/routes/browse.py` — toplist conversion to GalleryItem format
- `pandora_daemon/routes/library.py` — NEW: library list + file serving
- `pandora_daemon/app.py` — register library router

### TUI (Rust)
- `Cargo.toml` — add `unicode-width`
- `src/models.rs` — fix Comment.score type, add serde defaults
- `src/app.rs` — add `Picker` for ratatui-image, image state management
- `src/main.rs` — WebSocket background task, toplist handling
- `src/client.rs` — add `get_library()`, `get_library_file()` methods
- `src/state/search.rs` — fix category_bitmask(), add suggestion_scroll_offset
- `src/state/gallery_list.rs` — (no changes expected)
- `src/ui/gallery_card.rs` — unicode-width truncation, better highlight, color pairs
- `src/ui/thumb_grid.rs` — ratatui-image rendering
- `src/ui/info_panel.rs` — ratatui-image cover rendering
- `src/ui/reader.rs` — ratatui-image page rendering
- `src/ui/search.rs` — suggestion scroll support
- `src/models.rs` — category_to_color returns (fg, bg) pair
