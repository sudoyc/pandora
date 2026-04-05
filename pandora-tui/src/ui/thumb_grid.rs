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

    let total_thumbs = detail.pages as usize;
    if total_thumbs == 0 {
        let text = Paragraph::new("No thumbnails").fg(Color::DarkGray);
        frame.render_widget(text, inner);
        return;
    }

    let gid = detail.gid.clone();
    let token = detail.token.clone();

    let thumb_w: u16 = 14;
    let thumb_h: u16 = 8;
    let cols = (inner.width / thumb_w).max(1) as usize;
    let rows = (inner.height / thumb_h).max(1) as usize;

    for idx in 0..total_thumbs.min(cols * rows) {
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

        let page = (idx + 1) as u32;
        let cache_key = format!("thumb:{}:{}", gid, page);

        // Request cropped thumbnail if not cached
        if !app.image_cache.contains(&cache_key) {
            app.request_gallery_thumb(gid.clone(), token.clone(), page);
        }

        // Render image or placeholder
        if let Some(protocol) = app.get_image_protocol(&cache_key) {
            let image_widget = StatefulImage::default();
            frame.render_stateful_widget(image_widget, cell_area, protocol);
        } else {
            let label = format!("p.{}", page);
            let p = Paragraph::new(label)
                .alignment(Alignment::Center)
                .fg(Color::DarkGray);
            frame.render_widget(p, cell_area);
        }
    }
}
