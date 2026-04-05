use image::DynamicImage;

use crate::models::*;

pub enum AppEvent {
    // Daemon responses
    GalleriesLoaded(Result<Vec<GalleryItem>, String>, u64),
    DetailLoaded(Result<GalleryDetail, String>, u64),
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
