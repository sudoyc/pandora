mod app;
mod client;
mod config;
mod event;
mod models;
mod state;
mod ui;

use std::io;
use std::time::Duration;

use crossterm::{
    event::{Event, KeyCode, KeyEventKind, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::prelude::*;
use ratatui_image::picker::Picker;
use tokio::sync::mpsc;
use tokio_util::sync::CancellationToken;

use app::{App, AppMode, PageSource};
use client::DaemonClient;
use event::AppEvent;

const PRELOAD_WINDOW_LOCAL: u32 = 10;
const PRELOAD_WINDOW_ONLINE: u32 = 3;
const PRELOAD_CONCURRENT: usize = 3;
const RENDER_BURST_FRAMES: u8 = 2;

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

    // Detect terminal image protocol before entering raw mode
    let picker = Picker::from_query_stdio().unwrap_or_else(|_| Picker::halfblocks());

    let mut app = App::new(client, tx.clone(), picker);

    // Load initial page
    app.load_current_page();

    // WebSocket background connection
    {
        let ws_url = app.client.ws_url();
        let tx_ws = tx.clone();
        tokio::spawn(async move {
            use futures_util::StreamExt;
            use tokio_tungstenite::connect_async;

            loop {
                match connect_async(&ws_url).await {
                    Ok((ws_stream, _)) => {
                        let _ = tx_ws.send(crate::event::AppEvent::WsReconnected);
                        let (_, mut read) = ws_stream.split();
                        while let Some(msg) = read.next().await {
                            match msg {
                                Ok(tokio_tungstenite::tungstenite::Message::Text(text)) => {
                                    if let Ok(ev) = serde_json::from_str::<crate::models::WsEvent>(&text) {
                                        let _ = tx_ws.send(crate::event::AppEvent::WsEvent(ev));
                                    }
                                }
                                Err(_) => break,
                                _ => {}
                            }
                        }
                        let _ = tx_ws.send(crate::event::AppEvent::WsDisconnected);
                    }
                    Err(_) => {}
                }
                tokio::time::sleep(std::time::Duration::from_secs(3)).await;
            }
        });
    }

    // Install panic hook to restore terminal on crash
    let original_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |panic_info| {
        let _ = disable_raw_mode();
        let _ = execute!(io::stdout(), LeaveAlternateScreen);
        original_hook(panic_info);
    }));

    // Terminal setup
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // Async terminal event stream
    let mut term_events = crossterm::event::EventStream::new();

    // Render state
    let mut dirty = true;
    let mut render_burst: u8 = 0;

    // Debounce state for search suggestions
    let mut suggest_deadline: Option<tokio::time::Instant> = None;

    loop {
        // Render if dirty
        if dirty {
            terminal.draw(|frame| {
                ui::draw(frame, &mut app);
            })?;
            dirty = false;
            if render_burst > 0 {
                render_burst -= 1;
                dirty = true;
            }
        }

        if app.should_quit {
            break;
        }

        // Block until an event arrives
        tokio::select! {
            maybe_event = futures_util::StreamExt::next(&mut term_events) => {
                if let Some(Ok(event)) = maybe_event {
                    match event {
                        Event::Key(key) if key.kind == KeyEventKind::Press => {
                            handle_key(&mut app, key.code, key.modifiers);
                            dirty = true;
                        }
                        Event::Resize(_, _) => {
                            dirty = true;
                        }
                        _ => {}
                    }
                }
            }
            Some(app_event) = rx.recv() => {
                let is_image_event = matches!(
                    app_event,
                    AppEvent::ThumbnailLoaded { .. } | AppEvent::PageImageLoaded { .. }
                );
                handle_app_event(&mut app, app_event);
                dirty = true;
                if is_image_event {
                    render_burst = RENDER_BURST_FRAMES;
                }
            }
            _ = async {
                match suggest_deadline {
                    Some(deadline) => tokio::time::sleep_until(deadline).await,
                    None => std::future::pending::<()>().await,
                }
            }, if suggest_deadline.is_some() => {
                suggest_deadline = None;
                request_suggestions(&app);
                dirty = true;
            }
        }

        // Check if a keystroke scheduled a suggestion debounce
        if app.suggest_pending {
            suggest_deadline = Some(tokio::time::Instant::now() + Duration::from_millis(150));
            app.suggest_pending = false;
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
                let is_local = app.page_source == PageSource::Downloaded;
                app.reader = state::ReaderState {
                    current_page: 1,
                    total_pages: detail.pages,
                    gid: detail.gid.clone(),
                    token: detail.token.clone(),
                    title: detail.title.clone(),
                    is_local,
                    ..Default::default()
                };
                app.mode = AppMode::Read;
                start_page_load(app);
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
                let tx = app.tx.clone();
                let client = app.client.clone();
                tokio::spawn(async move {
                    if let Err(e) = client.add_favorite(&gid, &token, 0).await {
                        let _ = tx.send(AppEvent::ImageError {
                            url: String::new(),
                            error: e,
                        });
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
            app.page_image_state = None;
            app.page_cache.clear();
            app.pending_pages.clear();
        }
        KeyCode::Char('j') | KeyCode::Char('l') | KeyCode::Char(' ') | KeyCode::Down => {
            if app.reader.next_page() {
                start_page_load(app);
            }
        }
        KeyCode::Char('k') | KeyCode::Up => {
            if app.reader.prev_page() {
                start_page_load(app);
            }
        }
        KeyCode::Char('G') => {
            if app.reader.last_page() {
                start_page_load(app);
            }
        }
        KeyCode::Char('g') => {
            if was_pending_g {
                if app.reader.first_page() {
                    start_page_load(app);
                }
                app.pending_g = false;
            } else {
                app.pending_g = true;
            }
        }
        KeyCode::Char('r') => {
            start_page_load(app);
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
                app.page_source = PageSource::Search {
                    keyword: keyword.clone(),
                    category: cat,
                    min_rating: rating,
                };
                app.gallery_list.clear();
                app.gallery_list.loading = true;
                app.load_current_page();
            }
        }
        KeyCode::Backspace => {
            app.search.delete_char();
            app.suggest_pending = true;
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
            app.suggest_pending = true;
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

fn save_current_page_to_cache(app: &mut App) {
    if let Some(img) = app.page_image.take() {
        let key = format!("page:{}:{}", app.reader.gid, app.reader.current_page);
        app.page_cache.put(key, img);
        app.page_image_state = None;
    }
}

fn start_page_load(app: &mut App) {
    // Save outgoing page to cache before loading new one
    save_current_page_to_cache(app);

    let page = app.reader.current_page;
    let cache_key = format!("page:{}:{}", app.reader.gid, page);

    // Check page_cache first — instant display if cached
    if let Some(img) = app.page_cache.get(&cache_key) {
        app.page_image = Some(img.clone());
        app.page_image_state = None;
        app.reader.loading = false;
        app.reader.error = None;
        app.reader.loading_progress = None;
        // Still preload neighbors
        preload_adjacent_pages(app);
        return;
    }

    app.reader.loading = true;
    app.reader.error = None;
    app.page_image = None;
    app.page_image_state = None;
    app.page_load_cancel.cancel();
    app.page_load_cancel = CancellationToken::new();
    let cancel = app.page_load_cancel.clone();
    load_page_image(app, cancel);
    preload_adjacent_pages(app);
}

fn load_page_image(app: &App, cancel: CancellationToken) {
    let gid = app.reader.gid.clone();
    let token = app.reader.token.clone();
    let page = app.reader.current_page;
    let is_local = app.reader.is_local;
    let tx = app.tx.clone();
    let client = app.client.clone();

    if is_local {
        // Local: fetch from library file endpoint
        tokio::spawn(async move {
            tokio::select! {
                _ = cancel.cancelled() => {}
                _ = async {
                    let path = format!("page/{}", page);
                    match client.get_library_file(&gid, &path).await {
                        Ok(bytes) => {
                            let bytes_vec = bytes.to_vec();
                            match tokio::task::spawn_blocking(move || image::load_from_memory(&bytes_vec)).await {
                                Ok(Ok(img)) => {
                                    let _ = tx.send(AppEvent::PageImageLoaded { page, image: img });
                                }
                                Ok(Err(e)) => {
                                    let _ = tx.send(AppEvent::ImageError {
                                        url: format!("page:{}", page),
                                        error: e.to_string(),
                                    });
                                }
                                Err(_) => {
                                    let _ = tx.send(AppEvent::ImageError {
                                        url: format!("page:{}", page),
                                        error: "image decode task panicked".to_string(),
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
                } => {}
            }
        });
    } else {
        // Online: fetch from daemon page endpoint
        tokio::spawn(async move {
            tokio::select! {
                _ = cancel.cancelled() => {}
                _ = async {
                    match client.get_page_image(&gid, &token, page).await {
                        Ok(response) => {
                            let content_length = response.content_length().unwrap_or(0);
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
                            let bytes_vec = bytes.to_vec();
                            match tokio::task::spawn_blocking(move || image::load_from_memory(&bytes_vec)).await {
                                Ok(Ok(img)) => {
                                    let _ = tx.send(AppEvent::PageImageLoaded { page, image: img });
                                }
                                Ok(Err(e)) => {
                                    let _ = tx.send(AppEvent::ImageError {
                                        url: format!("page:{}", page),
                                        error: e.to_string(),
                                    });
                                }
                                Err(_) => {
                                    let _ = tx.send(AppEvent::ImageError {
                                        url: format!("page:{}", page),
                                        error: "image decode task panicked".to_string(),
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
                } => {}
            }
        });
        // Online prefetch on daemon side
        let gid2 = app.reader.gid.clone();
        let token2 = app.reader.token.clone();
        let client2 = app.client.clone();
        tokio::spawn(async move {
            let _ = client2.prefetch(&gid2, &token2, page).await;
        });
    }
}

/// Preload adjacent pages into page_cache in background.
fn preload_adjacent_pages(app: &mut App) {
    let page = app.reader.current_page;
    let total = app.reader.total_pages;
    let is_local = app.reader.is_local;
    let gid = app.reader.gid.clone();
    let token = app.reader.token.clone();

    let (behind, ahead) = if is_local {
        (PRELOAD_WINDOW_LOCAL, PRELOAD_WINDOW_LOCAL)
    } else {
        (PRELOAD_WINDOW_ONLINE, PRELOAD_WINDOW_ONLINE)
    };
    let start = page.saturating_sub(behind).max(1);
    let end = (page + ahead).min(total);

    // Priority order: N+1, N-1, N+2, N-2, ...
    let mut pages_to_load: Vec<u32> = Vec::new();
    for delta in 1..=ahead.max(behind) {
        if page + delta <= end {
            pages_to_load.push(page + delta);
        }
        if delta <= behind && page > delta && page - delta >= start {
            pages_to_load.push(page - delta);
        }
    }

    for p in pages_to_load {
        let cache_key = format!("page:{}:{}", gid, p);
        if app.page_cache.contains(&cache_key) || app.pending_pages.contains(&p) {
            continue;
        }
        app.pending_pages.insert(p);

        let tx = app.tx.clone();
        let client = app.client.clone();
        let gid = gid.clone();
        let token = token.clone();
        let sem = app.preload_semaphore.clone();

        if is_local {
            tokio::spawn(async move {
                let _permit = sem.acquire().await;
                let path = format!("page/{}", p);
                if let Ok(bytes) = client.get_library_file(&gid, &path).await {
                    let bytes_vec = bytes.to_vec();
                    if let Ok(Ok(img)) = tokio::task::spawn_blocking(move || image::load_from_memory(&bytes_vec)).await {
                        let _ = tx.send(AppEvent::PageImageLoaded { page: p, image: img });
                    }
                }
            });
        } else {
            tokio::spawn(async move {
                let _permit = sem.acquire().await;
                if let Ok(resp) = client.get_page_image(&gid, &token, p).await {
                    if let Ok(bytes) = resp.bytes().await {
                        let bytes_vec = bytes.to_vec();
                        if let Ok(Ok(img)) = tokio::task::spawn_blocking(move || image::load_from_memory(&bytes_vec)).await {
                            let _ = tx.send(AppEvent::PageImageLoaded { page: p, image: img });
                        }
                    }
                }
            });
        }
    }
}

fn switch_page_source(app: &mut App, source: PageSource) {
    if app.page_source == source {
        return;
    }
    app.page_source = source;
    app.gallery_list.clear();
    app.failed_images.clear();
    app.pending_images.clear();
    app.image_states.clear();
    app.load_current_page();
}

fn handle_app_event(app: &mut App, event: AppEvent) {
    match event {
        AppEvent::GalleriesLoaded(Ok(items), generation) => {
            if generation != app.list_generation { return; }
            let count = items.len();
            app.gallery_list.items = items;
            app.gallery_list.loading = false;
            app.gallery_list.selected = 0;
            app.status_msg = format!("Loaded {} galleries", count);
            app.load_selected_detail();
        }
        AppEvent::GalleriesLoaded(Err(e), generation) => {
            if generation != app.list_generation { return; }
            app.gallery_list.loading = false;
            app.status_msg = if e.contains("timed out") || e.contains("timeout") {
                "Connection timed out — check daemon".to_string()
            } else if e.contains("connect") || e.contains("Connection refused") {
                "Cannot reach daemon — is it running?".to_string()
            } else {
                format!("Load failed: {}", e)
            };
        }
        AppEvent::DetailLoaded(Ok(detail), generation) => {
            if generation == app.detail_generation {
                app.gallery_list.detail = Some(detail);
            }
        }
        AppEvent::DetailLoaded(Err(e), generation) => {
            if generation == app.detail_generation {
                app.gallery_list.detail = None;
                app.status_msg = format!("Detail load failed: {}", e);
            }
        }
        AppEvent::SuggestionsLoaded(Ok(suggestions)) => {
            app.search.suggestions = suggestions;
            app.search.selected_suggestion = None;
        }
        AppEvent::SuggestionsLoaded(Err(_)) => {
            app.search.suggestions.clear();
        }
        AppEvent::ThumbnailLoaded { url, image } => {
            app.pending_images.remove(&url);
            app.image_states.remove(&url);
            app.image_cache.put(url, image);
            // Prune image_states for keys no longer in cache
            if app.image_states.len() > 300 {
                let cached_keys: std::collections::HashSet<String> =
                    app.image_cache.iter().map(|(k, _)| k.clone()).collect();
                app.image_states.retain(|k, _| cached_keys.contains(k));
            }
        }
        AppEvent::PageImageLoaded { page, image } => {
            app.pending_pages.remove(&page);
            if page == app.reader.current_page {
                app.page_image_state = None;
                app.reader.loading = false;
                app.reader.loading_progress = None;
                app.page_image = Some(image);
            } else {
                let cache_key = format!("page:{}:{}", app.reader.gid, page);
                app.page_cache.put(cache_key, image);
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
            app.pending_images.remove(&url);
            if app.failed_images.len() > 500 {
                app.failed_images.clear();
            }
            app.failed_images.insert(url.clone());
            if url.starts_with("page:") {
                if let Ok(p) = url.trim_start_matches("page:").parse::<u32>() {
                    app.pending_pages.remove(&p);
                    if p == app.reader.current_page {
                        app.reader.loading = false;
                        app.reader.error = Some(error);
                    }
                }
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
    }
}
