# Exhentai API Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the existing monolithic parser and client into a clean, reusable `exhentai-api` Python package following the target architecture in `CLAUDE.md`.

**Architecture:** We will build this package bottom-up: Constants & Utilities -> Models -> Parsers -> Core Client -> High-level API. Each component will be developed using TDD.

**Tech Stack:** Python 3, `BeautifulSoup` (for parsing), `httpx` (for client), `pydantic`/`dataclasses` (for models), `pytest`.

---

### Task 1: Constants and Utilities

**Files:**
- Create: `exhentai-api/constants.py`
- Create: `exhentai-api/utils.py`
- Test: `tests/exhentai-api/test_utils.py`

- [ ] **Step 1: Write failing test for utils URL extraction**

```python
# tests/exhentai-api/test_utils.py
from exhentai_api.utils import extract_gallery_token

def test_extract_gallery_token():
    url = "https://exhentai.org/g/1234567/abcdef1234/"
    gid, token = extract_gallery_token(url)
    assert gid == "1234567"
    assert token == "abcdef1234"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/exhentai-api/test_utils.py -v`
Expected: FAIL (ModuleNotFoundError or ImportError)

- [ ] **Step 3: Minimal implementation of constants and utils**

```python
# exhentai-api/constants.py
class Category:
    DOUJINSHI = "Doujinshi"
    MANGA = "Manga"
    NON_H = "Non-H"

BASE_URL = "https://exhentai.org"

# exhentai-api/utils.py
import re

def extract_gallery_token(url: str) -> tuple[str, str]:
    match = re.search(r"/(?:g|mpv)/(\d+)/([0-9a-f]{10})", url)
    if not match:
        raise ValueError("Invalid gallery URL")
    return match.group(1), match.group(2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/exhentai-api/test_utils.py -v` (Note: need to ensure `exhentai-api` is importable, might need a symlink or adjust `sys.path` in tests, or name the directory `exhentai_api`. Let's rename the directory to `exhentai_api` to make it a valid Python module).

*Wait, Python module names shouldn't have hyphens.*

- [ ] **Step 5: Rename directory and Commit**

```bash
mv exhentai-api exhentai_api
mv tests/exhentai-api tests/exhentai_api
git add exhentai_api tests/exhentai_api
git commit -m "feat(api): add constants and url utils"
```

### Task 2: Data Models (Gallery)

**Files:**
- Create: `exhentai_api/models/gallery.py`
- Test: `tests/exhentai_api/test_models.py`

- [ ] **Step 1: Write failing test**

```python
# tests/exhentai_api/test_models.py
from exhentai_api.models.gallery import GalleryListItem

def test_gallery_list_item():
    item = GalleryListItem(
        gid="123",
        token="abc",
        title="Test Gallery",
        category="Manga",
        uploader="testuser",
        thumb_url="http://example.com/thumb.jpg",
        posted="2023-01-01 12:00"
    )
    assert item.url == "https://exhentai.org/g/123/abc/"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/exhentai_api/test_models.py -v`
Expected: FAIL (ModuleNotFoundError or ImportError)

- [ ] **Step 3: Minimal implementation**

```python
# exhentai_api/models/gallery.py
from dataclasses import dataclass
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

    @property
    def url(self) -> str:
        return f"{BASE_URL}/g/{self.gid}/{self.token}/"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/exhentai_api/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add exhentai_api/models/gallery.py tests/exhentai_api/test_models.py
git commit -m "feat(api): add gallery list item model"
```

### Task 3: Gallery List Parser

**Files:**
- Create: `exhentai_api/parsers/gallery.py`
- Test: `tests/exhentai_api/test_parser_gallery.py`
- Mock Data: `tests/exhentai_api/data/gallery_list.html` (Need to create a minimal HTML snippet based on CLAUDE.md)

- [ ] **Step 1: Write failing test & mock data**

```html
<!-- tests/exhentai_api/data/gallery_list.html -->
<table class="itg">
  <tr>
    <td class="gl3c"><a href="https://exhentai.org/g/12345/abcdef1234/"><div class="glname">Test Title</div></a></td>
    <td class="gl1c"><div class="cn">Manga</div></td>
    <td class="glhide"><a href="#">uploader_name</a></td>
    <td class="gl2c"><div class="glthumb"><img data-src="http://thumb.jpg" /></div></td>
    <td class="gl4c"><div>2023-01-01 12:00</div></td>
  </tr>
</table>
```

```python
# tests/exhentai_api/test_parser_gallery.py
from bs4 import BeautifulSoup
from exhentai_api.parsers.gallery import parse_gallery_list

def test_parse_gallery_list():
    with open("tests/exhentai_api/data/gallery_list.html", "r") as f:
        html = f.read()
    
    items = parse_gallery_list(html)
    assert len(items) == 1
    assert items[0].gid == "12345"
    assert items[0].token == "abcdef1234"
    assert items[0].title == "Test Title"
    assert items[0].category == "Manga"
    assert items[0].uploader == "uploader_name"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/exhentai_api/test_parser_gallery.py -v`
Expected: FAIL

- [ ] **Step 3: Minimal implementation**

```python
# exhentai_api/parsers/gallery.py
from bs4 import BeautifulSoup
from exhentai_api.models.gallery import GalleryListItem
from exhentai_api.utils import extract_gallery_token

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
        link_elem = row.find("td", class_="gl3c").find("a")
        gid, token = extract_gallery_token(link_elem["href"])
        
        cat_elem = row.find(class_=lambda x: x in ["cn", "cs"])
        category = cat_elem.get_text(strip=True) if cat_elem else ""
        
        uploader_elem = row.find("td", class_=["glhide", "gl4c"])
        uploader = uploader_elem.get_text(strip=True) if uploader_elem else ""
        
        items.append(GalleryListItem(
            gid=gid,
            token=token,
            title=title,
            category=category,
            uploader=uploader,
            thumb_url="", # Simplified for minimal pass
            posted=""     # Simplified for minimal pass
        ))
        
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/exhentai_api/test_parser_gallery.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add exhentai_api/parsers/gallery.py tests/exhentai_api/
git commit -m "feat(api): implement gallery list parser"
```

### Task 4: API Client Layer

**Files:**
- Create: `exhentai_api/client.py`
- Test: `tests/exhentai_api/test_client.py`

- [ ] **Step 1: Write failing test**

```python
# tests/exhentai_api/test_client.py
import pytest
from exhentai_api.client import ExhentaiClient

@pytest.mark.asyncio
async def test_client_headers():
    client = ExhentaiClient(igneous="test_ig", ipb_member_id="123")
    assert client.cookies["igneous"] == "test_ig"
    assert client.cookies["ipb_member_id"] == "123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/exhentai_api/test_client.py -v`
Expected: FAIL

- [ ] **Step 3: Minimal implementation**

```python
# exhentai_api/client.py
import httpx

class ExhentaiClient:
    def __init__(self, igneous: str = "", ipb_member_id: str = ""):
        self.cookies = {}
        if igneous:
            self.cookies["igneous"] = igneous
        if ipb_member_id:
            self.cookies["ipb_member_id"] = ipb_member_id
            
        self.session = httpx.AsyncClient(cookies=self.cookies)
        
    async def get_html(self, url: str) -> str:
        response = await self.session.get(url)
        response.raise_for_status()
        return response.text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/exhentai_api/test_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add exhentai_api/client.py tests/exhentai_api/test_client.py
git commit -m "feat(api): add core http client"
```

### Task 5: High-level API Wrapper

**Files:**
- Create: `exhentai_api/api.py`
- Test: `tests/exhentai_api/test_api.py`

- [ ] **Step 1: Write failing test**

```python
# tests/exhentai_api/test_api.py
import pytest
from unittest.mock import patch, AsyncMock
from exhentai_api.api import ExhentaiAPI
from exhentai_api.models.gallery import GalleryListItem

@pytest.mark.asyncio
async def test_get_homepage():
    api = ExhentaiAPI()
    
    mock_html = """
    <table class="itg"><tr>
      <td class="gl3c"><a href="https://exhentai.org/g/1/abc/"><div class="glname">Test</div></a></td>
      <td class="gl1c"><div class="cn">Manga</div></td>
    </tr></table>
    """
    
    with patch("exhentai_api.client.ExhentaiClient.get_html", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_html
        items = await api.get_homepage()
        
        assert len(items) == 1
        assert items[0].gid == "1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/exhentai_api/test_api.py -v`
Expected: FAIL

- [ ] **Step 3: Minimal implementation**

```python
# exhentai_api/api.py
from exhentai_api.client import ExhentaiClient
from exhentai_api.parsers.gallery import parse_gallery_list
from exhentai_api.constants import BASE_URL

class ExhentaiAPI:
    def __init__(self, client: ExhentaiClient = None):
        self.client = client or ExhentaiClient()
        
    async def get_homepage(self):
        html = await self.client.get_html(f"{BASE_URL}/")
        return parse_gallery_list(html)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/exhentai_api/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add exhentai_api/api.py tests/exhentai_api/test_api.py
git commit -m "feat(api): add high level api wrapper"
```

### Task 6: Verify Package and Cleanup

**Files:**
- Create: `demo.py` (Temporary for verification, then removed/ignored)

- [ ] **Step 1: Write demo script**

```python
# demo.py
import asyncio
from exhentai_api.api import ExhentaiAPI

async def main():
    print("API package structure verified.")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run demo to verify package imports correctly**

Run: `python demo.py`
Expected: "API package structure verified."

- [ ] **Step 3: Expose modules in `__init__.py`**

```python
# exhentai_api/__init__.py
from .api import ExhentaiAPI
from .client import ExhentaiClient
from .models.gallery import GalleryListItem
```

- [ ] **Step 4: Commit cleanup**

```bash
rm -rf exhentai-api  # Remove the incorrectly named directory from previous bash commands if it still exists
git add exhentai_api/__init__.py
git commit -m "chore(api): expose public api in __init__"
```
