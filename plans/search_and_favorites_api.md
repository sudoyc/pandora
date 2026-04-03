# Plan: Implement Search, Favorites, and Popular APIs

**Goal:** Expand the `exhentai_api` backend to support Search (with advanced filters), Favorites management (list, add, remove), and Popular/TopList galleries, strictly following TDD and using internal tools.

## Phase 1: Search Implementation

1. **Model Updates:**
   - Create a `SearchParams` dataclass in `exhentai_api/models/search.py`.
   - Fields should accurately mirror `ListUrlBuilder.java` parameters: `f_search` (str), `f_cats` (int), `advsearch` (bool).
   - Advanced toggles (bool mapped to `"on"`/None): `f_sname`, `f_stags`, `f_sdesc`, `f_storr`, `f_sto`, `f_sdt1`, `f_sdt2`, `f_sh`, `f_sr`, `f_sp`.
   - Advanced values: `f_srdd` (int for rating), `f_spf` (int, page from), `f_spt` (int, page to).

2. **API Endpoint:**
   - Implement `search(self, params: SearchParams, page: int = 0) -> List[GalleryListItem]` in `ExhentaiAPI`.
   - The method constructs the URL from params. Categories bitmask should follow `(~mCategory) & 1023` logic.
   - Reuse the `parse_gallery_list` parser for DOM parsing.
   
3. **Tests:**
   - Write `test_search.py` checking the generated URL query string for accuracy based on `SearchParams` state.

## Phase 2: Favorites Implementation

1. **Model Updates:**
   - Create `FavoriteCategory` dataclass containing `slot` (int), `name` (str), and `count` (int).
   - Create `FavoritesResponse` containing `categories` (List[FavoriteCategory]) and `galleries` (List[GalleryListItem]).
   
2. **Parsers:**
   - Implement `parse_favorites_list(html: str)` in `exhentai_api/parsers/favorites.py`. 
   - Parse `.ido > .fp`. Extract `count` from `fp.child(0)` and `name` from `fp.child(2)`. Read slots 0-9.
   - Use `parse_gallery_list` to parse the main gallery table.

3. **API Endpoints:**
   - `get_favorites(self, favcat: int = -1, page: int = 0) -> FavoritesResponse`: GET to `/favorites.php` (append `?favcat=X` if valid).
   - `add_favorite(self, gid: str, token: str, favcat: int = 0, favnote: str = "")`: POST to `/gallerypopups.php?gid={gid}&t={token}&act=addfav`. Payload: `{"favcat": str(favcat) or "favdel", "favnote": favnote, "submit": "Apply Changes", "update": "1"}`.
   - `modify_favorites(self, gids: List[str], ddact: str)`: POST batch update to `/favorites.php`. `ddact` is `"delete"` or `"fav0"`-`"fav9"`. Payload: `{"ddact": ddact, "apply": "Apply"}` + dynamically add `modifygids[]` for each gid.
   
4. **Tests:**
   - Write `test_favorites.py` mocking `httpx` and validating the correct form payload structures and category parser mapping.

## Phase 3: Popular & TopList Implementation

1. **Popular API:**
   - Endpoint: `get_popular(self) -> List[GalleryListItem]`
   - URL: `/popular`. Reuses the standard `parse_gallery_list`.
   
2. **TopList API:**
   - Model: Create `TopListItem` (type, name, link).
   - Endpoint: `get_toplist(self, tl: str = "15") -> List[TopListItem]` (Timeframes: 15=All-Time, 11=Past Year, 12=Past Month, 13=Yesterday).
   - URL: `/toplist.php?tl={tl}` (Note: Usually bound to e-hentai.org as exhentai lacks it, but we'll fetch from the active client host).
   - Parser: Create `parse_toplist(html)` in `parsers/toplist.py`. Parses `.ido`, extracting `.tun` items.
   
3. **Tests:**
   - Write `test_popular_toplist.py` to verify logic.

## Phase 4: CLI Downloader & Documentation Updates

1. Enhance `downloader.py` or create `cli.py` to allow searching and downloading favorites from the command line.
2. Update `docs/api_reference.md` with the newly added methods.
3. Mark tasks as complete in `CLAUDE.md` and `README.md`.
