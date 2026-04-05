use std::collections::HashMap;
use serde::Deserialize;

/// Gallery list item from /api/homepage, /api/search, /api/popular, /api/watched, /api/favorites
#[derive(Debug, Clone, Deserialize)]
pub struct GalleryItem {
    pub gid: String,
    pub token: String,
    pub title: String,
    pub category: String,
    pub uploader: String,
    pub thumb_url: String,
    pub posted: String,
    pub rating: f64,
    pub pages: u32,
    pub rated: bool,
    pub thumb_width: u32,
    pub thumb_height: u32,
    pub url: String,
}

/// Full gallery detail from /api/gallery/{gid}/{token}
#[derive(Debug, Clone, Deserialize)]
pub struct GalleryDetail {
    pub gid: String,
    pub token: String,
    pub title: String,
    pub title_jpn: Option<String>,
    pub category: String,
    pub uploader: String,
    pub cover_url: String,
    pub tags: HashMap<String, Vec<String>>,
    pub pages: u32,
    pub size: String,
    pub posted: String,
    pub favorite_slot: Option<i32>,
    #[serde(default)]
    pub preview_pages: u32,
    #[serde(default)]
    pub thumb_urls: Vec<String>,
    #[serde(default)]
    pub rating: f64,
    #[serde(default)]
    pub rating_count: u32,
    #[serde(default)]
    pub favorite_count: u32,
    #[serde(default)]
    pub torrent_count: u32,
    #[serde(default)]
    pub comments: Vec<Comment>,
    #[serde(default)]
    pub comments_has_more: bool,
    #[serde(default)]
    pub api_uid: String,
    #[serde(default)]
    pub api_key: String,
    #[serde(default)]
    pub url: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Comment {
    pub id: i64,
    pub user: String,
    pub comment: String,
    pub score: i64,
    pub time: String,
    pub is_uploader: bool,
    pub vote_up_able: bool,
    pub vote_down_able: bool,
    pub vote_up_ed: bool,
    pub vote_down_ed: bool,
    pub editable: bool,
    #[serde(default)]
    pub last_edited: String,
}

/// Tag suggestion from /api/tags/suggest
#[derive(Debug, Clone, Deserialize)]
pub struct TagSuggestion {
    pub namespace: String,
    pub tag: String,
    pub translation: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SuggestResponse {
    pub suggestions: Vec<TagSuggestion>,
}

/// Favorites response from /api/favorites
#[derive(Debug, Clone, Deserialize)]
pub struct FavoritesResponse {
    pub categories: Vec<FavoriteCategory>,
    pub galleries: Vec<GalleryItem>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct FavoriteCategory {
    pub slot: i32,
    pub name: String,
    pub count: u32,
}

/// Download task from /api/downloads
#[derive(Debug, Clone, Deserialize)]
pub struct DownloadTask {
    pub gid: String,
    pub token: String,
    pub title: String,
    pub total_pages: u32,
    pub output_dir: String,
    pub status: String,
    pub downloaded_pages: u32,
    pub downloaded_thumbs: u32,
    pub cover_downloaded: bool,
    pub metadata_saved: bool,
    pub error: String,
    pub created_at: String,
}

/// WebSocket event from /ws
#[derive(Debug, Clone, Deserialize)]
pub struct WsEvent {
    pub event: String,
    pub gid: Option<String>,
    pub title: Option<String>,
    pub phase: Option<String>,
    pub page: Option<u32>,
    pub total: Option<u32>,
    pub path: Option<String>,
    pub error: Option<String>,
}

/// Downloaded gallery metadata from local metadata.json
#[derive(Debug, Clone, Deserialize)]
pub struct DownloadedGalleryMeta {
    pub gid: String,
    pub token: String,
    pub title: String,
    pub title_jpn: Option<String>,
    pub category: String,
    pub uploader: String,
    pub tags: HashMap<String, Vec<String>>,
    pub pages: u32,
    pub size: String,
    pub posted: String,
    pub rating: f64,
    pub url: String,
    pub downloaded_at: Option<String>,
}

/// Category color mapping
pub fn category_to_color(category: &str) -> ratatui::style::Color {
    use ratatui::style::Color;
    match category.to_lowercase().as_str() {
        "doujinshi" => Color::Red,
        "manga" => Color::Yellow,
        "artist cg" => Color::LightYellow,
        "game cg" => Color::Green,
        "western" => Color::LightGreen,
        "non-h" => Color::Blue,
        "image set" => Color::Magenta,
        "cosplay" => Color::LightMagenta,
        "asian porn" => Color::DarkGray,
        "misc" => Color::Gray,
        _ => Color::White,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_gallery_item() {
        let json = r#"{
            "gid": "123", "token": "abc", "title": "Test",
            "category": "Manga", "uploader": "user1",
            "thumb_url": "https://img.com/t.jpg", "posted": "2024-01-01",
            "rating": 4.5, "pages": 20, "rated": false,
            "thumb_width": 250, "thumb_height": 353,
            "url": "https://exhentai.org/g/123/abc/"
        }"#;
        let item: GalleryItem = serde_json::from_str(json).unwrap();
        assert_eq!(item.gid, "123");
        assert_eq!(item.pages, 20);
        assert!((item.rating - 4.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_deserialize_gallery_detail() {
        let json = r#"{
            "gid": "123", "token": "abc", "title": "Test Detail",
            "title_jpn": null, "category": "Doujinshi",
            "uploader": "user1", "cover_url": "https://img.com/c.jpg",
            "tags": {"female": ["maid", "stockings"], "artist": ["someone"]},
            "pages": 30, "size": "50 MB", "posted": "2024-01-01",
            "favorite_slot": null, "preview_pages": 2,
            "thumb_urls": ["https://img.com/t1.jpg"],
            "rating": 4.0, "rating_count": 10,
            "favorite_count": 5, "torrent_count": 1,
            "comments": [
                {"id": 1, "user": "bob", "comment": "nice", "score": 42,
                 "time": "2024-01-01", "is_uploader": false,
                 "vote_up_able": true, "vote_down_able": true,
                 "vote_up_ed": false, "vote_down_ed": false,
                 "editable": false, "last_edited": ""}
            ],
            "comments_has_more": false,
            "api_uid": "uid", "api_key": "key",
            "url": "https://exhentai.org/g/123/abc/"
        }"#;
        let detail: GalleryDetail = serde_json::from_str(json).unwrap();
        assert_eq!(detail.pages, 30);
        assert_eq!(detail.tags["female"], vec!["maid", "stockings"]);
        assert_eq!(detail.comments.len(), 1);
        assert_eq!(detail.comments[0].score, 42);
        assert_eq!(detail.thumb_urls.len(), 1);
    }

    #[test]
    fn test_deserialize_suggest_response() {
        let json = r#"{"suggestions": [
            {"namespace": "female", "tag": "stockings", "translation": "丝袜"}
        ]}"#;
        let resp: SuggestResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.suggestions.len(), 1);
        assert_eq!(resp.suggestions[0].translation, "丝袜");
    }

    #[test]
    fn test_deserialize_ws_event() {
        let json = r#"{"event": "download_progress", "gid": "123", "phase": "pages", "page": 5, "total": 20}"#;
        let ev: WsEvent = serde_json::from_str(json).unwrap();
        assert_eq!(ev.event, "download_progress");
        assert_eq!(ev.page, Some(5));
    }

    #[test]
    fn test_category_color() {
        use ratatui::style::Color;
        assert_eq!(category_to_color("Doujinshi"), Color::Red);
        assert_eq!(category_to_color("Manga"), Color::Yellow);
        assert_eq!(category_to_color("Non-H"), Color::Blue);
    }
}
