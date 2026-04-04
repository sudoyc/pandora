# Exhentai API Full Alignment Design Spec

**Date:** 2026-04-04
**Goal:** Fully align `exhentai_api` Python package with the Android reference project's feature set.
**Approach:** Incremental expansion (Method A) — bottom-up layered implementation with TDD.

---

## 1. Scope Overview

### 1.1 Existing (already implemented)
- Gallery list parsing (homepage, search, popular)
- Gallery detail parsing
- Image URL fetching (HTML viewer + API)
- Search with advanced params (`SearchParams`)
- Favorites (get/add/modify/batch)
- TopList parsing
- Async HTTP client with retry + Sad Panda detection

### 1.2 Gaps to fill

| Priority Layer | Module | Description |
|---------------|--------|-------------|
| L1: Model Enhancement | GalleryListItem | Add `rating`, `pages`, `rated`, `thumb_width`, `thumb_height` |
| L1: Model Enhancement | GalleryDetail | Add `rating`, `rating_count`, `favorite_count`, `torrent_count`, `torrent_url`, `archive_url`, `parent_url`, `newer_versions`, `comments`, `comments_has_more`, `api_uid`, `api_key` |
| L2: New Models | GalleryComment | Comment data with vote state and edit ability |
| L2: New Models | TorrentItem | Torrent URL + filename |
| L2: New Models | ArchiverData + ArchiveOption | Archive quality/cost/size options |
| L2: New Models | HomeDetail | Image limits, GP stats, moderation power |
| L2: New Models | ProfileResult | Display name + avatar URL |
| L2: New Models | RateResult | Rating response from API |
| L2: New Models | VoteCommentResult | Comment vote response from API |
| L3: Parser Enhancement | gallery.py | Extract rating (CSS sprite), pages, thumb dimensions |
| L3: Parser Enhancement | gallery_detail.py | Extract api_uid/api_key, torrent/archive info, comments, rating/fav counts, parent, newer versions |
| L3: New Parsers | comments.py | Parse comment list from detail page |
| L3: New Parsers | torrent.py | Parse torrent list popup |
| L3: New Parsers | archive.py | Parse archive options page |
| L3: New Parsers | home.py | Parse home.php page |
| L3: New Parsers | profile.py | Parse profile page |
| L3: New Parsers | mytags.py | Parse mytags page |
| L3: Parser Enhancement | favorites.py | Support keyword search params |
| L4: New API Methods | comment_gallery | Post/edit comments |
| L4: New API Methods | vote_comment | Vote on comments via api.php JSON |
| L4: New API Methods | rate_gallery | Rate gallery via api.php JSON |
| L4: New API Methods | get_torrent_list | Fetch torrent list |
| L4: New API Methods | get_archive_list | Fetch archive options |
| L4: New API Methods | download_archive | Get archive download URL |
| L4: New API Methods | get_mytags | Fetch user's tag list |
| L4: New API Methods | add_tag / delete_tag | Manage user tags |
| L4: New API Methods | get_watched | Fetch watched galleries |
| L4: New API Methods | get_home_detail | Fetch home page info |
| L4: New API Methods | get_profile | Fetch user profile |
| L4: New API Methods | reset_image_limit | Reset image viewing limit |
| L4: New API Methods | get_gallery_token | Get page-specific token via api.php |
| L4: New API Methods | image_search | Search by image |
| L4: API Enhancement | get_favorites | Add keyword, sn, st, sf params |

---

## 2. Detailed Model Definitions

### 2.1 GalleryListItem Enhancements

Add to existing `models/gallery.py`:

```python
@dataclass
class GalleryListItem:
    gid: str
    token: str
    title: str
    category: str
    uploader: str
    thumb_url: str
    posted: str
    # NEW fields:
    rating: float = 0.0          # Star rating 0-5, calculated from CSS sprite
    pages: int = 0               # Page count
    rated: bool = False          # Whether current user has rated (via .irr/.irg/.irb class)
    thumb_width: int = 0         # Thumbnail width from style attribute
    thumb_height: int = 0        # Thumbnail height from style attribute
```

### 2.2 GalleryDetail Enhancements

Add to existing `models/gallery.py`:

```python
@dataclass
class GalleryDetail:
    # ... existing fields ...
    # NEW fields:
    rating: float = 0.0
    rating_count: int = 0
    favorite_count: int = 0
    torrent_count: int = 0
    torrent_url: str = ""
    archive_url: str = ""
    parent_url: Optional[str] = None
    newer_versions: List[dict] = field(default_factory=list)  # [{gid, token, title, posted}]
    comments: List['GalleryComment'] = field(default_factory=list)
    comments_has_more: bool = False
    api_uid: str = ""            # Extracted from page JS: apiuid = NNNN
    api_key: str = ""            # Extracted from page JS: apikey = "xxx"
```

