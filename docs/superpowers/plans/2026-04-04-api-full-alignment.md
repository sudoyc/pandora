# Exhentai API Full Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fully align the `exhentai_api` Python package with the Android reference project's feature set — adding comments, rating, torrents, archives, MyTags, watched, home, profile, image search, and enhancing existing models/parsers with missing fields.

**Architecture:** Bottom-up incremental expansion across 4 layers: L1 (enhance existing models + parsers), L2 (new data models), L3 (new parsers), L4 (new API methods). Each layer is independently testable via TDD.

**Tech Stack:** Python 3.12+, httpx (async HTTP), BeautifulSoup4 (HTML parsing), dataclasses, pytest + pytest-asyncio. Run all commands with `uv run`.

---

## File Structure

### Files to Modify
- `exhentai_api/models/gallery.py` — Add rating/pages/rated/thumb dimensions to GalleryListItem; add rating/comments/torrent/archive fields to GalleryDetail
- `exhentai_api/models/__init__.py` — Export new models
- `exhentai_api/__init__.py` — Export new models at top level
- `exhentai_api/parsers/gallery.py` — Extract rating from CSS sprite, pages, thumb dimensions
- `exhentai_api/parsers/gallery_detail.py` — Extract api_uid/api_key, torrent/archive info, comments, rating/fav counts
- `exhentai_api/parsers/favorites.py` — Support keyword search params (no parser change, only API change)
- `exhentai_api/api.py` — Add all new API methods
- `tests/exhentai_api/data/gallery_list.html` — Add rating/pages/thumb data to fixture
- `tests/exhentai_api/data/gallery_detail.html` — Add comments/torrent/archive/rating data to fixture
- `tests/exhentai_api/test_parser_gallery.py` — Add rating/pages/thumb assertions
- `tests/exhentai_api/test_parser_gallery_detail.py` — Add new field assertions

### Files to Create
- `exhentai_api/models/comment.py` — GalleryComment dataclass
- `exhentai_api/models/torrent.py` — TorrentItem dataclass
- `exhentai_api/models/archive.py` — ArchiveOption + ArchiverData dataclasses
- `exhentai_api/models/home.py` — HomeDetail dataclass
- `exhentai_api/models/profile.py` — ProfileResult dataclass
- `exhentai_api/models/vote.py` — RateResult + VoteCommentResult dataclasses
- `exhentai_api/parsers/comments.py` — parse_comments()
- `exhentai_api/parsers/torrent.py` — parse_torrent_list()
- `exhentai_api/parsers/archive.py` — parse_archive_list()
- `exhentai_api/parsers/home.py` — parse_home_detail()
- `exhentai_api/parsers/profile.py` — parse_profile()
- `exhentai_api/parsers/mytags.py` — parse_mytags()
- `tests/exhentai_api/test_models_new.py` — Tests for all new models
- `tests/exhentai_api/test_parser_comments.py` — Tests for comment parser
- `tests/exhentai_api/test_parser_torrent.py` — Tests for torrent parser
- `tests/exhentai_api/test_parser_archive.py` — Tests for archive parser
- `tests/exhentai_api/test_parser_home.py` — Tests for home parser
- `tests/exhentai_api/test_parser_profile.py` — Tests for profile parser
- `tests/exhentai_api/test_parser_mytags.py` — Tests for mytags parser
- `tests/exhentai_api/test_api_new.py` — Tests for all new API methods
- `tests/exhentai_api/data/comments.html` — Comment section fixture
- `tests/exhentai_api/data/torrent_list.html` — Torrent list fixture
- `tests/exhentai_api/data/archive_list.html` — Archive page fixture
- `tests/exhentai_api/data/home.html` — Home page fixture
- `tests/exhentai_api/data/profile.html` — Profile page fixture
- `tests/exhentai_api/data/mytags.html` — MyTags page fixture

---

## Task 1: Enhance GalleryListItem Model + Parser

**Files:**
- Modify: `exhentai_api/models/gallery.py:5-17`
- Modify: `exhentai_api/parsers/gallery.py:1-60`
- Modify: `tests/exhentai_api/data/gallery_list.html`
- Modify: `tests/exhentai_api/test_parser_gallery.py`

- [ ] **Step 1: Update the test fixture HTML to include rating/pages/thumb data**

Replace `tests/exhentai_api/data/gallery_list.html` with:

```html
<table class="itg">
  <tr>
    <td class="gl3c"><a href="https://exhentai.org/g/12345/abcdef1234/"><div class="glname">Test Title</div></a></td>
    <td class="gl1c"><div class="cn">Manga</div></td>
    <td class="glhide"><a href="#">uploader_name</a></td>
    <td class="gl2c"><div class="glthumb" style="height:200px;width:150px"><img data-src="http://thumb.jpg" /></div></td>
    <td class="gl4c"><div>2023-01-01 12:00</div><div>123 pages</div></td>
    <td class="gl3e"><div class="ir irr" style="background-position:-16px -1px"></div></td>
  </tr>
  <tr>
    <td class="gl3c"><a href="https://exhentai.org/g/67890/abcdef5678/"><div class="glname">Another Title</div></a></td>
    <td class="gl1c"><div class="cn">Doujinshi</div></td>
    <td class="glhide"><a href="#">another_uploader</a></td>
    <td class="gl2c"><div class="gl1e"><img src="http://thumb2.jpg" /></div></td>
    <td class="gl4c"><div id="posted_67890">2023-01-02 14:30</div><div>45 pages</div></td>
    <td class="gl3e"><div class="ir" style="background-position:0px -21px"></div></td>
  </tr>
  <tr>
    <td class="gl3c"><a href="https://exhentai.org/g/11111/abcdef1111/"><div class="glname">Missing Data Title</div></a></td>
    <td class="gl1c"><div class="cn">Non-H</div></td>
    <td class="glhide"></td>
    <td class="gl2c"><div>No Image Here</div></td>
    <td class="gl4c"><div>No Date Here</div></td>
    <td class="gl3e"></td>
  </tr>
  <tr>
    <td class="gl3c"><a><div class="glname">Missing Href Title</div></a></td>
    <td class="gl1c"><div class="cn">Image Set</div></td>
    <td class="glhide"></td>
    <td class="gl2c"><div></div></td>
    <td class="gl4c"><div></div></td>
  </tr>
  <tr>
    <td class="gl3c"><a href="https://exhentai.org/g/22222/abcdef2222/"><div class="glname">Missing Title Element</div></a></td>
    <td class="gl1c"><div class="cn">Cosplay</div></td>
    <td class="glhide"></td>
    <td class="gl2c"><div></div></td>
    <td class="gl4c"><div></div></td>
  </tr>
</table>
```

- [ ] **Step 2: Write failing tests for the new fields**

Add to `tests/exhentai_api/test_parser_gallery.py`:

```python
def test_parse_gallery_list_rating_and_pages():
    with open("tests/exhentai_api/data/gallery_list.html", "r") as f:
        html = f.read()

    items = parse_gallery_list(html)

    # Item 1: irr class with background-position:-16px -1px → rating=4.0, rated=True
    assert items[0].rating == 4.0
    assert items[0].rated is True
    assert items[0].pages == 123
    assert items[0].thumb_width == 150
    assert items[0].thumb_height == 200

    # Item 2: ir class with background-position:0px -21px → rating=4.5, rated=False
    assert items[1].rating == 4.5
    assert items[1].rated is False
    assert items[1].pages == 45

    # Item 3: No rating element → defaults
    assert items[2].rating == 0.0
    assert items[2].rated is False
    assert items[2].pages == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/exhentai_api/test_parser_gallery.py::test_parse_gallery_list_rating_and_pages -v`
Expected: FAIL — `GalleryListItem` has no `rating` attribute

- [ ] **Step 4: Add new fields to GalleryListItem model**

In `exhentai_api/models/gallery.py`, update the `GalleryListItem` class:

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
    rating: float = 0.0
    pages: int = 0
    rated: bool = False
    thumb_width: int = 0
    thumb_height: int = 0

    @property
    def url(self) -> str:
        return f"{BASE_URL}/g/{self.gid}/{self.token}/"
```

- [ ] **Step 5: Update gallery list parser to extract new fields**

In `exhentai_api/parsers/gallery.py`, add rating/pages/thumb extraction. The full updated file:

```python
import re
from bs4 import BeautifulSoup
from exhentai_api.models.gallery import GalleryListItem
from exhentai_api.utils import extract_gallery_token

PATTERN_RATING = re.compile(r"(\d+)px")

def _parse_rating(style: str) -> float:
    """Parse star rating from CSS sprite background-position.
    Formula: rating = 5 - (x / 16), if y == 21 subtract 0.5 more."""
    nums = PATTERN_RATING.findall(style)
    if len(nums) < 2:
        return 0.0
    x, y = int(nums[0]), int(nums[1])
    rating = 5.0 - (x / 16.0)
    if y == 21:
        rating -= 0.5
    return max(0.0, rating)

