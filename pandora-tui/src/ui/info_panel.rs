use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};

use crate::models::GalleryDetail;

pub fn draw_info_panel(frame: &mut Frame, detail: Option<&GalleryDetail>, area: Rect) {
    let block = Block::default()
        .title(" Info ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::DarkGray));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let detail = match detail {
        Some(d) => d,
        None => {
            let text = Paragraph::new("Select a gallery").fg(Color::DarkGray);
            frame.render_widget(text, inner);
            return;
        }
    };

    // Cover placeholder
    let cover_height = inner.height / 3;
    let cover_area = Rect::new(inner.x, inner.y, inner.width, cover_height);
    let cover_placeholder = Paragraph::new("[Cover]")
        .alignment(Alignment::Center)
        .fg(Color::DarkGray);
    frame.render_widget(cover_placeholder, cover_area);

    // Metadata
    let meta_y = inner.y + cover_height + 1;
    let meta_height = inner.height.saturating_sub(cover_height + 1);
    if meta_height == 0 {
        return;
    }
    let meta_area = Rect::new(inner.x, meta_y, inner.width, meta_height);

    let mut lines: Vec<Line> = Vec::new();

    lines.push(Line::from(Span::styled(
        &detail.title,
        Style::default().bold(),
    )));

    if let Some(ref jpn) = detail.title_jpn {
        lines.push(Line::from(Span::styled(
            jpn.as_str(),
            Style::default().fg(Color::Gray),
        )));
    }

    lines.push(Line::from(""));

    lines.push(Line::from(vec![
        Span::styled("Uploader: ", Style::default().fg(Color::DarkGray)),
        Span::raw(&detail.uploader),
    ]));

    lines.push(Line::from(vec![
        Span::styled("Pages: ", Style::default().fg(Color::DarkGray)),
        Span::raw(format!("{}", detail.pages)),
        Span::raw("  "),
        Span::styled("Size: ", Style::default().fg(Color::DarkGray)),
        Span::raw(&detail.size),
    ]));

    let stars = render_stars(detail.rating);
    lines.push(Line::from(vec![
        Span::styled("Rating: ", Style::default().fg(Color::DarkGray)),
        Span::styled(stars, Style::default().fg(Color::Yellow)),
        Span::raw(format!(" ({})", detail.rating_count)),
    ]));

    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        "Tags:",
        Style::default().fg(Color::DarkGray),
    )));
    for (namespace, tags) in &detail.tags {
        let tag_str = tags.join(", ");
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
