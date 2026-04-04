# Ehviewer_CN_SXJ Project Documentation

## Project Goal & Current State

This project is a gallery browser and downloader for Exhentai/E-Hentai, built with a **daemon + multi-frontend** architecture:

- **`exhentai_api`** (Python library): Fully implemented data-fetching and parsing layer, aligned with the Android reference project.
- **`ehviewer-daemon`** (planned): FastAPI-based service layer wrapping `exhentai_api`, providing REST + WebSocket API.
- **Rust TUI** (planned): ratatui-based terminal frontend with image preview (kitty/sixel).
- **Web frontend** (planned): Browser-based frontend, deployable to personal server.
- **CLI tools** (implemented): `cli.py` and `downloader.py` for command-line usage.

### Architecture

```
exhentai_api (Python library, stateless)
        │ import
ehviewer-daemon (Python, FastAPI + WebSocket)
        │ REST + WS (localhost:7860)
        ├── Rust TUI (ratatui + ratatui-image)
        ├── Web frontend (browser)
        └── CLI (direct import or daemon client)
```

### `exhentai_api` Package (complete)

```
exhentai_api/
├── __init__.py          # Exports: ExhentaiAPI, ExhentaiClient, 17 model types
├── api.py               # ExhentaiAPI: 22 async methods covering all endpoints
├── client.py            # ExhentaiClient: cookies, headers, Sad Panda, retry, get_html/post_json/post_form
├── constants.py         # BASE_URL, category constants
├── utils.py             # extract_gallery_token
├── models/
│   ├── gallery.py       # GalleryListItem, GalleryDetail
│   ├── image.py         # ImageDetail
│   ├── search.py        # SearchParams
│   ├── favorites.py     # FavoriteCategory, FavoritesResponse
│   ├── toplist.py       # TopListItem
│   ├── comment.py       # GalleryComment
│   ├── torrent.py       # TorrentItem
│   ├── archive.py       # ArchiveOption, ArchiverData
│   ├── home.py          # HomeDetail
│   ├── profile.py       # ProfileResult
│   ├── vote.py          # RateResult, VoteCommentResult
│   └── tags.py          # Tag, WatchedTag
└── parsers/
    ├── gallery.py       # parse_gallery_list (with rating/pages/thumb)
    ├── gallery_detail.py # parse_gallery_detail (full metadata + comments)
    ├── image.py         # parse_image_viewer, parse_image_api_response
    ├── favorites.py     # parse_favorites_list
    ├── toplist.py       # parse_toplist
    ├── comments.py      # parse_comments
    ├── torrent.py       # parse_torrent_list
    ├── archive.py       # parse_archive_list
    ├── home.py          # parse_home_detail
    ├── profile.py       # parse_profile
    └── mytags.py        # parse_mytags
```

### API Methods Summary

| Category | Methods |
|----------|---------|
| Browse | `get_homepage`, `search`, `get_popular`, `get_toplist`, `get_watched` |
| Gallery | `get_gallery_details`, `get_image_url`, `get_gallery_token` |
| Comments | `comment_gallery`, `vote_comment` |
| Rating | `rate_gallery` |
| Favorites | `get_favorites` (with keyword search), `add_favorite`, `modify_favorites` |
| Torrents/Archive | `get_torrent_list`, `get_archive_list`, `download_archive` |
| Tags | `get_mytags`, `add_tag`, `delete_tag` |
| User | `get_home_detail`, `reset_image_limit`, `get_profile` |
| Search | `image_search` (SHA1-based) |

### Test Coverage

77 tests covering all models, parsers, and API methods. Run with: `uv run pytest tests/ -v`

---

## NEXT STEPS

1. **ehviewer-daemon**: FastAPI service wrapping `exhentai_api` with session management, download queue, caching, config persistence.
2. **Rust TUI**: ratatui + ratatui-image frontend connecting to daemon via REST/WebSocket.
3. **Web frontend**: Browser-based UI, reusing daemon API, deployable to remote server.

---

## RULES & CONSTRAINTS

- **Tool Usage:** MUST use built-in `Read`, `Edit`, `Write` tools. NEVER use Bash (sed/cat/echo/awk) to read or edit files.
- **Python Environment:** Arch Linux with strict PEP 668. Always use `uv` (e.g., `uv run pytest`, `uv pip install`). Never use plain `pip` or `python` globally.

---

## Exhentai Data Parsing Reference

Reverse-engineered from the Android `reference_project`'s Java parsers. See `docs/superpowers/specs/2026-04-04-api-full-alignment-design.md` for the complete design spec.

### Key Parsing Rules

1. **Gallery List**: `.itg` container, `.glname` title, `.cn`/`.cs` category, `.glthumb`/`.gl1e`/`.gl3t` thumbnails (prefer `data-src`), `.ir`/`.irr`/`.irg`/`.irb` rating sprites (formula: `5 - x/16`, y==21 subtract 0.5)
2. **Gallery Detail**: `.gm` container, `#gn`/`#gj` titles, `#gdc` category, `#gdn` uploader, `#gd1` cover (CSS background-image), `#taglist` tags, `#gdd` metadata table, `#gdf` favorite status, `#gd5` torrent/archive links, `#rating_label`/`#rating_count` rating, `#gnd` newer versions
3. **Image Viewer**: `<img id="img">` src, `nl('...')` token regex, `api.php` showpage method for reload
4. **Favorites**: `/favorites.php`, `.ido`/`.fp` for categories (slots 0-9), standard gallery list for items, keyword search via `f_search`/`sn`/`st`/`sf`
5. **Comments**: `#cdiv` container, `.c1` per comment, `.c3` user/time, `.c5` score, `.c6` body, `.c4` vote state, `.c8` last edited
6. **Torrents**: Regex `<td colspan="5"> &nbsp; <a href="...">`, strip `?p=` params
7. **Archive**: Table parsing for Original/Resample options with cost/size
8. **Home**: Regex for image limits (`<strong>N</strong>`), BS4 for GP tables
9. **MyTags**: `#usertags_outer`, DOM IDs `tagpreview{N}`/`tagwatch{N}`/`taghide{N}`/`tagcolor{N}`/`tagweight{N}`
10. **Download**: Reference project uses per-page scraping (primary) + archive ZIP (optional). Per-page: GET `/s/{pToken}/{gid}-{page}` → parse image URL → download. Archive: GET `/archiver.php` → POST form → redirect → ZIP download.

### API Endpoints (api.php JSON POST)

- `votecomment`: `{method, apiuid, apikey, gid, token, comment_id, comment_vote}`
- `rategallery`: `{method, apiuid, apikey, gid, token, rating}`
- `gtoken`: `{method, pagelist: [[gid, imgkey, page]]}`
- `showpage`: `{method, gid, page, imgkey, showkey}`
