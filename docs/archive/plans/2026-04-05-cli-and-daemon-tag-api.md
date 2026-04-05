# CLI Download Command + Daemon Tag Suggest API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tag autocomplete API to the daemon, add streaming page images, rewrite CLI as a minimal daemon-client download command, and clean up legacy files.

**Architecture:** TagDatabase loads EhTagTranslation's `db.text.json` into memory at daemon startup, serves substring-match suggestions via a new REST endpoint. CLI uses httpx + websockets to submit downloads and display progress via rich. Page image route gains StreamingResponse for client-side progress tracking.

**Tech Stack:** Python 3.12+, FastAPI, httpx, rich, websockets

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `pandora_daemon/tag_database.py` | Load, cache, search EhTagTranslation data |
| Create | `pandora_daemon/routes/tags.py` | Tag suggest endpoint |
| Create | `pandora_daemon/cli.py` | CLI download command (daemon client) |
| Create | `tests/pandora_daemon/test_tag_database.py` | TagDatabase unit tests |
| Create | `tests/pandora_daemon/test_routes_tags.py` | Tag suggest route tests |
| Create | `tests/pandora_daemon/test_cli.py` | CLI tests |
| Modify | `pandora_daemon/state.py` | Add `tag_database` field |
| Modify | `pandora_daemon/dependencies.py` | Add `get_tag_database` |
| Modify | `pandora_daemon/app.py` | Wire TagDatabase into lifespan |
| Modify | `pandora_daemon/routes/__init__.py` | Register tags router |
| Modify | `pandora_daemon/routes/gallery.py:199-215` | StreamingResponse for page images |
| Modify | `pandora_daemon/image_service.py:37-79` | Streaming get_page_image variant |
| Modify | `pyproject.toml` | Update entry point, add websockets dep |
| Delete | `cli.py` (root) | Legacy CLI |
| Delete | `downloader.py` (root) | Legacy downloader |
| Delete | `tui.py` (root, if exists) | Legacy TUI |

---

### Task 1: TagDatabase — data loading and search

