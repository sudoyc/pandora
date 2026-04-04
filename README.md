# Pandora

Open the box. Browse, search, and download from ExHentai — daemon + multi-frontend.

## Architecture

```
exhentai_api (Python library)     ── stateless, reusable
        │
pandora-daemon (FastAPI)          ── session, cache, download, image proxy
        │ REST + WebSocket (localhost:7860)
        ├── Rust TUI (ratatui)    ── terminal with image preview
        ├── Web frontend          ── browser, deployable to server
        └── CLI                   ── scripts & automation
```

## Current Status

### `exhentai_api` -- Complete

Fully aligned with the Android reference project. 22 API methods, 17 model types, 11 parsers, 77 tests.

| Category | Methods |
|----------|---------|
| Browse | `get_homepage`, `search`, `get_popular`, `get_toplist`, `get_watched` |
| Gallery | `get_gallery_details`, `get_image_url`, `get_gallery_token` |
| Interaction | `comment_gallery`, `vote_comment`, `rate_gallery` |
| Favorites | `get_favorites`, `add_favorite`, `modify_favorites` |
| Resources | `get_torrent_list`, `get_archive_list`, `download_archive` |
| Tags | `get_mytags`, `add_tag`, `delete_tag` |
| User | `get_home_detail`, `reset_image_limit`, `get_profile` |
| Search | `image_search` (SHA1-based) |

### `pandora-daemon` -- Complete

FastAPI daemon wrapping `exhentai_api` as a local service. 203 tests.

- **Unified image cache** -- all image types cached with LRU eviction (2GB default)
- **Image proxy** -- daemon proxies all image requests, frontends never access exhentai directly
- **Server-side prefetch** -- background prefetch of surrounding pages during browsing
- **Complete offline library** -- downloads produce self-contained gallery clones (metadata + cover + thumbs + pages)
- **WebSocket events** -- real-time download progress, phase-based tracking
- **Config system** -- TOML-based (`~/.config/pandora/config.toml`)
- **REST API** -- 25+ endpoints covering browse, gallery, favorites, downloads, user, config

### CLI Tools -- Complete

- `cli.py` -- Verify access, search galleries, list favorites, download
- `downloader.py` -- Full gallery batch download with pagination

### Rust TUI / Web Frontend -- Planned

See CLAUDE.md for architecture details and next steps.

## Quick Start

### Using the API library directly

```python
import asyncio
from exhentai_api import ExhentaiAPI, ExhentaiClient

async def main():
    client = ExhentaiClient(igneous="...", ipb_member_id="...")
    async with ExhentaiAPI(client=client) as api:
        # Browse
        galleries = await api.get_homepage()
        for g in galleries:
            print(f"{g.title} ({g.rating}*) - {g.pages}p")

        # Search
        from exhentai_api.models.search import SearchParams
        results = await api.search(SearchParams(keyword="fate"))

        # Gallery details
        detail = await api.get_gallery_details("12345", "abcdef1234")
        print(detail.tags, detail.comments)

        # Favorites
        favs = await api.get_favorites(favcat=0, keyword="artist:name")

asyncio.run(main())
```

### Running the daemon

```bash
# Configure credentials first
# Edit ~/.config/pandora/config.toml

# Start daemon on localhost:7860
uv run python -m pandora_daemon
```

## Development

```bash
# Run tests (203 total)
uv run pytest tests/ -v

# Run CLI
uv run python cli.py search "keyword"
uv run python downloader.py "https://exhentai.org/g/12345/abctoken/"
```

## Documentation

- `docs/api_reference.md` -- Full exhentai_api method reference
- `docs/exhentai_api_usage.md` -- Detailed usage guide
- `docs/superpowers/specs/` -- Design specifications
- `docs/superpowers/plans/` -- Implementation plans
- `CLAUDE.md` -- Architecture, daemon API endpoints, development roadmap
