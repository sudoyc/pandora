use std::collections::HashMap;
use std::num::NonZeroUsize;

use image::DynamicImage;
use lru::LruCache;
use ratatui_image::picker::Picker;
use ratatui_image::protocol::StatefulProtocol;
use tokio::sync::mpsc;

use crate::client::DaemonClient;
use crate::event::AppEvent;
use crate::state::*;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppMode {
    Browse,
    Read,
    Search,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PageSource {
    Homepage,
    Popular,
    Toplist,
    Watched,
    Favorites,
    Downloaded,
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
    pub page_image: Option<DynamicImage>,
    pub status_msg: String,
    pub show_help: bool,
    pub should_quit: bool,
    pub pending_g: bool,

    pub picker: Picker,
    pub image_states: HashMap<String, StatefulProtocol>,
    pub page_image_state: Option<StatefulProtocol>,

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
            page_image: None,
            status_msg: String::new(),
            show_help: false,
            should_quit: false,
            pending_g: false,
            picker,
            image_states: HashMap::new(),
            page_image_state: None,
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
        self.gallery_list.loading = true;
        let page = self.gallery_list.current_page;
        match self.page_source {
            PageSource::Homepage => {
                self.spawn_fetch(|c| async move {
                    AppEvent::GalleriesLoaded(c.get_homepage().await)
                });
            }
            PageSource::Popular => {
                self.spawn_fetch(|c| async move {
                    AppEvent::GalleriesLoaded(c.get_popular().await)
                });
            }
            PageSource::Toplist => {
                self.spawn_fetch(|c| async move {
                    AppEvent::GalleriesLoaded(c.get_toplist("15").await)
                });
            }
            PageSource::Watched => {
                self.spawn_fetch(move |c| async move {
                    AppEvent::GalleriesLoaded(c.get_watched(page).await)
                });
            }
            PageSource::Favorites => {
                self.spawn_fetch(move |c| async move {
                    match c.get_favorites(-1, page).await {
                        Ok(resp) => AppEvent::GalleriesLoaded(Ok(resp.galleries)),
                        Err(e) => AppEvent::GalleriesLoaded(Err(e)),
                    }
                });
            }
            PageSource::Downloaded => {
                self.gallery_list.loading = false;
                self.status_msg = "Downloaded view: not yet implemented".to_string();
            }
        }
    }

    pub fn load_selected_detail(&mut self) {
        if let Some(item) = self.gallery_list.selected_item() {
            let gid = item.gid.clone();
            let token = item.token.clone();
            self.spawn_fetch(move |c| async move {
                AppEvent::DetailLoaded(c.get_gallery_detail(&gid, &token).await)
            });
        }
    }

    pub fn request_thumbnail(&mut self, url: String) {
        if self.image_cache.contains(&url) {
            return;
        }
        let tx = self.tx.clone();
        let client = self.client.clone();
        tokio::spawn(async move {
            match client.proxy_image(&url).await {
                Ok(bytes) => match image::load_from_memory(&bytes) {
                    Ok(img) => {
                        let _ = tx.send(AppEvent::ThumbnailLoaded { url, image: img });
                    }
                    Err(e) => {
                        let _ = tx.send(AppEvent::ImageError {
                            url,
                            error: e.to_string(),
                        });
                    }
                },
                Err(e) => {
                    let _ = tx.send(AppEvent::ImageError { url, error: e });
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
