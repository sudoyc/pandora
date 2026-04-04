# CLI Download Command + Rust TUI Design Spec

**Date:** 2026-04-05
**Scope:** Phase 1.6 CLI rewrite + Phase 2 Rust TUI + Daemon tag suggest API

---

## 1. Overview

Three deliverables, built sequentially:

1. **CLI Download Command** (Python, minimal) — `pandora download <url>` as daemon client
2. **Daemon Tag Suggest API** (Python) — EhTagTranslation-powered tag autocomplete endpoint
3. **Rust TUI** (Rust, ratatui) — Main frontend for browsing, searching, and downloading

### Directory Structure

```
pandora/
├── exhentai_api/        # Python lib (unchanged)
├── pandora_daemon/      # Python daemon (+ tag suggest API, + streaming page image)
│   ├── cli.py           # New: CLI download command
│   └── tag_database.py  # New: EhTagTranslation database
├── pandora-tui/         # New: Rust TUI
│   ├── Cargo.toml
│   └── src/
├── cli.py               # Delete (legacy)
└── downloader.py        # Delete (legacy)
```

Python directories use underscores (language convention), Rust uses hyphens.

---

## 2. CLI Download Command

**File:** `pandora_daemon/cli.py`
**Entry point:** `pandora` (registered in pyproject.toml)

### Usage

```bash
pandora download <gallery_url>
```

### Behavior

1. Parse gallery URL → extract gid, token
2. `POST /api/downloads` with `{"gid": gid, "token": token}` → submit download task
3. Connect to `WS /ws` → listen for progress events
4. Display progress with `rich` progress bar:
   - Phase: metadata → cover → thumbs → pages
   - Per-page progress within each phase
5. On `download_complete` event → print path, exit 0
6. On `download_error` event → print error, exit 1
7. Ctrl-C → graceful disconnect, exit 130

### Configuration

Reads daemon URL from `~/.config/pandora/config.toml` (`server.host` + `server.port`), defaults to `http://127.0.0.1:7860`.

### Dependencies

`httpx`, `websockets` or `httpx[ws]`, `rich`. All already in project deps.

### Cleanup

Delete legacy files: `cli.py`, `downloader.py` (root level). Remove `tui.py` if present.

---

## 3. Daemon Tag Suggest API

### New Component: TagDatabase

**File:** `pandora_daemon/tag_database.py`

**Data source:** `https://raw.githubusercontent.com/EhTagTranslation/DatabaseReleases/master/db.text.json`

**Lifecycle:**
- Daemon startup → load from local cache (`~/.cache/pandora/tags/db.text.json`)
- If cache missing → download from GitHub
- Background task: periodic update check (every 24h), compare ETag/SHA
- In-memory: flat list of `TagEntry(namespace, tag, translation)` (~15,000 entries)

**Data structure:**

```python
@dataclass
class TagEntry:
    namespace: str      # "female", "male", "artist", etc.
    tag: str            # "stockings"
    translation: str    # "丝袜"

class TagDatabase:
    entries: list[TagEntry]

    async def suggest(self, query: str, limit: int = 10) -> list[TagEntry]:
        """Substring match on tag name OR translation. Prefix match ranked first."""

    async def translate(self, namespace: str, tag: str) -> str | None:
        """Exact lookup for display purposes."""
```

**Search algorithm:**
1. Lowercase query
2. For each entry: check if `query in entry.tag` or `query in entry.translation`
3. Sort results: prefix matches first, then by position of match
4. Return top `limit` results

Linear scan over 15K entries is <1ms, no index needed.

### New Endpoint

```
GET /api/tags/suggest?q=stocking&limit=10

Response 200:
{
  "suggestions": [
    {"namespace": "female", "tag": "stockings", "translation": "丝袜"},
    {"namespace": "female", "tag": "stockings_only", "translation": "仅穿丝袜"},
    {"namespace": "female", "tag": "striped_stockings", "translation": "条纹丝袜"}
  ]
}
```

### Streaming Page Image

Modify `GET /api/gallery/{gid}/{token}/page/{page}` to use `StreamingResponse` for uncached images. Include `Content-Length` header when available so TUI can display download progress.

- Cache hit → return `Response(content=data)` immediately (no streaming needed)
- Cache miss → stream from exhentai through daemon to client with `Content-Length`

---

## 4. Rust TUI Architecture

### Crate Dependencies

```toml
[dependencies]
ratatui = "0.29"
crossterm = "0.28"
ratatui-image = "3"
reqwest = { version = "0.12", features = ["json", "stream"] }
tokio = { version = "1", features = ["full"] }
tokio-tungstenite = "0.24"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
image = "0.25"
clap = { version = "4", features = ["derive"] }
```

