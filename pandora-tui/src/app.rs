use std::collections::HashMap;
use std::num::NonZeroUsize;
use std::sync::Arc;

use image::DynamicImage;
use lru::LruCache;
use ratatui_image::picker::Picker;
use ratatui_image::protocol::StatefulProtocol;
use tokio::sync::mpsc;
use tokio::sync::Semaphore;

use crate::client::DaemonClient;
use crate::event::AppEvent;
use crate::models::GalleryItem;
use crate::state::*;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppMode {
    Browse,
    Read,
    Search,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PageSource {
    Homepage,
    Popular,
    Toplist,
    Watched,
    Favorites,
    Downloaded,
    Search {
        keyword: String,
        category: Option<u32>,
        min_rating: Option<u32>,
    },
}

impl PageSource {
    pub fn label(&self) -> &str {
        match self {
            Self::Homepage => "Homepage",
            Self::Popular => "Popular",
            Self::Toplist => "Toplist",
            Self::Watched => "Watched",
            Self::Favorites => "Favorites",
            Self::Downloaded => "Downloaded",
            Self::Search { .. } => "Search",
        }
    }
}

pub struct App {
    pub mode: AppMode,
    pub page_source: PageSource,
    pub gallery_list: GalleryListState,
    pub reader: ReaderState,
    pub search: SearchState,
    pub downloads: DownloadState,

    pub image_cache: LruCache<String, DynamicImage>,
    pub page_cache: LruCache<String, DynamicImage>,
    pub page_image: Option<DynamicImage>,
    pub status_msg: String,
    pub show_help: bool,
    pub should_quit: bool,
    pub pending_g: bool,
    pub detail_generation: u64,
    pub list_generation: u64,

    pub picker: Picker,
    pub image_states: HashMap<String, StatefulProtocol>,
    pub page_image_state: Option<StatefulProtocol>,
    pub failed_images: std::collections::HashSet<String>,
    pub pending_images: std::collections::HashSet<String>,
    pub pending_pages: std::collections::HashSet<u32>,

    pub suggest_pending: bool,

    pub preload_semaphore: Arc<Semaphore>,

    pub client: DaemonClient,
    pub tx: mpsc::UnboundedSender<AppEvent>,
}

impl App {
    pub fn new(client: DaemonClient, tx: mpsc::UnboundedSender<AppEvent>, picker: Picker) -> Self {
        Self {
            mode: AppMode::Browse,
            page_source: PageSource::Homepage,
            gallery_list: GalleryListState::default(),
            reader: ReaderState::default(),
            search: SearchState::default(),
            downloads: DownloadState::default(),
            image_cache: LruCache::new(NonZeroUsize::new(200).unwrap()),
            page_cache: LruCache::new(NonZeroUsize::new(30).unwrap()),
            page_image: None,
            status_msg: String::new(),
            show_help: false,
            should_quit: false,
            pending_g: false,
            detail_generation: 0,
            list_generation: 0,
            picker,
            image_states: HashMap::new(),
            page_image_state: None,
            failed_images: std::collections::HashSet::new(),
            pending_images: std::collections::HashSet::new(),
            pending_pages: std::collections::HashSet::new(),
            suggest_pending: false,
            preload_semaphore: Arc::new(Semaphore::new(3)),
            client,
            tx,
        }
    }

    pub fn spawn_fetch<F, Fut>(&self, f: F)
    where
        F: FnOnce(DaemonClient) -> Fut + Send + 'static,
        Fut: std::future::Future<Output = AppEvent> + Send,
    {
        let client = self.client.clone();
        let tx = self.tx.clone();
        tokio::spawn(async move {
            let event = f(client).await;
            let _ = tx.send(event);
        });
    }

    pub fn load_current_page(&mut self) {
        self.list_generation += 1;
        let generation = self.list_generation;
        self.gallery_list.loading = true;
        let page = self.gallery_list.current_page;
        match self.page_source {
            PageSource::Homepage => {
                self.spawn_fetch(move |c| async move {
                    AppEvent::GalleriesLoaded(c.get_homepage().await, generation)
                });
            }
            PageSource::Popular => {
                self.spawn_fetch(move |c| async move {
                    AppEvent::GalleriesLoaded(c.get_popular().await, generation)
                });
            }
            PageSource::Toplist => {
                self.spawn_fetch(move |c| async move {
                    AppEvent::GalleriesLoaded(c.get_toplist("15").await, generation)
                });
            }
            PageSource::Watched => {
                self.spawn_fetch(move |c| async move {
                    AppEvent::GalleriesLoaded(c.get_watched(page).await, generation)
                });
            }
            PageSource::Favorites => {
                self.spawn_fetch(move |c| async move {
                    match c.get_favorites(-1, page).await {
                        Ok(resp) => AppEvent::GalleriesLoaded(Ok(resp.galleries), generation),
                        Err(e) => AppEvent::GalleriesLoaded(Err(e), generation),
                    }
                });
            }
            PageSource::Downloaded => {
                let base = self.client.base_url().to_string();
                self.spawn_fetch(move |c| async move {
                    match c.get_library().await {
                        Ok(metas) => {
                            let items: Vec<GalleryItem> = metas
                                .into_iter()
                                .map(|m| {
                                    let thumb_url = m.thumb_url.as_ref().map_or(
                                        String::new(),
                                        |path| format!("{}{}", base, path),
                                    );
                                    GalleryItem {
                                        gid: m.gid,
                                        token: m.token,
                                        title: m.title,
                                        category: m.category,
                                        uploader: m.uploader,
                                        thumb_url,
                                        posted: m.posted,
                                        rating: m.rating,
                                        pages: m.pages,
                                        rated: false,
                                        thumb_width: 0,
                                        thumb_height: 0,
                                        url: m.url,
                                    }
                                })
                                .collect();
                            AppEvent::GalleriesLoaded(Ok(items), generation)
                        }
                        Err(e) => AppEvent::GalleriesLoaded(Err(e), generation),
                    }
                });
            }
            PageSource::Search {
                ref keyword,
                category,
                min_rating,
            } => {
                let keyword = keyword.clone();
                self.spawn_fetch(move |c| async move {
                    AppEvent::GalleriesLoaded(c.search(&keyword, page, category, min_rating).await, generation)
                });
            }
        }
    }

    pub fn load_selected_detail(&mut self) {
        if let Some(item) = self.gallery_list.selected_item() {
            self.detail_generation += 1;
            let generation = self.detail_generation;
            let gid = item.gid.clone();
            let token = item.token.clone();
            self.spawn_fetch(move |c| async move {
                AppEvent::DetailLoaded(c.get_gallery_detail(&gid, &token).await, generation)
            });
        }
    }

    pub fn request_thumbnail(&mut self, url: String) {
        if self.image_cache.contains(&url)
            || self.failed_images.contains(&url)
            || self.pending_images.contains(&url)
        {
            return;
        }
        self.pending_images.insert(url.clone());
        let tx = self.tx.clone();
        let client = self.client.clone();
        tokio::spawn(async move {
            match client.proxy_image(&url).await {
                Ok(bytes) => {
                    let bytes_vec = bytes.to_vec();
                    match tokio::task::spawn_blocking(move || image::load_from_memory(&bytes_vec)).await {
                        Ok(Ok(img)) => {
                            let _ = tx.send(AppEvent::ThumbnailLoaded { url, image: img });
                        }
                        Ok(Err(e)) => {
                            let _ = tx.send(AppEvent::ImageError {
                                url,
                                error: e.to_string(),
                            });
                        }
                        Err(_) => {
                            let _ = tx.send(AppEvent::ImageError {
                                url,
                                error: "image decode task panicked".to_string(),
                            });
                        }
                    }
                }
                Err(e) => {
                    let _ = tx.send(AppEvent::ImageError { url, error: e });
                }
            }
        });
    }

    /// Request a cropped thumbnail via the daemon's thumb endpoint.
    /// Uses "thumb:{gid}:{page}" as cache key.
    pub fn request_gallery_thumb(&mut self, gid: String, token: String, page: u32) {
        let cache_key = format!("thumb:{}:{}", gid, page);
        if self.image_cache.contains(&cache_key)
            || self.failed_images.contains(&cache_key)
            || self.pending_images.contains(&cache_key)
        {
            return;
        }
        self.pending_images.insert(cache_key.clone());
        let tx = self.tx.clone();
        let client = self.client.clone();
        tokio::spawn(async move {
            match client.get_thumb_image(&gid, &token, page).await {
                Ok(bytes) => {
                    let bytes_vec = bytes.to_vec();
                    match tokio::task::spawn_blocking(move || image::load_from_memory(&bytes_vec)).await {
                        Ok(Ok(img)) => {
                            let _ = tx.send(AppEvent::ThumbnailLoaded {
                                url: cache_key,
                                image: img,
                            });
                        }
                        Ok(Err(e)) => {
                            let _ = tx.send(AppEvent::ImageError {
                                url: cache_key,
                                error: e.to_string(),
                            });
                        }
                        Err(_) => {
                            let _ = tx.send(AppEvent::ImageError {
                                url: cache_key,
                                error: "image decode task panicked".to_string(),
                            });
                        }
                    }
                }
                Err(e) => {
                    let _ = tx.send(AppEvent::ImageError {
                        url: cache_key,
                        error: e,
                    });
                }
            }
        });
    }

    /// Get or create a StatefulProtocol for a cached image, keyed by URL.
    pub fn get_image_protocol(&mut self, url: &str) -> Option<&mut StatefulProtocol> {
        if !self.image_cache.contains(url) {
            return None;
        }
        if !self.image_states.contains_key(url) {
            if let Some(img) = self.image_cache.peek(url) {
                let protocol = self.picker.new_resize_protocol(img.clone());
                self.image_states.insert(url.to_string(), protocol);
            }
        }
        self.image_states.get_mut(url)
    }

    /// Get or create a StatefulProtocol for the current page image.
    pub fn get_page_protocol(&mut self) -> Option<&mut StatefulProtocol> {
        if self.page_image.is_some() && self.page_image_state.is_none() {
            let img = self.page_image.as_ref().unwrap();
            self.page_image_state = Some(self.picker.new_resize_protocol(img.clone()));
        }
        self.page_image_state.as_mut()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_page_source_label() {
        assert_eq!(PageSource::Homepage.label(), "Homepage");
        assert_eq!(PageSource::Downloaded.label(), "Downloaded");
    }
}
