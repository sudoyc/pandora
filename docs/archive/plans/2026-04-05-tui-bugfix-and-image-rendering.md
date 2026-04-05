# TUI Bugfix & Image Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all identified TUI bugs (serde mismatches, search logic, UI rendering) and integrate ratatui-image for real image display.

**Architecture:** Daemon-side Python fixes restore correct JSON serialization. Rust TUI model fixes enable deserialization. UI fixes improve usability. ratatui-image replaces text placeholders with kitty protocol image rendering. New Library API enables browsing downloaded galleries through daemon.

**Tech Stack:** Python/FastAPI (daemon), Rust/ratatui/ratatui-image (TUI), `unicode-width` crate (text truncation)

**Spec:** `docs/superpowers/specs/2026-04-05-tui-bugfix-and-image-rendering-design.md`

---

## File Structure

### Daemon (Python) — Modified
- `pandora_daemon/routes/gallery.py` — add `thumb_urls` to `_detail_to_dict`
- `pandora_daemon/routes/browse.py` — toplist returns GalleryItem format
- `pandora_daemon/routes/library.py` — **NEW**: library list + file serving
- `pandora_daemon/app.py` — register library router
- `tests/pandora_daemon/test_routes_gallery.py` — update detail test
- `tests/pandora_daemon/test_routes_browse.py` — update toplist test
- `tests/pandora_daemon/test_routes_library.py` — **NEW**: library tests

### TUI (Rust) — Modified
- `pandora-tui/Cargo.toml` — add `unicode-width = "0.2"`
- `pandora-tui/src/models.rs` — fix Comment.score, add serde defaults, category color pairs
- `pandora-tui/src/app.rs` — add `Picker`, image state map
- `pandora-tui/src/main.rs` — WebSocket background task
- `pandora-tui/src/client.rs` — add library client methods
- `pandora-tui/src/state/search.rs` — fix category_bitmask, add suggestion scroll
- `pandora-tui/src/ui/gallery_card.rs` — unicode-width, highlight, color pairs
- `pandora-tui/src/ui/thumb_grid.rs` — ratatui-image rendering
- `pandora-tui/src/ui/info_panel.rs` — ratatui-image cover rendering
- `pandora-tui/src/ui/reader.rs` — ratatui-image page rendering
- `pandora-tui/src/ui/search.rs` — suggestion scroll

---

### Task 1: Daemon — Fix `_detail_to_dict` missing `thumb_urls`

**Files:**
- Modify: `pandora_daemon/routes/gallery.py:62-86`
- Modify: `tests/pandora_daemon/test_routes_gallery.py`

- [ ] **Step 1: Write failing test**

In `tests/pandora_daemon/test_routes_gallery.py`, add a test that verifies `thumb_urls` is present in the gallery detail response:

```python
def test_gallery_detail_includes_thumb_urls(self):
    mock_api = AsyncMock()
    detail = _make_detail()
    detail.thumb_urls = ["https://ex.com/t1.jpg", "https://ex.com/t2.jpg"]
    mock_cache = MagicMock()
    mock_cache.get_gallery.return_value = detail
    app = _make_app(mock_api, mock_cache=mock_cache)
    client = TestClient(app)

    resp = client.get("/api/gallery/123/abc")
    assert resp.status_code == 200
    data = resp.json()
    assert "thumb_urls" in data
    assert data["thumb_urls"] == ["https://ex.com/t1.jpg", "https://ex.com/t2.jpg"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pandora_daemon/test_routes_gallery.py::TestGalleryRoutes::test_gallery_detail_includes_thumb_urls -v`
Expected: FAIL — `thumb_urls` not in response dict

- [ ] **Step 3: Add `thumb_urls` to `_detail_to_dict`**

In `pandora_daemon/routes/gallery.py`, add to `_detail_to_dict()` after line `"preview_pages": d.preview_pages,`:

```python
def _detail_to_dict(d) -> dict:
    return {
        "gid": d.gid,
        "token": d.token,
        "title": d.title,
        "title_jpn": d.title_jpn,
        "category": d.category,
        "uploader": d.uploader,
        "cover_url": d.cover_url,
        "tags": d.tags,
        "pages": d.pages,
        "size": d.size,
        "posted": d.posted,
        "favorite_slot": d.favorite_slot,
        "preview_pages": d.preview_pages,
        "thumb_urls": d.thumb_urls,
        "rating": d.rating,
        "rating_count": d.rating_count,
        "favorite_count": d.favorite_count,
        "torrent_count": d.torrent_count,
        "comments": [_comment_to_dict(c) for c in d.comments],
        "comments_has_more": d.comments_has_more,
        "api_uid": d.api_uid,
        "api_key": d.api_key,
        "url": d.url,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pandora_daemon/test_routes_gallery.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/routes/gallery.py tests/pandora_daemon/test_routes_gallery.py
git commit -m "fix: add thumb_urls to gallery detail API response"
```

---

### Task 2: Rust — Fix Comment.score type and add serde defaults

**Files:**
- Modify: `pandora-tui/src/models.rs`

- [ ] **Step 1: Fix Comment.score from `Option<String>` to `i64`**

In `pandora-tui/src/models.rs`, change the Comment struct:

```rust
#[derive(Debug, Clone, Deserialize)]
pub struct Comment {
    pub id: i64,
    pub user: String,
    pub comment: String,
    pub score: i64,
    pub time: String,
    pub is_uploader: bool,
    pub vote_up_able: bool,
    pub vote_down_able: bool,
    pub vote_up_ed: bool,
    pub vote_down_ed: bool,
    pub editable: bool,
    #[serde(default)]
    pub last_edited: String,
}
```

- [ ] **Step 2: Add `#[serde(default)]` to GalleryDetail fields**