### Architecture: Event-driven + tokio channels

```
┌──────────────────────────────────────┐
│          Main Event Loop             │
│  tokio::select! {                    │
│    key_event = terminal_rx ──┐       │
│    daemon_msg = daemon_rx ───┤→ App::update(event)
│    ws_event  = ws_rx ────────┘→ App::draw(frame)
│  }                                   │
└──────────────────────────────────────┘
         │ spawn
┌────────┴────────┐
│ Background Tasks │
│ • HTTP requests  │
│ • Image decode   │
│ • WS listener    │
└─────────────────┘
```

**Key principle:** All I/O in background tasks via `tokio::spawn`. Results sent back through `mpsc::channel`. Main loop only does `update()` + `draw()`, never blocks.

### State Structure

```rust
struct App {
    // Navigation
    mode: AppMode,                        // Browse | Read | Search
    page_source: PageSource,              // Homepage | Popular | Toplist | Watched | Favorites | Downloaded

    // Gallery list
    gallery_list: GalleryListState,       // items, selected_index, current_page, scroll_offset
    detail: Option<GalleryDetail>,        // Detail for currently selected gallery
    thumbnails: HashMap<String, DecodedImage>, // url → decoded image (for gallery list cards)

    // Thumbnail grid (middle pane in browse mode)
    thumb_grid: ThumbGridState,           // page thumbnails for selected gallery

    // Reader
    reader: ReaderState,                  // current_page, image, loading_progress, error

    // Search
    search: SearchState,                  // input, cursor_pos, suggestions, selected_suggestion, category_filter, min_rating, min_pages, filter_active

    // Downloads
    downloads: DownloadState,             // tasks, show_overlay

    // Infra
    daemon_url: String,
    image_cache: LruCache<String, DecodedImage>, // Decoded images (bounded)
    status_msg: String,
    show_help: bool,
}
```

### Module Layout

```
pandora-tui/src/
├── main.rs              # Entry point, tokio runtime, event loop
├── app.rs               # App struct, update() logic, mode transitions
├── event.rs             # Event enum (Key, DaemonResponse, WsEvent, ImageLoaded)
├── client.rs            # DaemonClient: HTTP + WS communication
├── ui/
│   ├── mod.rs           # draw() dispatcher based on app.mode
│   ├── browse.rs        # Three-pane browse layout
│   ├── gallery_card.rs  # Single gallery card widget (thumb + metadata)
│   ├── thumb_grid.rs    # Thumbnail grid widget (middle pane)
│   ├── info_panel.rs    # Info panel widget (right pane: cover + metadata)
│   ├── reader.rs        # Image viewer (left: page list, right: full image)
│   ├── search.rs        # Search input + suggestions + category filter
│   ├── downloads.rs     # Download overlay
│   ├── help.rs          # Help overlay
│   └── status_bar.rs    # Bottom status bar
├── state/
│   ├── mod.rs
│   ├── gallery_list.rs  # GalleryListState
│   ├── reader.rs        # ReaderState
│   ├── search.rs        # SearchState
│   └── downloads.rs     # DownloadState
└── models.rs            # API response types (GalleryItem, GalleryDetail, etc.)
```

---

## 5. TUI Layout

### Mode 1: Browse (default)

```
┌─ Gallery List (~35%) ──────────────┬─ Thumbnails (~35%) ──┬─ Info (~30%) ───────┐
│ ┌──────┐ (C89) [Muzin Syoujo...]  │ ┌─────┐ ┌─────┐     │ ┌──────────────┐   │
│ │      │ Completer                 │ │ p.1 │ │ p.2 │     │ │              │   │
│ │ thumb│ ★★★★☆   NON-H       KO  │ └─────┘ └─────┘     │ │    Cover     │   │
│ └──────┘          2016-02-13      │ ┌─────┐ ┌─────┐     │ │              │   │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │ │ p.3 │ │ p.4 │     │ └──────────────┘   │
│ ┌──────┐ [Artist] Another Title   │ └─────┘ └─────┘     │ Title              │
│ │      │ UploaderName              │ ┌─────┐ ┌─────┐     │ Artist: xxx        │
│ │ thumb│ ★★★☆☆   Manga       JP  │ │ p.5 │ │ p.6 │     │ Pages: 20          │
│ └──────┘          2024-01-15      │ └─────┘ └─────┘     │ Rating: ★★★★☆     │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │                     │ Tags:              │
│ ┌──────┐ Third Gallery Title      │                     │  female: maid      │
│ │      │ User3                     │                     │  parody: xxx       │
│ │ thumb│ ★★★★★   Doujin      JP  │                     │                    │
│ └──────┘          2025-12-01      │                     │                    │
├────────────────────────────────────┴─────────────────────┴────────────────────┤
│ [Homepage] j/k:nav l:open /:search d:download         ↓2 downloading  q:quit │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Gallery card format (each ~4 lines):**

```
Line 1-2: ┌──────┐ Title (up to 2 lines, truncate with ...)
          │ thumb│ Uploader
