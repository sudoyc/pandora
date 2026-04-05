use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui_image::StatefulImage;

use crate::app::App;

pub fn draw_info_panel(frame: &mut Frame, app: &mut App, area: Rect) {
    let block = Block::default()
        .title(" Info ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::DarkGray));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let detail = match &app.gallery_list.detail {
        Some(d) => d,
        None => {
            let text = Paragraph::new("Select a gallery").fg(Color::DarkGray);
            frame.render_widget(text, inner);
            return;
        }
    };

    // Clone all fields we need before calling mutable methods on app
    let cover_url = detail.cover_url.clone();
    let title = detail.title.clone();
    let title_jpn = detail.title_jpn.clone();
    let uploader = detail.uploader.clone();
    let pages = detail.pages;
    let size = detail.size.clone();
    let rating = detail.rating;
    let rating_count = detail.rating_count;
    let tags: Vec<(String, Vec<String>)> = detail
        .tags
        .iter()
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();

    // Cover image
    let cover_height = inner.height / 3;
    let cover_area = Rect::new(inner.x, inner.y, inner.width, cover_height);

    // Request thumbnail if not cached
    if !app.image_cache.contains(&cover_url) {
        app.request_thumbnail(cover_url.clone());
    }

    if let Some(protocol) = app.get_image_protocol(&cover_url) {
        let image_widget = StatefulImage::default();
        frame.render_stateful_widget(image_widget, cover_area, protocol);
    } else {
        let cover_placeholder = Paragraph::new("[Cover]")
            .alignment(Alignment::Center)
            .fg(Color::DarkGray);
        frame.render_widget(cover_placeholder, cover_area);
    }

    // Metadata
    let meta_y = inner.y + cover_height + 1;
    let meta_height = inner.height.saturating_sub(cover_height + 1);
    if meta_height == 0 {
        return;
    }
    let meta_area = Rect::new(inner.x, meta_y, inner.width, meta_height);

    let mut lines: Vec<Line> = Vec::new();

    lines.push(Line::from(Span::styled(
        title,
        Style::default().bold(),
    )));

    if let Some(ref jpn) = title_jpn {
        lines.push(Line::from(Span::styled(
            jpn.as_str(),
            Style::default().fg(Color::Gray),
        )));
    }

    lines.push(Line::from(""));

    lines.push(Line::from(vec![
        Span::styled("Uploader: ", Style::default().fg(Color::DarkGray)),
        Span::raw(uploader),
    ]));

    lines.push(Line::from(vec![
        Span::styled("Pages: ", Style::default().fg(Color::DarkGray)),
        Span::raw(format!("{}", pages)),
        Span::raw("  "),
        Span::styled("Size: ", Style::default().fg(Color::DarkGray)),
        Span::raw(size),
    ]));

    let stars = render_stars(rating);
    lines.push(Line::from(vec![
        Span::styled("Rating: ", Style::default().fg(Color::DarkGray)),
        Span::styled(stars, Style::default().fg(Color::Yellow)),
        Span::raw(format!(" ({})", rating_count)),
    ]));

    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        "Tags:",
        Style::default().fg(Color::DarkGray),
    )));
    for (namespace, tag_list) in &tags {
        let tag_str = tag_list.join(", ");
        lines.push(Line::from(vec![
            Span::styled(
                format!("  {}: ", namespace),
                Style::default().fg(Color::Cyan),
            ),
            Span::raw(tag_str),
        ]));
    }

    let paragraph = Paragraph::new(lines).wrap(Wrap { trim: false });
    frame.render_widget(paragraph, meta_area);
}

fn render_stars(rating: f64) -> String {
    let full = rating.floor() as usize;
    let half = if rating - rating.floor() >= 0.5 { 1 } else { 0 };
    let empty = 5usize.saturating_sub(full + half);
    "★".repeat(full)
        + if half > 0 { "☆" } else { "" }
        + &"☆".repeat(empty)
}
