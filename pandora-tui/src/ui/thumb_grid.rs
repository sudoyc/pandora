use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui_image::StatefulImage;

use crate::app::App;

pub fn draw_thumb_grid(frame: &mut Frame, app: &mut App, area: Rect) {
    let block = Block::default()
        .title(" Thumbnails ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::DarkGray));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let detail = match &app.gallery_list.detail {
        Some(d) => d,
        None => {
            let text = Paragraph::new("No gallery selected").fg(Color::DarkGray);
            frame.render_widget(text, inner);
            return;
        }
    };

    if detail.thumb_urls.is_empty() {
        let text = Paragraph::new("No thumbnails").fg(Color::DarkGray);
        frame.render_widget(text, inner);
        return;
    }

    let thumb_w: u16 = 10;
    let thumb_h: u16 = 7;
    let cols = (inner.width / thumb_w).max(1) as usize;
    let rows = (inner.height / thumb_h).max(1) as usize;

    let thumb_urls: Vec<String> = detail.thumb_urls.clone();

    for (idx, url) in thumb_urls.iter().enumerate().take(cols * rows) {
        let col = idx % cols;
        let row = idx / cols;
        let x = inner.x + (col as u16) * thumb_w;
        let y = inner.y + (row as u16) * thumb_h;

        if y + thumb_h > inner.y + inner.height {
            break;
        }

        let cell_area = Rect::new(
            x,
            y,
            thumb_w.min(inner.width.saturating_sub(x - inner.x)),
            thumb_h,
        );

        // Request thumbnail load if not cached
        if !app.image_cache.contains(url) {
            app.request_thumbnail(url.clone());
        }

        // Render image or placeholder
        if let Some(protocol) = app.get_image_protocol(url) {
            let image_widget = StatefulImage::default();
            frame.render_stateful_widget(image_widget, cell_area, protocol);
        } else {
            let label = format!("p.{}", idx + 1);
            let p = Paragraph::new(label)
                .alignment(Alignment::Center)
                .fg(Color::DarkGray);
            frame.render_widget(p, cell_area);
        }
    }
}