```rust
#[derive(Debug, Clone, Deserialize)]
pub struct GalleryDetail {
    pub gid: String,
    pub token: String,
    pub title: String,
    pub title_jpn: Option<String>,
    pub category: String,
    pub uploader: String,
    pub cover_url: String,
    pub tags: HashMap<String, Vec<String>>,
    pub pages: u32,
    pub size: String,
    pub posted: String,
    pub favorite_slot: Option<i32>,
    #[serde(default)]
    pub preview_pages: u32,
    #[serde(default)]
    pub thumb_urls: Vec<String>,
    #[serde(default)]
    pub rating: f64,
    #[serde(default)]
    pub rating_count: u32,
    #[serde(default)]
    pub favorite_count: u32,
    #[serde(default)]
    pub torrent_count: u32,
    #[serde(default)]
    pub comments: Vec<Comment>,
    #[serde(default)]
    pub comments_has_more: bool,
    #[serde(default)]
    pub api_uid: String,
    #[serde(default)]
    pub api_key: String,
    #[serde(default)]
    pub url: String,
}
```

- [ ] **Step 3: Update test_deserialize_gallery_detail to include comments with int score**

```rust
#[test]
fn test_deserialize_gallery_detail() {
    let json = r#"{
        "gid": "123", "token": "abc", "title": "Test Detail",
        "title_jpn": null, "category": "Doujinshi",
        "uploader": "user1", "cover_url": "https://img.com/c.jpg",
        "tags": {"female": ["maid", "stockings"], "artist": ["someone"]},
        "pages": 30, "size": "50 MB", "posted": "2024-01-01",
        "favorite_slot": null, "preview_pages": 2,
        "thumb_urls": ["https://img.com/t1.jpg"],
        "rating": 4.0, "rating_count": 10,
        "favorite_count": 5, "torrent_count": 1,
        "comments": [
            {"id": 1, "user": "bob", "comment": "nice", "score": 42,
             "time": "2024-01-01", "is_uploader": false,
             "vote_up_able": true, "vote_down_able": true,
             "vote_up_ed": false, "vote_down_ed": false,
             "editable": false, "last_edited": ""}
        ],
        "comments_has_more": false,
        "api_uid": "uid", "api_key": "key",
        "url": "https://exhentai.org/g/123/abc/"
    }"#;
    let detail: GalleryDetail = serde_json::from_str(json).unwrap();
    assert_eq!(detail.pages, 30);
    assert_eq!(detail.tags["female"], vec!["maid", "stockings"]);
    assert_eq!(detail.comments.len(), 1);
    assert_eq!(detail.comments[0].score, 42);
    assert_eq!(detail.thumb_urls.len(), 1);
}
```

- [ ] **Step 4: Run tests**

Run: `cd pandora-tui && cargo test`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd pandora-tui && git add src/models.rs && git commit -m "fix: Comment.score type i64, add serde defaults to GalleryDetail"
```

---

### Task 3: Rust — Fix category color pairs and selected highlight

**Files:**
- Modify: `pandora-tui/src/models.rs` (category_to_color → returns fg+bg)
- Modify: `pandora-tui/src/ui/gallery_card.rs` (highlight + color pairs + unicode-width)
- Modify: `pandora-tui/Cargo.toml` (add unicode-width)

- [ ] **Step 1: Add `unicode-width` to Cargo.toml**

Add to `[dependencies]`:

```toml
unicode-width = "0.2"
```

- [ ] **Step 2: Replace `category_to_color` with `category_colors` returning (fg, bg)**

In `pandora-tui/src/models.rs`:

```rust
/// Category color mapping — returns (foreground, background) for readability.
pub fn category_colors(category: &str) -> (ratatui::style::Color, ratatui::style::Color) {
    use ratatui::style::Color;
    match category.to_lowercase().as_str() {
        "doujinshi" => (Color::White, Color::Red),
        "manga" => (Color::Black, Color::Yellow),
        "artist cg" => (Color::Black, Color::Rgb(200, 150, 0)),
        "game cg" => (Color::Black, Color::Green),
        "western" => (Color::Black, Color::Rgb(140, 200, 60)),
        "non-h" => (Color::White, Color::Blue),
        "image set" => (Color::White, Color::Magenta),
        "cosplay" => (Color::Black, Color::LightMagenta),
        "asian porn" => (Color::White, Color::DarkGray),
        "misc" => (Color::Black, Color::Gray),
        _ => (Color::White, Color::DarkGray),
    }
}
```

- [ ] **Step 3: Update `test_category_color` test**

```rust
#[test]
fn test_category_colors() {
    use ratatui::style::Color;
    let (fg, bg) = category_colors("Doujinshi");
    assert_eq!(fg, Color::White);
    assert_eq!(bg, Color::Red);
    let (fg, bg) = category_colors("Manga");
    assert_eq!(fg, Color::Black);
    assert_eq!(bg, Color::Yellow);
}
```

- [ ] **Step 4: Rewrite `gallery_card.rs` with unicode-width, highlight indicator, and color pairs**

```rust
use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Widget};
use unicode_width::UnicodeWidthStr;

use crate::models::{category_colors, GalleryItem};

/// Height of a single gallery card in rows.
pub const CARD_HEIGHT: u16 = 4;

pub struct GalleryCard<'a> {
    pub item: &'a GalleryItem,
    pub selected: bool,
}