**Files:**
- Create: `pandora_daemon/tag_database.py`
- Create: `tests/pandora_daemon/test_tag_database.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pandora_daemon/test_tag_database.py
import pytest
from pandora_daemon.tag_database import TagDatabase, TagEntry


SAMPLE_DB_JSON = {
    "data": [
        {
            "namespace": "female",
            "data": {
                "stockings": {"name": "丝袜", "intro": "", "links": ""},
                "stockings only": {"name": "仅穿丝袜", "intro": "", "links": ""},
                "striped stockings": {"name": "条纹丝袜", "intro": "", "links": ""},
                "maid": {"name": "女仆", "intro": "", "links": ""},
            },
        },
        {
            "namespace": "male",
            "data": {
                "stockings": {"name": "丝袜", "intro": "", "links": ""},
            },
        },
        {
            "namespace": "artist",
            "data": {
                "kemuri haku": {"name": "けむり白", "intro": "", "links": ""},
            },
        },
    ],
}


class TestTagDatabase:
    def setup_method(self):
        self.db = TagDatabase()
        self.db.load_from_dict(SAMPLE_DB_JSON)

    def test_load_entry_count(self):
        assert len(self.db.entries) == 6

    def test_suggest_english_substring(self):
        results = self.db.suggest("stocking", limit=10)
        tags = [r.tag for r in results]
        assert "stockings" in tags
        assert "stockings only" in tags
        assert "striped stockings" in tags

    def test_suggest_chinese_substring(self):
        results = self.db.suggest("丝袜", limit=10)
        assert len(results) >= 2  # female:stockings + male:stockings

    def test_suggest_limit(self):
        results = self.db.suggest("stock", limit=2)
        assert len(results) == 2

    def test_suggest_prefix_match_ranked_first(self):
        results = self.db.suggest("stock", limit=10)
        # "stockings" and "stockings only" start with "stock" → ranked before "striped stockings"
        first_tags = [r.tag for r in results[:3]]
        assert first_tags[0] == "stockings" or first_tags[0] == "stockings only"

    def test_suggest_no_match(self):
        results = self.db.suggest("zzzznotexist", limit=10)
        assert results == []

    def test_suggest_empty_query(self):
        results = self.db.suggest("", limit=10)
        assert results == []

    def test_translate_exact(self):
        result = self.db.translate("female", "maid")
        assert result == "女仆"

    def test_translate_not_found(self):
        result = self.db.translate("female", "nonexistent")
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_tag_database.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'pandora_daemon.tag_database')

- [ ] **Step 3: Write minimal implementation**

```python
# pandora_daemon/tag_database.py
"""EhTagTranslation database for tag autocomplete."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DB_URL = "https://raw.githubusercontent.com/EhTagTranslation/DatabaseReleases/master/db.text.json"
DEFAULT_CACHE_PATH = Path("~/.cache/pandora/tags/db.text.json")


@dataclass
class TagEntry:
    namespace: str
    tag: str
    translation: str


class TagDatabase:
    """In-memory EhTagTranslation database with substring search."""

    def __init__(self) -> None:
        self.entries: list[TagEntry] = []
        self._lookup: dict[tuple[str, str], str] = {}  # (namespace, tag) → translation

    def load_from_dict(self, data: dict[str, Any]) -> None:
        """Parse db.text.json structure into flat entry list."""
        entries: list[TagEntry] = []
        lookup: dict[tuple[str, str], str] = {}
        for ns_block in data.get("data", []):
            namespace = ns_block.get("namespace", "")
            for tag, info in ns_block.get("data", {}).items():
                translation = info.get("name", "")
                entry = TagEntry(namespace=namespace, tag=tag, translation=translation)
                entries.append(entry)
                lookup[(namespace, tag)] = translation
        self.entries = entries
        self._lookup = lookup
        logger.info("TagDatabase loaded %d entries", len(entries))

    def load_from_file(self, path: Path) -> None:
        """Load from a local JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_from_dict(data)

    async def download_and_load(self, cache_path: Path = DEFAULT_CACHE_PATH) -> None:
        """Download db.text.json from GitHub, cache locally, and load."""
        cache_path = cache_path.expanduser()
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Try loading from cache first
        if cache_path.exists():
            try:
                self.load_from_file(cache_path)
                return
            except Exception:
                logger.warning("Cached tag database corrupted, re-downloading")

        # Download fresh copy
        async with httpx.AsyncClient() as client:
            resp = await client.get(DB_URL, timeout=60.0)
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)

        self.load_from_file(cache_path)

    async def check_update(self, cache_path: Path = DEFAULT_CACHE_PATH) -> bool:
        """Check GitHub for newer version and update if available. Returns True if updated."""
        cache_path = cache_path.expanduser()
        try:
            async with httpx.AsyncClient() as client:
                headers = {}
                if cache_path.exists():
                    import email.utils
                    import os
                    mtime = os.path.getmtime(cache_path)
                    headers["If-Modified-Since"] = email.utils.formatdate(mtime, usegmt=True)

                resp = await client.get(DB_URL, headers=headers, timeout=60.0)
                if resp.status_code == 304:
                    return False
                resp.raise_for_status()
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(resp.content)
                self.load_from_file(cache_path)
                logger.info("TagDatabase updated from GitHub")
                return True
        except Exception:
            logger.warning("TagDatabase update check failed", exc_info=True)
            return False

    def suggest(self, query: str, limit: int = 10) -> list[TagEntry]:
        """Substring match on tag name or translation. Prefix matches ranked first."""
        if not query:
            return []
        q = query.lower()
        prefix_matches: list[TagEntry] = []
        substring_matches: list[TagEntry] = []
        for entry in self.entries:
            tag_lower = entry.tag.lower()
            if tag_lower.startswith(q) or entry.translation.startswith(query):
                prefix_matches.append(entry)
            elif q in tag_lower or query in entry.translation:
                substring_matches.append(entry)
            if len(prefix_matches) + len(substring_matches) >= limit * 2:
                break  # Early exit, we have enough candidates
        results = prefix_matches + substring_matches
        return results[:limit]

    def translate(self, namespace: str, tag: str) -> str | None:
        """Exact lookup for a single tag translation."""
        return self._lookup.get((namespace, tag))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_tag_database.py -v`
Expected: PASS (all 9 tests)

- [ ] **Step 5: Commit**

```
git add pandora_daemon/tag_database.py tests/pandora_daemon/test_tag_database.py
git commit -m "feat: add TagDatabase for EhTagTranslation autocomplete"
```

---

### Task 2: Tag suggest route

**Files:**
- Create: `pandora_daemon/routes/tags.py`
- Create: `tests/pandora_daemon/test_routes_tags.py`
- Modify: `pandora_daemon/routes/__init__.py`
- Modify: `pandora_daemon/dependencies.py`
- Modify: `pandora_daemon/state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/pandora_daemon/test_routes_tags.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from pandora_daemon.tag_database import TagDatabase, TagEntry

