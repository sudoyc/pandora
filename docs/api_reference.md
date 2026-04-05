# Exhentai API Reference

Complete reference for the `exhentai_api` package. All methods are async and require `await`.

## Initialization

```python
from exhentai_api import ExhentaiAPI, ExhentaiClient

client = ExhentaiClient(igneous="...", ipb_member_id="...")
api = ExhentaiAPI(client=client)

# Or with context manager (auto-closes):
async with ExhentaiAPI(client=client) as api:
    ...
```

---

## 1. Browse

### `get_homepage(page: int = 0) -> list[GalleryListItem]`
Fetches the main gallery list.

### `search(params: SearchParams, page: int = 0) -> list[GalleryListItem]`
Searches galleries with advanced filters. See `SearchParams` model below.

### `get_popular() -> list[GalleryListItem]`
Fetches the current "What's Hot" popular galleries.

### `get_toplist(tl: str = "15") -> list[TopListItem]`
Fetches toplist rankings. `tl`: `"15"` All-Time, `"11"` Past Year, `"12"` Past Month, `"13"` Yesterday. E-Hentai only.

### `get_watched(page: int = 0) -> list[GalleryListItem]`
Fetches galleries matching the user's watched tags.

### `image_search(file_path: str, similar: bool = True, covers: bool = True, exp: bool = True) -> list[GalleryListItem]`
Searches galleries by image file using SHA1 hash.

---

## 2. Gallery Details

### `get_gallery_details(gid: str, token: str) -> GalleryDetail`
Fetches complete gallery metadata including tags, comments, rating, torrent/archive URLs, api_uid/api_key.

### `get_image_url(gid: str, imgkey: str, page: int, nl: str = None) -> ImageDetail`
Fetches full-resolution image URL.
- Without `nl`: GET viewer page `/s/{imgkey}/{gid}-{page}`.
- With `nl`: POST to `api.php` showpage method (reload/next image).

### `get_gallery_token(gid: int, imgkey: str, page: int) -> str`
Fetches gallery token via `api.php` gtoken method.

---

## 3. Comments & Rating

### `comment_gallery(gid: str, token: str, comment: str, edit_id: int = None) -> list[GalleryComment]`
Posts or edits a comment. Pass `edit_id` to edit an existing comment. Returns updated comment list.

### `vote_comment(api_uid: str, api_key: str, gid: int, token: str, comment_id: int, vote: int) -> VoteCommentResult`
Votes on a comment. `vote`: `1` (up) or `-1` (down). `api_uid`/`api_key` from `GalleryDetail`.

### `rate_gallery(api_uid: str, api_key: str, gid: int, token: str, rating: int) -> RateResult`
Rates a gallery. `rating`: integer 2-10 (representing 1.0-5.0 stars in 0.5 steps).

---

## 4. Favorites

### `get_favorites(favcat: int = -1, page: int = 0, keyword: str = "", sn: bool = False, st: bool = False, sf: bool = False) -> FavoritesResponse`
Fetches user's favorites. `favcat`: slot 0-9 or -1 for all. Supports keyword search with `sn` (name), `st` (tags), `sf` (note) toggles.

### `add_favorite(gid: str, token: str, favcat: int = 0, favnote: str = "") -> str`
Adds gallery to favorite slot 0-9. Pass `favcat=-1` to remove.

### `modify_favorites(gids: list[str], ddact: str) -> str`
Batch action on favorites. `ddact`: `"delete"` or `"fav0"`-`"fav9"`.

---

## 5. Torrents & Archives

### `get_torrent_list(gid: str, token: str) -> list[TorrentItem]`
Fetches available torrents for a gallery.

### `get_archive_list(gid: str, token: str) -> ArchiverData`
Fetches archive download options (Original/Resample) with cost and size info.

### `download_archive(archive_url: str, resolution: str = "org") -> str`
Initiates archive download. `resolution`: `"org"` (original) or `"res"` (resample). Returns download URL.

---

## 6. Tag Management

### `get_mytags() -> list[WatchedTag]`
Fetches user's watched/hidden tag configuration.

### `add_tag(tag_name: str, watched: bool = False, hidden: bool = False, color: str = "", weight: int = 0) -> list[WatchedTag]`
Adds a new tag config. Returns updated list.

### `delete_tag(tag_id: int) -> list[WatchedTag]`
Deletes a tag config by ID. Returns updated list.

---

## 7. User Info

### `get_home_detail() -> HomeDetail`
Fetches home page with image limits and GP statistics.

### `reset_image_limit() -> HomeDetail`
Resets image viewing limit by spending GP. Returns updated home detail.

### `get_profile() -> ProfileResult`
Fetches current user's display name and avatar URL.

---

## Data Models

### `ThumbSprite`
A single thumbnail extracted from a CSS sprite sheet (used in `gdtm` preview mode).
- `url` (str): Sprite image URL
- `offset_x` (int): CSS background-position x (pixels, positive = crop from left)
- `offset_y` (int): CSS background-position y (pixels, positive = crop from top)
- `width` (int): Thumbnail width in pixels
- `height` (int): Thumbnail height in pixels