impl<'a> Widget for GalleryCard<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        if area.height < CARD_HEIGHT || area.width < 25 {
            return;
        }

        // Highlight background for selected card
        if self.selected {
            for y in area.y..area.y + area.height.min(CARD_HEIGHT) {
                for x in area.x..area.x + area.width {
                    if let Some(cell) = buf.cell_mut((x, y)) {
                        cell.set_bg(Color::Rgb(50, 50, 80));
                    }
                }
            }
        }

        // Selection indicator
        let indicator_width: u16 = 2;
        if self.selected {
            buf.set_string(
                area.x,
                area.y,
                "▶ ",
                Style::default().fg(Color::Cyan).bold(),
            );
        }

        // Text area (after indicator)
        let text_x = area.x + indicator_width;
        let text_width = area.width.saturating_sub(indicator_width) as usize;
        if text_width < 10 {
            return;
        }

        // Line 1: Title (truncated to display width)
        let title = truncate_to_width(&self.item.title, text_width);
        buf.set_string(text_x, area.y, &title, Style::default().bold());

        // Line 2: Uploader
        let uploader = truncate_to_width(&self.item.uploader, text_width);
        buf.set_string(
            text_x,
            area.y + 1,
            &uploader,
            Style::default().fg(Color::Gray),
        );

        // Line 3: Rating + Category
        let rating_y = area.y + 2;
        if rating_y < area.y + area.height {
            let stars = render_stars(self.item.rating);
            buf.set_string(text_x, rating_y, &stars, Style::default().fg(Color::Yellow));

            let cat_x = text_x + UnicodeWidthStr::width(stars.as_str()) as u16 + 2;
            let (cat_fg, cat_bg) = category_colors(&self.item.category);
            let cat_style = Style::default().fg(cat_fg).bg(cat_bg);
            let cat_label = format!(" {} ", self.item.category);
            if cat_x + cat_label.len() as u16 <= area.x + area.width {
                buf.set_string(cat_x, rating_y, &cat_label, cat_style);
            }
        }

        // Line 4: Date + Pages
        let date_y = area.y + 3;
        if date_y < area.y + area.height {
            let date = if self.item.posted.len() >= 10 {
                &self.item.posted[..10]
            } else {
                &self.item.posted
            };
            buf.set_string(text_x, date_y, date, Style::default().fg(Color::DarkGray));

            let pages_str = format!("{}p", self.item.pages);
            let pages_x = text_x + date.len() as u16 + 2;
            if pages_x + pages_str.len() as u16 <= area.x + area.width {
                buf.set_string(
                    pages_x,
                    date_y,
                    &pages_str,
                    Style::default().fg(Color::DarkGray),
                );
            }
        }
    }
}

fn render_stars(rating: f64) -> String {
    let full = rating.floor() as usize;
    let half = if rating - rating.floor() >= 0.5 { 1 } else { 0 };
    let empty = 5usize.saturating_sub(full + half);
    let mut s = "★".repeat(full);
    if half > 0 {
        s.push('☆');
    }
    s.push_str(&"☆".repeat(empty));
    s
}

/// Truncate string to fit within `max_width` display columns.
fn truncate_to_width(s: &str, max_width: usize) -> String {
    let width = UnicodeWidthStr::width(s);
    if width <= max_width {
        return s.to_string();
    }
    let mut result = String::new();
    let mut current_width = 0;
    let target = max_width.saturating_sub(3); // reserve space for "..."
    for ch in s.chars() {
        let ch_width = unicode_width::UnicodeWidthChar::width(ch).unwrap_or(0);
        if current_width + ch_width > target {
            break;
        }
        result.push(ch);
        current_width += ch_width;
    }
    result.push_str("...");
    result
}
```

- [ ] **Step 5: Run tests**

Run: `cd pandora-tui && cargo test`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd pandora-tui && git add Cargo.toml src/models.rs src/ui/gallery_card.rs
git commit -m "fix: category color pairs, unicode-width truncation, selected highlight indicator"
```

---

### Task 4: Rust — Fix search category bitmask and suggestion scroll

**Files:**
- Modify: `pandora-tui/src/state/search.rs`
- Modify: `pandora-tui/src/ui/search.rs`

- [ ] **Step 1: Fix `category_bitmask()` to return INCLUDE mask**

In `pandora-tui/src/state/search.rs`:

```rust
pub fn category_bitmask(&self) -> Option<u32> {
    if self.excluded_categories == 0 {
        None // no filtering — all included
    } else {
        // Invert excluded → included for daemon API
        Some((!self.excluded_categories) & 1023)
    }
}
```

- [ ] **Step 2: Add `suggestion_scroll` field to SearchState**

Add field to the struct:

```rust
#[derive(Debug, Default)]
pub struct SearchState {
    pub active: bool,
    pub input: String,
    pub cursor_pos: usize,
    pub suggestions: Vec<TagSuggestion>,
    pub selected_suggestion: Option<usize>,
    pub suggestion_scroll: usize,
    pub filter_active: bool,
    pub filter_cursor: usize,
    pub excluded_categories: u32,
    pub min_rating: u32,
    pub min_pages: u32,
}
```

Add method to adjust scroll:

```rust
pub fn adjust_suggestion_scroll(&mut self, visible_count: usize) {
    if let Some(sel) = self.selected_suggestion {
        if sel < self.suggestion_scroll {
            self.suggestion_scroll = sel;
        } else if sel >= self.suggestion_scroll + visible_count {
            self.suggestion_scroll = sel - visible_count + 1;
        }
    }
}
```

Update `reset()` to also clear `suggestion_scroll`:

```rust
pub fn reset(&mut self) {
    self.active = false;
    self.input.clear();
    self.cursor_pos = 0;
    self.suggestions.clear();
    self.selected_suggestion = None;
    self.suggestion_scroll = 0;
    self.filter_active = false;
}
```

- [ ] **Step 3: Update `draw_suggestions` to use scroll offset**

In `pandora-tui/src/ui/search.rs`, replace `draw_suggestions`:

```rust
fn draw_suggestions(frame: &mut Frame, app: &App, area: Rect) {
    frame.render_widget(Clear, area);

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::Cyan));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let visible_count = (inner.height / 2) as usize; // 2 lines per suggestion
    let scroll = app.search.suggestion_scroll;

    for (vi, suggestion) in app
        .search
        .suggestions
        .iter()
        .enumerate()
        .skip(scroll)
        .take(visible_count)
    {
        let row = vi - scroll;
        let y = inner.y + (row as u16) * 2;
        if y + 1 >= inner.y + inner.height {
            break;
        }

        let selected = app.search.selected_suggestion == Some(vi);
        let style = if selected {
            Style::default().fg(Color::Yellow).bold()
        } else {
            Style::default()
        };
        let prefix = if selected { "▶ " } else { "  " };

        let tag_line = format!("{}{}:{}", prefix, suggestion.namespace, suggestion.tag);
        frame.render_widget(
            Paragraph::new(tag_line).style(style),
            Rect::new(inner.x, y, inner.width, 1),
        );

        let trans_line = format!("    {}", suggestion.translation);
        frame.render_widget(
            Paragraph::new(trans_line).fg(Color::Gray),
            Rect::new(inner.x, y + 1, inner.width, 1),
        );
    }
}
```

