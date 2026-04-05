use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Gauge, List, ListItem, Paragraph};
use ratatui_image::StatefulImage;

use crate::app::App;

pub fn draw_reader(frame: &mut Frame, app: &mut App, area: Rect) {
    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(20), Constraint::Percentage(80)])
        .split(area);

    draw_page_list(frame, app, chunks[0]);
    draw_viewer(frame, app, chunks[1]);
}

fn draw_page_list(frame: &mut Frame, app: &App, area: Rect) {
    let block = Block::default()
        .title(" Pages ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::DarkGray));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let total = app.reader.total_pages;
    let current = app.reader.current_page;
    let visible = inner.height as usize;
    let offset = if (current as usize) > visible / 2 {
        (current as usize).saturating_sub(visible / 2)
    } else {
        0
    };

    let items: Vec<ListItem> = (1..=total)
        .skip(offset)
        .take(visible)
        .map(|p| {
            let style = if p == current {
                Style::default().fg(Color::Yellow).bold()
            } else {
                Style::default().fg(Color::Gray)
            };
            let prefix = if p == current { "▶ " } else { "  " };
            ListItem::new(format!("{}[{:03}]", prefix, p)).style(style)
        })
        .collect();

    let list = List::new(items);
    frame.render_widget(list, inner);
}

fn draw_viewer(frame: &mut Frame, app: &mut App, area: Rect) {
    let title = format!(
        " {} — Page {}/{} ",
        app.reader.title, app.reader.current_page, app.reader.total_pages,
    );
    let block = Block::default()
        .title(title)
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::DarkGray));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    // Error state
    if let Some(ref error) = app.reader.error {
        let text = Paragraph::new(vec![
            Line::from(""),
            Line::from(Span::styled(
                error.as_str(),
                Style::default().fg(Color::Red),
            )),
            Line::from(""),
            Line::from(Span::styled(
                "Press r to retry",
                Style::default().fg(Color::DarkGray),
            )),
        ])
        .alignment(Alignment::Center);
        frame.render_widget(text, inner);
        return;
    }

    // Loading state with progress
    if app.reader.loading {
        let center_y = inner.y + inner.height / 2;

        if let Some((received, total)) = app.reader.loading_progress {
            let size_mb = received as f64 / 1024.0 / 1024.0;
            let pct = if total > 0 {
                (received as f64 / total as f64 * 100.0) as u16
            } else {
                0
            };
            let label = format!(
                "Loading page {}...  {:.1}MB  {}%",
                app.reader.current_page, size_mb, pct
            );
            let label_line = Paragraph::new(label)
                .alignment(Alignment::Center)
                .fg(Color::Gray);
            frame.render_widget(
                label_line,
                Rect::new(inner.x, center_y.saturating_sub(1), inner.width, 1),
            );

            let gauge_width = inner.width.min(40);
            let gauge_x = inner.x + (inner.width.saturating_sub(gauge_width)) / 2;
            let ratio = if total > 0 {
                received as f64 / total as f64
            } else {
                0.0
            };
            let gauge = Gauge::default()
                .ratio(ratio.min(1.0))
                .gauge_style(Style::default().fg(Color::Cyan));
            frame.render_widget(
                gauge,
                Rect::new(gauge_x, center_y, gauge_width, 1),
            );
        } else {
            let text = Paragraph::new(format!("Loading page {}...", app.reader.current_page))
                .alignment(Alignment::Center)
                .fg(Color::Gray);
            frame.render_widget(
                text,
                Rect::new(inner.x, center_y, inner.width, 1),
            );
        }
        return;
    }

    // Image display
    if app.page_image.is_some() {
        if let Some(protocol) = app.get_page_protocol() {
            let image_widget = StatefulImage::default();
            frame.render_stateful_widget(image_widget, inner, protocol);
        } else {
            let text = Paragraph::new("Preparing image...")
                .alignment(Alignment::Center)
                .fg(Color::DarkGray);
            frame.render_widget(text, inner);
        }
    } else {
        let text = Paragraph::new("No image loaded")
            .alignment(Alignment::Center)
            .fg(Color::DarkGray);
        frame.render_widget(text, inner);
    }
}
