use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui_image::StatefulImage;

use crate::app::{App, PageSource};
use super::gallery_card::{GalleryCard, CARD_HEIGHT};
use super::info_panel;
use super::thumb_grid;

pub fn draw_browse(frame: &mut Frame, app: &mut App, area: Rect) {
    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(35),
            Constraint::Percentage(35),
            Constraint::Percentage(30),
        ])
        .split(area);

    draw_gallery_list(frame, app, chunks[0]);
    thumb_grid::draw_thumb_grid(frame, app, chunks[1]);
    info_panel::draw_info_panel(frame, app, chunks[2]);
}

const COVER_WIDTH: u16 = 8;

fn draw_gallery_list(frame: &mut Frame, app: &mut App, area: Rect) {
    let title = format!(" {} ", app.page_source.label());
    let block = Block::default()
        .title(title)
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::DarkGray));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    if app.gallery_list.loading {
        let loading = Paragraph::new("Loading...");
        frame.render_widget(loading, inner);
        return;
    }

    if app.gallery_list.items.is_empty() {
        let msg = match &app.page_source {
            PageSource::Search { .. } => "No results found",
            PageSource::Downloaded => "No downloaded galleries",
            PageSource::Favorites => "No favorites",
            _ => "No galleries",
        };
        let empty = Paragraph::new(msg).fg(Color::DarkGray);
        frame.render_widget(empty, inner);
        return;
    }

    let visible_cards = (inner.height / CARD_HEIGHT) as usize;
    let selected = app.gallery_list.selected;
    app.gallery_list.adjust_scroll(visible_cards);
    let scroll_offset = app.gallery_list.scroll_offset;

    // Collect visible items data to avoid borrow conflicts
    let visible: Vec<(usize, crate::models::GalleryItem)> = app
        .gallery_list
        .items
        .iter()
        .enumerate()
        .skip(scroll_offset)
        .take(visible_cards)
        .map(|(i, item)| (i, item.clone()))
        .collect();

    // Request cover loads
    for (_, item) in &visible {
        if !item.thumb_url.is_empty()
            && !app.image_cache.contains(&item.thumb_url)
            && !app.failed_images.contains(&item.thumb_url)
        {
            app.request_thumbnail(item.thumb_url.clone());
        }
    }

    // Render cards with covers
    for (i, item) in &visible {
        let card_y = inner.y + ((i - scroll_offset) as u16) * CARD_HEIGHT;
        if card_y + CARD_HEIGHT > inner.y + inner.height {
            break;
        }

        // Cover image area (left side)
        let cover_area = Rect::new(inner.x, card_y, COVER_WIDTH, CARD_HEIGHT);
        if !item.thumb_url.is_empty() {
            if let Some(protocol) = app.get_image_protocol(&item.thumb_url) {
                let img = StatefulImage::default();
                frame.render_stateful_widget(img, cover_area, protocol);
            }
        }

        // Card text area (right of cover)
        let card_area = Rect::new(
            inner.x + COVER_WIDTH,
            card_y,
            inner.width.saturating_sub(COVER_WIDTH),
            CARD_HEIGHT,
        );
        let card = GalleryCard {
            item,
            selected: *i == selected,
        };
        frame.render_widget(card, card_area);
    }
}
