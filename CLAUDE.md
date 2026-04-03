# Ehviewer_CN_SXJ Project Documentation

## 🎯 Project Goal & Current State
This project is building a Python/Textual-based 3-pane TUI gallery browser and downloader (`workspace/`) for Exhentai/E-Hentai. It aims to mimic the efficient file-browser experience of tools like `yazi`/`ranger` while incorporating the rich metadata display of mobile applications (like the `reference_project` EhViewer for Android).

**Current Implementation State (`workspace/`):**
- **`exhentai_api` Package:** A clean, reusable Python package handling the data-fetching and parsing layer.
  - **`api.py`:** High-level API wrapper (`ExhentaiAPI`) managing clients and orchestrating network requests. Currently supports `get_homepage()`.
  - **`client.py`:** Core asynchronous HTTP client (`ExhentaiClient`) handling cookies (`igneous`, `ipb_member_id`), required headers (User-Agent), Sad Panda detection, and retry logic.
  - **`models/`:** Strongly typed `dataclasses` (e.g., `GalleryListItem`, `GalleryDetail`, `Tag`, `ImageDetail`) for data representation.
  - **`parsers/`:** Pure functions for HTML parsing using `BeautifulSoup` (e.g., `gallery.py` for list parsing).
- **`tui.py`:** Functional 3-pane layout using `Textual`. *(Note: Needs to be updated to integrate with the new `exhentai_api`)*.
  - **Left Pane:** Gallery list. Styled to resemble the mobile app using rich text.
  - **Middle Pane:** Thumbnail pages list. 
  - **Right Pane:** Metadata Markdown view.
- **`downloader.py`:** Handles full gallery downloads to the `downloads/` folder.

---

## 🚀 NEXT STEPS: API Expansion & TUI Integration
*(Crucial instruction for the next session)*

Now that the core foundation of `exhentai_api` is complete, the next steps are to expand the API and integrate it with the frontend TUI:

1. **Expand `exhentai_api`:** Implement the remaining endpoints and parsers based on the reverse-engineered reference (See `plans/search_and_favorites_api.md` for execution steps):
   - Detail Pages (`get_gallery_details`) - ✅ DONE
   - Image Viewing (`get_image_url`) - ✅ DONE
   - Search (`search`) - ✅ DONE
   - Favorites (`get_favorites`, `add_favorite`) - ✅ DONE
   - Popular / TopList - ✅ DONE
   - **Important Source Code Reference:** You should look into the parent directory `../reference_project/` (especially its Java parsers and clients) to extract relevant details, logic, and constants to accurately implement the above remaining endpoints.

2. **Implement CLI Downloader:** Before dealing with complex GUI/TUI integrations, build a simple Command Line Interface (CLI) tool. This CLI should:
   - Accept a gallery URL as input.
   - Use `exhentai_api` to parse the details and iterate through image pages.
   - Download the full-resolution images into the `downloads/` directory. - ✅ DONE (Available as `downloader.py`)
3. **GUI / TUI Integration (TODO):** The existing `tui.py` is mostly a prototype. Once the API and CLI downloader are fully robust, design and integrate a proper UI (either Textual-based TUI or a graphical GUI) to consume the `exhentai_api`.

---

## 🛑 IMPORTANT RULES & CONSTRAINTS
- **Tool Usage:** When reading or editing files, you MUST use the built-in `Read`, `Edit`, or `Write` tools. **NEVER use Bash scripts (like `sed`, `cat`, `echo`, `awk`) to read or edit files.** This avoids unnecessary permission prompts and ensures safe file handling.
- **Python Environment:** The host system is Arch Linux, which has very strict Python environment isolation (`PEP 668`). When executing Python scripts or installing packages, **always use `uv`** (e.g., `uv run python script.py`, `uv pip install <package>`, `uv run pytest`). Never use plain `pip install` or `python` globally.

---