- [ ] **Step 4: Call `adjust_suggestion_scroll` in main.rs after selection change**

In `handle_key_search` in `main.rs`, after Tab/Down and BackTab/Up blocks that modify `selected_suggestion`, add:

```rust
KeyCode::Tab | KeyCode::Down => {
    let len = app.search.suggestions.len();
    if len > 0 {
        app.search.selected_suggestion = Some(
            app.search
                .selected_suggestion
                .map(|i| (i + 1) % len)
                .unwrap_or(0),
        );
        app.search.adjust_suggestion_scroll(5); // ~5 visible items
    }
}
KeyCode::BackTab | KeyCode::Up => {
    let len = app.search.suggestions.len();
    if len > 0 {
        app.search.selected_suggestion = Some(
            app.search
                .selected_suggestion
                .map(|i| if i == 0 { len - 1 } else { i - 1 })
                .unwrap_or(len - 1),
        );
        app.search.adjust_suggestion_scroll(5);
    }
}
```

- [ ] **Step 5: Update tests**

In `pandora-tui/src/state/search.rs` tests:

```rust
#[test]
fn test_category_bitmask_returns_include_mask() {
    let mut s = SearchState::default();
    // Exclude doujinshi (bit 2)
    s.excluded_categories = 2;
    // Should return INCLUDE mask = all bits except 2 = 1021
    assert_eq!(s.category_bitmask(), Some(1021));
}

#[test]
fn test_category_bitmask_none_when_no_exclusions() {
    let s = SearchState::default();
    assert_eq!(s.category_bitmask(), None);
}

#[test]
fn test_suggestion_scroll() {
    let mut s = SearchState::default();
    s.selected_suggestion = Some(7);
    s.adjust_suggestion_scroll(5);
    assert_eq!(s.suggestion_scroll, 3); // 7 - 5 + 1
}
```

- [ ] **Step 6: Run tests**

Run: `cd pandora-tui && cargo test`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
cd pandora-tui && git add src/state/search.rs src/ui/search.rs src/main.rs
git commit -m "fix: search category bitmask semantics, suggestion scroll"
```

---

### Task 5: Daemon — Toplist returns GalleryItem format

**Files:**
- Modify: `pandora_daemon/routes/browse.py`
- Modify: `tests/pandora_daemon/test_routes_browse.py`

The current toplist parser only returns `TopListItem(type, name, link)`. The link contains gallery URLs. We cannot easily convert these to full `GalleryItem` without fetching each gallery. Instead, we parse the link to extract gid/token and return a minimal GalleryItem with available info.

- [ ] **Step 1: Write failing test**

```python
def test_toplist_returns_gallery_item_format(self):
    """Toplist should return items with GalleryItem-compatible fields."""
    mock_api = AsyncMock()
    from exhentai_api.models.toplist import TopListItem
    mock_api.get_toplist.return_value = [
        TopListItem(type="All-Time", name="Test Gallery", link="https://exhentai.org/g/12345/abcdef0123/"),
    ]
    app = _make_app(mock_api)
    client = TestClient(app)

    resp = client.get("/api/toplist?tl=15")
    data = resp.json()
    assert resp.status_code == 200
    assert len(data) == 1
    item = data[0]
    assert item["gid"] == "12345"
    assert item["token"] == "abcdef0123"
    assert item["title"] == "Test Gallery"
    assert "category" in item
    assert "thumb_url" in item
    assert "url" in item
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pandora_daemon/test_routes_browse.py::TestBrowseRoutes::test_toplist_returns_gallery_item_format -v`
Expected: FAIL

- [ ] **Step 3: Update toplist route to convert TopListItem → GalleryItem dict**

In `pandora_daemon/routes/browse.py`:

```python
import re

def _toplist_to_gallery_item(item) -> dict | None:
    """Convert TopListItem to GalleryItem-compatible dict by parsing link URL."""
    match = re.search(r"/g/(\d+)/([0-9a-f]+)", item.link)
    if not match:
        return None
    gid = match.group(1)
    token = match.group(2)
    return {
        "gid": gid,
        "token": token,
        "title": item.name,
        "category": "",
        "uploader": "",
        "thumb_url": "",
        "posted": "",
        "rating": 0.0,
        "pages": 0,
        "rated": False,
        "thumb_width": 0,
        "thumb_height": 0,
        "url": item.link,
    }
