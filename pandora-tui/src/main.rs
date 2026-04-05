mod app;
mod client;
mod config;
mod event;
mod models;
mod state;
mod ui;

use std::io;
use std::time::{Duration, Instant};

use crossterm::{
    event::{self as ct_event, Event, KeyCode, KeyEventKind, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::prelude::*;
use tokio::sync::mpsc;

use app::{App, AppMode, PageSource};
use client::DaemonClient;
use event::AppEvent;

#[tokio::main]
async fn main() -> io::Result<()> {
    let tui_config = config::load_config();
    let client = DaemonClient::new(&tui_config.daemon_url);

    // Health check
    if let Err(e) = client.health_check().await {
        eprintln!(
            "Cannot connect to daemon at {}: {}",
            tui_config.daemon_url, e
        );
        eprintln!("Make sure pandora-daemon is running.");
        std::process::exit(1);
    }

    let (tx, mut rx) = mpsc::unbounded_channel::<AppEvent>();
    let mut app = App::new(client, tx.clone());

    // Load initial page
    app.load_current_page();

    // Terminal setup
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let tick_rate = Duration::from_millis(50);
    let mut last_tick = Instant::now();

    loop {
        // Draw
        terminal.draw(|frame| {
            ui::draw(frame, &mut app);
        })?;

        // Poll for terminal events with timeout
        let timeout = tick_rate.saturating_sub(last_tick.elapsed());
        if ct_event::poll(timeout)? {
            if let Event::Key(key) = ct_event::read()? {
                if key.kind == KeyEventKind::Press {
                    handle_key(&mut app, key.code, key.modifiers);
                }
            }
        }

        // Drain channel events
        while let Ok(app_event) = rx.try_recv() {
            handle_app_event(&mut app, app_event);
        }

        // Tick
        if last_tick.elapsed() >= tick_rate {
            last_tick = Instant::now();
        }

        if app.should_quit {
            break;
        }
    }

    // Cleanup
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    Ok(())
}

fn handle_key(app: &mut App, code: KeyCode, _modifiers: KeyModifiers) {
    // Help/download overlay dismiss
    if app.show_help {
        if matches!(code, KeyCode::Esc | KeyCode::Char('?') | KeyCode::Char('q')) {
            app.show_help = false;
        }
        return;
    }
    if app.downloads.show_overlay {
        if matches!(code, KeyCode::Esc | KeyCode::Char('D')) {
            app.downloads.show_overlay = false;
        }
        return;
    }

    match app.mode {
        AppMode::Browse => handle_key_browse(app, code),
        AppMode::Read => handle_key_read(app, code),
        AppMode::Search => handle_key_search(app, code, _modifiers),
    }
}

fn handle_key_browse(app: &mut App, code: KeyCode) {
    // Reset pending_g on any non-g key
    let was_pending_g = app.pending_g;
    if code != KeyCode::Char('g') {
        app.pending_g = false;
    }

    match code {
        KeyCode::Char('q') => app.should_quit = true,
        KeyCode::Char('j') | KeyCode::Down => {
            app.gallery_list.select_next();
            app.load_selected_detail();
        }
        KeyCode::Char('k') | KeyCode::Up => {
            app.gallery_list.select_prev();
            app.load_selected_detail();
        }
        KeyCode::Char('l') | KeyCode::Enter => {
            if let Some(detail) = &app.gallery_list.detail {
                app.reader = state::ReaderState {
                    current_page: 1,
                    total_pages: detail.pages,
                    gid: detail.gid.clone(),
                    token: detail.token.clone(),
                    title: detail.title.clone(),
                    loading: true,
                    ..Default::default()
                };
                app.mode = AppMode::Read;
                app.page_image = None;
                load_page_image(app);
            }
        }
        KeyCode::Char('n') => {
            app.gallery_list.current_page += 1;
            app.gallery_list.clear();
            app.load_current_page();
        }
        KeyCode::Char('p') => {
            if app.gallery_list.current_page > 0 {
                app.gallery_list.current_page -= 1;
                app.gallery_list.clear();
                app.load_current_page();
            }
        }
        KeyCode::Char('d') => {
            if let Some(item) = app.gallery_list.selected_item() {
                let gid = item.gid.clone();
                let token = item.token.clone();
                app.spawn_fetch(move |c| async move {
                    AppEvent::DownloadSubmitted(c.submit_download(&gid, &token).await)
                });
                app.status_msg = "Download submitted".to_string();
            }
        }
        KeyCode::Char('f') => {
            if let Some(item) = app.gallery_list.selected_item() {
                let gid = item.gid.clone();
                let token = item.token.clone();
                app.spawn_fetch(move |c| async move {
                    match c.add_favorite(&gid, &token, 0).await {
                        Ok(()) => AppEvent::Tick,
                        Err(e) => AppEvent::ImageError {
                            url: String::new(),
                            error: e,
                        },
                    }
                });
                app.status_msg = "Added to favorites".to_string();
            }
        }
        KeyCode::Char('r') => {
            app.gallery_list.clear();
            app.load_current_page();
        }
        KeyCode::Char('G') => {
            app.gallery_list.select_last();
            app.load_selected_detail();
        }
        KeyCode::Char('g') => {
            if was_pending_g {
                app.gallery_list.select_first();
                app.load_selected_detail();
                app.pending_g = false;
            } else {
                app.pending_g = true;
            }
        }
        KeyCode::Char('/') => {
            app.mode = AppMode::Search;
            app.search.active = true;
        }
        KeyCode::Char('?') => app.show_help = !app.show_help,
        KeyCode::Char('D') => app.downloads.show_overlay = !app.downloads.show_overlay,
        KeyCode::Char('1') => switch_page_source(app, PageSource::Homepage),
        KeyCode::Char('2') => switch_page_source(app, PageSource::Popular),
        KeyCode::Char('3') => switch_page_source(app, PageSource::Toplist),
        KeyCode::Char('4') => switch_page_source(app, PageSource::Watched),
        KeyCode::Char('5') => switch_page_source(app, PageSource::Favorites),
        KeyCode::Char('6') => switch_page_source(app, PageSource::Downloaded),
        _ => {}
    }
}

fn handle_key_read(app: &mut App, code: KeyCode) {
    let was_pending_g = app.pending_g;
    if code != KeyCode::Char('g') {
        app.pending_g = false;
    }

    match code {
        KeyCode::Esc | KeyCode::Char('h') => {
            app.mode = AppMode::Browse;
            app.page_image = None;
        }
        KeyCode::Char('j') | KeyCode::Char('l') | KeyCode::Char(' ') | KeyCode::Down => {
            app.reader.next_page();
            app.reader.loading = true;
            app.reader.error = None;
            app.page_image = None;
            load_page_image(app);
        }
        KeyCode::Char('k') | KeyCode::Up => {
            app.reader.prev_page();
            app.reader.loading = true;
            app.reader.error = None;
            app.page_image = None;
            load_page_image(app);
        }
        KeyCode::Char('G') => {
            app.reader.last_page();
            app.reader.loading = true;
            app.reader.error = None;
            app.page_image = None;
            load_page_image(app);
        }
        KeyCode::Char('g') => {
            if was_pending_g {
                app.reader.first_page();
                app.reader.loading = true;
                app.reader.error = None;
                app.page_image = None;
                load_page_image(app);
                app.pending_g = false;
            } else {
                app.pending_g = true;
            }
        }
        KeyCode::Char('r') => {
            app.reader.loading = true;
            app.reader.error = None;
            app.page_image = None;
            load_page_image(app);
        }
        KeyCode::Char('d') => {
            let gid = app.reader.gid.clone();
            let token = app.reader.token.clone();
            app.spawn_fetch(move |c| async move {
                AppEvent::DownloadSubmitted(c.submit_download(&gid, &token).await)
            });
            app.status_msg = "Download submitted".to_string();
        }
        _ => {}
    }
}

fn handle_key_search(app: &mut App, code: KeyCode, modifiers: KeyModifiers) {
    if app.search.filter_active {
        match code {
            KeyCode::Left => {
                app.search.filter_cursor = app.search.filter_cursor.saturating_sub(1);
            }
            KeyCode::Right => {
                if app.search.filter_cursor < state::search::CATEGORIES.len() - 1 {
                    app.search.filter_cursor += 1;
                }
            }
            KeyCode::Char(' ') => app.search.toggle_category(),
            KeyCode::Esc => app.search.filter_active = false,
            _ => {}
        }
        return;
    }

    match code {
        KeyCode::Esc => {
            app.search.reset();
            app.mode = AppMode::Browse;
        }
        KeyCode::Enter => {
            if let Some(idx) = app.search.selected_suggestion {
                // Insert selected tag
                let s = &app.search.suggestions[idx];
                let ns = s.namespace.clone();
                let tag = s.tag.clone();
                app.search.insert_tag(&ns, &tag);
            } else {
                // Execute search
                let keyword = app.search.input.clone();
                let cat = app.search.category_bitmask();
                let rating = if app.search.min_rating > 0 {
                    Some(app.search.min_rating)
                } else {
                    None
                };
                app.search.reset();
                app.mode = AppMode::Browse;
                app.page_source = PageSource::Homepage; // Search results shown in list
                app.gallery_list.clear();
                app.gallery_list.loading = true;
                app.spawn_fetch(move |c| async move {
                    AppEvent::GalleriesLoaded(c.search(&keyword, 0, cat, rating).await)
                });
            }
        }
        KeyCode::Backspace => {
            app.search.delete_char();
            request_suggestions(app);
        }
        KeyCode::Tab | KeyCode::Down => {
            let len = app.search.suggestions.len();
            if len > 0 {
                app.search.selected_suggestion = Some(
                    app.search
                        .selected_suggestion
                        .map(|i| (i + 1) % len)
                        .unwrap_or(0),
                );
                app.search.adjust_suggestion_scroll(5);
            }
        }
        KeyCode::BackTab | KeyCode::Up => {
            let len = app.search.suggestions.len();
            if len > 0 {
                app.search.selected_suggestion = Some(
                    app.search
                        .selected_suggestion
                        .map(|i| if i == 0 { len - 1 } else { i - 1 })
                        .unwrap_or(len - 1),
                );
                app.search.adjust_suggestion_scroll(5);
            }
        }
        KeyCode::Char('t') if modifiers.contains(KeyModifiers::CONTROL) => {
            app.search.filter_active = true;
        }
        KeyCode::Char('r') if modifiers.contains(KeyModifiers::CONTROL) => {
            app.search.cycle_min_rating();
        }
        KeyCode::Char(c) => {
            app.search.insert_char(c);
            request_suggestions(app);
        }
        _ => {}
    }
}

fn request_suggestions(app: &App) {
    let keyword = app.search.extract_last_keyword().to_string();
    if keyword.is_empty() {
        return;
    }
    let tx = app.tx.clone();
    let client = app.client.clone();
    tokio::spawn(async move {
        match client.suggest_tags(&keyword, 10).await {
            Ok(resp) => {
                let _ = tx.send(AppEvent::SuggestionsLoaded(Ok(resp.suggestions)));
            }
            Err(e) => {
                let _ = tx.send(AppEvent::SuggestionsLoaded(Err(e)));
            }
        }
    });
}

fn load_page_image(app: &App) {
    let gid = app.reader.gid.clone();
    let token = app.reader.token.clone();
    let page = app.reader.current_page;
    let tx = app.tx.clone();
    let client = app.client.clone();
    tokio::spawn(async move {
        match client.get_page_image(&gid, &token, page).await {
            Ok(response) => {
                let content_length = response
                    .content_length()
                    .unwrap_or(0);
                let bytes = match response.bytes().await {
                    Ok(b) => b,
                    Err(e) => {
                        let _ = tx.send(AppEvent::ImageError {
                            url: format!("page:{}", page),
                            error: e.to_string(),
                        });
                        return;
                    }
                };
                if content_length > 0 {
                    let _ = tx.send(AppEvent::PageImageProgress {
                        page,
                        received: bytes.len() as u64,
                        total: content_length,
                    });
                }
                match image::load_from_memory(&bytes) {
                    Ok(img) => {
                        let _ = tx.send(AppEvent::PageImageLoaded { page, image: img });
                    }
                    Err(e) => {
                        let _ = tx.send(AppEvent::ImageError {
                            url: format!("page:{}", page),
                            error: e.to_string(),
                        });
                    }
                }
            }
            Err(e) => {
                let _ = tx.send(AppEvent::ImageError {
                    url: format!("page:{}", page),
                    error: e,
                });
            }
        }
    });
    // Trigger prefetch
    let gid2 = app.reader.gid.clone();
    let token2 = app.reader.token.clone();
    let client2 = app.client.clone();
    tokio::spawn(async move {
        let _ = client2.prefetch(&gid2, &token2, page).await;
    });
}

fn switch_page_source(app: &mut App, source: PageSource) {
    if app.page_source == source {
        return;
    }
    app.page_source = source;
    app.gallery_list.clear();
    app.load_current_page();
}

fn handle_app_event(app: &mut App, event: AppEvent) {
    match event {
        AppEvent::GalleriesLoaded(Ok(items)) => {
            let count = items.len();
            app.gallery_list.items = items;
            app.gallery_list.loading = false;
            app.gallery_list.selected = 0;
            app.status_msg = format!("Loaded {} galleries", count);
            app.load_selected_detail();
        }
        AppEvent::GalleriesLoaded(Err(e)) => {
            app.gallery_list.loading = false;
            app.status_msg = format!("Error: {}", e);
        }
        AppEvent::DetailLoaded(Ok(detail)) => {
            app.gallery_list.detail = Some(detail);
        }
        AppEvent::DetailLoaded(Err(e)) => {
            app.status_msg = format!("Detail error: {}", e);
        }
        AppEvent::SuggestionsLoaded(Ok(suggestions)) => {
            app.search.suggestions = suggestions;
            app.search.selected_suggestion = None;
        }
        AppEvent::SuggestionsLoaded(Err(_)) => {
            app.search.suggestions.clear();
        }
        AppEvent::ThumbnailLoaded { url, image } => {
            app.image_cache.put(url, image);
        }
        AppEvent::PageImageLoaded { page, image } => {
            if page == app.reader.current_page {
                app.page_image = Some(image);
                app.reader.loading = false;
                app.reader.loading_progress = None;
            }
        }
        AppEvent::PageImageProgress {
            page,
            received,
            total,
        } => {
            if page == app.reader.current_page {
                app.reader.loading_progress = Some((received, total));
            }
        }
        AppEvent::ImageError { url, error } => {
            if url.starts_with("page:") {
                app.reader.loading = false;
                app.reader.error = Some(error);
            }
        }
        AppEvent::DownloadSubmitted(Ok(task)) => {
            app.downloads.tasks.push(task);
            app.downloads.active_count += 1;
        }
        AppEvent::DownloadSubmitted(Err(e)) => {
            app.status_msg = format!("Download error: {}", e);
        }
        AppEvent::DownloadsRefreshed(Ok(tasks)) => {
            app.downloads.tasks = tasks;
        }
        AppEvent::DownloadsRefreshed(Err(_)) => {}
        AppEvent::FavoritesLoaded(Ok(resp)) => {
            app.gallery_list.items = resp.galleries;
            app.gallery_list.loading = false;
            app.gallery_list.selected = 0;
        }
        AppEvent::FavoritesLoaded(Err(e)) => {
            app.gallery_list.loading = false;
            app.status_msg = format!("Favorites error: {}", e);
        }
        AppEvent::WsEvent(ev) => {
            if let Some(ref gid) = ev.gid {
                app.downloads.update_from_ws(
                    gid,
                    &ev.event,
                    ev.page,
                    ev.total,
                    ev.path.as_deref(),
                    ev.error.as_deref(),
                );
            }
        }
        AppEvent::WsDisconnected => {
            app.status_msg = "WS disconnected".to_string();
        }
        AppEvent::WsReconnected => {
            app.status_msg.clear();
        }
        AppEvent::Tick => {}
        AppEvent::Key(_) => {} // Keys are handled separately in handle_key
    }
}