### 2.3 GalleryComment (NEW: models/comment.py)

```python
@dataclass
class GalleryComment:
    id: int                      # Comment ID (from c[N] div id)
    score: int = 0               # Aggregated comment score
    user: str = ""               # Comment author
    comment: str = ""            # Comment body (HTML content)
    time: str = ""               # Posted timestamp string
    is_uploader: bool = False    # Whether author is the gallery uploader
    vote_up_able: bool = False   # Can vote up
    vote_down_able: bool = False # Can vote down
    vote_up_ed: bool = False     # Already voted up
    vote_down_ed: bool = False   # Already voted down
    editable: bool = False       # Can edit this comment
    last_edited: str = ""        # Last edit timestamp (empty if never edited)
```

### 2.4 TorrentItem (NEW: models/torrent.py)

```python
@dataclass
class TorrentItem:
    url: str       # Full torrent download URL
    name: str      # Torrent filename / display name
```

### 2.5 ArchiverData (NEW: models/archive.py)

```python
@dataclass
class ArchiveOption:
    cost: str        # e.g. "Free!", "20 GP", "350 Credits"
    size: str        # e.g. "123 MB"
    url: str = ""    # Download URL (populated after selection)

@dataclass
class ArchiverData:
    original: Optional[ArchiveOption] = None
    resample: Optional[ArchiveOption] = None
    funds: str = ""  # Current user funds, e.g. "1,234 GP / 5,678 Credits"
```

### 2.6 HomeDetail (NEW: models/home.py)

```python
@dataclass
class HomeDetail:
    image_used: int = 0           # Current image viewing count
    image_total: int = 0          # Image viewing limit
    reset_cost: int = 0           # GP cost to reset limit
    gp_from_gallery: int = 0      # GP gained from gallery visits
    gp_from_torrent: int = 0      # GP gained from torrent completions
    gp_from_archive: int = 0      # GP gained from archive downloads
    gp_from_hath: int = 0         # GP gained from Hentai@Home
    moderation_power: int = 0     # Current moderation power
```

### 2.7 ProfileResult (NEW: models/profile.py)

```python
@dataclass
class ProfileResult:
    display_name: str = ""
    avatar_url: str = ""
```

### 2.8 Vote/Rate Results (NEW: models/vote.py)

```python
@dataclass
class RateResult:
    rating: float = 0.0       # New average rating
    rating_count: int = 0     # Total rating count

@dataclass
class VoteCommentResult:
    comment_id: int = 0       # The comment that was voted on
    comment_score: int = 0    # New aggregate score
    comment_vote: int = 0     # User's current vote state (-1, 0, 1)
```

---

## 3. Parser Specifications

### 3.1 Gallery List Parser Enhancement (parsers/gallery.py)

**Rating calculation from CSS sprite:**
- Element class: `.ir`, `.irr` (red/rated), `.irg` (green), `.irb` (blue)
- CSS `background-position: -Xpx -Ypx`
- Rating formula: `5 - (x / 16) - (y == -21 ? 0.5 : 0)`
  - x offset: each 16px step = 1 full star reduction
  - y = -1px: full star; y = -21px: half star deducted
- If class contains `irr`, `irg`, or `irb` → `rated = True`

**Pages extraction:**
- From gallery list row, find text containing pattern like `123 pages` or `1 page`
- Located in uploader/info column

**Thumbnail dimensions:**
- Parse `style` attribute of thumbnail container for `height:Npx` and `width:Npx`

### 3.2 Gallery Detail Parser Enhancement (parsers/gallery_detail.py)

**api_uid / api_key extraction:**
- Find `<script>` tag containing `var apiuid` and `var apikey`
- Regex: `apiuid\s*=\s*(\d+)` and `apikey\s*=\s*"([a-f0-9]+)"`

**torrent_count / torrent_url:**
- Find element `#gd5` or link containing `gallerytorrents.php`
- Parse count from link text: `Torrent Download (N)`

**archive_url:**
- Find link containing `archiver.php`

**rating / rating_count:**
- `#rating_label`: text like "Average: 4.65" → parse float
- `#rating_count`: text like "123 times" → parse int

**favorite_count:**
- From `#favcount` or `#gdd` table row containing "Favorited"

**parent_url:**
- From `#gdd` table, row labeled "Parent:" → extract `<a href>`

**newer_versions:**
- From `#gnd` div, parse `<a>` tags as `{gid, token, title, posted}`

**Comments integration:**
- Call `parse_comments()` on the same HTML
- Store result in `comments` and `comments_has_more` fields

### 3.3 Comments Parser (NEW: parsers/comments.py)

**Function:** `parse_comments(html: str) -> tuple[list[GalleryComment], bool]`

