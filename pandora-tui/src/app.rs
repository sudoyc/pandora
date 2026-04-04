use std::num::NonZeroUsize;

use image::DynamicImage;
use lru::LruCache;
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

    pub client: DaemonClient,
    pub tx: mpsc::UnboundedSender<AppEvent>,
}

impl App {
    pub fn new(client: DaemonClient, tx: mpsc::UnboundedSender<AppEvent>) -> Self {
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
