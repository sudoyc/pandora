# Pandora Library PDF Export Implementation Plan

> **For Hermes:** Use strict TDD for production changes. OpenCode may be used for bounded coding/review tasks, but Hermes owns architecture, verification, staging, and final commit hygiene.

**Goal:** Add a daemon-backed PDF export capability for downloaded gallery/library items, with an explicit password input surface for protected PDF output and documented bot hooks.

**Architecture:** Keep downloads and local library state inside `pandora-daemon`. PDF export is a new library/export feature that consumes already-downloaded `pages/` files and emits machine-readable REST/CLI responses plus WebSocket export events. Agent Pack documentation is the canonical delivery surface; the Hermes/Pandora skill remains a packaged consumer and pointer.

**Tech Stack:** Python 3.12, FastAPI, Pillow for image-to-PDF, optional pypdf for PDF encryption if Pillow cannot provide password protection, httpx CLI client, pytest via `uv run python -m pytest`, Markdown Agent Pack docs, JSON Schema.

---

## Product Decisions

1. PDF export is a separate library feature, not part of the gallery download worker.
2. Export source is an already-downloaded gallery under the daemon library path.
3. Password support is for PDF open/protection use. Do not document or implement it as evasion of any platform policy or risk engine.
4. Password must have at least one explicit entry point; implement both REST and CLI entry points:
   - REST body: `{"password": "..."}`
   - CLI flag: `--password "..."`
5. Password values must not be included in JSON responses, WebSocket events, logs, metadata files, or Agent Pack examples with real secrets.
6. If a configured default password is added, it must be optional and redacted from public config output. Prefer explicit CLI/REST password over config default.
7. Hooks must be documented in the generic Agent Pack (`docs/agent/`) and summarized in `.agents/skills/pandora/SKILL.md`.

## Existing WIP Boundary

Do not stage or edit unrelated current WIP unless the user explicitly asks:

- `pandora-web/*`
- `pandora-tui/Cargo.lock`
- unrelated hunks in `pandora_daemon/app.py`

Use exact-path staging only.

## Target Interface

### REST

```http
POST /api/library/{gid}/export/pdf
Content-Type: application/json
```

Request body:

```json
{
  "password": "optional-open-password",
  "output_name": "optional-file-name.pdf",
  "include_cover": false
}
```

Response:

```json
{
  "ok": true,
  "gid": "123",
  "format": "pdf",
  "path": "/absolute/path/to/export.pdf",
  "password_protected": true
}
```

Errors:

- `400`: invalid gid, invalid output name, no pages available, unsupported image set.
- `404`: library gallery not found.
- `500`: export failure.

### CLI

```bash
uv run python -m pandora_daemon.cli library export-pdf 123 --password "..." --json
uv run python -m pandora_daemon.cli library export-pdf 123 --output-name "123.pdf" --json
```

Machine output mirrors REST response and never echoes the password.

### WebSocket hook/events

If export runs synchronously in the first implementation, still broadcast lifecycle events from the daemon route/service so bots can subscribe to the same hook path later:

```json
{"event":"pdf_export_started","gid":"123"}
{"event":"pdf_export_complete","gid":"123","path":"/path/to/file.pdf","password_protected":true}
{"event":"pdf_export_error","gid":"123","error":"..."}
```

The event discriminator remains `event`, not `type`.

## Task 1: Add failing route/service tests

**Objective:** Lock the REST contract before implementation.

**Files:**
- Modify: `tests/pandora_daemon/test_routes_library.py`
- Create if needed: `tests/pandora_daemon/test_pdf_export.py`

**Tests:**
- Export endpoint returns `200` with `ok`, `gid`, `format: pdf`, `path`, `password_protected`.
- Request `password` sets `password_protected: true` without echoing the password anywhere in response.
- Missing gallery returns `404`.
- Gallery with no page files returns `400`.
- Invalid output name/path traversal returns `400`.
- WebSocket manager receives `pdf_export_started` then `pdf_export_complete` on success, or `pdf_export_error` on failure.

**RED command:**

```bash
uv run python -m pytest tests/pandora_daemon/test_routes_library.py -q
```

Expected before implementation: fails because route/service does not exist.

## Task 2: Implement minimal PDF export service

**Objective:** Convert downloaded page images into a local PDF file and optionally protect it with a password.

**Files:**
- Create: `pandora_daemon/pdf_export.py`
- Modify: `pandora_daemon/routes/library.py`
- Potentially modify: `pyproject.toml`, `uv.lock` if encryption needs a new dependency.

