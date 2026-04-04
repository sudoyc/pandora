use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Widget};

use crate::models::{category_to_color, GalleryItem};

/// Height of a single gallery card in rows.
pub const CARD_HEIGHT: u16 = 4;
/// Width reserved for the thumbnail placeholder on the left.
pub const THUMB_WIDTH: u16 = 10;

pub struct GalleryCard<'a> {
    pub item: &'a GalleryItem,
    pub selected: bool,
}

impl<'a> Widget for GalleryCard<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        if area.height < CARD_HEIGHT || area.width < THUMB_WIDTH + 20 {
            return;
        }

        // Highlight background for selected card
        if self.selected {
            for y in area.y..area.y + area.height.min(CARD_HEIGHT) {
                for x in area.x..area.x + area.width {
                    if let Some(cell) = buf.cell_mut((x, y)) {
                        cell.set_bg(Color::Rgb(40, 40, 60));
                    }
                }
            }
        }

        // Thumbnail placeholder
        let thumb_area = Rect::new(area.x, area.y, THUMB_WIDTH, CARD_HEIGHT.min(area.height));
        let thumb_block = Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray));
        thumb_block.render(thumb_area, buf);

        // Text area
        let text_x = area.x + THUMB_WIDTH + 1;
        let text_width = area.width.saturating_sub(THUMB_WIDTH + 1);
        if text_width < 10 {
            return;
        }

        // Line 1-2: Title
        let title = truncate(&self.item.title, text_width as usize * 2);
        let title_line1 = if title.chars().count() > text_width as usize {
            truncate(&title, text_width as usize)
        } else {
            title.clone()
        };
        buf.set_string(text_x, area.y, &title_line1, Style::default().bold());

        if title.chars().count() > text_width as usize {
            let skip: String = title.chars().take(text_width as usize).collect();
            let rest: String = title.chars().skip(skip.chars().count()).collect();
            let title_line2 = truncate(&rest, text_width as usize);
            buf.set_string(text_x, area.y + 1, &title_line2, Style::default().bold());
        } else {
            // Line 2: Uploader
            buf.set_string(
                text_x,
                area.y + 1,
                &self.item.uploader,
                Style::default().fg(Color::Gray),
            );
        }

        // Line 3: Rating + Category
        let rating_y = area.y + 2;
        if rating_y < area.y + area.height {
            let stars = render_stars(self.item.rating);
            buf.set_string(text_x, rating_y, &stars, Style::default().fg(Color::Yellow));

            let cat_x = text_x + stars.len() as u16 + 2;
            let cat_style = Style::default()
                .fg(Color::White)
                .bg(category_to_color(&self.item.category));
            let cat_label = format!(" {} ", self.item.category);
            if cat_x + cat_label.len() as u16 <= area.x + area.width {
                buf.set_string(cat_x, rating_y, &cat_label, cat_style);
            }
        }

        // Line 4: Date + Pages
        let date_y = area.y + 3;
        if date_y < area.y + area.height {
            let date = if self.item.posted.len() >= 10 {
                &self.item.posted[..10]
            } else {
                &self.item.posted
            };
            buf.set_string(text_x, date_y, date, Style::default().fg(Color::DarkGray));

            let pages_str = format!("{}p", self.item.pages);
            let pages_x = text_x + date.len() as u16 + 2;
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

fn truncate(s: &str, max_len: usize) -> String {
    if s.chars().count() <= max_len {
        s.to_string()
    } else {
        let truncated: String = s.chars().take(max_len.saturating_sub(3)).collect();
        format!("{}...", truncated)
    }
}
