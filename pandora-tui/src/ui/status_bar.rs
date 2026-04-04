use ratatui::prelude::*;
use ratatui::widgets::Paragraph;

use crate::app::{App, AppMode};

pub fn draw_status_bar(frame: &mut Frame, app: &App, area: Rect) {
    let mode_label = match app.mode {
        AppMode::Browse => app.page_source.label(),
        AppMode::Read => "Reader",
        AppMode::Search => "Search",
    };

    let hints = match app.mode {
        AppMode::Browse => "j/k:nav l:open /:search d:download ?:help",
        AppMode::Read => "j/k:page h:back d:download r:retry",
        AppMode::Search => "Tab:suggest Enter:search Esc:cancel",
    };

    let dl_indicator = if app.downloads.active_count > 0 {
        format!(" ↓{} downloading", app.downloads.active_count)
    } else {
        String::new()
    };

    let left = format!(" [{}] {}", mode_label, hints);
    let right = format!("{}{} q:quit ", app.status_msg, dl_indicator);

    let width = area.width as usize;
    let padding = width.saturating_sub(left.len() + right.len());
    let line = format!("{}{:padding$}{}", left, "", right, padding = padding);

    let bar =
        Paragraph::new(line).style(Style::default().bg(Color::DarkGray).fg(Color::White));
    frame.render_widget(bar, area);
}