**Implementation notes:**
- Reuse `_find_gallery_dir()` to resolve the gallery directory.
- Read `pages/` files sorted by numeric filename (`0001.*`, `0002.*`, ...).
- Use Pillow to open each image, convert to `RGB`, and save multipage PDF atomically through a temp file.
- Write exports under the gallery dir, e.g. `exports/{gid}.pdf`, unless `output_name` is provided.
- Sanitize `output_name`: filename only, must end in `.pdf`, no slash/backslash/path traversal.
- Password handling:
  - Preferred: generate plain PDF with Pillow, then encrypt copy with a dedicated PDF library if needed.
  - If adding `pypdf`, use `PdfReader`, `PdfWriter`, `writer.encrypt(password)`, atomic write, then replace output.
  - Never log or return password.
- Synchronous route is acceptable initially because export is local CPU/file work; if large galleries become slow, convert to background queue later without changing event names.

**GREEN command:**

```bash
uv run python -m pytest tests/pandora_daemon/test_routes_library.py -q
```

## Task 3: Add CLI command and tests

**Objective:** Give bots a stable machine command with a password input surface.

**Files:**
- Modify: `pandora_daemon/cli.py`
- Modify: `tests/pandora_daemon/test_cli.py`

**CLI parser:**
- Convert `library` from a loose positional subcommand into explicit subparsers while preserving `library list --json`.
- Add `library export-pdf <gid>`.
- Add flags:
  - `--password`
  - `--output-name`
  - `--include-cover`
  - common `--json`, `--daemon-url`, `--timeout`

**Behavior:**
- POST `/api/library/{gid}/export/pdf` with JSON body containing only provided options.
- `--json` output returns REST response.
- Human output may print the PDF path and password-protected boolean, but never prints password.

**RED/GREEN command:**

```bash
uv run python -m pytest tests/pandora_daemon/test_cli.py -q
```

## Task 4: Update Agent Pack contract, workflow, snippets, and schema

**Objective:** Make hook configuration and bot success criteria part of the generic delivery documentation.

**Files:**
- Modify: `docs/agent/contract.md`
- Modify: `docs/agent/workflows/library.md`
- Modify: `docs/agent/snippets/download-agent.md` or create `docs/agent/snippets/library-export-agent.md`
- Modify: `docs/agent/README.md`
- Create: `docs/agent/schemas/pdf-export-event.schema.json`
- Modify: `tests/pandora_daemon/test_agent_contracts.py`

**Content requirements:**
- Document `library export-pdf` CLI command and REST endpoint.
- Document `--password` / REST `password` as PDF protection input, with a warning not to expose or log passwords.
- Document WebSocket hook events:
  - `pdf_export_started`
  - `pdf_export_complete`
  - `pdf_export_error`
- Document bot success criteria:
  - REST/CLI response `ok: true` and `password_protected` boolean.
  - Optional WS `pdf_export_complete` event.
  - Do not treat password-protected status as a signal to bypass any platform policy.
- Keep Agent Pack as source of truth; Hermes skill points to it.

**Verification:**

```bash
uv run python - <<'PY'
import json
from pathlib import Path
for p in Path('docs/agent/schemas').glob('*.json'):
    json.load(open(p))
    print(p)
PY
uv run python -m pytest tests/pandora_daemon/test_agent_contracts.py -q
```

## Task 5: Update Pandora skill packaging note

**Objective:** Keep `.agents/skills/pandora/SKILL.md` aligned without duplicating the whole contract.

**Files:**
- Modify: `.agents/skills/pandora/SKILL.md`

**Content requirements:**
- Add `library export-pdf` command example.
- Add concise note: export hooks and password handling are documented in `docs/agent/contract.md` and `docs/agent/workflows/library.md`.
- Emphasize the skill is a consumer/wrapper, not the canonical source.

## Task 6: Verification and review

**Commands:**

```bash
uv run python -m pytest tests/pandora_daemon/test_routes_library.py tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_agent_contracts.py -q
uv run python -m pytest -q
git diff --check
git diff --stat
```

**Review checklist:**
- Password never appears in response/event/docs examples except placeholder values.
- No platform-evasion framing in docs or code comments.
- No direct `exhentai_api` access from Agent Pack/plugin layers.
- No Web/TUI WIP staged.
- Exact files only.

## Task 7: Commit and push

**Stage exact intended files only**, for example:

```bash
git add \
  .hermes/plans/2026-05-22_1701-pandora-library-pdf-export.md \
  pyproject.toml uv.lock \
  pandora_daemon/pdf_export.py \
  pandora_daemon/routes/library.py \
  pandora_daemon/cli.py \
  tests/pandora_daemon/test_routes_library.py \
  tests/pandora_daemon/test_cli.py \
  tests/pandora_daemon/test_agent_contracts.py \
  docs/agent/README.md \
  docs/agent/contract.md \
  docs/agent/workflows/library.md \
  docs/agent/snippets/download-agent.md \
  docs/agent/schemas/pdf-export-event.schema.json \
  .agents/skills/pandora/SKILL.md
```

Only include `pyproject.toml`/`uv.lock` if a PDF encryption dependency is actually added.

Commit message:

```bash
git commit -m "feat: add library PDF export contract"
```

Push:

```bash
git push origin HEAD
```
