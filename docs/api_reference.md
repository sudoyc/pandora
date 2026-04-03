# Exhentai API Reference

This document describes the core endpoints and models currently implemented in the `exhentai_api` package.

## 1. High-Level API: `ExhentaiAPI`

The primary interface for interacting with the website is the `ExhentaiAPI` class. It orchestrates the HTTP client and the HTML parsers.

```python
from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient

# Initialize with credentials for exhentai.org
client = ExhentaiClient(igneous="...", ipb_member_id="...")
api = ExhentaiAPI(client=client)
```

### `get_homepage(self, page: int = 0) -> List[GalleryListItem]`
Fetches the main gallery list (homepage).
* **Parameters:**
  * `page` (int): The page number to fetch (0-indexed). Defaults to 0.
* **Returns:** A list of `GalleryListItem` instances.

### `get_gallery_details(self, gid: str, token: str) -> GalleryDetail`
Fetches the complete metadata and preview image URLs for a specific gallery.
* **Parameters:**
  * `gid` (str): The Gallery ID.
  * `token` (str): The Gallery Token.
* **Returns:** A `GalleryDetail` instance containing title, tags, uploader, size, pagination info, and preview image URLs.

### `get_image_url(self, gid: str, imgkey: str, page: int, nl: str = None) -> ImageDetail`
Fetches the full-resolution image URL for a specific page in a gallery. It supports the dynamic "reload" mechanism via the `nl` token.
* **Parameters:**
  * `gid` (str): The Gallery ID.
  * `imgkey` (str): The unique image key (found in the URL of the preview image).
  * `page` (int): The image page number (1-indexed).
  * `nl` (str, optional): The reload token. If provided, the API uses a POST request to dynamically reload the image URL (useful to bypass limits or broken images).
* **Returns:** An `ImageDetail` instance containing the `image_url` and the next `nl` token.

### `search(self, params: SearchParams, page: int = 0) -> List[GalleryListItem]`
Searches for galleries using advanced filters and parameters.
* **Parameters:**
  * `params` (`SearchParams`): An object containing search configuration (query, category bitmask, advanced toggles).
  * `page` (int): Page number (0-indexed).
* **Returns:** A list of `GalleryListItem` instances.

### `get_favorites(self, favcat: int = -1, page: int = 0) -> FavoritesResponse`
Fetches a user's favorite galleries and the category list.
* **Parameters:**
  * `favcat` (int): The favorite slot (0-9) to filter by. Defaults to -1 (All).
  * `page` (int): Page number (0-indexed).
* **Returns:** A `FavoritesResponse` containing `categories` and `galleries`.

### `add_favorite(self, gid: str, token: str, favcat: int = 0, favnote: str = "") -> str`
Adds a gallery to a specific favorite slot.
* **Parameters:**
  * `gid`, `token`: Gallery identifiers.
  * `favcat` (int): Slot (0-9). Passing `-1` removes the favorite.
  * `favnote` (str): Optional note for the favorite.
* **Returns:** The raw HTML response string.

### `modify_favorites(self, gids: List[str], ddact: str) -> str`
Batch applies an action to multiple favorited galleries.
* **Parameters:**
  * `gids` (List[str]): List of gallery IDs to modify.
  * `ddact` (str): The action to apply (`"delete"` to remove, `"fav0"`-`"fav9"` to move).
* **Returns:** The raw HTML response string.

### `get_popular(self) -> List[GalleryListItem]`
Fetches the current popular/what's hot galleries.
* **Returns:** A list of `GalleryListItem` instances.

### `get_toplist(self, tl: str = "15") -> List[TopListItem]`
Fetches the toplist galleries (e.g. All-Time, Past Year).
* **Parameters:**
  * `tl` (str): Timeframe parameter (15=All-Time, 11=Past Year, 12=Past Month, 13=Yesterday).
* **Returns:** A list of `TopListItem` instances.

---

## 2. Data Models (`exhentai_api.models`)

### `GalleryListItem`
Represents a single gallery card in a list view (like the homepage or search results).
* `gid` (str): Gallery ID.
* `token` (str): Gallery Token.
* `title` (str): Gallery Title.
* `category` (str): Category (e.g., "Doujinshi", "Manga").
* `uploader` (str): Uploader name.
* `thumb_url` (str): URL to the thumbnail image.
* `posted` (str): Timestamp/Date posted.
* `url` (property -> str): The full Exhentai URL for this gallery.

### `GalleryDetail`
Represents the full metadata parsed from a gallery's detail page.
* `gid` (str)
* `token` (str)
* `title` (str): English/Romanized title.
* `title_jpn` (Optional[str]): Original Japanese title.
* `category` (str)
* `uploader` (str)
* `cover_url` (str): High-res cover image URL.
* `tags` (Dict[str, List[str]]): A dictionary of tags grouped by namespace (e.g., `{"artist": ["name"], "parody": ["game"]}`).
* `pages` (int): Total number of images in the gallery.
* `size` (str): File size string (e.g., "100 MB").
* `posted` (str)
* `favorite_slot` (Optional[int]): The favorite slot index (0-9) if favorited, else `None`.
* `preview_pages` (int): Total number of pages of thumbnails.
* `preview_urls` (List[str]): Extracted URLs to the image viewer pages.

### `ImageDetail`
Represents the result of an image viewer page or an API reload request.
* `gid` (str)
* `page` (int)
* `image_url` (str): The direct URL to the full-resolution image.
* `nl` (str): The token required to reload this image or navigate securely in the future.
