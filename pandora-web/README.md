# Pandora Web Frontend

React + TypeScript + Vite frontend for Pandora. The web app talks only to the local `pandora-daemon` REST and WebSocket API; it never requests ExHentai directly.

## Current state

Implemented:

- Vite/React project scaffold
- gallery feed with paginated search/watched views and single-page homepage/popular views
- homepage / popular / watched / search view switching
- gallery cards using the daemon image proxy (`/api/image/proxy`)
- gallery detail drawer backed by `/api/gallery/{gid}/{token}`
- fullscreen reader backed by `/api/gallery/{gid}/{token}/page/{page}`
- WebSocket hook for daemon download events using the `event` field
- recent download progress panel
- Vitest unit/component coverage for feed, detail, reader, and WebSocket state
- Playwright browser smoke coverage for the feed-to-reader workflow
- CSS variable based dark theme

Still intentionally lightweight / next refactor targets:

- `src/App.tsx` still owns layout, sidebar state, search form, search history, gallery selection, and download progress rendering; split it before adding more views.
- WebSocket progress state is live-event only; reconcile with `/api/downloads` on load/reconnect.
- Add dedicated pages for favorites, history, downloads, and local library.
- Expand browser coverage for reconnect/restart behavior and the remaining views.
- Generated `dist/` and `node_modules/` are ignored under `pandora-web/.gitignore` and should not be treated as source.

## Run

Start daemon first:

```bash
uv run python -m pandora_daemon
```

Then run the web app:

```bash
cd pandora-web
npm run dev
```

Default daemon target: `http://127.0.0.1:7860`.

Override in development if needed:

```bash
VITE_PANDORA_DAEMON_URL=http://127.0.0.1:7860 npm run dev
```

## Test / lint / build

```bash
cd pandora-web
npm run test:unit
npm run test:browser
npm run lint
npm run build
```

## Recommended next refactor

1. Split `App.tsx`:
   - `components/layout/AppShell.tsx`
   - `components/layout/Sidebar.tsx`
   - `components/search/SearchBar.tsx`
   - `features/gallery/GalleryFeed.tsx`
   - `features/downloads/DownloadProgressPanel.tsx`
2. Expand `src/api/client.ts` into a typed API client:
   - `apiGet<T>()`, `apiPost<T>()`, `apiDelete<T>()`
   - explicit error type for non-2xx responses
   - typed helpers for downloads/favorites/library
3. Introduce route/view state:
   - home
   - search
   - popular
   - watched
   - favorites
   - history
   - downloads
   - library
4. Make `useGalleries` accept a typed source/query object instead of `(mode, keyword)`.
5. Add smoke tests for: gallery feed load, search, drawer open, reader image URL, WS event reducer.