**DOM structure:**
- Comments are in `#cdiv` container
- Each comment: `<div class="c1" id="comment_N">`
- Score: `<span id="comment_score_N">`
- User: `<a>` inside `.c3`
- Time: text in `.c3` before user link, pattern like "Posted on DD Month YYYY, HH:MM"
- Body: `.c6` div content (HTML)
- Vote buttons: `.c4` links with specific onclick handlers
- Edit link: `.c8` if present
- "has more" flag: presence of link "click to show all" or similar pagination

### 3.4 Torrent Parser (NEW: parsers/torrent.py)

**Function:** `parse_torrent_list(html: str) -> list[TorrentItem]`

**DOM structure (popup page):**
- Torrent entries in `<table>` rows
- Each row has an `<a>` with `href` pointing to `.torrent` file
- The link text is the torrent name

### 3.5 Archive Parser (NEW: parsers/archive.py)

**Function:** `parse_archive_list(html: str) -> ArchiverData`

**DOM structure:**
- Contains two main sections: "Original Archive" and "Resample Archive"
- Each section shows cost and file size
- Current funds displayed at top

### 3.6 Home Parser (NEW: parsers/home.py)

**Function:** `parse_home_detail(html: str) -> HomeDetail`

**Data extraction (from reference EhHomeParser.java):**
- Image limit: regex `You are currently at (\d+) towards a limit of (\d+)`
- Reset cost: regex `reset_cost.*?(\d+)`
- GP stats table: parse individual rows for gallery visits, torrent completions, etc.
- Moderation power: regex pattern from overview table

### 3.7 Profile Parser (NEW: parsers/profile.py)

**Function:** `parse_profile(html: str) -> ProfileResult`

**Data extraction (from reference ProfileParser.java):**
- Display name: from profile info section, typically in a heading or bold element
- Avatar URL: `<img>` in profile avatar section

### 3.8 MyTags Parser (NEW: parsers/mytags.py)

**Function:** `parse_mytags(html: str) -> list[WatchedTag]`

**DOM structure (from reference MyTagLitParser.java):**
- Container: `#usertags_outer`
- For each tag entry:
  - `#tagpreview[id]` → `title` attribute = tag name
  - `#tagwatch[id]` → `checked` attribute = watched status
  - `#taghide[id]` → `checked` attribute = hidden status
  - `#tagcolor[id]` → `placeholder` attribute = color
  - `#tagweight[id]` → `value` attribute = weight

Uses existing `WatchedTag` model from `models/tags.py`.

---

## 4. API Method Specifications

### 4.1 Comment Gallery

```python
async def comment_gallery(
    self, gid: str, token: str,
    comment: str, edit_id: Optional[int] = None
) -> list[GalleryComment]:
```
- **Method:** POST form to gallery detail URL `{BASE_URL}/g/{gid}/{token}/`
- **Payload:** `comment_text={comment}` (new) or `comment_text={comment}&edit_comment={edit_id}` (edit)
- **Parse:** Response HTML → `parse_comments()`

### 4.2 Vote Comment

```python
async def vote_comment(
    self, api_uid: str, api_key: str,
    gid: int, token: str,
    comment_id: int, vote: int  # -1 or 1
) -> VoteCommentResult:
```
- **Method:** POST JSON to `{BASE_URL}/api.php`
- **Payload:** `{"method": "votecomment", "apiuid": api_uid, "apikey": api_key, "gid": gid, "token": token, "comment_id": comment_id, "comment_vote": vote}`
- **Parse:** JSON response → `VoteCommentResult`

### 4.3 Rate Gallery

```python
async def rate_gallery(
    self, api_uid: str, api_key: str,
    gid: int, token: str,
    rating: int  # 2-10 (half-stars: 2=1star, 3=1.5stars, ..., 10=5stars)
) -> RateResult:
```
- **Method:** POST JSON to `{BASE_URL}/api.php`
- **Payload:** `{"method": "rategallery", "apiuid": api_uid, "apikey": api_key, "gid": gid, "token": token, "rating": rating}`
- **Parse:** JSON response → `RateResult`

### 4.4 Torrent List

```python
async def get_torrent_list(self, gid: str, token: str) -> list[TorrentItem]:
```
- **Method:** GET `{BASE_URL}/gallerytorrents.php?gid={gid}&t={token}`
- **Parse:** HTML → `parse_torrent_list()`

### 4.5 Archive List

```python
async def get_archive_list(self, gid: str, token: str) -> ArchiverData:
```
- **Method:** GET `{BASE_URL}/archiver.php?gid={gid}&token={token}`
- **Parse:** HTML → `parse_archive_list()`

### 4.6 Download Archive

```python
async def download_archive(self, archive_url: str, resolution: str = "org") -> str:
```
- **Method:** POST form to `archive_url`
- **Payload:** `dltype={resolution}&dlcheck=Download+Archive`
- **Returns:** Download URL string extracted from response

### 4.7 MyTags