```

Update the toplist route:

```python
@router.get("/toplist")
async def get_toplist(tl: str = "15", api=Depends(get_api)):
    """Return toplist entries as GalleryItem-compatible dicts."""
    items = await api.get_toplist(tl)
    result = []
    for item in items:
        converted = _toplist_to_gallery_item(item)
        if converted:
            result.append(converted)
    return result
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/pandora_daemon/test_routes_browse.py -v`
Expected: ALL PASS (update existing toplist tests if they assert old format)

- [ ] **Step 5: Update existing toplist tests that assert old format**

Replace `test_toplist_returns_correct_fields` to match new format:

```python
def test_toplist_returns_correct_fields(self):
    mock_api = AsyncMock()
    from exhentai_api.models.toplist import TopListItem
    mock_api.get_toplist.return_value = [
        TopListItem(type="All-Time", name="Gallery A", link="https://exhentai.org/g/111/aaa1111111/"),
        TopListItem(type="All-Time", name="Gallery B", link="https://exhentai.org/g/222/bbb2222222/"),
    ]
    app = _make_app(mock_api)
    client = TestClient(app)

    resp = client.get("/api/toplist?tl=15")
    data = resp.json()
    assert len(data) == 2
    assert data[0]["gid"] == "111"
    assert data[0]["title"] == "Gallery A"
    assert data[1]["gid"] == "222"
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest tests/pandora_daemon/test_routes_browse.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add pandora_daemon/routes/browse.py tests/pandora_daemon/test_routes_browse.py
git commit -m "fix: toplist endpoint returns GalleryItem-compatible format"
```

---

### Task 6: Daemon — Library API

**Files:**
- Create: `pandora_daemon/routes/library.py`
- Create: `tests/pandora_daemon/test_routes_library.py`
- Modify: `pandora_daemon/app.py`

- [ ] **Step 1: Write failing tests**

Create `tests/pandora_daemon/test_routes_library.py`:

```python
"""Tests for pandora_daemon.routes.library module."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.library import router
from pandora_daemon.state import AppState


def _make_app(download_path: str):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.config.download.path = download_path
    app.state.pandora = state
    return app


class TestLibraryRoutes:
    def test_library_list_returns_downloaded_galleries(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test Gallery"
        gallery_dir.mkdir()
        metadata = {
            "gid": "12345",
            "token": "abc",
            "title": "Test Gallery",
            "category": "Manga",
            "pages": 10,
        }
        (gallery_dir / "metadata.json").write_text(json.dumps(metadata))

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["gid"] == "12345"
        assert data[0]["title"] == "Test Gallery"

    def test_library_list_empty_when_no_downloads(self, tmp_path):
        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_library_file_serves_cover(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345"}')
        (gallery_dir / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library/12345/file?path=cover")
        assert resp.status_code == 200
        assert b"fake-jpeg" in resp.content

    def test_library_file_serves_page(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345"}')
        pages_dir = gallery_dir / "pages"
        pages_dir.mkdir()
        (pages_dir / "0003.jpg").write_bytes(b"\xff\xd8\xff\xe0page-data")

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library/12345/file?path=page/3")
        assert resp.status_code == 200
        assert b"page-data" in resp.content

    def test_library_file_serves_thumb(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345"}')
        thumbs_dir = gallery_dir / "thumbs"
        thumbs_dir.mkdir()
        (thumbs_dir / "0005.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBPthumb")

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library/12345/file?path=thumb/5")
        assert resp.status_code == 200
        assert b"thumb" in resp.content

    def test_library_file_404_for_missing_gallery(self, tmp_path):
        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library/99999/file?path=cover")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_library.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement library routes**

Create `pandora_daemon/routes/library.py`:

```python
"""Library routes for pandora-daemon.

Provides endpoints for browsing downloaded galleries from the local filesystem.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from pandora_daemon.dependencies import get_config

router = APIRouter(prefix="/api/library", tags=["library"])


def _find_gallery_dir(download_path: Path, gid: str) -> Path | None:
    """Find gallery directory matching {gid}-* pattern."""
    if not download_path.exists():
        return None
    for d in download_path.iterdir():
        if d.is_dir() and d.name.startswith(f"{gid}-"):
            return d
    return None


def _detect_media_type(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:4] == b"GIF8":
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


@router.get("")
async def list_library(config=Depends(get_config)):
    """List all downloaded galleries by scanning download directory."""
    download_path = Path(config.download.path).expanduser()
    if not download_path.exists():
        return []

    galleries = []
    for d in sorted(download_path.iterdir()):
        if not d.is_dir():
            continue
        meta_file = d / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            galleries.append(meta)
        except (json.JSONDecodeError, OSError):
            continue
    return galleries


@router.get("/{gid}/file")
async def get_library_file(
    gid: str,
    path: str = Query(..., description="cover | thumb/{page} | page/{page}"),
    config=Depends(get_config),
):
    """Serve a file from a downloaded gallery."""
    download_path = Path(config.download.path).expanduser()
    gallery_dir = _find_gallery_dir(download_path, gid)
    if gallery_dir is None:
        raise HTTPException(status_code=404, detail=f"Gallery {gid} not found")

    if path == "cover":
        # Find cover.* file
        for ext in ("jpg", "jpeg", "png", "webp", "gif"):
            cover = gallery_dir / f"cover.{ext}"
            if cover.exists():
                data = cover.read_bytes()
                return Response(content=data, media_type=_detect_media_type(data))
        raise HTTPException(status_code=404, detail="Cover not found")

    # thumb/{page} or page/{page}
    match = re.match(r"^(thumb|page)/(\d+)$", path)
    if not match:
        raise HTTPException(status_code=400, detail=f"Invalid path: {path}")

    file_type = match.group(1)
    page_num = int(match.group(2))
    subdir = "thumbs" if file_type == "thumb" else "pages"
    target_dir = gallery_dir / subdir

    if not target_dir.exists():
        raise HTTPException(status_code=404, detail=f"{subdir}/ not found")

    # Find file matching {page_num:04d}.*
    import glob as glob_mod
    pattern = str(target_dir / f"{page_num:04d}.*")
    matches = glob_mod.glob(pattern)
    if not matches:
        raise HTTPException(status_code=404, detail=f"{file_type} {page_num} not found")

    data = Path(matches[0]).read_bytes()
    return Response(content=data, media_type=_detect_media_type(data))
```

- [ ] **Step 4: Register library router in app.py**

In `pandora_daemon/app.py`, add import and include:

```python
from pandora_daemon.routes.library import router as library_router
```

And in the app setup (alongside other router includes):

```python
app.include_router(library_router)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/pandora_daemon/test_routes_library.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run all daemon tests to check for regressions**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add pandora_daemon/routes/library.py tests/pandora_daemon/test_routes_library.py pandora_daemon/app.py
git commit -m "feat: add Library API for browsing downloaded galleries"
```

---

### Task 7: Rust — ratatui-image integration

**Files:**
- Modify: `pandora-tui/src/app.rs` — add Picker, image_states map
- Modify: `pandora-tui/src/main.rs` — init Picker before terminal setup
- Modify: `pandora-tui/src/ui/info_panel.rs` — render cover image
- Modify: `pandora-tui/src/ui/thumb_grid.rs` — render thumbnail images
- Modify: `pandora-tui/src/ui/reader.rs` — render page image

- [ ] **Step 1: Add Picker and image state to App**

In `pandora-tui/src/app.rs`, add imports and fields:

```rust
use std::num::NonZeroUsize;
use std::collections::HashMap;