Line 3:   │      │ ★★★★☆   Category       Language
Line 4:   └──────┘          YYYY-MM-DD
```

Alignment rules:
- Thumbnail: fixed width (8 cols), left-aligned
- Title: starts at column 10, wraps to line 2 if needed
- Rating: fixed position after uploader line
- Category: right-padded to fixed width, colored by type
- Language + Date: right-aligned

Category colors (matching exhentai):
- Doujinshi: red
- Manga: orange
- Artist CG: yellow
- Game CG: green
- Western: bright green
- Non-H: blue
- Image Set: purple
- Cosplay: magenta
- Asian Porn: dim
- Misc: gray

### Mode 2: Read (Enter from browse)

```
┌─ Pages (~20%) ───────────┬─ Viewer (~80%) ──────────────────────────────────┐
│ ▶ [01] ┌────┐            │                                                 │
│   [02] │tiny│            │                                                 │
│   [03] │thumb│           │           Full-size Page Image                  │
│        └────┘            │               (kitty protocol)                  │
│   [04] ┌────┐            │                                                 │
│   [05] │tiny│            │                                                 │
│        │thumb│           │                                                 │
│        └────┘            │                                                 │
│   [06]                   │                                                 │
│   [07]                   │                                                 │
├──────────────────────────┴─────────────────────────────────────────────────┤
│ [Gallery: Title...] Page 3/20  j/k:page h:back d:download r:retry          │
└────────────────────────────────────────────────────────────────────────────┘
```

Loading state (uncached image):

```
│                                                 │
│              Loading page 3...                  │
│              ████████░░░░░░░  52% (1.2MB)      │
│                                                 │
```

Error state:

```
│                                                 │
│              Error 401: authentication failed   │
│              Press r to retry                   │
│                                                 │
```

---

## 6. Search & Tag Autocomplete

### Trigger

Press `/` → bottom status bar becomes input line.

### Layout

```
│ ┌─ Suggestions ──────────────┐     │
│ │▶ f:stockings       丝袜    │     │
│ │  f:stockings_only  仅穿丝袜│     │
│ │  f:striped_stockings 条纹丝袜│   │
│ └────────────────────────────┘     │
│ [Doujin✓] [Manga✓] [CG✓] [Game✓] [Western✓] [Non-H✓] [ImageSet✓] [Cosplay✓] [Misc✓]
├────────────────────────────────────┴──────────────────────────────────────┤
│ / stockings█                                           ★min:0  pages:0   │
└──────────────────────────────────────────────────────────────────────────┘
```

### Interaction

| Key | Action |
|-----|--------|
| Any char | Append to input, trigger suggest API (150ms debounce) |
| `Backspace` | Delete char |
| `Tab` / `↓` | Select next suggestion |
| `Shift-Tab` / `↑` | Select prev suggestion |
| `Enter` (suggestion selected) | Insert tag + space, continue input |
| `Enter` (no selection) | Execute search with current input + filters |
| `Ctrl-t` | Toggle category filter bar; `←`/`→` move, `Space` toggle |
| `Ctrl-r` | Cycle min rating: 0→2→3→4→5→0 |
| `Ctrl-p` | Input minimum page count |
| `Esc` | Cancel search, return to normal mode |

### Suggest API Request

```
GET /api/tags/suggest?q={last_incomplete_keyword}&limit=10
```

Keyword extraction: split input by spaces, take the last token that doesn't end with `$"` (completed tag syntax). This matches the reference project's keyword extraction logic.

### Tag Insertion

When user selects a suggestion, insert using exhentai search syntax:

```
Input: "f:maid "         (user typed, then selected f:stockings)
Result: "f:maid f:stockings "   (appended with space)
```

Category filters persist across searches within the session.

---

## 7. Keybinding Map

### Global

| Key | Action |
|-----|--------|
| `q` | Quit TUI (confirm if downloads active) |
| `1`-`6` | Switch page source: 1=Homepage 2=Popular 3=Toplist 4=Watched 5=Favorites 6=Downloaded |
| `/` | Enter search mode |
| `?` | Toggle help overlay |
| `D` | Toggle download status overlay |

