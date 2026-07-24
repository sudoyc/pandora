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
- typed daemon GET/error client and discriminated gallery view state
- split sidebar, search/header, gallery feed, and download progress components
- CSS variable based dark theme

Still intentionally lightweight / next refactor targets:

- The typed API client currently covers the GET/error behavior used by existing views; add endpoint-specific helpers as new workflows land.
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

## Recommended next work

1. Reconcile WebSocket download state from `/api/downloads` on initial load and reconnect.
2. Add endpoint-specific typed helpers alongside favorites, history, downloads, and library views.
3. Cover reconnect/restart behavior with browser tests before expanding the workflows.
4. Complete responsive layout and keyboard/focus checks across desktop and mobile viewports.