### `GalleryListItem`
Gallery card in list views.
- `gid`, `token`, `title`, `category`, `uploader`, `thumb_url`, `posted` (str)
- `rating` (float), `pages` (int), `rated` (bool), `thumb_width`, `thumb_height` (int)
- `url` (property): Full gallery URL.

### `GalleryDetail`
Full gallery metadata.
- `gid`, `token`, `title`, `title_jpn`, `category`, `uploader`, `cover_url`, `posted`, `size` (str)
- `tags` (Dict[str, List[str]]): Tags grouped by namespace.
- `pages`, `preview_pages`, `rating_count`, `favorite_count`, `torrent_count` (int)
- `rating` (float)
- `favorite_slot` (Optional[int]): Slot 0-9 if favorited, else None.
- `torrent_url`, `archive_url`, `api_uid`, `api_key` (str)
- `parent_url` (Optional[str])
- `newer_versions` (List[dict]): Each has `gid`, `token`, `title`, `posted`.
- `comments` (list[GalleryComment])
- `comments_has_more` (bool)
- `viewer_urls` (List[str]): Viewer page URLs (`/s/{imgkey}/{gid}-{page}`).
- `thumb_urls` (List[str]): Page thumbnail image URLs (extracted from `.gdtm`/`.gdtl` elements or fallback CSS parsing).
- `thumb_sprites` (List[ThumbSprite]): CSS sprite crop coordinates for sprite-mode thumbnails. Empty if thumbnails are individual images (`gdtl` mode).

### `ImageDetail`
Image viewer result.
- `gid` (str), `page` (int), `image_url` (str), `nl` (str): Reload token.

### `SearchParams`
Search query builder.
- `keyword` (str), `category_mask` (int)
- `advanced` (bool), `search_name`/`search_tags`/`search_desc`/`search_torrent` (bool)
- `min_rating` (int), `show_expunged` (bool)
- `page_from`/`page_to` (int)
- `to_dict() -> dict`: Converts to URL query parameters.

### `FavoritesResponse`
- `categories` (list[FavoriteCategory]): Slots with name and count.
- `galleries` (list[GalleryListItem])

### `FavoriteCategory`
- `slot` (int), `name` (str), `count` (int)

### `GalleryComment`
- `id` (int), `score` (int), `user` (str), `comment` (str), `time` (str)
- `is_uploader`, `vote_up_able`, `vote_down_able`, `vote_up_ed`, `vote_down_ed`, `editable` (bool)
- `last_edited` (str)

### `TorrentItem`
- `url` (str), `name` (str)

### `ArchiveOption`
- `cost` (str), `size` (str), `url` (str)

### `ArchiverData`
- `original`, `resample` (Optional[ArchiveOption]), `funds` (str)

### `HomeDetail`
- `image_used`, `image_total`, `reset_cost` (int)
- `gp_from_gallery`, `gp_from_torrent`, `gp_from_archive`, `gp_from_hath`, `moderation_power` (int)

### `ProfileResult`
- `display_name` (str), `avatar_url` (str)

### `RateResult`
- `rating` (float), `rating_count` (int)

### `VoteCommentResult`
- `comment_id` (int), `comment_score` (int), `comment_vote` (int)

### `TopListItem`
- `type` (str), `name` (str), `link` (str)

### `WatchedTag`
- `tag_id` (int), `name` (str), `watched` (bool), `hidden` (bool), `color` (str), `weight` (int)

---

## Daemon REST API — Local Database Endpoints

These endpoints manage local data stored in SQLite (`~/.config/pandora/pandora.db`).

### History

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/history?limit=50&offset=0` | List browsing history (newest first) |
| DELETE | `/api/history/{gid}` | Delete single history entry |
| DELETE | `/api/history` | Clear all history |

History is auto-populated when viewing gallery details (`GET /api/gallery/{gid}/{token}`). Max 200 entries.

### Local Favorites

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/local-favorites?limit=50&offset=0` | List local favorites |
| POST | `/api/local-favorites` | Add local favorite (body: `{gid, token, title, category, uploader, thumb_url, posted, rating, pages, title_jpn?}`) |
| DELETE | `/api/local-favorites/{gid}` | Remove local favorite |

### Bookmarks (Reading Progress)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/bookmarks?limit=50&offset=0` | List all bookmarks |
| GET | `/api/bookmarks/{gid}` | Get bookmark for gallery (404 if none) |
| DELETE | `/api/bookmarks/{gid}` | Delete bookmark |

Bookmarks are auto-updated on prefetch (`POST /api/gallery/{gid}/{token}/prefetch`).

### Quick Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/quick-search` | List saved search presets |
| POST | `/api/quick-search` | Add preset (body: `{name, keyword?, category?, min_rating?, page_from?, page_to?}`) → `{id}` |
| DELETE | `/api/quick-search/{search_id}` | Delete preset |

### Filters

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/filters` | List filter rules |
| POST | `/api/filters` | Add filter (body: `{mode, text}`) → `{id}`. Modes: 0=title, 1=uploader, 2=tag, 3=tag_namespace |
| PUT | `/api/filters/{filter_id}` | Toggle filter enabled/disabled |
| DELETE | `/api/filters/{filter_id}` | Delete filter |
