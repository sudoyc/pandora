# Ehviewer_CN_SXJ

A Python/Textual-based TUI gallery browser and downloader for Exhentai/E-Hentai.

## Current State
- `exhentai_api`: Core data fetching and parsing logic implemented.
  - Implemented `get_homepage()`.
  - Implemented `get_gallery_details()` to extract robust gallery metadata.
  - Implemented `get_image_url()` supporting dynamic API reloading via tokens.
- `tui.py`: Functional 3-pane TUI layout prototype (to be integrated with new API).
- `downloader.py`: CLI script for full gallery downloads.