use image::DynamicImage;
use lru::LruCache;
use ratatui_image::picker::Picker;
use ratatui_image::protocol::StatefulProtocol;
use tokio::sync::mpsc;

use crate::client::DaemonClient;
use crate::event::AppEvent;
use crate::state::*;

// ... AppMode, PageSource unchanged ...

pub struct App {
    pub mode: AppMode,
    pub page_source: PageSource,
    pub gallery_list: GalleryListState,
    pub reader: ReaderState,
    pub search: SearchState,
    pub downloads: DownloadState,

    pub image_cache: LruCache<String, DynamicImage>,
    pub page_image: Option<DynamicImage>,
    pub status_msg: String,
    pub show_help: bool,
    pub should_quit: bool,
    pub pending_g: bool,

    pub client: DaemonClient,
    pub tx: mpsc::UnboundedSender<AppEvent>,

    // ratatui-image
    pub picker: Picker,
    pub image_states: HashMap<String, Box<dyn StatefulProtocol>>,
    pub page_image_state: Option<Box<dyn StatefulProtocol>>,
}

impl App {
    pub fn new(client: DaemonClient, tx: mpsc::UnboundedSender<AppEvent>, picker: Picker) -> Self {
        Self {
            mode: AppMode::Browse,
            page_source: PageSource::Homepage,
            gallery_list: GalleryListState::default(),
            reader: ReaderState::default(),
            search: SearchState::default(),
            downloads: DownloadState::default(),
            image_cache: LruCache::new(NonZeroUsize::new(200).unwrap()),
            page_image: None,
            status_msg: String::new(),
            show_help: false,
            should_quit: false,
            pending_g: false,
            client,
            tx,
            picker,
            image_states: HashMap::new(),
            page_image_state: None,
        }
    }

    /// Get or create a StatefulProtocol for a cached image, keyed by URL.
    pub fn get_image_protocol(&mut self, url: &str) -> Option<&mut Box<dyn StatefulProtocol>> {
        if !self.image_cache.contains(url) {
            return None;
        }
        if !self.image_states.contains_key(url) {
            if let Some(img) = self.image_cache.peek(url) {
                let protocol = self.picker.new_resize_protocol(img.clone());
                self.image_states.insert(url.to_string(), protocol);
            }
        }
        self.image_states.get_mut(url)
    }

    /// Get or create a StatefulProtocol for the current page image.
    pub fn get_page_protocol(&mut self) -> Option<&mut Box<dyn StatefulProtocol>> {
        if self.page_image.is_some() && self.page_image_state.is_none() {
            let img = self.page_image.as_ref().unwrap();
            self.page_image_state = Some(self.picker.new_resize_protocol(img.clone()));
        }
        self.page_image_state.as_mut()
    }

    // ... rest of methods unchanged, except update spawn_fetch, load_current_page, etc.
    // They don't change.
```

- [ ] **Step 2: Initialize Picker in main.rs before terminal setup**

In `pandora-tui/src/main.rs`, before `enable_raw_mode()`:

```rust
use ratatui_image::picker::Picker;

// ... inside main(), after health check:

let mut picker = Picker::from_query_stdio().unwrap_or_else(|_| {
    // Fallback: use halfblocks if terminal query fails
    Picker::new((8, 16))
});
picker.guess_protocol();

let (tx, mut rx) = mpsc::unbounded_channel::<AppEvent>();
let mut app = App::new(client, tx.clone(), picker);
```

- [ ] **Step 3: Update ThumbnailLoaded handler to clear stale protocol**

In `handle_app_event` in `main.rs`:

```rust
AppEvent::ThumbnailLoaded { url, image } => {
    app.image_states.remove(&url); // clear stale protocol
    app.image_cache.put(url, image);
}
AppEvent::PageImageLoaded { page, image } => {
    if page == app.reader.current_page {
        app.page_image = Some(image);
        app.page_image_state = None; // reset protocol for new image
        app.reader.loading = false;
        app.reader.loading_progress = None;
    }
}
```

Also when entering reader mode (in `handle_key_browse`, `KeyCode::Char('l') | KeyCode::Enter`):

```rust
app.page_image = None;
app.page_image_state = None;
```

And when navigating pages (in `handle_key_read`):

```rust
app.page_image = None;
app.page_image_state = None;
```

- [ ] **Step 4: Render cover in info_panel.rs**

```rust
use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui_image::StatefulImage;

use crate::app::App;

pub fn draw_info_panel(frame: &mut Frame, app: &mut App, area: Rect) {
    let block = Block::default()
        .title(" Info ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::DarkGray));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let detail = match &app.gallery_list.detail {
        Some(d) => d,
        None => {
            let text = Paragraph::new("Select a gallery").fg(Color::DarkGray);
            frame.render_widget(text, inner);
            return;
        }
    };

    // Cover image
    let cover_height = inner.height / 3;
    let cover_area = Rect::new(inner.x, inner.y, inner.width, cover_height);
    let cover_url = detail.cover_url.clone();

    // Request cover load if not cached
    if !app.image_cache.contains(&cover_url) {
        app.request_thumbnail(cover_url.clone());
    }

    if let Some(protocol) = app.get_image_protocol(&cover_url) {
        let image_widget = StatefulImage::default();
        frame.render_stateful_widget(image_widget, cover_area, protocol);
    } else {
        let cover_placeholder = Paragraph::new("[Cover]")
            .alignment(Alignment::Center)
            .fg(Color::DarkGray);
        frame.render_widget(cover_placeholder, cover_area);
    }

    // Metadata below cover — clone detail fields before mutable borrow ends
    let title = detail.title.clone();
    let title_jpn = detail.title_jpn.clone();
    let uploader = detail.uploader.clone();
    let pages = detail.pages;
    let size = detail.size.clone();
    let rating = detail.rating;
    let rating_count = detail.rating_count;
    let tags = detail.tags.clone();

    let meta_y = inner.y + cover_height + 1;
    let meta_height = inner.height.saturating_sub(cover_height + 1);
    if meta_height == 0 {
        return;
    }
    let meta_area = Rect::new(inner.x, meta_y, inner.width, meta_height);

    let mut lines: Vec<Line> = Vec::new();
    lines.push(Line::from(Span::styled(&title, Style::default().bold())));
    if let Some(ref jpn) = title_jpn {
        lines.push(Line::from(Span::styled(jpn.as_str(), Style::default().fg(Color::Gray))));
    }
    lines.push(Line::from(""));
    lines.push(Line::from(vec![
        Span::styled("Uploader: ", Style::default().fg(Color::DarkGray)),
        Span::raw(&uploader),
    ]));
    lines.push(Line::from(vec![
        Span::styled("Pages: ", Style::default().fg(Color::DarkGray)),
        Span::raw(format!("{}", pages)),
        Span::raw("  "),
        Span::styled("Size: ", Style::default().fg(Color::DarkGray)),
        Span::raw(&size),
    ]));
    let stars = render_stars(rating);
    lines.push(Line::from(vec![
        Span::styled("Rating: ", Style::default().fg(Color::DarkGray)),
        Span::styled(stars, Style::default().fg(Color::Yellow)),
        Span::raw(format!(" ({})", rating_count)),
    ]));
    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled("Tags:", Style::default().fg(Color::DarkGray))));
    for (namespace, tag_list) in &tags {
        let tag_str = tag_list.join(", ");
        lines.push(Line::from(vec![
            Span::styled(format!("  {}: ", namespace), Style::default().fg(Color::Cyan)),
            Span::raw(tag_str),
        ]));
    }

    let paragraph = Paragraph::new(lines).wrap(Wrap { trim: false });
    frame.render_widget(paragraph, meta_area);
}

