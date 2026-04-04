use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Clear, Paragraph, Wrap};

pub fn draw_help_overlay(frame: &mut Frame, show: bool) {
    if !show {
        return;
    }

    let area = frame.area();
    let width = area.width.min(50);
    let height = area.height.min(25);
    let x = (area.width - width) / 2;
    let y = (area.height - height) / 2;
    let overlay = Rect::new(x, y, width, height);

    frame.render_widget(Clear, overlay);
    let block = Block::default()
        .title(" Help — pandora-tui ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::Yellow));
    let inner = block.inner(overlay);
    frame.render_widget(block, overlay);

    let help_text = vec![
        Line::from(Span::styled("Global", Style::default().bold())),
        Line::from("  1-6    Switch page source"),
        Line::from("  /      Search"),
        Line::from("  ?      Toggle help"),
        Line::from("  D      Toggle downloads"),
        Line::from("  q      Quit"),
        Line::from(""),
        Line::from(Span::styled("Browse", Style::default().bold())),
        Line::from("  j/k    Navigate galleries"),
        Line::from("  l/Enter  Open gallery"),
        Line::from("  n/p    Next/prev page"),
        Line::from("  d      Download"),
        Line::from("  f      Favorite"),
        Line::from("  r      Refresh"),
        Line::from("  gg/G   Top/bottom"),
        Line::from(""),
        Line::from(Span::styled("Reader", Style::default().bold())),
        Line::from("  j/k/Space  Next/prev page"),
        Line::from("  Esc/h  Back to browse"),
        Line::from("  r      Retry load"),
        Line::from("  gg/G   First/last page"),
    ];

    let paragraph = Paragraph::new(help_text).wrap(Wrap { trim: false });
    frame.render_widget(paragraph, inner);
}
