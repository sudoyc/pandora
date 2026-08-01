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
- download state reconciled from `/api/downloads` on load and WebSocket reconnect
- bounded exponential-backoff WebSocket reconnect for daemon restarts
- recent download progress panel
- favorites, browsing history, downloads, and local library workspace views
- local library reader using daemon-served page files
- loading, empty, error, and retry states for workspace data
- Vitest unit/component coverage for feed, detail, reader, and WebSocket state
- Playwright browser coverage for gallery, daemon-restart, workspace navigation, and local reader workflows
- typed daemon GET/error client and discriminated app view state
- split sidebar, search/header, gallery feed, and download progress components
- CSS variable based dark theme

Still intentionally lightweight / next refactor targets:

- The typed API client currently covers the GET/error behavior used by existing views; add endpoint-specific helpers as new workflows land.
- Expand browser coverage for the remaining views.
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

The default browser suite is deterministic and intercepts daemon requests with
fixtures. Its image fixtures contain decodable pixels and assert non-zero
browser image dimensions; it does not claim that the current upstream session
or CDN is usable.

```bash
cd pandora-web
npm run test:unit
npm run test:browser
npm run lint
npm run build
```

For read-only end-to-end usability evidence, start an authenticated daemon and
run the separate live suite. It requires readiness to be fully healthy, loads
real gallery data through the daemon, decodes multiple thumbnails plus the
detail cover and first reader page, rejects failed image responses, and checks
that the browser never contacts upstream image hosts directly:

```bash
cd pandora-web
npm run test:live
```

The daemon defaults to `http://127.0.0.1:7860`. Override it with
`PANDORA_LIVE_DAEMON_URL`; change the sample size with
`PANDORA_LIVE_IMAGE_SAMPLES`. Live tests remain outside hosted CI because they
require credentials and a changing external service, but they are mandatory
release-gate evidence for upstream-facing changes. See
[testing and usability acceptance](../docs/development/testing.md).

## Recommended next work

1. Add endpoint-specific typed helpers as mutation workflows land.
2. Add download cancel/resume/retry controls with explicit confirmation where needed.
3. Cover remaining empty, error, retry, and critical browser paths.
4. Complete responsive layout and keyboard/focus checks across desktop and mobile viewports.
