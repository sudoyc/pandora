use crate::models::TagSuggestion;

/// ExHentai category bitmask values.
/// When a bit is SET, the category is EXCLUDED from search.
pub const CATEGORIES: &[(&str, u32)] = &[
    ("Doujinshi", 2),
    ("Manga", 4),
    ("Artist CG", 8),
    ("Game CG", 16),
    ("Western", 512),
    ("Non-H", 256),
    ("Image Set", 32),
    ("Cosplay", 64),
    ("Asian Porn", 128),
    ("Misc", 1),
];

#[derive(Debug, Default)]
pub struct SearchState {
    pub active: bool,
    pub input: String,
    pub(crate) cursor_pos: usize,
    pub suggestions: Vec<TagSuggestion>,
    pub selected_suggestion: Option<usize>,
    pub suggestion_scroll: usize,
    pub filter_active: bool,
    pub filter_cursor: usize,
    pub excluded_categories: u32,
    pub min_rating: u32,
    pub min_pages: u32,
    pub suggest_generation: u64,
}

impl SearchState {
    pub fn category_bitmask(&self) -> Option<u32> {
        if self.excluded_categories == 0 {
            None // no filtering — all included
        } else {
            // Invert excluded → included for daemon API
            Some((!self.excluded_categories) & 1023)
        }
    }

    pub fn adjust_suggestion_scroll(&mut self, visible_count: usize) {
        if visible_count == 0 {
            return;
        }
        if let Some(sel) = self.selected_suggestion {
            if sel < self.suggestion_scroll {
                self.suggestion_scroll = sel;
            } else if sel >= self.suggestion_scroll + visible_count {
                self.suggestion_scroll = sel - visible_count + 1;
            }
        }
    }

    pub fn toggle_category(&mut self) {
        if let Some(&(_, bit)) = CATEGORIES.get(self.filter_cursor) {
            self.excluded_categories ^= bit;
        }
    }

    pub fn is_category_included(&self, index: usize) -> bool {
        if let Some(&(_, bit)) = CATEGORIES.get(index) {
            self.excluded_categories & bit == 0
        } else {
            true
        }
    }

    pub fn cycle_min_rating(&mut self) {
        self.min_rating = match self.min_rating {
            0 => 2,
            2 => 3,
            3 => 4,
            4 => 5,
            _ => 0,
        };
    }

    pub fn insert_char(&mut self, c: char) {
        self.input.insert(self.cursor_pos, c);
        self.cursor_pos += c.len_utf8();
    }

    pub fn delete_char(&mut self) {
        if self.cursor_pos > 0 {
            let prev = self.input[..self.cursor_pos]
                .char_indices()
                .next_back()
                .map(|(i, _)| i)
                .unwrap_or(0);
            self.input.replace_range(prev..self.cursor_pos, "");
            self.cursor_pos = prev;
        }
    }

    pub fn insert_tag(&mut self, namespace: &str, tag: &str) {
        let prefix = namespace_to_prefix(namespace);
        let formatted = format!("{}\"{}$\" ", prefix, tag);
        let before = &self.input[..self.cursor_pos];
        let last_space = before.trim_end().rfind(' ').map(|i| i + 1).unwrap_or(0);
        self.input.replace_range(last_space..self.cursor_pos, &formatted);
        self.cursor_pos = last_space + formatted.len();
        self.suggestions.clear();
        self.selected_suggestion = None;
    }

    pub fn extract_last_keyword(&self) -> &str {
        let text = &self.input[..self.cursor_pos];
        let trimmed = text.trim_end();
        let last_space = trimmed.rfind(' ').map(|i| i + 1).unwrap_or(0);
        let keyword = &trimmed[last_space..];
        if keyword.contains("$\"") {
            ""
        } else {
            keyword
        }
    }

    pub fn reset(&mut self) {
        self.active = false;
        self.input.clear();
        self.cursor_pos = 0;
        self.suggestions.clear();
        self.selected_suggestion = None;
        self.suggestion_scroll = 0;
        self.filter_active = false;
    }
}

fn namespace_to_prefix(ns: &str) -> &str {
    match ns {
        "artist" => "a:",
        "cosplayer" => "cos:",
        "character" => "c:",
        "female" => "f:",
        "group" => "g:",
        "language" => "l:",
        "male" => "m:",
        "misc" => "",
        "mixed" => "x:",
        "other" => "o:",
        "parody" => "p:",
        "reclass" => "r:",
        _ => "",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_category_toggle() {
        let mut s = SearchState::default();
        assert!(s.is_category_included(0));
        s.filter_cursor = 0;
        s.toggle_category();
        assert!(!s.is_category_included(0));
        s.toggle_category();
        assert!(s.is_category_included(0));
    }

    #[test]
    fn test_insert_tag() {
        let mut s = SearchState::default();
        s.input = "some text ".to_string();
        s.cursor_pos = 10;
        s.insert_tag("female", "stockings");
        assert!(s.input.contains("f:\"stockings$\""));
    }

    #[test]
    fn test_cycle_min_rating() {
        let mut s = SearchState::default();
        assert_eq!(s.min_rating, 0);
        s.cycle_min_rating();
        assert_eq!(s.min_rating, 2);
        s.cycle_min_rating();
        assert_eq!(s.min_rating, 3);
    }

    #[test]
    fn test_extract_last_keyword() {
        let mut s = SearchState::default();
        s.input = "f:\"maid$\" stock".to_string();
        s.cursor_pos = s.input.len();
        assert_eq!(s.extract_last_keyword(), "stock");
    }

    #[test]
    fn test_category_bitmask_returns_include_mask() {
        let mut s = SearchState::default();
        s.excluded_categories = 2; // exclude doujinshi
        // Should return INCLUDE mask = all bits except 2 = 1021
        assert_eq!(s.category_bitmask(), Some(1021));
    }

    #[test]
    fn test_category_bitmask_none_when_no_exclusions() {
        let s = SearchState::default();
        assert_eq!(s.category_bitmask(), None);
    }

    #[test]
    fn test_suggestion_scroll() {
        let mut s = SearchState::default();
        s.selected_suggestion = Some(7);
        s.adjust_suggestion_scroll(5);
        assert_eq!(s.suggestion_scroll, 3); // 7 - 5 + 1
    }
}
