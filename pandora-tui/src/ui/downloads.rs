use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Clear, Gauge, Paragraph};

use crate::app::App;

pub fn draw_download_overlay(frame: &mut Frame, app: &App) {
    if !app.downloads.show_overlay {
        return;
    }

    let area = frame.area();
    if area.width < 20 || area.height < 8 {
        return;
    }
    let overlay_width = (area.width * 70 / 100).min(60);
    let overlay_height = (app.downloads.tasks.len() as u16 * 2 + 4)
        .min(area.height.saturating_sub(4))
        .max(6);
    let x = area.width.saturating_sub(overlay_width) / 2;
    let y = area.height.saturating_sub(overlay_height) / 2;
    let overlay_area = Rect::new(x, y, overlay_width, overlay_height);

    frame.render_widget(Clear, overlay_area);

    let block = Block::default()
        .title(" Downloads ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::Cyan));
    let inner = block.inner(overlay_area);
    frame.render_widget(block, overlay_area);

    if app.downloads.tasks.is_empty() {
        let text = Paragraph::new("No downloads")
            .alignment(Alignment::Center)
            .fg(Color::DarkGray);
        frame.render_widget(text, inner);
        return;
    }

    for (i, task) in app.downloads.tasks.iter().enumerate() {
        let y = inner.y + (i as u16) * 2;
        if y + 1 >= inner.y + inner.height {
            break;
        }

        let title_truncated = if task.title.chars().count() > 30 {
            let t: String = task.title.chars().take(27).collect();
            format!("{}...", t)
        } else {
            task.title.clone()
        };

        let status_label = match task.status.as_str() {
            "queued" => Span::styled(" queue ", Style::default().fg(Color::Yellow)),
            "downloading" => Span::styled(" dl ", Style::default().fg(Color::Cyan)),
            "complete" => Span::styled(" done ", Style::default().fg(Color::Green)),
            "error" => Span::styled(" err ", Style::default().fg(Color::Red)),
            _ => Span::raw(&task.status),
        };

        let line = Line::from(vec![
            status_label,
            Span::raw(" "),
            Span::raw(title_truncated),
        ]);
        frame.render_widget(
            Paragraph::new(line),
            Rect::new(inner.x, y, inner.width, 1),
        );

        if task.total_pages > 0 && task.status == "downloading" {
            let ratio = task.downloaded_pages as f64 / task.total_pages as f64;
            let gauge = Gauge::default()
                .ratio(ratio.min(1.0))
                .gauge_style(Style::default().fg(Color::Cyan));
            frame.render_widget(
                gauge,
                Rect::new(inner.x + 2, y + 1, inner.width.saturating_sub(4), 1),
            );
        }
    }
}
