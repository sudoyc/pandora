# Ehviewer_CN_SXJ

A Python/Textual-based TUI gallery browser and downloader for Exhentai/E-Hentai.

## Current State
- `exhentai_api`: Core data fetching and parsing logic implemented.
  - Implemented `get_homepage()`.
  - Implemented `get_gallery_details()` to extract robust gallery metadata.
  - Implemented `get_image_url()` supporting dynamic API reloading via tokens.
- `docs/api_reference.md`: Formal API documentation is available for all completed endpoints.
- `tui.py`: Functional 3-pane TUI layout prototype (to be integrated with new API).
- `downloader.py`: Simple CLI script for full gallery downloads, supports pagination and async concurrent downloads.

## Next Steps
- Continue expanding `exhentai_api` to include core endpoints (See `plans/search_and_favorites_api.md` for full breakdown):
  - Search functionality (`search` with complex parameter building)
  - Favorites management (`get_favorites`, `add_favorite`, `remove_favorite`)
  - Popular / TopList