## 📚 Exhentai Data Parsing & API Reference
*(Comprehensive learnings reverse-engineered from the Android `reference_project`'s Java parsers)*

To build the `exhentai-api`, you must strictly adhere to these scraping rules, HTML structures, and API endpoints discovered in the reference code:

### 1. Gallery List Page & Search (`GalleryListParser.java`, `ListUrlBuilder.java`)
- **Main Container:** All gallery rows/blocks are inside the `.itg` class container.
- **Gallery URL & Token:** Must be extracted from `<td class="gl3c"><a href="...">` using the regex `/(?:g|mpv)/(\d+)/([0-9a-f]{10})`.
- **Title:** Extract the deepest text node inside the `.glname` div.
- **Category:** The text of the element with class `.cn` or `.cs`. Map this to constants (e.g., DOUJINSHI, MANGA, NON-H).
- **Uploader:** Extracted from `<td class="glhide">` or `<td class="gl4c">`.
- **Thumbnail (Image):** Found in `.glthumb img`, `.gl1e img`, or `.gl3t img` (depending on user view mode). Prefer `data-src` over `src` to handle lazy loading.
- **Thumbnail (Dimensions):** Must be extracted from the `style` tag (e.g., `height:200px;width:150px`) using regex.
- **Rating:** The visual star rating is sprite-based. It is calculated by parsing the CSS background `x` and `y` offsets of elements with the class `.ir` (or `.irr`, `.irg`, `.irb`).
- **Search Query Construction (URL Params):**
  - `f_search`: The main keyword or query string.
  - `f_cats`: An integer bitmask used to filter out specific gallery categories.
  - `advsearch=1`: Flag to enable advanced search fields.
  - `f_sname`, `f_stags`, `f_sdesc`, `f_storr`: Toggles to search name, tags, description, or torrents.
  - `f_sr`: Boolean to enable minimum rating filter.
  - `f_srdd`: The actual integer value for the minimum rating limit (2, 3, 4, 5).
  - `f_sh`: Boolean to show expunged galleries.
  - `f_sp`, `f_spf`, `f_spt`: Boolean and values for Page limit filters (Pages from / Pages to).

### 2. Gallery Detail Parsing (`GalleryDetailParser.java`)
- **Main Container:** The entire detail block is inside `.gm`.
- **Title:** `#gn` (English/Romanized) and `#gj` (Original Japanese).
- **Category:** `#gdc > .cn` or `#gdc > .cs`.
- **Uploader:** `#gdn`.
- **Cover Image:** The high-res cover is a background image on `#gd1`. Extract `url(...)` from its CSS `style` attribute using regex.
- **Tags:** The `#taglist` table contains `<tbody> > <tr>`. For each row:
  - `td[0]` contains the namespace (e.g., `artist:`, `parody:`).
  - `td[1]` contains multiple `<a>` tags which are the actual tags.
- **Metadata (Pages, Size, Posted Date):** Located in the `#gdd` table structure.
- **Favorite Status:** Check `#gdf`. If the text is "Add to Favorites", it is not favorited. If it says something else, it is favorited in a specific slot.

### 3. Thumbnails / Preview Pages (Image Grids)
- **Pagination:** The total number of preview pages is found by parsing the `.ptt` pagination table at the top or bottom of the gallery details.
- **Thumbnail Links (Image Viewers):**
  - **Normal/Small mode:** `<div class="gdtm">`. The thumbnail itself is a CSS sprite (background image with `x` and `y` offsets).
  - **Large mode:** `<div class="gdtl">`. The thumbnail is a standard `<img src="...">`.
  - In both cases, the `href` of the wrapping anchor tag (`<a>`) points to the specific Image Viewer Page (e.g., `/s/12345/67890-1`).

### 4. Full-Resolution Images (`GalleryPageParser.java`, `api.php`)
- **Image Viewer HTML:** When the user navigates to a preview link, the HTML contains `<img id="img">`. The `src` of this image is the actual full-resolution image URL.
- **Dynamic Fetching via API (`api.php`):** 
  - To load the next image without reloading the whole page, or to reload a broken image (the "Reload Image" link), the client uses an internal JSON API.
  - The image viewer page contains a script block defining variables like an `nl` token.
  - The client POSTs a JSON payload to `https://exhentai.org/api.php`: 
    `{"method": "showpage", "gid": ..., "pagetoken": ..., "imgkey": ..., "showkey": ...}`
  - The API responds with JSON containing an `i3` property, which holds the new image URL.

### 5. Favorites (收藏) (`FavoritesParser.java`)
- **Fetching Favorites List:** 
  - URL: `/favorites.php`
  - Parser: Looks for elements with `.ido` and `.fp` classes to extract the user's custom favorite categories (names and counts, slots 0-9). The galleries themselves are extracted using the standard Gallery List logic.
- **Adding to Favorites:** 
  - URL: `/gallerypopups.php?gid=[gid]&t=[token]&act=addfav`
  - Method: POST request submitting form URL-encoded data (`favcat` from 0-9, `favnote`, and `update="1"`). Sending `favcat=-1` represents removal.
- **Modifying/Removing Multiple Favorites (Batch):**
  - Method: POST request directly to the favorites page URL.
  - Payload includes `ddact=delete` (to remove) or `ddact=fav[0-9]` (to move to another slot), along with an array `modifygids[]` containing the gallery IDs to be updated.

### 6. Popular / TopList (热门) (`TopListParser.java`)
- **Popular (What's Hot):**
  - URL: `/popular`
  - Parser: Uses the standard Gallery List parsing logic.
- **TopList:**
  - URL: `/toplist.php` (Note: Only supported on E-Hentai, not EX).
  - Parser: Parses the `.ido` container. It extracts ranking categories (`GALLERY`, `UPLOADER`, `TAGGING`, etc.) and breaks them down into timeframe columns (All Time, Past Year, Past Month, Yesterday) by checking for the `.tun` class.

### 7. Watched / Subscriptions (订阅) (`MyTagLitParser.java`)
- **Fetching Watched Galleries:**
  - URL: `/watched`
  - Parser: Uses the standard Gallery List parsing logic. It specifically checks if the HTML contains the text `<p>You do not have any watched tags` to set an empty state flag (`noWatchedTags=true`).
- **My Tags Configuration (Watched Tags Setup):**
  - URL: `/mytags`
  - Parser: Scans the `#usertags_outer` container. For each tag, it reads:
    - The `title` attribute from `#tagpreview[id]` for the tag name.
    - The `checked` attribute of `#tagwatch[id]` and `#taghide[id]` to determine if it is watched or hidden.
    - The `placeholder` attribute of `#tagcolor[id]` for the custom color.
    - The `value` attribute of `#tagweight[id]` for the tag's weight score.