def parse_gallery_list(html: str) -> list[GalleryListItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    itg = soup.find(class_="itg")
    if not itg:
        return []

    for row in itg.find_all("tr"):
        title_elem = row.find(class_="glname")
        if not title_elem:
            continue

        title = title_elem.get_text(strip=True)
        link_elem = row.find("td", class_="gl3c")
        if not link_elem:
            continue
        link_elem = link_elem.find("a")
        if not link_elem or not link_elem.get("href"):
            continue
        gid, token = extract_gallery_token(link_elem["href"])

        cat_elem = row.find(class_=lambda x: x in ["cn", "cs"])
        category = cat_elem.get_text(strip=True) if cat_elem else ""

        uploader_elem = row.find("td", class_=["glhide", "gl4c"])
        uploader = uploader_elem.get_text(strip=True) if uploader_elem else ""

        thumb_url = ""
        thumb_width = 0
        thumb_height = 0
        thumb_elem = row.find(class_=["glthumb", "gl1e", "gl3t"])
        if thumb_elem:
            img = thumb_elem.find("img")
            if img:
                thumb_url = img.get("data-src") or img.get("src") or ""
            style = thumb_elem.get("style", "")
            w_match = re.search(r"width:\s*(\d+)px", style)
            h_match = re.search(r"height:\s*(\d+)px", style)
            if w_match:
                thumb_width = int(w_match.group(1))
            if h_match:
                thumb_height = int(h_match.group(1))

        posted = ""
        posted_elem = row.find(id=re.compile(r"^posted_"))
        if posted_elem:
            posted = posted_elem.get_text(strip=True)
        else:
            date_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", row.get_text())
            if date_match:
                posted = date_match.group(0)

        # Parse pages from text like "123 pages"
        pages = 0
        pages_match = re.search(r"(\d+)\s+page", row.get_text())
        if pages_match:
            pages = int(pages_match.group(1))

        # Parse rating from .ir CSS sprite
        rating = 0.0
        rated = False
        ir_elem = row.find(class_=re.compile(r"^ir"))
        if ir_elem:
            ir_style = ir_elem.get("style", "")
            rating = _parse_rating(ir_style)
            ir_classes = ir_elem.get("class", [])
            rated = any(c in ir_classes for c in ["irr", "irg", "irb"])

        items.append(GalleryListItem(
            gid=gid,
            token=token,
            title=title,
            category=category,
            uploader=uploader,
            thumb_url=thumb_url,
            posted=posted,
            rating=rating,
            pages=pages,
            rated=rated,
            thumb_width=thumb_width,
            thumb_height=thumb_height,
        ))

    return items
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/exhentai_api/test_parser_gallery.py -v`
Expected: ALL PASS (both old and new tests)

- [ ] **Step 7: Commit**

```bash
cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace
git add exhentai_api/models/gallery.py exhentai_api/parsers/gallery.py tests/exhentai_api/test_parser_gallery.py tests/exhentai_api/data/gallery_list.html
git commit -m "feat(api): add rating, pages, thumb dimensions to GalleryListItem"
```

---

## Task 2: New Data Models (L2)

**Files:**
- Create: `exhentai_api/models/comment.py`
- Create: `exhentai_api/models/torrent.py`
- Create: `exhentai_api/models/archive.py`
- Create: `exhentai_api/models/home.py`
- Create: `exhentai_api/models/profile.py`
- Create: `exhentai_api/models/vote.py`
- Modify: `exhentai_api/models/__init__.py`
- Create: `tests/exhentai_api/test_models_new.py`

- [ ] **Step 1: Write failing tests for all new models**

Create `tests/exhentai_api/test_models_new.py`:

```python
from exhentai_api.models.comment import GalleryComment
from exhentai_api.models.torrent import TorrentItem
from exhentai_api.models.archive import ArchiveOption, ArchiverData
from exhentai_api.models.home import HomeDetail
from exhentai_api.models.profile import ProfileResult
from exhentai_api.models.vote import RateResult, VoteCommentResult


def test_gallery_comment_defaults():
    c = GalleryComment(id=123)
    assert c.id == 123
    assert c.score == 0
    assert c.user == ""
    assert c.comment == ""
    assert c.time == ""
    assert c.is_uploader is False
    assert c.vote_up_able is False
    assert c.vote_down_able is False
    assert c.vote_up_ed is False
    assert c.vote_down_ed is False
    assert c.editable is False
    assert c.last_edited == ""


def test_gallery_comment_full():
    c = GalleryComment(
        id=456, score=-5, user="alice", comment="<p>Great!</p>",
        time="14 December 2023, 15:30", is_uploader=True,
        vote_up_able=True, vote_down_able=True,
        vote_up_ed=True, vote_down_ed=False,
        editable=True, last_edited="15 December 2023, 10:00"
    )
    assert c.id == 456
    assert c.score == -5
    assert c.is_uploader is True
    assert c.editable is True


def test_torrent_item():
    t = TorrentItem(url="https://example.com/t.torrent", name="gallery.torrent")
    assert t.url == "https://example.com/t.torrent"
    assert t.name == "gallery.torrent"


def test_archive_option():
    opt = ArchiveOption(cost="Free!", size="123 MB")
    assert opt.cost == "Free!"
    assert opt.size == "123 MB"
    assert opt.url == ""


def test_archiver_data_defaults():
    a = ArchiverData()
    assert a.original is None
    assert a.resample is None
    assert a.funds == ""


def test_archiver_data_full():
    a = ArchiverData(
        original=ArchiveOption(cost="20 GP", size="200 MB", url="https://a.com/dl"),
        resample=ArchiveOption(cost="10 GP", size="100 MB"),
        funds="1,234 GP / 5,678 Credits"
    )
    assert a.original.cost == "20 GP"
    assert a.resample.size == "100 MB"
    assert a.funds == "1,234 GP / 5,678 Credits"


def test_home_detail_defaults():
    h = HomeDetail()
    assert h.image_used == 0
    assert h.image_total == 0
    assert h.reset_cost == 0
    assert h.gp_from_gallery == 0
    assert h.gp_from_torrent == 0
    assert h.gp_from_archive == 0
    assert h.gp_from_hath == 0
    assert h.moderation_power == 0


def test_profile_result_defaults():
    p = ProfileResult()
    assert p.display_name == ""
    assert p.avatar_url == ""


def test_rate_result():
    r = RateResult(rating=4.5, rating_count=123)
    assert r.rating == 4.5
    assert r.rating_count == 123


def test_vote_comment_result():
    v = VoteCommentResult(comment_id=99, comment_score=-3, comment_vote=1)
    assert v.comment_id == 99
    assert v.comment_score == -3
    assert v.comment_vote == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/exhentai_api/test_models_new.py -v`
Expected: FAIL — ModuleNotFoundError for `exhentai_api.models.comment`

- [ ] **Step 3: Create all new model files**

Create `exhentai_api/models/comment.py`:

```python
from dataclasses import dataclass


@dataclass
class GalleryComment:
    id: int
    score: int = 0
    user: str = ""
    comment: str = ""
    time: str = ""
    is_uploader: bool = False
    vote_up_able: bool = False
    vote_down_able: bool = False
    vote_up_ed: bool = False
    vote_down_ed: bool = False
    editable: bool = False
    last_edited: str = ""
```

Create `exhentai_api/models/torrent.py`:

```python
from dataclasses import dataclass


@dataclass
class TorrentItem:
    url: str
    name: str
```

Create `exhentai_api/models/archive.py`:

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class ArchiveOption:
    cost: str
    size: str
    url: str = ""


@dataclass
class ArchiverData:
    original: Optional[ArchiveOption] = None
    resample: Optional[ArchiveOption] = None
    funds: str = ""
```

Create `exhentai_api/models/home.py`:

```python
from dataclasses import dataclass


@dataclass
class HomeDetail:
    image_used: int = 0
    image_total: int = 0
    reset_cost: int = 0
    gp_from_gallery: int = 0
    gp_from_torrent: int = 0
    gp_from_archive: int = 0
    gp_from_hath: int = 0
    moderation_power: int = 0
```

Create `exhentai_api/models/profile.py`:

```python
from dataclasses import dataclass


@dataclass
class ProfileResult:
    display_name: str = ""
    avatar_url: str = ""
```

Create `exhentai_api/models/vote.py`:

```python
from dataclasses import dataclass


@dataclass
class RateResult:
    rating: float = 0.0
    rating_count: int = 0


@dataclass
class VoteCommentResult:
    comment_id: int = 0
    comment_score: int = 0
    comment_vote: int = 0
```

- [ ] **Step 4: Update models/__init__.py to export all new models**

Replace `exhentai_api/models/__init__.py` with:

```python
from .gallery import GalleryListItem, GalleryDetail
from .tags import Tag, WatchedTag
from .image import ImageDetail
from .search import SearchParams
from .favorites import FavoriteCategory, FavoritesResponse
from .toplist import TopListItem
from .comment import GalleryComment
from .torrent import TorrentItem
from .archive import ArchiveOption, ArchiverData
from .home import HomeDetail
from .profile import ProfileResult
from .vote import RateResult, VoteCommentResult

__all__ = [
    "GalleryListItem",
    "GalleryDetail",
    "Tag",
    "WatchedTag",
    "ImageDetail",
    "SearchParams",
    "FavoriteCategory",
    "FavoritesResponse",
    "TopListItem",
    "GalleryComment",
    "TorrentItem",
    "ArchiveOption",
    "ArchiverData",
    "HomeDetail",
    "ProfileResult",
    "RateResult",
    "VoteCommentResult",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/exhentai_api/test_models_new.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace
git add exhentai_api/models/comment.py exhentai_api/models/torrent.py exhentai_api/models/archive.py exhentai_api/models/home.py exhentai_api/models/profile.py exhentai_api/models/vote.py exhentai_api/models/__init__.py tests/exhentai_api/test_models_new.py
git commit -m "feat(models): add GalleryComment, TorrentItem, ArchiverData, HomeDetail, ProfileResult, vote models"
```

---

## Task 3: Enhance GalleryDetail Model + Parser

**Files:**
- Modify: `exhentai_api/models/gallery.py:19-39`
- Modify: `exhentai_api/parsers/gallery_detail.py`
- Modify: `tests/exhentai_api/data/gallery_detail.html`
- Modify: `tests/exhentai_api/test_parser_gallery_detail.py`

- [ ] **Step 1: Update the detail fixture HTML with new data**

Replace `tests/exhentai_api/data/gallery_detail.html` with:

```html
<html>
<body>
    <div class="gm">
        <h1 id="gn">Test Gallery Title</h1>
        <h1 id="gj">Test Gallery Title JPN</h1>
        <div id="gdc"><div class="cn">Manga</div></div>
        <div id="gdn"><a href="">UploaderName</a></div>
        <div id="gd1"><div style="width:250px; height:356px; background:transparent url(https://example.com/cover.jpg) 0 0 no-repeat"></div></div>
        <div id="gdf"><div><a id="favoritelink">Favorite Name</a></div></div>
        <table id="taglist">
            <tr>
                <td class="tc">parody:</td>
                <td><div class="gt"><a href="">tag1</a></div><div class="gt"><a href="">tag2</a></div></td>
            </tr>
        </table>
        <table id="gdd">
            <tr><td class="gdt1">Posted:</td><td class="gdt2">2023-01-01 12:00</td></tr>
            <tr><td class="gdt1">File Size:</td><td class="gdt2">100 MB</td></tr>
            <tr><td class="gdt1">Length:</td><td class="gdt2">20 pages</td></tr>
            <tr><td class="gdt1">Favorited:</td><td class="gdt2">42 times</td></tr>
        </table>
        <div id="gd5">
            <p class="g2 gsp"><img /><a href="https://exhentai.org/gallerytorrents.php?gid=12345&t=abcdef1234" onclick="">Torrent Download (3)</a></p>
            <p class="g2"><img /><a href="https://exhentai.org/archiver.php?gid=12345&token=abcdef1234&or=abc123" onclick="">Archive Download</a></p>
        </div>
        <div id="rating_label">Average: 4.65</div>
        <div id="rating_count">150 times</div>
        <div id="gnd">
            <a href="https://exhentai.org/g/99999/fedcba9876/">New Version Title</a> 2023-06-15 10:00
        </div>
    </div>
    <script type="text/javascript">
        var apiuid = 12345;
        var apikey = "abcdef0123456789";
    </script>
    <div id="cdiv">
        <div id="chd"><p>All 5 comments</p></div>
        <a name="c100"></a>
        <div class="c1">
            <div class="c3">Posted on 14 December 2023, 15:30 by: <a href="">TestUser</a></div>
            <div class="c4"><a style="" onclick="">Vote+</a><a style="color:blue" onclick="">Vote-</a></div>
            <div class="c5"><span>+10</span></div>
            <div class="c6">Great gallery!</div>
            <div class="c7"></div>
        </div>
        <a name="c200"></a>
        <div class="c1">
            <div class="c3">Posted on 15 December 2023, 08:00 by: <a href="">Uploader</a></div>
            <div class="c4"><a onclick="">Edit</a></div>
            <div class="c5"><span>Uploader Comment</span></div>
            <div class="c6">Thanks for the feedback!</div>
            <div class="c7"></div>
            <div class="c8"><a>Last edited on 15 December 2023, 09:00</a></div>
        </div>
    </div>
    <table class="ptt">
        <tr>
            <td class="ptds"><a>1</a></td>
            <td><a>2</a></td>
            <td><a>3</a></td>
            <td><a>&gt;</a></td>
        </tr>
    </table>
</body>
</html>
```

- [ ] **Step 2: Write failing tests for new GalleryDetail fields**

Update `tests/exhentai_api/test_parser_gallery_detail.py`:

```python
from pathlib import Path
from exhentai_api.parsers.gallery_detail import parse_gallery_detail


def test_parse_gallery_detail():
    html_path = Path(__file__).parent / "data" / "gallery_detail.html"
    html = html_path.read_text()

    detail = parse_gallery_detail(html, "12345", "abcdef1234")

    # Existing assertions
    assert detail.gid == "12345"
    assert detail.token == "abcdef1234"
    assert detail.title == "Test Gallery Title"
    assert detail.title_jpn == "Test Gallery Title JPN"
    assert detail.category == "Manga"
    assert detail.uploader == "UploaderName"
    assert detail.cover_url == "https://example.com/cover.jpg"
    assert detail.tags == {"parody": ["tag1", "tag2"]}
    assert detail.pages == 20
    assert detail.size == "100 MB"
    assert detail.posted == "2023-01-01 12:00"
    assert detail.favorite_slot == 0
    assert detail.preview_pages == 3

    # NEW assertions
    assert detail.rating == 4.65
    assert detail.favorite_count == 42
    assert detail.torrent_count == 3
    assert "gallerytorrents.php" in detail.torrent_url
    assert "archiver.php" in detail.archive_url
    assert detail.api_uid == "12345"
    assert detail.api_key == "abcdef0123456789"

    # Comments
    assert len(detail.comments) == 2
    assert detail.comments[0].id == 100
    assert detail.comments[0].user == "TestUser"
    assert detail.comments[0].comment == "Great gallery!"
    assert detail.comments[0].vote_up_able is True
    assert detail.comments[0].vote_down_ed is True
    assert detail.comments[1].user == "Uploader"
    assert detail.comments[1].editable is True
    assert detail.comments[1].last_edited != ""
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/exhentai_api/test_parser_gallery_detail.py -v`
Expected: FAIL — `GalleryDetail` has no `rating` attribute

- [ ] **Step 4: Update GalleryDetail model with new fields**

In `exhentai_api/models/gallery.py`, update the `GalleryDetail` class. Add import for `GalleryComment` and the new fields:

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from exhentai_api.constants import BASE_URL


@dataclass
class GalleryListItem:
    gid: str
    token: str
    title: str
    category: str
    uploader: str
    thumb_url: str
    posted: str
    rating: float = 0.0
    pages: int = 0
    rated: bool = False
    thumb_width: int = 0
    thumb_height: int = 0

    @property
    def url(self) -> str:
        return f"{BASE_URL}/g/{self.gid}/{self.token}/"


@dataclass
class GalleryDetail:
    gid: str
    token: str
    title: str
    title_jpn: Optional[str]
    category: str
    uploader: str
    cover_url: str
    tags: Dict[str, List[str]]
    pages: int
    size: str
    posted: str
    favorite_slot: Optional[int]
    preview_pages: int = 1
    preview_urls: List[str] = field(default_factory=list)
    rating: float = 0.0
    rating_count: int = 0
    favorite_count: int = 0
    torrent_count: int = 0
    torrent_url: str = ""
    archive_url: str = ""
    parent_url: Optional[str] = None
    newer_versions: List[dict] = field(default_factory=list)
    comments: list = field(default_factory=list)
    comments_has_more: bool = False
    api_uid: str = ""
    api_key: str = ""

    @property
    def url(self) -> str:
        return f"{BASE_URL}/g/{self.gid}/{self.token}/"
```

- [ ] **Step 5: Create the comments parser**

Create `exhentai_api/parsers/comments.py`:

```python
import re
from bs4 import BeautifulSoup, Tag
from exhentai_api.models.comment import GalleryComment


def parse_comments(html: str) -> tuple[list[GalleryComment], bool]:
    """Parse comments from gallery detail page HTML.
    Returns (comments_list, has_more)."""
    soup = BeautifulSoup(html, "html.parser")
    cdiv = soup.find(id="cdiv")
    if not cdiv:
        return [], False

    comments = []
    c1_elements = cdiv.find_all(class_="c1")

    for c1 in c1_elements:
        comment = _parse_single_comment(c1)
        if comment:
            comments.append(comment)

    has_more = False
    chd = cdiv.find(id="chd")
    if chd:
        text = chd.get_text()
        if "click to show all" in text.lower() or "all" in text.lower():
            has_more = len(comments) > 0

    return comments, has_more


def _parse_single_comment(element: Tag) -> GalleryComment | None:
    """Parse a single comment from a .c1 div element."""
    # Extract comment ID from previous sibling <a name="cNNN">
    comment_id = 0
    prev = element.find_previous_sibling("a")
    if prev and prev.get("name", "").startswith("c"):
        try:
            comment_id = int(prev["name"][1:])
        except (ValueError, IndexError):
            pass

    # Score from .c5
    score = 0
    c5 = element.find(class_="c5")
    if c5:
        score_text = c5.get_text(strip=True)
        score_match = re.search(r"([+-]?\d+)", score_text)
        if score_match:
            score = int(score_match.group(1))

    # User and time from .c3
    user = ""
    time_str = ""
    c3 = element.find(class_="c3")
    if c3:
        user_link = c3.find("a")
        if user_link:
            user = user_link.get_text(strip=True)
        c3_text = c3.get_text(strip=True) if not c3.string else c3.string.strip()
        # Extract from "Posted on DD MMMMM YYYY, HH:MM by: Username"
        own_texts = []
        for child in c3.children:
            if isinstance(child, str):
                own_texts.append(child.strip())
        own_text = " ".join(own_texts)
        time_match = re.search(r"Posted on (.+?)(?:\s+by:|\s*$)", own_text)
        if time_match:
            time_str = time_match.group(1).strip()

    # Comment body from .c6
    comment_body = ""
    c6 = element.find(class_="c6")
    if c6:
        comment_body = c6.decode_contents().strip()

    # Vote/edit buttons from .c4
    vote_up_able = False
    vote_down_able = False
    vote_up_ed = False
    vote_down_ed = False
    editable = False
    c4 = element.find(class_="c4")
    if c4:
        for child in c4.find_all("a"):
            text = child.get_text(strip=True)
            if text == "Vote+":
                vote_up_able = True
                style = child.get("style", "").strip()
                vote_up_ed = style != ""
            elif text == "Vote-":
                vote_down_able = True
                style = child.get("style", "").strip()
                vote_down_ed = style != ""
            elif text == "Edit":
                editable = True

    # Last edited from .c8
    last_edited = ""
    c8 = element.find(class_="c8")
    if c8 and c8.find("a"):
        last_edited = c8.find("a").get_text(strip=True)

    return GalleryComment(
        id=comment_id,
        score=score,
        user=user,
        comment=comment_body,
        time=time_str,
        vote_up_able=vote_up_able,
        vote_down_able=vote_down_able,
        vote_up_ed=vote_up_ed,
        vote_down_ed=vote_down_ed,
        editable=editable,
        last_edited=last_edited,
    )
```

- [ ] **Step 6: Update gallery detail parser to extract all new fields**

Replace `exhentai_api/parsers/gallery_detail.py` with:

```python
import re
from bs4 import BeautifulSoup
from exhentai_api.models.gallery import GalleryDetail
from exhentai_api.parsers.comments import parse_comments


def parse_gallery_detail(html: str, gid: str, token: str) -> GalleryDetail:
    soup = BeautifulSoup(html, "html.parser")

    gn = soup.find(id="gn")
    title = gn.get_text(strip=True) if gn else ""

    gj = soup.find(id="gj")
    title_jpn = gj.get_text(strip=True) if gj else None

    gdc = soup.find(id="gdc")
    category = gdc.get_text(strip=True) if gdc else ""

    gdn = soup.find(id="gdn")
    uploader = gdn.get_text(strip=True) if gdn else ""

    gd1 = soup.find(id="gd1")
    cover_url = ""
    if gd1 and gd1.find("div"):
        style = gd1.find("div").get("style", "")
        match = re.search(r"url\((.+?)\)", style)
        if match:
            cover_url = match.group(1)

    tags = {}
    taglist = soup.find(id="taglist")
    if taglist:
        for tr in taglist.find_all("tr"):
            tc = tr.find(class_="tc")
            if tc:
                namespace = tc.get_text(strip=True).replace(":", "")
                tag_vals = [t.get_text(strip=True) for t in tr.find_all(class_="gt")]
                tags[namespace] = tag_vals

    pages = 0
    size = ""
    posted = ""
    favorite_count = 0
    gdd = soup.find(id="gdd")
    if gdd:
        for tr in gdd.find_all("tr"):
            gdt1 = tr.find(class_="gdt1")
            gdt2 = tr.find(class_="gdt2")
            if gdt1 and gdt2:
                label = gdt1.get_text(strip=True)
                val = gdt2.get_text(strip=True)
                if label == "Posted:":
                    posted = val
                elif label == "File Size:":
                    size = val
                elif label == "Length:":
                    match = re.search(r"(\d+)", val.replace(",", ""))
                    if match:
                        pages = int(match.group(1))
                elif label == "Favorited:":
                    fav_match = re.search(r"(\d+)", val.replace(",", ""))
                    if fav_match:
                        favorite_count = int(fav_match.group(1))

    gdf = soup.find(id="gdf")
    favorite_slot = None
    if gdf:
        fav_text = gdf.get_text(strip=True)
        if fav_text and fav_text != "Add to Favorites":
            favorite_slot = 0

    preview_pages = 1
    ptt = soup.find("table", class_="ptt")
    if ptt:
        tds = ptt.find_all("td")
        if len(tds) > 2:
            try:
                preview_pages = int(tds[-2].get_text(strip=True))
            except ValueError:
                pass

    preview_urls = []
    for gdt in soup.find_all(class_=["gdtm", "gdtl"]):
        a_tag = gdt.find("a")
        if a_tag and a_tag.get("href"):
            preview_urls.append(a_tag.get("href"))
    if not preview_urls:
        gdt = soup.find(id="gdt")
        if gdt:
            for a_tag in gdt.find_all("a"):
                if a_tag and a_tag.get("href") and "/s/" in a_tag.get("href"):
                    preview_urls.append(a_tag.get("href"))

    # Rating from #rating_label
    rating = 0.0
    rating_label = soup.find(id="rating_label")
    if rating_label:
        rating_text = rating_label.get_text(strip=True)
        rating_match = re.search(r"([\d.]+)", rating_text)
        if rating_match:
            rating = float(rating_match.group(1))

    # Rating count
    rating_count = 0
    rating_count_elem = soup.find(id="rating_count")
    if rating_count_elem:
        rc_match = re.search(r"(\d+)", rating_count_elem.get_text().replace(",", ""))
        if rc_match:
            rating_count = int(rc_match.group(1))

    # Torrent info from #gd5
    torrent_count = 0
    torrent_url = ""
    archive_url = ""
    gd5 = soup.find(id="gd5")
    if gd5:
        for a_tag in gd5.find_all("a"):
            href = a_tag.get("href", "")
            text = a_tag.get_text(strip=True)
            if "gallerytorrents" in href:
                torrent_url = href
                tc_match = re.search(r"\((\d+)\)", text)
                if tc_match:
                    torrent_count = int(tc_match.group(1))
            elif "archiver" in href:
                archive_url = href

    # api_uid and api_key from <script>
    api_uid = ""
    api_key = ""
    for script in soup.find_all("script"):
        script_text = script.string or ""
        uid_match = re.search(r"apiuid\s*=\s*(\d+)", script_text)
        key_match = re.search(r'apikey\s*=\s*"([a-f0-9]+)"', script_text)
        if uid_match:
            api_uid = uid_match.group(1)
        if key_match:
            api_key = key_match.group(1)

    # Newer versions from #gnd
    newer_versions = []
    gnd = soup.find(id="gnd")
    if gnd:
        for a_tag in gnd.find_all("a"):
            href = a_tag.get("href", "")
            nv_match = re.search(r"/g/(\d+)/([0-9a-f]{10})/", href)
            if nv_match:
                newer_versions.append({
                    "gid": nv_match.group(1),
                    "token": nv_match.group(2),
                    "title": a_tag.get_text(strip=True),
                    "url": href,
                })

    # Parent URL from gdd (if exists)
    parent_url = None
    if gdd:
        for tr in gdd.find_all("tr"):
            gdt1 = tr.find(class_="gdt1")
            if gdt1 and "Parent:" in gdt1.get_text():
                gdt2 = tr.find(class_="gdt2")
                if gdt2:
                    parent_link = gdt2.find("a")
                    if parent_link:
                        parent_url = parent_link.get("href")

    # Comments
    comments, comments_has_more = parse_comments(html)

    return GalleryDetail(
        gid=gid,
        token=token,
        title=title,
        title_jpn=title_jpn,
        category=category,
        uploader=uploader,
        cover_url=cover_url,
        tags=tags,
        pages=pages,
        size=size,
        posted=posted,
        favorite_slot=favorite_slot,
        preview_pages=preview_pages,
        preview_urls=preview_urls,
        rating=rating,
        rating_count=rating_count,
        favorite_count=favorite_count,
        torrent_count=torrent_count,
        torrent_url=torrent_url,
        archive_url=archive_url,
        parent_url=parent_url,
        newer_versions=newer_versions,
        comments=comments,
        comments_has_more=comments_has_more,
        api_uid=api_uid,
        api_key=api_key,
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/exhentai_api/test_parser_gallery_detail.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace
git add exhentai_api/models/gallery.py exhentai_api/parsers/gallery_detail.py exhentai_api/parsers/comments.py tests/exhentai_api/test_parser_gallery_detail.py tests/exhentai_api/data/gallery_detail.html
git commit -m "feat(api): enhance GalleryDetail with rating, comments, torrent, archive fields"
```

---

## Task 4: New Parsers — Torrent, Archive, Home, Profile, MyTags

**Files:**
- Create: `exhentai_api/parsers/torrent.py`
- Create: `exhentai_api/parsers/archive.py`
- Create: `exhentai_api/parsers/home.py`
- Create: `exhentai_api/parsers/profile.py`
- Create: `exhentai_api/parsers/mytags.py`
- Create: `tests/exhentai_api/test_parser_torrent.py`
- Create: `tests/exhentai_api/test_parser_archive.py`
- Create: `tests/exhentai_api/test_parser_home.py`
- Create: `tests/exhentai_api/test_parser_profile.py`
- Create: `tests/exhentai_api/test_parser_mytags.py`
- Create: `tests/exhentai_api/data/torrent_list.html`
- Create: `tests/exhentai_api/data/archive_list.html`
- Create: `tests/exhentai_api/data/home.html`
- Create: `tests/exhentai_api/data/profile.html`
- Create: `tests/exhentai_api/data/mytags.html`

- [ ] **Step 1: Create all test fixture HTML files**

Create `tests/exhentai_api/data/torrent_list.html`:

```html
<html><body>
<table>
<tr><td colspan="5"> &nbsp; <a href="https://exhentai.org/torrent/12345/aaa.torrent?p=xxx">Gallery Pack v1.torrent</a></td></tr>
<tr><td colspan="5"> &nbsp; <a href="https://exhentai.org/torrent/12345/bbb.torrent?p=yyy">[Author] Gallery Name.torrent</a></td></tr>
</table>
</body></html>
```

Create `tests/exhentai_api/data/archive_list.html`:

```html
<html><body>
<div>
<p>Current funds: <strong>1,234 GP</strong> / <strong>5,678 Credits</strong></p>
<table>
<tr>
<td><strong>Original</strong></td>
<td>Cost: 20 GP or 200 Credits</td>
<td>Size: 200 MB</td>
</tr>
<tr>
<td><strong>Resample</strong></td>
<td>Cost: 10 GP or 100 Credits</td>
<td>Size: 100 MB</td>
</tr>
</table>
</div>
</body></html>
```

Create `tests/exhentai_api/data/home.html`:

```html
<html><body>
<div class="homebox">First box</div>
<div class="homebox">Second box</div>
<div class="homebox">
<p>You are currently at <strong>5,000</strong> towards a limit of <strong>25,000</strong>.</p>
<p>Reset Cost: <strong>100</strong> GP</p>
<table><tbody>
<tr><td>10,000</td><td>Gallery Visits</td></tr>
<tr><td>5,000</td><td>Torrent Completions</td></tr>
<tr><td>2,000</td><td>Archive Downloads</td></tr>
<tr><td>1,000</td><td>Hentai@Home</td></tr>
</tbody></table>
</div>
<div class="homebox">Fourth box</div>
<div class="homebox">
<table><tbody><tr><td><table><tr><td><td>500</td></td></tr></table></td></tr></tbody></table>
</div>
</body></html>
```

Create `tests/exhentai_api/data/profile.html`:

```html
<html><body>
<div id="profilename"><span>TestDisplayUser</span></div>
<div>spacer</div>
<div><img src="https://forums.e-hentai.org/uploads/avatar_12345.jpg" /></div>
</body></html>
```

Create `tests/exhentai_api/data/mytags.html`:

```html
<html><body>
<div id="usertags_outer">
<div>Header row (skipped)</div>
<div id="utag_100">
    <div id="tagpreview100" title="artist:testartist">artist:testartist</div>
    <input id="tagwatch100" type="checkbox" checked="checked" />
    <input id="taghide100" type="checkbox" />
    <input id="tagcolor100" type="text" placeholder="#ff0000" />
    <input id="tagweight100" type="text" value="10" />
</div>
<div id="utag_200">
    <div id="tagpreview200" title="parody:testparody">parody:testparody</div>
    <input id="tagwatch200" type="checkbox" />
    <input id="taghide200" type="checkbox" checked="checked" />
    <input id="tagcolor200" type="text" placeholder="" />
    <input id="tagweight200" type="text" value="5" />
</div>
</div>
</body></html>
```

- [ ] **Step 2: Write failing tests for all new parsers**

Create `tests/exhentai_api/test_parser_torrent.py`:

```python
from pathlib import Path
from exhentai_api.parsers.torrent import parse_torrent_list


def test_parse_torrent_list():
    html = (Path(__file__).parent / "data" / "torrent_list.html").read_text()
    items = parse_torrent_list(html)

    assert len(items) == 2
    assert items[0].name == "Gallery Pack v1.torrent"
    # URL should have ?p= param stripped
    assert "?p=" not in items[0].url
    assert "aaa.torrent" in items[0].url
    assert items[1].name == "[Author] Gallery Name.torrent"


def test_parse_torrent_list_empty():
    items = parse_torrent_list("<html><body></body></html>")
    assert items == []
```

Create `tests/exhentai_api/test_parser_archive.py`:

```python
from pathlib import Path
from exhentai_api.parsers.archive import parse_archive_list


def test_parse_archive_list():
    html = (Path(__file__).parent / "data" / "archive_list.html").read_text()
    data = parse_archive_list(html)

    assert "1,234 GP" in data.funds
    assert data.original is not None
    assert "20 GP" in data.original.cost
    assert "200 MB" in data.original.size
    assert data.resample is not None
    assert "10 GP" in data.resample.cost
    assert "100 MB" in data.resample.size


def test_parse_archive_list_empty():
    data = parse_archive_list("<html><body></body></html>")
    assert data.original is None
    assert data.resample is None
```

Create `tests/exhentai_api/test_parser_home.py`:

```python
from pathlib import Path
from exhentai_api.parsers.home import parse_home_detail


def test_parse_home_detail():
    html = (Path(__file__).parent / "data" / "home.html").read_text()
    detail = parse_home_detail(html)

    assert detail.image_used == 5000
    assert detail.image_total == 25000
    assert detail.reset_cost == 100
    assert detail.gp_from_gallery == 10000
    assert detail.gp_from_torrent == 5000
    assert detail.gp_from_archive == 2000
    assert detail.gp_from_hath == 1000


def test_parse_home_detail_empty():
    detail = parse_home_detail("<html><body></body></html>")
    assert detail.image_used == 0
    assert detail.image_total == 0
```

Create `tests/exhentai_api/test_parser_profile.py`:

```python
from pathlib import Path
from exhentai_api.parsers.profile import parse_profile


def test_parse_profile():
    html = (Path(__file__).parent / "data" / "profile.html").read_text()
    result = parse_profile(html)

    assert result.display_name == "TestDisplayUser"
    assert "avatar_12345" in result.avatar_url


def test_parse_profile_empty():
    result = parse_profile("<html><body></body></html>")
    assert result.display_name == ""
    assert result.avatar_url == ""
```

Create `tests/exhentai_api/test_parser_mytags.py`:

```python
from pathlib import Path
from exhentai_api.parsers.mytags import parse_mytags


def test_parse_mytags():
    html = (Path(__file__).parent / "data" / "mytags.html").read_text()
    tags = parse_mytags(html)

    assert len(tags) == 2

    assert tags[0].id == 100
    assert tags[0].name == "artist:testartist"
    assert tags[0].watched is True
    assert tags[0].hidden is False
    assert tags[0].color == "#ff0000"
    assert tags[0].weight == 10

    assert tags[1].id == 200
    assert tags[1].name == "parody:testparody"
    assert tags[1].watched is False
    assert tags[1].hidden is True
    assert tags[1].color is None
    assert tags[1].weight == 5


def test_parse_mytags_empty():
    tags = parse_mytags("<html><body></body></html>")
    assert tags == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/exhentai_api/test_parser_torrent.py tests/exhentai_api/test_parser_archive.py tests/exhentai_api/test_parser_home.py tests/exhentai_api/test_parser_profile.py tests/exhentai_api/test_parser_mytags.py -v`
Expected: FAIL — modules not found

- [ ] **Step 4: Implement torrent parser**

Create `exhentai_api/parsers/torrent.py`:

```python
import re
from exhentai_api.models.torrent import TorrentItem

PATTERN_TORRENT = re.compile(
    r'<td colspan="5"> &nbsp; <a href="([^"]+)"[^<]*>([^<]+)</a></td>'
)


def parse_torrent_list(html: str) -> list[TorrentItem]:
    """Parse torrent list popup HTML into TorrentItem list."""
    items = []
    for match in PATTERN_TORRENT.finditer(html):
        url = match.group(1)
        name = match.group(2)
        # Strip ?p= tracking parameter
        p_idx = url.find("?p=")
        if p_idx != -1:
            url = url[:p_idx]
        items.append(TorrentItem(url=url, name=name))
    return items
```

- [ ] **Step 5: Implement archive parser**

Create `exhentai_api/parsers/archive.py`:

```python
import re
from bs4 import BeautifulSoup
from exhentai_api.models.archive import ArchiveOption, ArchiverData


def parse_archive_list(html: str) -> ArchiverData:
    """Parse archive options page HTML into ArchiverData."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract funds
    funds = ""
    for p in soup.find_all("p"):
        text = p.get_text()
        if "funds" in text.lower() or "GP" in text or "Credits" in text:
            # Extract the full funds text
            strongs = p.find_all("strong")
            if strongs:
                funds = " / ".join(s.get_text(strip=True) for s in strongs)
            break

    # Extract archive options from table rows
    original = None
    resample = None
    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 3:
            label = cells[0].get_text(strip=True)
            cost = cells[1].get_text(strip=True).replace("Cost: ", "")
            size = cells[2].get_text(strip=True).replace("Size: ", "")
            if "Original" in label:
                original = ArchiveOption(cost=cost, size=size)
            elif "Resample" in label:
                resample = ArchiveOption(cost=cost, size=size)

    return ArchiverData(original=original, resample=resample, funds=funds)
```

- [ ] **Step 6: Implement home parser**

Create `exhentai_api/parsers/home.py`:

```python
import re
from bs4 import BeautifulSoup
from exhentai_api.models.home import HomeDetail

PATTERN_LIMITS = re.compile(
    r"at <strong>([\d,]+)</strong> towards (?:a limit|your account limit) of <strong>([\d,]+)</strong>",
    re.DOTALL,
)
PATTERN_RESET = re.compile(r"<strong>([\d,]+)</strong>\s*GP")


def _parse_int(s: str) -> int:
    return int(s.replace(",", "")) if s else 0


def parse_home_detail(html: str) -> HomeDetail:
    """Parse home.php page HTML into HomeDetail."""
    detail = HomeDetail()

    # Image limits
    limits_match = PATTERN_LIMITS.search(html)
    if limits_match:
        detail.image_used = _parse_int(limits_match.group(1))
        detail.image_total = _parse_int(limits_match.group(2))

    # Reset cost
    reset_match = re.search(r"Reset Cost:\s*<strong>([\d,]+)</strong>", html)
    if reset_match:
        detail.reset_cost = _parse_int(reset_match.group(1))
    else:
        # Try alternate format
        reset_match2 = re.search(r"spending <strong>([\d,]+)</strong> GP", html)
        if reset_match2:
            detail.reset_cost = _parse_int(reset_match2.group(1))

    # GP sources from homebox table
    soup = BeautifulSoup(html, "html.parser")
    homeboxes = soup.find_all(class_="homebox")
    if len(homeboxes) >= 3:
        gp_box = homeboxes[2]
        rows = gp_box.find_all("tr")
        gp_values = []
        for row in rows:
            cells = row.find_all("td")
            if cells:
                val_text = cells[0].get_text(strip=True)
                gp_values.append(_parse_int(val_text))

        if len(gp_values) >= 1:
            detail.gp_from_gallery = gp_values[0]
        if len(gp_values) >= 2:
            detail.gp_from_torrent = gp_values[1]
        if len(gp_values) >= 3:
            detail.gp_from_archive = gp_values[2]
        if len(gp_values) >= 4:
            detail.gp_from_hath = gp_values[3]

    # Moderation power from 5th homebox
    if len(homeboxes) >= 5:
        mod_box = homeboxes[4]
        mod_match = re.search(r"(\d[\d,]*)", mod_box.get_text())
        if mod_match:
            detail.moderation_power = _parse_int(mod_match.group(1))

    return detail
```

- [ ] **Step 7: Implement profile parser**

Create `exhentai_api/parsers/profile.py`:

```python
from bs4 import BeautifulSoup
from exhentai_api.models.profile import ProfileResult


def parse_profile(html: str) -> ProfileResult:
    """Parse user profile page HTML into ProfileResult."""
    soup = BeautifulSoup(html, "html.parser")
    result = ProfileResult()

    # Display name from #profilename
    profilename = soup.find(id="profilename")
    if profilename:
        first_child = profilename.find()
        if first_child:
            result.display_name = first_child.get_text(strip=True)
        else:
            result.display_name = profilename.get_text(strip=True)

        # Avatar: two siblings after profilename
        avatar_container = profilename.find_next_sibling()
        if avatar_container:
            avatar_container = avatar_container.find_next_sibling()
        if avatar_container:
            img = avatar_container.find("img")
            if img:
                result.avatar_url = img.get("src", "")

    # Fallback: try #userlinks (new format)
    if not result.display_name:
        userlinks = soup.find(id="userlinks")
        if userlinks:
            try:
                result.display_name = userlinks.find().find().find().get_text(strip=True)
            except (AttributeError, TypeError):
                pass
            avatar_container = userlinks.find_next_sibling()
            if avatar_container:
                avatar_container = avatar_container.find_next_sibling()
            if avatar_container:
                img = avatar_container.find("img")
                if img:
                    result.avatar_url = img.get("src", "")

    return result
```

- [ ] **Step 8: Implement mytags parser**

Create `exhentai_api/parsers/mytags.py`:

```python
from bs4 import BeautifulSoup
from exhentai_api.models.tags import WatchedTag


def parse_mytags(html: str) -> list[WatchedTag]:
    """Parse mytags page HTML into list of WatchedTag."""
    soup = BeautifulSoup(html, "html.parser")
    outer = soup.find(id="usertags_outer")
    if not outer:
        return []

    tags = []
    children = list(outer.children)
    # Filter to element nodes only
    elements = [c for c in children if hasattr(c, "get") and c.name is not None]

    # Skip first element (header row)
    for elem in elements[1:]:
        elem_id = elem.get("id", "")
        if not elem_id.startswith("utag_"):
            continue

        tag_num = elem_id[5:]  # strip "utag_"
        try:
            tag_id = int(tag_num)
        except ValueError:
            continue

        # Tag name from #tagpreviewNNN title attribute
        name_elem = elem.find(id=f"tagpreview{tag_num}")
        name = name_elem.get("title", "") if name_elem else ""

        # Watched from #tagwatchNNN checked attribute
        watch_elem = elem.find(id=f"tagwatch{tag_num}")
        watched = watch_elem.get("checked") == "checked" if watch_elem else False

        # Hidden from #taghideNNN checked attribute
        hide_elem = elem.find(id=f"taghide{tag_num}")
        hidden = hide_elem.get("checked") == "checked" if hide_elem else False

        # Color from #tagcolorNNN placeholder attribute
        color_elem = elem.find(id=f"tagcolor{tag_num}")
        color = None
        if color_elem:
            color_val = color_elem.get("placeholder", "")
            color = color_val if color_val else None

        # Weight from #tagweightNNN value attribute
        weight_elem = elem.find(id=f"tagweight{tag_num}")
        weight = 0
        if weight_elem:
            weight_str = weight_elem.get("value", "0")
            try:
                weight = int(weight_str) if weight_str else 0
            except ValueError:
                weight = 0

        tags.append(WatchedTag(
            id=tag_id,
            name=name,
            watched=watched,
            hidden=hidden,
            color=color,
            weight=weight,
        ))

    return tags
```

- [ ] **Step 9: Run all parser tests to verify they pass**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/exhentai_api/test_parser_torrent.py tests/exhentai_api/test_parser_archive.py tests/exhentai_api/test_parser_home.py tests/exhentai_api/test_parser_profile.py tests/exhentai_api/test_parser_mytags.py -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace
git add exhentai_api/parsers/torrent.py exhentai_api/parsers/archive.py exhentai_api/parsers/home.py exhentai_api/parsers/profile.py exhentai_api/parsers/mytags.py tests/exhentai_api/test_parser_torrent.py tests/exhentai_api/test_parser_archive.py tests/exhentai_api/test_parser_home.py tests/exhentai_api/test_parser_profile.py tests/exhentai_api/test_parser_mytags.py tests/exhentai_api/data/torrent_list.html tests/exhentai_api/data/archive_list.html tests/exhentai_api/data/home.html tests/exhentai_api/data/profile.html tests/exhentai_api/data/mytags.html
git commit -m "feat(parsers): add torrent, archive, home, profile, mytags parsers"
```

---

## Task 5: New API Methods + Favorites Enhancement

**Files:**
- Modify: `exhentai_api/api.py`
- Modify: `exhentai_api/__init__.py`
- Create: `tests/exhentai_api/test_api_new.py`

- [ ] **Step 1: Write failing tests for all new API methods**

Create `tests/exhentai_api/test_api_new.py`:

```python
import pytest
from unittest.mock import AsyncMock
from exhentai_api.api import ExhentaiAPI
from exhentai_api.constants import BASE_URL


@pytest.mark.asyncio
async def test_comment_gallery():
    mock_client = AsyncMock()
    mock_client.post_form.return_value = '<div id="cdiv"><div class="c1"><div class="c3">Posted on 01 January 2024, 12:00 by: <a>user</a></div><div class="c6">test</div></div></div>'
    api = ExhentaiAPI(client=mock_client)

    comments = await api.comment_gallery("123", "abc", "Hello!")
    mock_client.post_form.assert_called_once()
    call_args = mock_client.post_form.call_args
    assert call_args[0][0] == f"{BASE_URL}/g/123/abc/"
    assert call_args[1]["data"]["comment_text"] == "Hello!"


@pytest.mark.asyncio
async def test_comment_gallery_edit():
    mock_client = AsyncMock()
    mock_client.post_form.return_value = '<div id="cdiv"></div>'
    api = ExhentaiAPI(client=mock_client)

    await api.comment_gallery("123", "abc", "Edited!", edit_id=456)
    call_data = mock_client.post_form.call_args[1]["data"]
    assert call_data["edit_comment"] == "456"


@pytest.mark.asyncio
async def test_vote_comment():
    mock_client = AsyncMock()
    mock_client.post_json.return_value = {
        "comment_id": 99, "comment_score": -3, "comment_vote": 1
    }
    api = ExhentaiAPI(client=mock_client)

    result = await api.vote_comment("uid1", "key1", 123, "abc", 99, 1)
    assert result.comment_id == 99
    assert result.comment_score == -3
    assert result.comment_vote == 1
    mock_client.post_json.assert_called_once_with(
        f"{BASE_URL}/api.php",
        json={
            "method": "votecomment", "apiuid": "uid1", "apikey": "key1",
            "gid": 123, "token": "abc", "comment_id": 99, "comment_vote": 1,
        },
    )


@pytest.mark.asyncio
async def test_rate_gallery():
    mock_client = AsyncMock()
    mock_client.post_json.return_value = {
        "rating_avg": 4.5, "rating_cnt": 100
    }
    api = ExhentaiAPI(client=mock_client)

    result = await api.rate_gallery("uid1", "key1", 123, "abc", 8)
    assert result.rating == 4.5
    assert result.rating_count == 100
    mock_client.post_json.assert_called_once_with(
        f"{BASE_URL}/api.php",
        json={
            "method": "rategallery", "apiuid": "uid1", "apikey": "key1",
            "gid": 123, "token": "abc", "rating": 8,
        },
    )


@pytest.mark.asyncio
async def test_get_torrent_list():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<table><tr><td colspan="5"> &nbsp; <a href="https://ex.com/t.torrent">name.torrent</a></td></tr></table>'
    api = ExhentaiAPI(client=mock_client)

    items = await api.get_torrent_list("123", "abc")
    assert len(items) == 1
    assert items[0].name == "name.torrent"
    mock_client.get_html.assert_called_once_with(
        f"{BASE_URL}/gallerytorrents.php?gid=123&t=abc"
    )


@pytest.mark.asyncio
async def test_get_archive_list():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = "<html><body></body></html>"
    api = ExhentaiAPI(client=mock_client)

    data = await api.get_archive_list("123", "abc")
    mock_client.get_html.assert_called_once_with(
        f"{BASE_URL}/archiver.php?gid=123&token=abc"
    )


@pytest.mark.asyncio
async def test_get_mytags():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = "<html><body></body></html>"
    api = ExhentaiAPI(client=mock_client)

    tags = await api.get_mytags()
    assert tags == []
    mock_client.get_html.assert_called_once_with(f"{BASE_URL}/mytags")


@pytest.mark.asyncio
async def test_get_watched():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<table class="itg"></table>'
    api = ExhentaiAPI(client=mock_client)

    items = await api.get_watched(page=2)
    mock_client.get_html.assert_called_once_with(
        f"{BASE_URL}/watched", params={"page": "2"}
    )


@pytest.mark.asyncio
async def test_get_home_detail():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = "<html><body></body></html>"
    api = ExhentaiAPI(client=mock_client)

    detail = await api.get_home_detail()
    assert detail.image_used == 0
    mock_client.get_html.assert_called_once_with(f"{BASE_URL}/home.php")


@pytest.mark.asyncio
async def test_reset_image_limit():
    mock_client = AsyncMock()
    mock_client.post_form.return_value = "<html><body></body></html>"
    api = ExhentaiAPI(client=mock_client)

    detail = await api.reset_image_limit()
    mock_client.post_form.assert_called_once_with(
        f"{BASE_URL}/home.php",
        data={"reset_imagelimit": "Reset Limit"},
    )


@pytest.mark.asyncio
async def test_get_gallery_token():
    mock_client = AsyncMock()
    mock_client.post_json.return_value = {
        "tokenlist": [{"gid": 123, "token": "abcdef1234"}]
    }
    api = ExhentaiAPI(client=mock_client)

    token = await api.get_gallery_token(123, "imgkey1", 5)
    assert token == "abcdef1234"


@pytest.mark.asyncio
async def test_get_favorites_with_keyword():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<html><body></body></html>'
    api = ExhentaiAPI(client=mock_client)

    await api.get_favorites(favcat=0, keyword="test", sn=True, st=True)
    call_args = mock_client.get_html.call_args
    params = call_args[1]["params"] if "params" in call_args[1] else call_args[0][1]
    assert params["f_search"] == "test"
    assert params["sn"] == "on"
    assert params["st"] == "on"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/exhentai_api/test_api_new.py -v`
Expected: FAIL — `ExhentaiAPI` has no `comment_gallery` attribute

- [ ] **Step 3: Implement all new API methods**

Replace `exhentai_api/api.py` with:

```python
from typing import Optional, List
from exhentai_api.client import ExhentaiClient
from exhentai_api.parsers.gallery import parse_gallery_list
from exhentai_api.parsers.gallery_detail import parse_gallery_detail
from exhentai_api.parsers.image import parse_image_viewer, parse_image_api_response
from exhentai_api.parsers.favorites import parse_favorites_list
from exhentai_api.parsers.toplist import parse_toplist
from exhentai_api.parsers.comments import parse_comments
from exhentai_api.parsers.torrent import parse_torrent_list
from exhentai_api.parsers.archive import parse_archive_list
from exhentai_api.parsers.home import parse_home_detail
from exhentai_api.parsers.profile import parse_profile
from exhentai_api.parsers.mytags import parse_mytags
from exhentai_api.models.gallery import GalleryDetail, GalleryListItem
from exhentai_api.models.image import ImageDetail
from exhentai_api.models.search import SearchParams
from exhentai_api.models.favorites import FavoritesResponse
from exhentai_api.models.toplist import TopListItem
from exhentai_api.models.comment import GalleryComment
from exhentai_api.models.torrent import TorrentItem
from exhentai_api.models.archive import ArchiverData
from exhentai_api.models.home import HomeDetail
from exhentai_api.models.profile import ProfileResult
from exhentai_api.models.tags import WatchedTag
from exhentai_api.models.vote import RateResult, VoteCommentResult
from exhentai_api.constants import BASE_URL
import re


class ExhentaiAPI:
    def __init__(self, client: Optional[ExhentaiClient] = None):
        self._owns_client = client is None
        self.client = client or ExhentaiClient()

    async def aclose(self):
        if self._owns_client:
            await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    # ── Gallery List ──

    async def get_homepage(self) -> list[GalleryListItem]:
        html = await self.client.get_html(f"{BASE_URL}/")
        return parse_gallery_list(html)

    async def search(self, params: SearchParams, page: int = 0) -> list[GalleryListItem]:
        query_params = params.to_dict()
        if page > 0:
            query_params["page"] = str(page)
        html = await self.client.get_html(f"{BASE_URL}/", params=query_params)
        return parse_gallery_list(html)

    # ── Gallery Detail ──

    async def get_gallery_details(self, gid: str, token: str) -> GalleryDetail:
        url = f"{BASE_URL}/g/{gid}/{token}/"
        html = await self.client.get_html(url)
        return parse_gallery_detail(html, gid, token)

    # ── Images ──

    async def get_image_url(self, gid: str, imgkey: str, page: int, nl: Optional[str] = None) -> ImageDetail:
        if nl:
            payload = {
                "method": "showpage",
                "gid": gid,
                "page": str(page),
                "imgkey": imgkey,
                "showkey": nl,
            }
            json_resp = await self.client.post_json(f"{BASE_URL}/api.php", json=payload)
            image_url, new_nl = parse_image_api_response(json_resp)
            return ImageDetail(gid=str(gid), page=page, image_url=image_url, nl=new_nl)
        else:
            url = f"{BASE_URL}/s/{imgkey}/{gid}-{page}"
            html = await self.client.get_html(url)
            image_url, new_nl = parse_image_viewer(html)
            return ImageDetail(gid=str(gid), page=page, image_url=image_url, nl=new_nl)

    # ── Comments ──

    async def comment_gallery(
        self, gid: str, token: str, comment: str, edit_id: Optional[int] = None
    ) -> list[GalleryComment]:
        url = f"{BASE_URL}/g/{gid}/{token}/"
        data = {"comment_text": comment}
        if edit_id is not None:
            data["edit_comment"] = str(edit_id)
        html = await self.client.post_form(url, data=data)
        comments, _ = parse_comments(html)
        return comments

    async def vote_comment(
        self, api_uid: str, api_key: str,
        gid: int, token: str,
        comment_id: int, vote: int,
    ) -> VoteCommentResult:
        payload = {
            "method": "votecomment",
            "apiuid": api_uid,
            "apikey": api_key,
            "gid": gid,
            "token": token,
            "comment_id": comment_id,
            "comment_vote": vote,
        }
        resp = await self.client.post_json(f"{BASE_URL}/api.php", json=payload)
        return VoteCommentResult(
            comment_id=resp.get("comment_id", 0),
            comment_score=resp.get("comment_score", 0),
            comment_vote=resp.get("comment_vote", 0),
        )

    # ── Rating ──

    async def rate_gallery(
        self, api_uid: str, api_key: str,
        gid: int, token: str, rating: int,
    ) -> RateResult:
        payload = {
            "method": "rategallery",
            "apiuid": api_uid,
            "apikey": api_key,
            "gid": gid,
            "token": token,
            "rating": rating,
        }
        resp = await self.client.post_json(f"{BASE_URL}/api.php", json=payload)
        return RateResult(
            rating=resp.get("rating_avg", 0.0),
            rating_count=resp.get("rating_cnt", 0),
        )

    # ── Torrents ──

    async def get_torrent_list(self, gid: str, token: str) -> list[TorrentItem]:
        url = f"{BASE_URL}/gallerytorrents.php?gid={gid}&t={token}"
        html = await self.client.get_html(url)
        return parse_torrent_list(html)

    # ── Archives ──

    async def get_archive_list(self, gid: str, token: str) -> ArchiverData:
        url = f"{BASE_URL}/archiver.php?gid={gid}&token={token}"
        html = await self.client.get_html(url)
        return parse_archive_list(html)

    async def download_archive(self, archive_url: str, resolution: str = "org") -> str:
        dlcheck = "Download Original Archive" if resolution == "org" else "Download Resample Archive"
        html = await self.client.post_form(
            archive_url,
            data={"dltype": resolution, "dlcheck": dlcheck},
        )
        match = re.search(r'href="(.+?)">Click Here To Start Downloading', html)
        return match.group(1) if match else ""

    # ── Favorites ──

    async def get_favorites(
        self, favcat: int = -1, page: int = 0,
        keyword: str = "", sn: bool = False, st: bool = False, sf: bool = False,
    ) -> FavoritesResponse:
        params = {}
        if favcat != -1:
            params["favcat"] = str(favcat)
        if page > 0:
            params["page"] = str(page)
        if keyword:
            params["f_search"] = keyword
        if sn:
            params["sn"] = "on"
        if st:
            params["st"] = "on"
        if sf:
            params["sf"] = "on"
        html = await self.client.get_html(
            f"{BASE_URL}/favorites.php", params=params if params else None
        )
        return parse_favorites_list(html)

    async def add_favorite(self, gid: str, token: str, favcat: int = 0, favnote: str = "") -> str:
        url = f"{BASE_URL}/gallerypopups.php?gid={gid}&t={token}&act=addfav"
        favcat_val = "favdel" if favcat == -1 else str(favcat)
        payload = {
            "favcat": favcat_val,
            "favnote": favnote,
            "submit": "Apply Changes",
            "update": "1",
        }
        return await self.client.post_form(url, data=payload)

    async def modify_favorites(self, gids: List[str], ddact: str) -> str:
        if ddact != "delete" and not re.match(r"^fav[0-9]$", ddact):
            raise ValueError("ddact must be 'delete' or 'fav[0-9]'")
        url = f"{BASE_URL}/favorites.php"
        payload = {"ddact": ddact, "apply": "Apply"}
        form_data = list(payload.items())
        for gid in gids:
            form_data.append(("modifygids[]", str(gid)))
        return await self.client.post_form(url, data=form_data)

    # ── Popular / TopList ──

    async def get_popular(self) -> List[GalleryListItem]:
        html = await self.client.get_html(f"{BASE_URL}/popular")
        return parse_gallery_list(html)

    async def get_toplist(self, tl: str = "15") -> List[TopListItem]:
        url = f"{BASE_URL}/toplist.php"
        params = {}
        if tl:
            params["tl"] = tl
        html = await self.client.get_html(url, params=params if params else None)
        return parse_toplist(html)

    # ── MyTags ──

    async def get_mytags(self) -> list[WatchedTag]:
        html = await self.client.get_html(f"{BASE_URL}/mytags")
        return parse_mytags(html)

    async def add_tag(
        self, tag_name: str,
        watched: bool = False, hidden: bool = False,
        color: str = "", weight: int = 10,
    ) -> list[WatchedTag]:
        payload = {
            "tagname_new": tag_name,
            "tagwatch_new": "1" if watched else "0",
            "taghide_new": "1" if hidden else "0",
            "tagcolor_new": color,
            "tagweight_new": str(weight),
            "usertags_action": "add",
        }
        html = await self.client.post_form(f"{BASE_URL}/mytags", data=payload)
        return parse_mytags(html)

    async def delete_tag(self, tag_id: int) -> list[WatchedTag]:
        form_data = [
            ("modify_usertags[]", str(tag_id)),
            ("usertags_action", "mass"),
        ]
        html = await self.client.post_form(f"{BASE_URL}/mytags", data=form_data)
        return parse_mytags(html)

    # ── Watched ──

    async def get_watched(self, page: int = 0) -> list[GalleryListItem]:
        params = {}
        if page > 0:
            params["page"] = str(page)
        html = await self.client.get_html(
            f"{BASE_URL}/watched", params=params if params else None
        )
        return parse_gallery_list(html)

    # ── Home / Profile ──

    async def get_home_detail(self) -> HomeDetail:
        html = await self.client.get_html(f"{BASE_URL}/home.php")
        return parse_home_detail(html)

    async def get_profile(self) -> ProfileResult:
        html = await self.client.get_html("https://forums.e-hentai.org/")
        # Extract profile URL from forums page
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        userlinks = soup.find(id="userlinks")
        if userlinks:
            try:
                profile_url = userlinks.find().find().find().get("href", "")
            except (AttributeError, TypeError):
                return ProfileResult()
            if profile_url:
                profile_html = await self.client.get_html(profile_url)
                return parse_profile(profile_html)
        return ProfileResult()

    async def reset_image_limit(self) -> HomeDetail:
        html = await self.client.post_form(
            f"{BASE_URL}/home.php",
            data={"reset_imagelimit": "Reset Limit"},
        )
        return parse_home_detail(html)

    # ── Gallery Token API ──

    async def get_gallery_token(self, gid: int, imgkey: str, page: int) -> str:
        payload = {
            "method": "gtoken",
            "pagelist": [[gid, imgkey, page]],
        }
        resp = await self.client.post_json(f"{BASE_URL}/api.php", json=payload)
        tokenlist = resp.get("tokenlist", [])
        if tokenlist:
            return tokenlist[0].get("token", "")
        return ""

    # ── Image Search ──

    async def image_search(
        self, file_path: str,
        similar: bool = True, covers: bool = True, exp: bool = True,
    ) -> list[GalleryListItem]:
        import hashlib
        with open(file_path, "rb") as f:
            sha_hash = hashlib.sha1(f.read()).hexdigest()
        params = {"f_shash": sha_hash}
        if similar:
            params["fs_similar"] = "1"
        if covers:
            params["fs_covers"] = "1"
        if exp:
            params["fs_exp"] = "1"
        html = await self.client.get_html(f"{BASE_URL}/", params=params)
        return parse_gallery_list(html)
```

- [ ] **Step 4: Update top-level __init__.py exports**

Replace `exhentai_api/__init__.py` with:

```python
from .api import ExhentaiAPI
from .client import ExhentaiClient
from .models.gallery import GalleryListItem, GalleryDetail
from .models.comment import GalleryComment
from .models.torrent import TorrentItem
from .models.archive import ArchiveOption, ArchiverData
from .models.home import HomeDetail
from .models.profile import ProfileResult
from .models.vote import RateResult, VoteCommentResult
from .models.tags import Tag, WatchedTag
from .models.image import ImageDetail
from .models.search import SearchParams
from .models.favorites import FavoriteCategory, FavoritesResponse
from .models.toplist import TopListItem
```

- [ ] **Step 5: Run all new API tests**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/exhentai_api/test_api_new.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run the complete test suite to check for regressions**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/ -v`
Expected: ALL PASS — no regressions in existing tests

- [ ] **Step 7: Commit**

```bash
cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace
git add exhentai_api/api.py exhentai_api/__init__.py tests/exhentai_api/test_api_new.py
git commit -m "feat(api): add comment, rating, torrent, archive, mytags, watched, home, profile, gallery token, image search, favorites keyword search"
```

---

## Task 6: Full Test Suite Verification + Final Cleanup

**Files:**
- All test files
- `exhentai_api/models/__init__.py` (verify exports)

- [ ] **Step 1: Run complete test suite**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run pytest tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 2: Verify all models are importable from top-level package**

Run: `cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace && uv run python -c "from exhentai_api import ExhentaiAPI, ExhentaiClient, GalleryListItem, GalleryDetail, GalleryComment, TorrentItem, ArchiveOption, ArchiverData, HomeDetail, ProfileResult, RateResult, VoteCommentResult, WatchedTag, Tag, ImageDetail, SearchParams, FavoriteCategory, FavoritesResponse, TopListItem; print('All imports OK')"` 
Expected: `All imports OK`

- [ ] **Step 3: Final commit if any cleanup was needed**

If any fixes were required during verification:
```bash
cd /home/ycyc/code/project/Ehviewer_CN_SXJ/workspace
git add -A
git commit -m "fix: address test suite regressions from full alignment"
```

---

## Summary of Deliverables

After completing all 6 tasks:

- **7 new model files** with 8 new dataclasses
- **6 new parser files** for comments, torrents, archives, home, profile, mytags
- **2 enhanced parsers** (gallery list + gallery detail) with missing fields
- **15+ new API methods** covering all reference project features
- **Enhanced favorites** with keyword search support
- **Full test coverage** for all new and modified code
- **5-6 atomic commits** with clear messages