fn render_stars(rating: f64) -> String {
    let full = rating.floor() as usize;
    let half = if rating - rating.floor() >= 0.5 { 1 } else { 0 };
    let empty = 5usize.saturating_sub(full + half);
    "★".repeat(full) + if half > 0 { "☆" } else { "" } + &"☆".repeat(empty)
}
```

Note: `draw_info_panel` signature changes from `(frame, detail: Option<&GalleryDetail>, area)` to `(frame, app: &mut App, area)` because we need `app` to access image cache and protocols.

- [ ] **Step 5: Update `browse.rs` call site for new `draw_info_panel` signature**

In `pandora-tui/src/ui/browse.rs`:

```rust
pub fn draw_browse(frame: &mut Frame, app: &mut App, area: Rect) {
    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(35),
            Constraint::Percentage(35),
            Constraint::Percentage(30),
        ])
        .split(area);

    draw_gallery_list(frame, app, chunks[0]);
    thumb_grid::draw_thumb_grid(frame, app, chunks[1]);
    info_panel::draw_info_panel(frame, app, chunks[2]);
}
```

- [ ] **Step 6: Render thumbnails in thumb_grid.rs**

```rust
use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui_image::StatefulImage;

use crate::app::App;

pub fn draw_thumb_grid(frame: &mut Frame, app: &mut App, area: Rect) {
    let block = Block::default()
        .title(" Thumbnails ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::DarkGray));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let detail = match &app.gallery_list.detail {
        Some(d) => d,
        None => {
            let text = Paragraph::new("No gallery selected").fg(Color::DarkGray);
            frame.render_widget(text, inner);
            return;
        }
    };

    if detail.thumb_urls.is_empty() {
        let text = Paragraph::new("No thumbnails").fg(Color::DarkGray);
        frame.render_widget(text, inner);
        return;
    }

    let thumb_w: u16 = 14;
    let thumb_h: u16 = 8;
    let cols = (inner.width / thumb_w).max(1) as usize;
    let rows = (inner.height / thumb_h).max(1) as usize;

    let thumb_urls: Vec<String> = detail.thumb_urls.clone();

    for (idx, url) in thumb_urls.iter().enumerate().take(cols * rows) {
        let col = idx % cols;
        let row = idx / cols;
        let x = inner.x + (col as u16) * thumb_w;
        let y = inner.y + (row as u16) * thumb_h;

        if y + thumb_h > inner.y + inner.height {
            break;
        }

        let cell_area = Rect::new(
            x,
            y,
            thumb_w.min(inner.width.saturating_sub(x - inner.x)),
            thumb_h,
        );

        // Request thumbnail load if not cached
        if !app.image_cache.contains(url) {
            app.request_thumbnail(url.clone());
        }

        // Render image or placeholder
        if let Some(protocol) = app.get_image_protocol(url) {
            let image_widget = StatefulImage::default();
            frame.render_stateful_widget(image_widget, cell_area, protocol);
        } else {
            let label = format!("p.{}", idx + 1);
            let p = Paragraph::new(label)
                .alignment(Alignment::Center)
                .fg(Color::DarkGray);
            frame.render_widget(p, cell_area);
        }
    }
}
```

- [ ] **Step 7: Render page image in reader.rs**

Replace the image display section in `draw_viewer`:

```rust
use ratatui_image::StatefulImage;

// ... inside draw_viewer, replace the placeholder section at the end:

    // Image display
    if app.page_image.is_some() {
        if let Some(protocol) = app.get_page_protocol() {
            let image_widget = StatefulImage::default();
            frame.render_stateful_widget(image_widget, inner, protocol);
        } else {
            let text = Paragraph::new("Preparing image...")
                .alignment(Alignment::Center)
                .fg(Color::DarkGray);
            frame.render_widget(text, inner);
        }
    } else {
        let text = Paragraph::new("No image loaded")
            .alignment(Alignment::Center)
            .fg(Color::DarkGray);
        frame.render_widget(text, inner);
    }
```

Note: `draw_reader` and `draw_viewer` signatures need to take `&mut App` instead of `&App` because we need mutable access to `get_page_protocol()`.

Update `reader.rs` function signatures:

```rust
pub fn draw_reader(frame: &mut Frame, app: &mut App, area: Rect) {
    // ... unchanged layout code ...
    draw_page_list(frame, app, chunks[0]);
    draw_viewer(frame, app, chunks[1]);
}