SAMPLE_DB = {
    "data": [
        {
            "namespace": "female",
            "data": {
                "stockings": {"name": "丝袜", "intro": "", "links": ""},
                "maid": {"name": "女仆", "intro": "", "links": ""},
            },
        },
    ],
}


@pytest.fixture
def app_with_tags():
    from pandora_daemon.app import create_app

    app = create_app()
    tag_db = TagDatabase()
    tag_db.load_from_dict(SAMPLE_DB)

    mock_state = MagicMock()
    mock_state.tag_database = tag_db
    app.state.pandora = mock_state
    return app


def test_suggest_returns_matches(app_with_tags):
    client = TestClient(app_with_tags)
    resp = client.get("/api/tags/suggest?q=stock")
    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) >= 1
    assert data["suggestions"][0]["tag"] == "stockings"
    assert data["suggestions"][0]["namespace"] == "female"
    assert data["suggestions"][0]["translation"] == "丝袜"


def test_suggest_empty_query(app_with_tags):
    client = TestClient(app_with_tags)
    resp = client.get("/api/tags/suggest?q=")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []


def test_suggest_respects_limit(app_with_tags):
    client = TestClient(app_with_tags)
    resp = client.get("/api/tags/suggest?q=m&limit=1")
    assert resp.status_code == 200
    assert len(resp.json()["suggestions"]) <= 1


def test_suggest_chinese_query(app_with_tags):
    client = TestClient(app_with_tags)
    resp = client.get("/api/tags/suggest?q=女仆")
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert any(s["tag"] == "maid" for s in suggestions)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_tags.py -v`
Expected: FAIL (route not found / tag_database not in state)

- [ ] **Step 3: Add tag_database to state and dependencies**

```python
# pandora_daemon/state.py — add tag_database field
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from pandora_daemon.config import PandoraConfig
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager
from pandora_daemon.image_service import ImageService
from pandora_daemon.tag_database import TagDatabase

@dataclass
class AppState:
    config: PandoraConfig
    config_path: Path
    client: ExhentaiClient
    api: ExhentaiAPI
    downloads: DownloadManager
    cache: CacheManager
    image_service: ImageService
    ws: WebSocketManager
    tag_database: TagDatabase = field(default_factory=TagDatabase)
```

```python
# pandora_daemon/dependencies.py — add get_tag_database at end of file
from pandora_daemon.tag_database import TagDatabase

def get_tag_database(state: AppState = Depends(get_state)) -> TagDatabase:
    return state.tag_database
