# Ehviewer_CN_SXJ

A Python/Textual-based TUI gallery browser and downloader for Exhentai/E-Hentai.

## Current State
- `exhentai_api`: Core data fetching and parsing logic implemented.
  - Implemented `get_homepage()`.
  - Implemented `get_gallery_details()` to extract robust gallery metadata.
  - Implemented `get_image_url()` supporting dynamic API reloading via tokens.
  - Implemented `search()` for advanced gallery querying.
  - Implemented `get_favorites()`, `add_favorite()`, and `modify_favorites()` for user collections.
  - Implemented `get_popular()` and `get_toplist()` for rankings.
- `docs/api_reference.md`: Formal API documentation is available for all completed endpoints.
- `tui.py`: Functional 3-pane TUI layout prototype (to be integrated with new API).
- `cli.py`: Command line interface to verify access, search galleries, list favorites, and download.
- `downloader.py`: CLI script for full gallery downloads, supports pagination and async downloads.

## Next Steps
- Integrate `exhentai_api` into the `tui.py` frontend components to build a robust Yazi/Ranger-style UI for browsing, searching, and managing favorites.