use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Paragraph};

use crate::app::App;
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
    info_panel::draw_info_panel(frame, app.gallery_list.detail.as_ref(), chunks[2]);
}

fn draw_gallery_list(frame: &mut Frame, app: &mut App, area: Rect) {
    let block = Block::default()
        .title(" Gallery List ")
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
        let empty = Paragraph::new("No galleries");
        frame.render_widget(empty, inner);
        return;
    }

    let visible_cards = (inner.height / CARD_HEIGHT) as usize;
    let selected = app.gallery_list.selected;
    app.gallery_list.adjust_scroll(visible_cards);
    let scroll_offset = app.gallery_list.scroll_offset;

    for (i, item) in app
        .gallery_list
        .items
        .iter()
        .enumerate()
        .skip(scroll_offset)
        .take(visible_cards)
    {
        let card_y = inner.y + ((i - scroll_offset) as u16) * CARD_HEIGHT;
        if card_y + CARD_HEIGHT > inner.y + inner.height {
            break;
        }
        let card_area = Rect::new(inner.x, card_y, inner.width, CARD_HEIGHT);
        let card = GalleryCard {
            item,
            selected: i == selected,
        };
        frame.render_widget(card, card_area);
    }
}
