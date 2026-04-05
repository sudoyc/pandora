use crate::models::*;
use reqwest::Client;

#[derive(Clone)]
pub struct DaemonClient {
    http: Client,
    base_url: String,
}

impl DaemonClient {
    pub fn new(base_url: &str) -> Self {
        let http = Client::builder()
            .pool_max_idle_per_host(10)
            .build()
            .unwrap_or_else(|_| Client::new());
        Self {
            http,
            base_url: base_url.trim_end_matches('/').to_string(),
        }
    }

    pub fn ws_url(&self) -> String {
        self.base_url
            .replace("http://", "ws://")
            .replace("https://", "wss://")
            + "/ws"
    }

    // ── Browse ──

    pub async fn get_homepage(&self) -> Result<Vec<GalleryItem>, String> {
        let resp = self.http
            .get(format!("{}/api/homepage", self.base_url))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        resp.json::<Vec<GalleryItem>>().await.map_err(|e| e.to_string())
    }

    pub async fn search(
        &self,
        keyword: &str,
        page: u32,
        category: Option<u32>,
        min_rating: Option<u32>,
    ) -> Result<Vec<GalleryItem>, String> {
        let mut url = format!(
            "{}/api/search?keyword={}&page={}",
            self.base_url,
            urlencoding::encode(keyword),
            page
        );
        if let Some(cat) = category {
            url.push_str(&format!("&category={}", cat));
        }
        if let Some(rating) = min_rating {
            url.push_str(&format!("&min_rating={}", rating));
        }
        let resp = self.http.get(&url).send().await.map_err(|e| e.to_string())?;
        resp.json().await.map_err(|e| e.to_string())
    }

    pub async fn get_popular(&self) -> Result<Vec<GalleryItem>, String> {
        let resp = self.http
            .get(format!("{}/api/popular", self.base_url))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        resp.json().await.map_err(|e| e.to_string())
    }

    pub async fn get_toplist(&self, tl: &str) -> Result<Vec<GalleryItem>, String> {
        let resp = self.http
            .get(format!("{}/api/toplist?tl={}", self.base_url, tl))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        resp.json().await.map_err(|e| e.to_string())
    }

    pub async fn get_watched(&self, page: u32) -> Result<Vec<GalleryItem>, String> {
        let resp = self.http
            .get(format!("{}/api/watched?page={}", self.base_url, page))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        resp.json().await.map_err(|e| e.to_string())
    }

    // ── Gallery ──

    pub async fn get_gallery_detail(
        &self,
        gid: &str,
        token: &str,
    ) -> Result<GalleryDetail, String> {
        let resp = self.http
            .get(format!("{}/api/gallery/{}/{}", self.base_url, gid, token))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        resp.json().await.map_err(|e| e.to_string())
    }

    pub async fn get_page_image(
        &self,
        gid: &str,
        token: &str,
        page: u32,
    ) -> Result<reqwest::Response, String> {
        self.http
            .get(format!(
                "{}/api/gallery/{}/{}/page/{}",
                self.base_url, gid, token, page
            ))
            .send()
            .await
            .map_err(|e| e.to_string())
    }

    pub async fn get_thumb_image(
        &self,
        gid: &str,
        token: &str,
        page: u32,
    ) -> Result<Vec<u8>, String> {
        let resp = self.http
            .get(format!(
                "{}/api/gallery/{}/{}/thumb/{}",
                self.base_url, gid, token, page
            ))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        if !resp.status().is_success() {
            return Err(format!("HTTP {}", resp.status()));
        }
        let bytes = resp.bytes().await.map_err(|e| e.to_string())?;
        Ok(bytes.to_vec())
    }

    pub async fn prefetch(
        &self,
        gid: &str,
        token: &str,
        current_page: u32,
    ) -> Result<(), String> {
        self.http
            .post(format!(
                "{}/api/gallery/{}/{}/prefetch",
                self.base_url, gid, token
            ))
            .json(&serde_json::json!({"current_page": current_page}))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        Ok(())
    }

    // ── Favorites ──

    pub async fn get_favorites(
        &self,
        slot: i32,
        page: u32,
    ) -> Result<FavoritesResponse, String> {
        let resp = self.http
            .get(format!(
                "{}/api/favorites?slot={}&page={}",
                self.base_url, slot, page
            ))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        resp.json().await.map_err(|e| e.to_string())
    }

    pub async fn add_favorite(&self, gid: &str, token: &str, slot: i32) -> Result<(), String> {
        self.http
            .post(format!("{}/api/favorites", self.base_url))
            .json(&serde_json::json!({"gid": gid, "token": token, "slot": slot}))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        Ok(())
    }

    // ── Downloads ──

    pub async fn submit_download(&self, gid: &str, token: &str) -> Result<DownloadTask, String> {
        let resp = self.http
            .post(format!("{}/api/downloads", self.base_url))
            .json(&serde_json::json!({"gid": gid, "token": token}))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        resp.json().await.map_err(|e| e.to_string())
    }

    pub async fn list_downloads(&self) -> Result<Vec<DownloadTask>, String> {
        let resp = self.http
            .get(format!("{}/api/downloads", self.base_url))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        resp.json().await.map_err(|e| e.to_string())
    }

    // ── Tags ──

    pub async fn suggest_tags(
        &self,
        query: &str,
        limit: u32,
    ) -> Result<SuggestResponse, String> {
        let resp = self.http
            .get(format!(
                "{}/api/tags/suggest?q={}&limit={}",
                self.base_url,
                urlencoding::encode(query),
                limit
            ))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        resp.json().await.map_err(|e| e.to_string())
    }

    // ── Library ──

    pub async fn get_library(&self) -> Result<Vec<DownloadedGalleryMeta>, String> {
        let resp = self.http
            .get(format!("{}/api/library", self.base_url))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        resp.json().await.map_err(|e| e.to_string())
    }

    pub async fn get_library_file(&self, gid: &str, path: &str) -> Result<Vec<u8>, String> {
        let resp = self.http
            .get(format!(
                "{}/api/library/{}/file?path={}",
                self.base_url,
                gid,
                urlencoding::encode(path)
            ))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        if !resp.status().is_success() {
            return Err(format!("HTTP {}", resp.status()));
        }
        let bytes = resp.bytes().await.map_err(|e| e.to_string())?;
        Ok(bytes.to_vec())
    }

    // ── Image proxy ──

    pub async fn proxy_image(&self, url: &str) -> Result<Vec<u8>, String> {
        let resp = self.http
            .get(format!(
                "{}/api/image/proxy?url={}",
                self.base_url,
                urlencoding::encode(url)
            ))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        let bytes = resp.bytes().await.map_err(|e| e.to_string())?;
        Ok(bytes.to_vec())
    }

    // ── Health ──

    pub async fn health_check(&self) -> Result<(), String> {
        self.http
            .get(format!("{}/api/config", self.base_url))
            .timeout(std::time::Duration::from_secs(5))
            .send()
            .await
            .map_err(|e| e.to_string())?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ws_url() {
        let client = DaemonClient::new("http://127.0.0.1:7860");
        assert_eq!(client.ws_url(), "ws://127.0.0.1:7860/ws");
    }

    #[test]
    fn test_ws_url_trailing_slash() {
        let client = DaemonClient::new("http://localhost:7860/");
        assert_eq!(client.ws_url(), "ws://localhost:7860/ws");
    }
}