### Browse Mode (Gallery List)

| Key | Action |
|-----|--------|
| `j` / `k` | Move cursor down/up (card unit) |
| `l` / `Enter` | Open selected gallery → read mode |
| `h` / `Esc` | No-op (already at top level) |
| `n` / `p` | Next page / prev page (list pagination) |
| `d` | Download selected gallery |
| `f` | Add selected gallery to favorites |
| `r` | Refresh current list |
| `G` | Jump to bottom |
| `g` `g` | Jump to top (double-tap g) |

### Read Mode (Image Viewer)

| Key | Action |
|-----|--------|
| `j` / `l` / `Space` | Next page |
| `k` / `h` | Prev page |
| `Esc` | Back to browse mode |
| `d` | Download current gallery |
| `r` | Retry loading current page |
| `G` | Jump to last page |
| `g` `g` | Jump to first page |
| Number + `Enter` | Jump to page N |

### Search Mode

| Key | Action |
|-----|--------|
| Chars | Input text |
| `Backspace` | Delete char |
| `Tab` / `↓` | Next suggestion |
| `Shift-Tab` / `↑` | Prev suggestion |
| `Enter` (with selection) | Insert tag |
| `Enter` (no selection) | Execute search |
| `Ctrl-t` | Toggle category filter |
| `Ctrl-r` | Cycle min rating |
| `Ctrl-p` | Set min pages |
| `Esc` | Cancel |

---

## 8. Download Integration

Downloads are **not** a separate view. Integration points:

### Status Bar

Bottom-right corner always shows active download count: `↓N downloading`

### Download Overlay (toggle with `D`)

Floating panel over main content:

```
┌─ Downloads ───────────────────────────────────────────────┐
│ [████████░░] 45%  (C89) Gallery Title 1       pages 12/20│
│ [██████████] done [Artist] Gallery Title 2               │
│ [░░░░░░░░░░] queue [Circle] Gallery Title 3              │
│                                                           │
│ d:dismiss  c:cancel selected                              │
└───────────────────────────────────────────────────────────┘
```

### WebSocket Events

TUI connects to `WS /ws` on startup. Events drive download state updates:

- `download_queued` → add task to list
- `download_progress` → update progress bar
- `download_complete` → mark done, flash status bar
- `download_error` → show error indicator
- `download_cancelled` → remove from list

---

## 9. Image Loading Strategy

### Principle

**Never block the UI.** All image I/O in background tasks.

### Gallery List Thumbnails

- When gallery list loads, visible card thumbnails are queued for async fetch
- Fetch via `GET /api/image/proxy?url={thumb_url}`
- Decode with `image` crate in background task
- Send decoded image back via channel
- On receive → store in `image_cache`, trigger redraw
- Before image loads → show placeholder (gray box or spinner char)

### Thumbnail Grid (middle pane)

- When cursor moves to a gallery, queue all its `thumb_urls` for fetch
- Same async pipeline as list thumbnails
- Grid renders available thumbnails, placeholders for pending ones

### Cover Image (right pane)

- Fetched alongside detail when cursor moves
- Same async pipeline

### Full-Size Page (reader mode)

- `GET /api/gallery/{gid}/{token}/page/{page}` with streaming
- Track `Content-Length` vs bytes received → progress bar
- On complete → decode → render via kitty protocol
- Prefetch: daemon auto-prefetches adjacent pages (configurable)

### Image Cache

In-memory LRU cache of decoded images, bounded by count (e.g., 200 entries). Evicts oldest on overflow. Separate from daemon's disk cache.

### Cancellation

When user navigates away from a gallery, cancel pending image requests for that gallery (drop the `tokio::JoinHandle`). Prevents wasted bandwidth and memory.

---

## 10. Daemon Connection

### Startup

1. Read config from `~/.config/pandora/config.toml` → get daemon URL
2. Health check: `GET /api/config` → if fail, show "Daemon not running" error and exit
3. Connect WebSocket: `WS /ws` → background task reads events
4. Fetch initial page (Homepage by default)

### Reconnection

If WebSocket disconnects:
- Status bar shows "⚠ WS disconnected"
- Background task retries every 5s
- REST calls continue working independently

### Error Handling

All daemon errors display in status bar or viewer area. TUI never crashes on network errors.

---

## 11. Non-Goals (v1)

- GIF animation (render first frame only)
- Comment posting/editing
- Gallery rating
- Comment voting
- Favorites management (add only, no move/delete)
- Mouse support
- Config editing from TUI
- Torrent/archive download
- Multiple simultaneous daemon connections
