use crate::models::{GalleryDetail, GalleryItem};

#[derive(Debug, Default)]
pub struct GalleryListState {
    pub items: Vec<GalleryItem>,
    pub selected: usize,
    pub current_page: u32,
    pub scroll_offset: usize,
    pub detail: Option<GalleryDetail>,
    pub loading: bool,
}

impl GalleryListState {
    pub fn select_next(&mut self) {
        if !self.items.is_empty() {
            self.selected = (self.selected + 1).min(self.items.len() - 1);
        }
    }

    pub fn select_prev(&mut self) {
        self.selected = self.selected.saturating_sub(1);
    }

    pub fn select_first(&mut self) {
        self.selected = 0;
    }

    pub fn select_last(&mut self) {
        if !self.items.is_empty() {
            self.selected = self.items.len() - 1;
        }
    }

    pub fn selected_item(&self) -> Option<&GalleryItem> {
        self.items.get(self.selected)
    }

    pub fn clear(&mut self) {
        self.items.clear();
        self.selected = 0;
        self.current_page = 0;
        self.scroll_offset = 0;
        self.detail = None;
    }

    /// Ensure scroll_offset keeps selected item visible within `visible_count` rows.
    pub fn adjust_scroll(&mut self, visible_count: usize) {
        if visible_count == 0 {
            return;
        }
        if self.selected < self.scroll_offset {
            self.scroll_offset = self.selected;
        } else if self.selected >= self.scroll_offset + visible_count {
            self.scroll_offset = self.selected - visible_count + 1;
        }
    }
}
