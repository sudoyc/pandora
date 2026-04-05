use ratatui::prelude::*;
use ratatui::widgets::Paragraph;
use unicode_width::UnicodeWidthStr;

use crate::app::{App, AppMode, PageSource};

pub fn draw_status_bar(frame: &mut Frame, app: &App, area: Rect) {
    let mode_label = match app.mode {
        AppMode::Browse => app.page_source.label(),
        AppMode::Read => "Reader",
        AppMode::Search => "Search",
    };

    let page_info = match app.mode {
        AppMode::Browse => {
            if matches!(app.page_source, PageSource::Downloaded) {
                String::new()
            } else {
                format!(" p{}", app.gallery_list.current_page + 1)
            }
        }
        AppMode::Read => format!(
            " {}/{}",
            app.reader.current_page, app.reader.total_pages
        ),
        AppMode::Search => String::new(),
    };

    let hints = match app.mode {
        AppMode::Browse => "j/k:nav l:open /:search n/p:page d:dl ?:help 1-6:src",
        AppMode::Read => "j/k:page h:back d:dl r:retry",
        AppMode::Search => "Tab:suggest Enter:search Ctrl+T:filter Esc:cancel",
    };

    let dl_indicator = if app.downloads.active_count > 0 {
        format!(" ↓{}", app.downloads.active_count)
    } else {
        String::new()
    };

    let left = format!(" [{}{}] {}", mode_label, page_info, hints);
    let right = format!("{}{} ", app.status_msg, dl_indicator);

    let width = area.width as usize;
    let padding = width.saturating_sub(UnicodeWidthStr::width(left.as_str()) + UnicodeWidthStr::width(right.as_str()));
    let line = format!("{}{:padding$}{}", left, "", right, padding = padding);

    let bar =
        Paragraph::new(line).style(Style::default().bg(Color::DarkGray).fg(Color::White));
    frame.render_widget(bar, area);
}
