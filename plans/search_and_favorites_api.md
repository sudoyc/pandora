# Plan: Implement Search, Favorites, and Popular APIs

**Goal:** Expand the `exhentai_api` backend to support Search (with advanced filters), Favorites management (list, add, remove), and Popular/TopList galleries, strictly following TDD and using internal tools.

## Phase 1: Search Implementation

1. **Model Updates:**
   - Create a `SearchParams` or `SearchFilter` dataclass in `exhentai_api/models/search.py` to represent all the advanced search flags (categories, rating limits, text matching toggles, page limits) mapped from `f_cats`, `advsearch`, etc.
   
2. **API Endpoint:**
   - Implement `search(self, query: str = "", params: SearchParams = None, page: int = 0) -> List[GalleryListItem]` in `ExhentaiAPI`.
   - The method will construct the complex query parameters and reuse the existing `parse_gallery_list` parser since the DOM structure of search results is identical to the homepage.
   
3. **Tests:**
   - Write `test_search.py` to mock `httpx` GET requests, verifying that the constructed URL parameters are perfectly formatted and that the response correctly returns `GalleryListItem` objects.

## Phase 2: Favorites Implementation

1. **Model Updates:**
   - Create `FavoriteCategory` dataclass (name and count for slots 0-9).
   
2. **Parsers:**
   - Implement `parse_favorites_list(html: str)` in `exhentai_api/parsers/favorites.py`. This must extract both the user's custom favorite categories (from `.ido`/`.fp`) and the list of favorited galleries (reusing `parse_gallery_list`).

3. **API Endpoints:**
   - `get_favorites(self, favcat: int = -1, page: int = 0)`: Fetches the favorites page.
   - `add_favorite(self, gid: str, token: str, favcat: int = 0, favnote: str = "")`: Submits a POST request to `/gallerypopups.php` to add a gallery to a slot.
   - `remove_favorite(self, gid: str)`: Submits a batch delete POST request to `/favorites.php`.
   
4. **Tests:**
   - Write `test_favorites.py` ensuring GET and POST payloads are accurate and DOM parsing for favorites categories is robust.

## Phase 3: Popular & TopList Implementation

1. **Popular API:**
   - Endpoint: `get_popular(self) -> List[GalleryListItem]`
   - URL: `/popular`. Reuses `parse_gallery_list`.
   
2. **TopList API:**
   - Endpoint: `get_toplist(self, category: str = "all", timeframe: str = "15")`
   - Parser: Create `parse_toplist` to handle the `.ido` structure on `/toplist.php`.
   - Tests: Ensure fetching and parsing logic for the toplist tables is covered.

## Phase 4: CLI Downloader & Documentation Updates

1. Enhance `downloader.py` or create `cli.py` to allow searching and downloading favorites from the command line.
2. Update `docs/api_reference.md` with the newly added methods.
3. Mark tasks as complete in `CLAUDE.md` and `README.md`.