fn draw_page_list(frame: &mut Frame, app: &App, area: Rect) {
    // unchanged
}

fn draw_viewer(frame: &mut Frame, app: &mut App, area: Rect) {
    // ... with image rendering
}
```

- [ ] **Step 8: Update `ui/mod.rs` draw function for new signatures**

The `draw` function already passes `&mut App`, so no changes needed there. But `draw_reader` now takes `&mut App`, and `draw_browse` already does. Verify compilation.

- [ ] **Step 9: Build and test**

Run: `cd pandora-tui && cargo build`
Expected: Compiles clean

Run: `cd pandora-tui && cargo test`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
cd pandora-tui && git add -A
git commit -m "feat: integrate ratatui-image for cover, thumbnails, and reader rendering"
```

---

### Task 8: Rust — WebSocket background connection

**Files:**
- Modify: `pandora-tui/src/main.rs`

- [ ] **Step 1: Add WebSocket connect task after terminal setup**

In `main.rs`, after `app.load_current_page()` and before the main loop, add:

```rust
// WebSocket background connection
{
    let ws_url = app.client.ws_url();
    let tx_ws = tx.clone();
    tokio::spawn(async move {
        use futures_util::StreamExt;
        use tokio_tungstenite::connect_async;

        loop {
            match connect_async(&ws_url).await {
                Ok((ws_stream, _)) => {
                    let (_, mut read) = ws_stream.split();
                    while let Some(msg) = read.next().await {
                        match msg {
                            Ok(tokio_tungstenite::tungstenite::Message::Text(text)) => {
                                if let Ok(ev) = serde_json::from_str::<WsEvent>(&text) {
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
            // Reconnect after 3 seconds
            tokio::time::sleep(std::time::Duration::from_secs(3)).await;
            let _ = tx_ws.send(AppEvent::WsReconnected);
        }
    });
}
```

Add necessary imports at the top of main.rs:

```rust
use crate::models::WsEvent;
```

- [ ] **Step 2: Build and test**

Run: `cd pandora-tui && cargo build`
Expected: Compiles clean

- [ ] **Step 3: Commit**

```bash
cd pandora-tui && git add src/main.rs
git commit -m "feat: wire WebSocket background connection into TUI main loop"
```

---

### Task 9: Rust — Library client and PageSource::Downloaded

**Files:**
- Modify: `pandora-tui/src/client.rs`
- Modify: `pandora-tui/src/app.rs`
- Modify: `pandora-tui/src/models.rs`

- [ ] **Step 1: Add library client methods**

In `pandora-tui/src/client.rs`:

```rust
pub async fn get_library(&self) -> Result<Vec<DownloadedGalleryMeta>, String> {
    let resp = self.http
        .get(format!("{}/api/library", self.base_url))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    resp.json().await.map_err(|e| e.to_string())
}

pub async fn get_library_file(&self, gid: &str, path: &str) -> Result<Vec<u8>, String> {
    let resp = self.http
        .get(format!(
            "{}/api/library/{}/file?path={}",
            self.base_url,
            gid,
            urlencoding::encode(path)
        ))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }
    let bytes = resp.bytes().await.map_err(|e| e.to_string())?;
    Ok(bytes.to_vec())
}
```

- [ ] **Step 2: Add `#[serde(default)]` to DownloadedGalleryMeta optional fields**

In `pandora-tui/src/models.rs`, update `DownloadedGalleryMeta`:

```rust
#[derive(Debug, Clone, Deserialize)]
pub struct DownloadedGalleryMeta {
    pub gid: String,
    pub token: String,
    pub title: String,
    #[serde(default)]
    pub title_jpn: Option<String>,
    #[serde(default)]
    pub category: String,
    #[serde(default)]
    pub uploader: String,
    #[serde(default)]
    pub tags: HashMap<String, Vec<String>>,
    #[serde(default)]
    pub pages: u32,
    #[serde(default)]
    pub size: String,
    #[serde(default)]
    pub posted: String,
    #[serde(default)]
    pub rating: f64,
    #[serde(default)]
    pub url: String,
    #[serde(default)]
    pub downloaded_at: Option<String>,
}
```

- [ ] **Step 3: Implement PageSource::Downloaded in app.rs load_current_page**

Replace the stub in `load_current_page`:

```rust
PageSource::Downloaded => {
    self.spawn_fetch(|c| async move {
        match c.get_library().await {
            Ok(metas) => {
                let items: Vec<GalleryItem> = metas
                    .into_iter()
                    .map(|m| GalleryItem {
                        gid: m.gid.clone(),
                        token: m.token.clone(),
                        title: m.title,
                        category: m.category,
                        uploader: m.uploader,
                        thumb_url: String::new(),
                        posted: m.posted,
                        rating: m.rating,
                        pages: m.pages,
                        rated: false,
                        thumb_width: 0,
                        thumb_height: 0,
                        url: m.url,
                    })
                    .collect();
                AppEvent::GalleriesLoaded(Ok(items))
            }
            Err(e) => AppEvent::GalleriesLoaded(Err(e)),
        }
    });
}
```

- [ ] **Step 4: Build and test**

Run: `cd pandora-tui && cargo build && cargo test`
Expected: Compiles clean, tests pass

- [ ] **Step 5: Commit**

```bash
cd pandora-tui && git add src/client.rs src/app.rs src/models.rs
git commit -m "feat: library client and PageSource::Downloaded implementation"
```

---

### Task 10: Integration test — manual verification

- [ ] **Step 1: Run all Python tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS (203+ tests)

- [ ] **Step 2: Run all Rust tests**

Run: `cd pandora-tui && cargo test`
Expected: ALL PASS

- [ ] **Step 3: Build release binary**

Run: `cd pandora-tui && cargo build --release`
Expected: Clean build

- [ ] **Step 4: Commit any remaining changes**

```bash
git add -A && git status
```

If there are uncommitted changes, commit them with an appropriate message.
