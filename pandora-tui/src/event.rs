use crossterm::event::KeyEvent;
use image::DynamicImage;

use crate::models::*;

/// All events flowing into the main App::update() loop.
pub enum AppEvent {
    /// Terminal key press
    Key(KeyEvent),
    /// Tick for periodic updates (e.g., debounce timers)
    Tick,

    // ── Daemon responses ──
    GalleriesLoaded(Result<Vec<GalleryItem>, String>),
    DetailLoaded(Result<GalleryDetail, String>),
    FavoritesLoaded(Result<FavoritesResponse, String>),
    SuggestionsLoaded(Result<Vec<TagSuggestion>, String>),
    DownloadSubmitted(Result<DownloadTask, String>),
    DownloadsRefreshed(Result<Vec<DownloadTask>, String>),

    // ── Image events ──
    ThumbnailLoaded { url: String, image: DynamicImage },
    PageImageLoaded { page: u32, image: DynamicImage },
    PageImageProgress { page: u32, received: u64, total: u64 },
    ImageError { url: String, error: String },

    // ── WebSocket events ──
    WsEvent(WsEvent),
    WsDisconnected,
    WsReconnected,
}
