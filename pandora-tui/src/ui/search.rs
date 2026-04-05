use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Clear, Paragraph};

use crate::app::App;
use crate::state::search::CATEGORIES;

/// Draw search overlays: suggestions + category filter.
pub fn draw_search_overlay(frame: &mut Frame, app: &App, area: Rect) {
    let filter_y = area.y + area.height.saturating_sub(2);
    draw_category_filter(
        frame,
        app,
        Rect::new(area.x, filter_y, area.width, 1),
    );

    if !app.search.suggestions.is_empty() {
        let popup_height = (app.search.suggestions.len() as u16 * 2).min(12);
        let popup_y = filter_y.saturating_sub(popup_height + 1);
        let popup_area = Rect::new(area.x + 1, popup_y, area.width.min(50), popup_height);
        draw_suggestions(frame, app, popup_area);
    }
}

fn draw_suggestions(frame: &mut Frame, app: &App, area: Rect) {
    frame.render_widget(Clear, area);

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::Cyan));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let visible_count = (inner.height / 2) as usize;
    let scroll = app.search.suggestion_scroll;

    for (vi, suggestion) in app
        .search
        .suggestions
        .iter()
        .enumerate()
        .skip(scroll)
        .take(visible_count)
    {
        let row = vi - scroll;
        let y = inner.y + (row as u16) * 2;
        if y + 1 >= inner.y + inner.height {
            break;
        }

        let selected = app.search.selected_suggestion == Some(vi);
        let style = if selected {
            Style::default().fg(Color::Yellow).bold()
        } else {
            Style::default()
        };
        let prefix = if selected { "▶ " } else { "  " };

        let tag_line = format!("{}{}:{}", prefix, suggestion.namespace, suggestion.tag);
        frame.render_widget(
            Paragraph::new(tag_line).style(style),
            Rect::new(inner.x, y, inner.width, 1),
        );

        let trans_line = format!("    {}", suggestion.translation);
        frame.render_widget(
            Paragraph::new(trans_line).fg(Color::Gray),
            Rect::new(inner.x, y + 1, inner.width, 1),
        );
    }
}

fn draw_category_filter(frame: &mut Frame, app: &App, area: Rect) {
    let mut spans: Vec<Span> = Vec::new();

    for (i, &(name, _)) in CATEGORIES.iter().enumerate() {
        let included = app.search.is_category_included(i);
        let focused = app.search.filter_active && app.search.filter_cursor == i;

        let label = if included {
            format!("[{}✓]", name)
        } else {
            format!("[{}✗]", name)
        };

        let style = if focused {
            Style::default().fg(Color::Yellow).bold()
        } else if included {
            Style::default().fg(Color::Green)
        } else {
            Style::default().fg(Color::DarkGray)
        };

        spans.push(Span::styled(label, style));
        spans.push(Span::raw(" "));
    }

    let rating_label = if app.search.min_rating > 0 {
        format!("★min:{}", app.search.min_rating)
    } else {
        "★min:0".to_string()
    };
    spans.push(Span::styled(
        rating_label,
        Style::default().fg(Color::Yellow),
    ));

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

/// Draw the search input line (replaces status bar in search mode).
pub fn draw_search_input(frame: &mut Frame, app: &App, area: Rect) {
    let spans = vec![
        Span::styled("/ ", Style::default().fg(Color::Cyan)),
        Span::raw(&app.search.input),
        Span::styled("█", Style::default().fg(Color::Cyan)),
    ];

    let line = Line::from(spans);
    let bar = Paragraph::new(line).style(Style::default().bg(Color::Rgb(30, 30, 40)));
    frame.render_widget(bar, area);
}