```

- [ ] **Step 4: Create the route**

```python
# pandora_daemon/routes/tags.py
"""Tag suggest routes for pandora-daemon."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pandora_daemon.dependencies import get_tag_database
from pandora_daemon.tag_database import TagDatabase

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("/suggest")
async def suggest_tags(
    q: str = Query("", description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    tag_db: TagDatabase = Depends(get_tag_database),
):
    """Return tag suggestions matching the query."""
    results = tag_db.suggest(q, limit=limit)
    return {
        "suggestions": [
            {"namespace": r.namespace, "tag": r.tag, "translation": r.translation}
            for r in results
        ]
    }
```

- [ ] **Step 5: Register the router**

```python
# pandora_daemon/routes/__init__.py — add tags router
from pandora_daemon.routes.tags import router as tags_router

# Add after the last include_router line:
router.include_router(tags_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_routes_tags.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 7: Commit**

```
git add pandora_daemon/routes/tags.py pandora_daemon/state.py pandora_daemon/dependencies.py pandora_daemon/routes/__init__.py tests/pandora_daemon/test_routes_tags.py
git commit -m "feat: add GET /api/tags/suggest endpoint for tag autocomplete"
```

---

### Task 3: Wire TagDatabase into daemon lifecycle

**Files:**
- Modify: `pandora_daemon/app.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/pandora_daemon/test_tag_lifecycle.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pandora_daemon.tag_database import TagDatabase


@pytest.mark.asyncio
async def test_tag_database_loaded_on_startup():
    """Verify TagDatabase.download_and_load is called during app lifespan."""
    with patch("pandora_daemon.app.TagDatabase") as MockTagDB:
        mock_instance = MagicMock(spec=TagDatabase)
        mock_instance.download_and_load = AsyncMock()
        mock_instance.entries = []
        MockTagDB.return_value = mock_instance

        from pandora_daemon.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app):
            pass  # lifespan runs on enter/exit

        mock_instance.download_and_load.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pandora_daemon/test_tag_lifecycle.py -v`
Expected: FAIL (download_and_load not called — TagDatabase not yet wired)

- [ ] **Step 3: Wire TagDatabase into app.py lifespan**

In `pandora_daemon/app.py`, add after `ws = WebSocketManager()`:

```python
from pandora_daemon.tag_database import TagDatabase

# Inside lifespan(), after ws = WebSocketManager():
    tag_database = TagDatabase()
    try:
        await tag_database.download_and_load()
    except Exception:
        pass  # Non-fatal: suggest will return empty results
```

Add `tag_database=tag_database` to the `AppState(...)` constructor call.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pandora_daemon/test_tag_lifecycle.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `uv run pytest tests/pandora_daemon/ -v`
Expected: All tests pass (existing 203 + new tag tests)

- [ ] **Step 6: Commit**

```
git add pandora_daemon/app.py tests/pandora_daemon/test_tag_lifecycle.py
git commit -m "feat: wire TagDatabase into daemon lifecycle"
```

---

### Task 4: Streaming page image response

**Files:**
- Modify: `pandora_daemon/image_service.py`
- Modify: `pandora_daemon/routes/gallery.py:199-215`
- Create: `tests/pandora_daemon/test_streaming_page.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/pandora_daemon/test_streaming_page.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_mock_image():
    from pandora_daemon.app import create_app
    app = create_app()

    mock_image_service = MagicMock()
    # Simulate uncached: returns an async generator
    image_data = b"\x89PNG" + b"\x00" * 1000  # 1004 bytes fake PNG

    async def mock_stream(gid, token, page):
        yield image_data[:500]
        yield image_data[500:]

    mock_image_service.stream_page_image = MagicMock(return_value=mock_stream("1", "abc", 1))
    mock_image_service.get_page_image_info = AsyncMock(
        return_value={"size": 1004, "media_type": "image/png", "cached": False}
    )
    # For cached path
    mock_image_service.get_page_image = AsyncMock(return_value=image_data)

    mock_state = MagicMock()
    mock_state.image_service = mock_image_service
    app.state.pandora = mock_state
    return app


def test_page_image_returns_content_length(app_with_mock_image):
    """Cached page image should include Content-Length header."""
    client = TestClient(app_with_mock_image)
    resp = client.get("/api/gallery/1/abc/page/1")
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("image/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pandora_daemon/test_streaming_page.py -v`
Expected: FAIL (current route doesn't set Content-Length)

- [ ] **Step 3: Add Content-Length to page image response**

Modify `pandora_daemon/routes/gallery.py`, replace the `get_page_image` function:

```python
@router.get("/{gid}/{token}/page/{page}")
async def get_page_image(gid: str, token: str, page: int, image_service=Depends(get_image_service)):
    """Return full-size image bytes for a gallery page. Includes Content-Length."""
    try:
        data = await image_service.get_page_image(gid, token, page)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Detect media type from magic bytes
    if data[:4] == b"\x89PNG":
        media_type = "image/png"
    elif data[:4] == b"GIF8":
        media_type = "image/gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Length": str(len(data))},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pandora_daemon/test_streaming_page.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/pandora_daemon/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```
git add pandora_daemon/routes/gallery.py tests/pandora_daemon/test_streaming_page.py
git commit -m "feat: add Content-Length header to page image responses"
```

---

### Task 5: CLI download command

**Files:**
- Create: `pandora_daemon/cli.py`
- Create: `tests/pandora_daemon/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/pandora_daemon/test_cli.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pandora_daemon.cli import parse_gallery_url, build_daemon_url


def test_parse_gallery_url_standard():
    gid, token = parse_gallery_url("https://exhentai.org/g/1234567/a1b2c3d4e5/")
    assert gid == "1234567"
    assert token == "a1b2c3d4e5"


def test_parse_gallery_url_e_hentai():
    gid, token = parse_gallery_url("https://e-hentai.org/g/9999/abcdef0123/")
    assert gid == "9999"
    assert token == "abcdef0123"


def test_parse_gallery_url_invalid():
    with pytest.raises(ValueError, match="Invalid gallery URL"):
        parse_gallery_url("https://example.com/not/a/gallery")


def test_build_daemon_url_default():
    url = build_daemon_url("127.0.0.1", 7860)
    assert url == "http://127.0.0.1:7860"


def test_build_daemon_url_custom():
    url = build_daemon_url("0.0.0.0", 8080)
    assert url == "http://0.0.0.0:8080"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pandora_daemon/test_cli.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write the CLI implementation**

```python
# pandora_daemon/cli.py
"""Pandora CLI — minimal daemon client for downloading galleries."""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

from pandora_daemon.config import load_config


def parse_gallery_url(url: str) -> tuple[str, str]:
    """Extract (gid, token) from an exhentai/e-hentai gallery URL."""
    match = re.search(r"/g/(\d+)/([0-9a-f]{10})", url)
    if not match:
        raise ValueError(f"Invalid gallery URL: {url}")
    return match.group(1), match.group(2)


def build_daemon_url(host: str, port: int) -> str:
    """Build the daemon base URL from config."""
    return f"http://{host}:{port}"


async def download_command(url: str, daemon_url: str) -> int:
    """Submit a download and monitor progress via WebSocket. Returns exit code."""
    console = Console()
    gid, token = parse_gallery_url(url)

    async with httpx.AsyncClient(base_url=daemon_url, timeout=30.0) as client:
        # Submit download
        resp = await client.post("/api/downloads", json={"gid": gid, "token": token})
        if resp.status_code == 409:
            console.print(f"[yellow]Already queued: {resp.json().get('detail', '')}[/yellow]")
        elif resp.status_code != 200:
            console.print(f"[red]Error submitting download: {resp.status_code} {resp.text}[/red]")
            return 1
        else:
            task_info = resp.json()
            console.print(f"[green]Queued:[/green] {task_info.get('title', gid)}")

    # Monitor via WebSocket
    ws_url = daemon_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
    try:
        import websockets
        async with websockets.connect(ws_url) as ws:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task_id = progress.add_task("Waiting...", total=None)

                async for message in ws:
                    event = json.loads(message)
                    if event.get("gid") != gid:
                        continue

                    ev_type = event.get("event", "")
                    if ev_type == "download_progress":
                        phase = event.get("phase", "")
                        page = event.get("page", 0)
                        total = event.get("total", 0)
                        if total > 0:
                            progress.update(task_id, description=f"{phase}", completed=page, total=total)
                        else:
                            progress.update(task_id, description=f"{phase}...")
                    elif ev_type == "download_complete":
                        progress.update(task_id, description="Done", completed=100, total=100)
                        console.print(f"\n[bold green]Download complete:[/bold green] {event.get('path', '')}")
                        return 0
                    elif ev_type == "download_error":
                        console.print(f"\n[bold red]Download error:[/bold red] {event.get('error', 'unknown')}")
                        return 1
                    elif ev_type == "download_cancelled":
                        console.print("\n[yellow]Download cancelled[/yellow]")
                        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        return 130
    except Exception as e:
        console.print(f"\n[red]WebSocket error: {e}[/red]")
        console.print("[dim]Download continues in background on the daemon.[/dim]")
        return 1

    return 0


def main():
    """Entry point for the `pandora` CLI command."""
    import argparse

    parser = argparse.ArgumentParser(prog="pandora", description="Pandora CLI — ExHentai daemon client")
    subparsers = parser.add_subparsers(dest="command")

    dl_parser = subparsers.add_parser("download", aliases=["dl"], help="Download a gallery via daemon")
    dl_parser.add_argument("url", help="Gallery URL (e.g. https://exhentai.org/g/123456/abcdef0123/)")

    args = parser.parse_args()

    if args.command in ("download", "dl"):
        config_path = Path("~/.config/pandora/config.toml").expanduser()
        config = load_config(config_path)
        daemon_url = build_daemon_url(config.server.host, config.server.port)
        exit_code = asyncio.run(download_command(args.url, daemon_url))
        sys.exit(exit_code)
    else:
        parser.print_help()
        sys.exit(0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_cli.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```
git add pandora_daemon/cli.py tests/pandora_daemon/test_cli.py
git commit -m "feat: add CLI download command as daemon client"
```

---

### Task 6: Cleanup legacy files and update pyproject.toml

**Files:**
- Modify: `pyproject.toml`
- Delete: `cli.py` (root)
- Delete: `downloader.py` (root)

- [ ] **Step 1: Update pyproject.toml**

Change the `[project.scripts]` section and add `websockets` dependency:

```toml
[project]
name = "pandora"
version = "0.2.0"
description = "Open the box. Browse, search, and download from ExHentai — daemon + multi-frontend."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "beautifulsoup4>=4.14.3",
    "fastapi>=0.115",
    "httpx>=0.28.1",
    "rich>=14.3.3",
    "tomli-w>=1.0",
    "uvicorn>=0.34",
    "websockets>=13.0",
]

[project.scripts]
pandora = "pandora_daemon.cli:main"
pandora-daemon = "pandora_daemon.__main__:main"
```

Remove `textual` from dependencies (legacy TUI dependency).

- [ ] **Step 2: Delete legacy files**

Delete: `cli.py` (root level)
Delete: `downloader.py` (root level)
Delete: `tui.py` (root level, if exists)

- [ ] **Step 3: Verify no imports break**

Run: `uv run pytest tests/ -v`
Expected: All tests pass. No code imports the deleted files.

- [ ] **Step 4: Commit**

```
git add pyproject.toml
git rm cli.py downloader.py
git rm tui.py  # if exists
git commit -m "chore: update pyproject.toml, remove legacy CLI and downloader"
```

---

## Verification

Run the full test suite:
```
uv run pytest tests/ -v
```

All existing tests (203 daemon + 77 API) plus new tests (TagDatabase 9 + routes 4 + lifecycle 1 + streaming 1 + CLI 5 = 20) should pass.

Verify CLI entry point:
```
uv run pandora --help
uv run pandora download --help
```
