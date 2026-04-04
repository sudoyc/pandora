#[derive(Debug, Default)]
pub struct ReaderState {
    pub current_page: u32,
    pub total_pages: u32,
    pub gid: String,
    pub token: String,
    pub title: String,
    pub loading: bool,
    pub loading_progress: Option<(u64, u64)>, // (received, total)
    pub error: Option<String>,
}

impl ReaderState {
    pub fn next_page(&mut self) {
        if self.current_page < self.total_pages {
            self.current_page += 1;
        }
    }

    pub fn prev_page(&mut self) {
        if self.current_page > 1 {
            self.current_page -= 1;
        }
    }

    pub fn first_page(&mut self) {
        self.current_page = 1;
    }

    pub fn last_page(&mut self) {
        self.current_page = self.total_pages;
    }
}