```python
async def get_mytags(self) -> list[WatchedTag]:
```
- **Method:** GET `{BASE_URL}/mytags`
- **Parse:** HTML → `parse_mytags()`

```python
async def add_tag(
    self, tag_name: str,
    watched: bool = False, hidden: bool = False,
    color: str = "", weight: int = 10
) -> list[WatchedTag]:
```
- **Method:** POST form to `{BASE_URL}/mytags`
- **Payload:** `tagname_new={tag_name}&tagwatch_new={1|0}&taghide_new={1|0}&tagcolor_new={color}&tagweight_new={weight}&usertags_action=add`
- **Parse:** Response HTML → `parse_mytags()`

```python
async def delete_tag(self, tag_id: int) -> list[WatchedTag]:
```
- **Method:** POST form to `{BASE_URL}/mytags`
- **Payload:** `modify_usertags[]={tag_id}&usertags_action=mass`
- **Parse:** Response HTML → `parse_mytags()`

### 4.8 Watched

```python
async def get_watched(self, page: int = 0) -> list[GalleryListItem]:
```
- **Method:** GET `{BASE_URL}/watched?page={page}`
- **Parse:** HTML → `parse_gallery_list()` (reuses existing parser)

### 4.9 Home / Profile

```python
async def get_home_detail(self) -> HomeDetail:
```
- **Method:** GET `{BASE_URL}/home.php`
- **Parse:** HTML → `parse_home_detail()`

```python
async def get_profile(self) -> ProfileResult:
```
- **Method:** GET forums URL → parse profile link → GET profile page
- **Parse:** HTML → `parse_profile()`

```python
async def reset_image_limit(self) -> HomeDetail:
```
- **Method:** POST form to `{BASE_URL}/home.php`
- **Payload:** `reset_imagelimit=Reset+Limit`
- **Parse:** Response HTML → `parse_home_detail()`

### 4.10 Gallery Token API

```python
async def get_gallery_token(self, gid: int, page: int) -> str:
```
- **Method:** POST JSON to `{BASE_URL}/api.php`
- **Payload:** `{"method": "gtoken", "pagelist": [[gid, "imgkey_placeholder", page]]}`
- **Returns:** Token string from JSON response

### 4.11 Image Search

```python
async def image_search(self, image_path: str) -> list[GalleryListItem]:
```
- **Method:** POST multipart form to `{BASE_URL}/`
- **Payload:** `f_shash` (image SHA hash), `fs_similar=1`, `fs_covers=1`, `fs_exp=1`
- **Parse:** Response HTML → `parse_gallery_list()`

### 4.12 Favorites Enhancement

```python
async def get_favorites(
    self, favcat: int = -1, page: int = 0,
    # NEW params:
    keyword: str = "",
    sn: bool = False,    # search name
    st: bool = False,    # search tags
    sf: bool = False,    # search note
) -> FavoritesResponse:
```
- Adds `f_search`, `sn=on`, `st=on`, `sf=on` query params when provided

---

## 5. models/__init__.py Export Updates

All new models must be added to `models/__init__.py`:
```python
from .comment import GalleryComment
from .torrent import TorrentItem
from .archive import ArchiveOption, ArchiverData
from .home import HomeDetail
from .profile import ProfileResult
from .vote import RateResult, VoteCommentResult
```

And to `exhentai_api/__init__.py` top-level exports as appropriate.

---

## 6. Error Handling

No new exception classes. Use existing patterns:
- Network errors → retry with backoff (existing client behavior)
- Sad Panda → immediate raise (existing behavior)
- Parse failures → return default/empty values with logging

---

## 7. Testing Strategy

Every layer uses TDD (test-first):
- **Model tests:** Verify field defaults, dataclass construction
- **Parser tests:** Use fixture HTML files, verify all extracted fields
- **API tests:** Mock `client.get_html`/`post_json`/`post_form`, verify correct URL construction and response handling

Test fixture HTML will be minimal but representative snippets, based on real page structure from the CLAUDE.md reference documentation and the Java parser implementations.

---

## 8. Implementation Order (Bottom-Up)

1. **L1:** Enhance `GalleryListItem` + update `parse_gallery_list()` + tests
2. **L1:** Enhance `GalleryDetail` + update `parse_gallery_detail()` + tests
3. **L2:** New models: `GalleryComment`, `TorrentItem`, `ArchiverData`, `HomeDetail`, `ProfileResult`, `RateResult`, `VoteCommentResult` + tests
4. **L3:** New parsers: `comments.py`, `torrent.py`, `archive.py`, `home.py`, `profile.py`, `mytags.py` + tests
5. **L4:** New API methods in `api.py` + tests
6. **L4:** Enhance `get_favorites()` with keyword search + tests
7. **Final:** Update `models/__init__.py` and `exhentai_api/__init__.py` exports
