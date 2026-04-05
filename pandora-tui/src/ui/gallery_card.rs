use ratatui::prelude::*;
use ratatui::widgets::Widget;
use unicode_width::UnicodeWidthStr;

use crate::models::{category_colors, GalleryItem};

/// Height of a single gallery card in rows.
pub const CARD_HEIGHT: u16 = 4;

pub struct GalleryCard<'a> {
    pub item: &'a GalleryItem,
    pub selected: bool,
}

impl<'a> Widget for GalleryCard<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        if area.height < CARD_HEIGHT || area.width < 25 {
            return;
        }

        // Highlight background for selected card
        if self.selected {
            for y in area.y..area.y + area.height.min(CARD_HEIGHT) {
                for x in area.x..area.x + area.width {
                    if let Some(cell) = buf.cell_mut((x, y)) {
                        cell.set_bg(Color::Rgb(50, 50, 80));
                    }
                }
            }
        }

        // Selection indicator
        let indicator_width: u16 = 2;
        if self.selected {
            buf.set_string(
                area.x,
                area.y,
                "▶ ",
                Style::default().fg(Color::Cyan).bold(),
            );
        }

        // Text area (after indicator)
        let text_x = area.x + indicator_width;
        let text_width = area.width.saturating_sub(indicator_width) as usize;
        if text_width < 10 {
            return;
        }

        // Line 1: Title (truncated to display width)
        let title = truncate_to_width(&self.item.title, text_width);
        buf.set_string(text_x, area.y, &title, Style::default().bold());

        // Line 2: Uploader
        let uploader = truncate_to_width(&self.item.uploader, text_width);
        buf.set_string(
            text_x,
            area.y + 1,
            &uploader,
            Style::default().fg(Color::Gray),
        );

        // Line 3: Rating + Category
        let rating_y = area.y + 2;
        if rating_y < area.y + area.height {
            let stars = render_stars(self.item.rating);
            buf.set_string(text_x, rating_y, &stars, Style::default().fg(Color::Yellow));

            let cat_x = text_x + UnicodeWidthStr::width(stars.as_str()) as u16 + 2;
            let (cat_fg, cat_bg) = category_colors(&self.item.category);
            let cat_style = Style::default().fg(cat_fg).bg(cat_bg);
            let cat_label = format!(" {} ", self.item.category);
            if cat_x + UnicodeWidthStr::width(cat_label.as_str()) as u16 <= area.x + area.width {
                buf.set_string(cat_x, rating_y, &cat_label, cat_style);
            }
        }

        // Line 4: Date + Pages
        let date_y = area.y + 3;
        if date_y < area.y + area.height {
            let date = if self.item.posted.len() >= 10 {
                let end = self.item.posted
                    .char_indices()
                    .nth(10)
                    .map(|(i, _)| i)
                    .unwrap_or(self.item.posted.len());
                &self.item.posted[..end]
            } else {
                &self.item.posted
            };
            buf.set_string(text_x, date_y, date, Style::default().fg(Color::DarkGray));

            let pages_str = format!("{}p", self.item.pages);
            let pages_x = text_x + UnicodeWidthStr::width(date) as u16 + 2;
            if pages_x + pages_str.len() as u16 <= area.x + area.width {
                buf.set_string(
                    pages_x,
                    date_y,
                    &pages_str,
                    Style::default().fg(Color::DarkGray),
                );
            }
        }
    }
}

fn render_stars(rating: f64) -> String {
    let full = rating.floor() as usize;
    let half = if rating - rating.floor() >= 0.5 { 1 } else { 0 };
    let empty = 5usize.saturating_sub(full + half);
    let mut s = "★".repeat(full);
    if half > 0 {
        s.push('☆');
    }
    s.push_str(&"☆".repeat(empty));
    s
}

/// Truncate string to fit within `max_width` display columns.
fn truncate_to_width(s: &str, max_width: usize) -> String {
    let width = UnicodeWidthStr::width(s);
    if width <= max_width {
        return s.to_string();
    }
    let mut result = String::new();
    let mut current_width = 0;
    let target = max_width.saturating_sub(3);
    for ch in s.chars() {
        let ch_width = unicode_width::UnicodeWidthChar::width(ch).unwrap_or(0);
        if current_width + ch_width > target {
            break;
        }
        result.push(ch);
        current_width += ch_width;
    }
    result.push_str("...");
    result
}
