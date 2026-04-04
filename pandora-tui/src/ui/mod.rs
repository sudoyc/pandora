pub mod browse;
pub mod downloads;
pub mod gallery_card;
pub mod help;
pub mod info_panel;
pub mod reader;
pub mod search;
pub mod status_bar;
pub mod thumb_grid;

use ratatui::prelude::*;

use crate::app::{App, AppMode};

pub fn draw(frame: &mut Frame, app: &mut App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(1), Constraint::Length(1)])
        .split(frame.area());

    match app.mode {
        AppMode::Browse => browse::draw_browse(frame, app, chunks[0]),
        AppMode::Read => reader::draw_reader(frame, app, chunks[0]),
        AppMode::Search => {
            browse::draw_browse(frame, app, chunks[0]);
            search::draw_search_overlay(frame, app, chunks[0]);
        }
    }

    if app.mode == AppMode::Search {
        search::draw_search_input(frame, app, chunks[1]);
    } else {
        status_bar::draw_status_bar(frame, app, chunks[1]);
    }

    // Overlays (on top of everything)
    help::draw_help_overlay(frame, app.show_help);
    downloads::draw_download_overlay(frame, app);
}
