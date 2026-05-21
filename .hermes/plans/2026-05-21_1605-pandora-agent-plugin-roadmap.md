# Pandora Agent/Plugin Roadmap and Repository整理计划

> **For Hermes:** Use this plan as the handoff document before implementing. Implementation may coordinate OpenCode, but Hermes should verify every diff and test result before reporting success.

**Goal:** Re-orient Pandora from “daemon + multiple human frontends” toward a stable daemon/CLI contract that is easy to drive from Hermes skills/plugins, while treating the Rust TUI as deprecated and removable.

**Architecture direction:** Keep `exhentai_api` stateless and keep `pandora_daemon` as the only stateful gateway to ExHentai. Move agent-facing interaction into stable REST + CLI JSON/NDJSON contracts first; package those workflows as a Hermes skill, and only then consider a full Hermes tool/plugin wrapper. Do not invest further in the Rust TUI unless it is needed as a temporary API contract reference.

**Tech stack:** Python 3.12 + FastAPI + httpx + aiosqlite + uv; optional React/Vite web frontend; optional Hermes skill/plugin integration; OpenCode may be used for implementation subtasks.

---

## 1. Read-only exploration summary

### Current tracked source layout

Tracked top-level file counts from `git ls-files`:

- `tests/`: 55 tracked entries
- `docs/`: 35 tracked entries
- `exhentai_api/`: 30 Python source files
- `pandora_daemon/`: 27 Python source files
- `pandora-web/`: 25 tracked entries
- `pandora-tui/`: 23 tracked entries
- `.agents/`: 1 tracked Pandora agent skill
- root context/docs: `README.md`, `GEMINI.md`, `ARCHITECTURE.md`, `todo.md`, `pyproject.toml`, `pytest.ini`, `uv.lock`

Code size from `uvx pygount` excluding `.git`, `.venv`, `node_modules`, `dist`, `target`, caches:

- Python: 104 files, 8420 code lines
- Rust: 21 files, 2282 code lines
- Web frontend TS/TSX/CSS/HTML: small WIP surface, roughly 800-900 code lines depending generated assets exclusion
- Markdown docs: 45 files, 11939 documentation/comment lines
- Total scanned: 233 files, 11753 code lines

Generated artifacts are present locally but not tracked:

- `pandora-tui/target/`
- `pandora-web/dist/`
- `pandora-web/node_modules/`

Do not include those in source review or commits. They can be deleted locally when convenient, but deletion is not required for the plan.

### Current uncommitted user/workspace changes

Existing modified files before this plan was written:

- `README.md`
- `docs/api_reference.md`
- `docs/architecture.md`
- `pandora-tui/Cargo.lock`
- `pandora-web/README.md`
- `pandora-web/src/App.tsx`
- `pandora-web/src/api/client.ts`
- `pandora-web/src/components/GalleryCard.tsx`
- `pandora-web/src/components/GalleryDrawer.tsx`
- `pandora-web/src/components/Reader.tsx`
- `pandora-web/src/hooks/useGalleries.ts`
- `pandora-web/src/hooks/useWebSocket.ts`
- `pandora-web/src/models.ts`
- `pandora-web/src/styles/variables.css`
- `pandora_daemon/app.py`

These look like prior WIP around web UI/API docs and CLI contract documentation. This plan does not overwrite them.

### OpenCode read-only review outcome

OpenCode was available (`opencode 1.15.3`) and authenticated. It performed a read-only architecture review and agreed with the following:

- `pandora-tui/` is a pure REST/WebSocket consumer and is not imported by daemon/CLI/package code.
- Python packaging in `pyproject.toml` includes only `exhentai_api` and `pandora_daemon`.
- TUI can be deprecated from the core architecture, but its endpoint/model expectations should be preserved in daemon/CLI/schema tests before deletion.
- Main agent/plugin gaps are health/config CLI commands, explicit response schemas, consistent error envelopes, and daemon lifecycle/probe contracts.

---

## 2. File organization decisions

### Keep as core source

- `exhentai_api/`
  - Role: stateless HTTP + parser + model library.
  - Rule: no config, cache, DB, UI, daemon lifecycle, or agent-specific state.

- `pandora_daemon/`
  - Role: stateful daemon, cache, DB, downloads, local library, REST/WS, CLI automation.
  - Priority files for next work:
    - `pandora_daemon/app.py`
    - `pandora_daemon/config.py`
    - `pandora_daemon/cli.py`
    - `pandora_daemon/routes/config_routes.py`
    - `pandora_daemon/routes/downloads.py`
    - `pandora_daemon/routes/gallery.py`
    - `pandora_daemon/routes/library.py`
    - `pandora_daemon/ws.py`

- `tests/exhentai_api/` and `tests/pandora_daemon/`
  - Role: primary safety net.
  - Add new agent-contract tests here rather than relying on TUI behavior.

- `.agents/skills/pandora/SKILL.md`
  - Role: current repo-local agent skill.
  - Keep and update after the daemon/CLI contract is made true. It currently documents `config --json`, but `pandora_daemon/cli.py` does not implement a `config` subcommand yet.

### Mark as deprecated/frozen

- `pandora-tui/`
  - Current role: mature but likely obsolete Rust frontend and useful reference consumer.
  - New role: frozen/deprecated reference until the agent/Hermes contract covers equivalent flows.
  - Do not spend development time on TUI polish.
  - Do not delete immediately until P1/P2 below are done.
  - If kept temporarily, remove it from default Quick Start and default verification commands; keep a short “legacy TUI” note.

### Keep optional but lower priority

- `pandora-web/`
  - Current role: WIP React/Vite frontend.
  - New role: optional human UI, secondary to daemon/CLI/Hermes contract.
  - Avoid expanding web scope until agent/plugin flows are stable.
  - Existing web WIP can remain, but do not let it define the API contract.

### Archive or rename docs/context later

Candidate doc cleanup after contracts are updated:

- Root `ARCHITECTURE.md`
  - It is actually an EhViewer Android reference report, not current Pandora architecture.
  - Proposed move: `docs/archive/reference/ehviewer-android-architecture.md`.
  - Replace root pointer with a short note or remove root file if no tools require it.

- `GEMINI.md`
  - Stale: says web frontend is current objective and TUI is suspended.
  - Update after roadmap shift to “daemon/CLI/Hermes skill/plugin first; web optional; TUI deprecated.”

- `todo.md`
  - Stale: only lists completed web frontend implementation tasks.
  - Replace with a concise active roadmap or move to `docs/archive/plans/`.

- `docs/tui-audit-2026-04-05.md`, `docs/tui-bugfix-design.md`, `docs/tui-visual-design.md`
  - Keep as historical reference if TUI remains frozen.
  - If TUI is deleted, move under `docs/archive/tui/` or remove after extracting any API contract expectations.

---

## 3. Target agent/plugin interface design

### Contract principle

Hermes should not need to know ExHentai HTML, cookies, page parsing, binary image fetching, or internal DB/cache paths. It should call stable daemon REST or stable `pandora` CLI commands and receive machine-readable JSON/NDJSON.

Preferred stack for agents:

1. `pandora-daemon` provides local service and state.
2. `pandora` CLI provides stable JSON/NDJSON operations for scripts and skills.
3. Hermes skill documents exact commands, expected JSON, verification, and pitfalls.
4. Optional Hermes plugin/toolset wraps the CLI/REST with first-class tools only after the CLI is stable.

### Minimum daemon capabilities for agents

Add a real health endpoint:

- `GET /api/health`

Proposed JSON shape:

```json
{
  "ok": true,
  "version": "0.2.0",
  "service": "pandora-daemon",
  "auth_configured": true,
  "config_path": "~/.config/pandora/config.toml",
  "database_path": "~/.config/pandora/pandora.db",
  "download_path": "~/Downloads/pandora",
  "cache_path": "~/.cache/pandora/images",
  "capabilities": {
    "browse": true,
    "gallery_detail": true,
    "downloads": true,
    "library": true,
    "tags": true,
    "favorites": true,
    "websocket": true
  }
}
```

Add or standardize public config endpoint:

- Existing: `GET /api/config`
- Keep credentials stripped.
- Add `credentials_configured` boolean either here or only in `/api/health`.

Standardize error envelopes:

- Existing daemon sometimes returns `{"error": "...", "detail": "..."}` and sometimes `{"detail": "..."}`.
- For agent work, prefer:

```json
{
  "error": "machine_readable_code",
  "detail": "human readable message"
}
```

### Minimum CLI commands for Hermes skill

Already present or mostly present:

```bash
pandora status --json
pandora search "keyword" --page 0 --json
pandora gallery "https://exhentai.org/g/123/abcdef0123/" --json
pandora gallery 123 abcdef0123 --json
pandora download add "https://exhentai.org/g/123/abcdef0123/" --json
pandora download list --json
pandora download watch 123 --ndjson
pandora download pages 123 --json
pandora download cancel 123 --json
pandora download resume 123 --json
pandora download retry 123 --json
pandora library list --json
pandora tags suggest "artist" --json
pandora favorites list --json
pandora popular --json
pandora toplist --tl 15 --json
pandora watched --page 0 --json
```

Need to add or align:

```bash
pandora health --json
pandora config --json
```

Consider later:

```bash
pandora daemon status --json
pandora daemon start
pandora daemon ensure --json
```

For the first implementation pass, avoid daemon process supervision unless needed; it is enough for `health --json` to fail cleanly when daemon is not running and point to `uv run python -m pandora_daemon` / `pandora-daemon`.

### Optional Hermes plugin tools

Only after the CLI contract is stable, a Hermes plugin/toolset can expose thin wrappers:

- `pandora_health()`
- `pandora_search(keyword, page=0, category=None, min_rating=None)`
- `pandora_gallery(target, token=None)`
- `pandora_download_add(target, token=None)`
- `pandora_download_list()`
- `pandora_download_watch(gid=None)`
- `pandora_library_list()`
- `pandora_tags_suggest(query, limit=10)`

Implementation preference:

- Tool handlers call `pandora` CLI or REST on `PANDORA_DAEMON_URL`.
- Tool handlers return JSON strings.
- Tool registration should include requirement checks: `pandora` executable available and daemon health reachable.
- Do not put ExHentai credentials in Hermes config or memory. Pandora daemon owns credentials.

---

## 4. Development phases

### Phase P0 — Repo hygiene and context alignment

**Objective:** Make the project’s docs and source layout reflect the new direction without changing runtime behavior.

**Files likely to change:**

- `README.md`
- `docs/architecture.md`
- `docs/api_reference.md`
- `GEMINI.md`
- `todo.md`
- `.agents/skills/pandora/SKILL.md`
- Optional: `.gitignore` if root ignores need to explicitly cover generated local artifacts.

**Steps:**

1. Update README architecture diagram:
   - Core: `exhentai_api -> pandora-daemon -> CLI/Hermes skill/plugin/Web optional`.
   - Move Rust TUI to “legacy/deprecated” section.
   - Remove TUI from default Quick Start; keep legacy command if desired.

2. Update `docs/architecture.md`:
   - State the current priority: agent-friendly daemon/CLI contract.
   - Mark Web as optional human frontend, TUI as frozen/deprecated.

3. Update `GEMINI.md`:
   - Replace “Web Frontend current objective” with “daemon/CLI/Hermes integration current objective”.

4. Update or archive `todo.md`:
   - Replace completed web checklist with active roadmap P0-P4.

5. Update `.agents/skills/pandora/SKILL.md` only after CLI reality is fixed in P1, or add a temporary warning that `config --json` is planned but not yet implemented.

**Verification:**

```bash
git diff --check
```

Do not run full test suite unless code changes happen.

### Phase P1 — Harden daemon/CLI agent contract

**Objective:** Make Pandora reliably scriptable by Hermes skills and external agents.

**Files likely to change:**

- `pandora_daemon/app.py`
- `pandora_daemon/routes/config_routes.py`
- `pandora_daemon/cli.py`
- `pandora_daemon/config.py`
- `tests/pandora_daemon/test_routes_config.py`
- `tests/pandora_daemon/test_cli.py`
- `docs/api_reference.md`
- `.agents/skills/pandora/SKILL.md`

**Tasks:**

1. Add `GET /api/health`.
   - Include service, version, `ok`, `auth_configured`, public paths, and capabilities.
   - Do not expose raw credentials.
   - Test with FastAPI test client.

2. Add `pandora health --json`.
   - Calls `/api/health`.
   - Exit `0` when daemon responds with ok.
   - Exit `1` on connection failure or non-2xx.
   - Human output can be simple; JSON is the important path.

3. Add `pandora config --json`.
   - Calls `/api/config`.
   - Keep output credential-free.
   - This aligns `.agents/skills/pandora/SKILL.md` with reality.

4. Add tests for parser exposure and dispatch.
   - `build_parser()` includes `health` and `config`.
   - Mock HTTP call paths if possible.
   - Keep existing download watcher terminal-event semantics.

5. Improve CLI JSON consistency.
   - For commands documented as `--json`, always emit JSON and avoid Rich markup on stdout.
   - Error messages should go to stderr if practical.

6. Document the final command set in `docs/api_reference.md` and `.agents/skills/pandora/SKILL.md`.

**Verification:**

```bash
uv run python -m pytest tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_routes_config.py -q
git diff --check
```

### Phase P2 — Formalize response schemas and contract tests

**Objective:** Replace TUI as the implicit API contract consumer with explicit Python tests and documented schemas.

**Files likely to change/create:**

- Create: `pandora_daemon/schemas.py` or `pandora_daemon/serializers.py`
- Modify: `pandora_daemon/routes/browse.py`
- Modify: `pandora_daemon/routes/gallery.py`
- Modify: `pandora_daemon/routes/downloads.py`
- Modify: `pandora_daemon/routes/library.py`
- Modify: `pandora_daemon/routes/tags.py`
- Add/modify tests under `tests/pandora_daemon/`
- Modify: `docs/api_reference.md`

**Tasks:**

1. Inventory current JSON shapes from:
   - `pandora_daemon/routes/browse.py:_gallery_item_to_dict`
   - `pandora_daemon/routes/gallery.py:_detail_to_dict`
   - `pandora_daemon/download.py:DownloadTask.to_dict`
   - `pandora_daemon/routes/downloads.py:get_page_status`
   - `pandora_daemon/routes/library.py:list_library`
   - `pandora_daemon/routes/tags.py`

2. Extract serializers or Pydantic models.
   - Prefer minimal change: keep serializer functions but centralize them.
   - Avoid rewriting domain models unless necessary.

3. Add contract tests that assert required keys and types for:
   - gallery list item
   - gallery detail
   - download task
   - download page status
   - library item
   - websocket terminal event examples

4. Compare against `pandora-tui/src/models.rs` and `pandora-web/src/models.ts`; preserve any useful compatibility fields or consciously drop them with docs.

**Verification:**

```bash
uv run python -m pytest tests/pandora_daemon/test_routes_browse.py tests/pandora_daemon/test_routes_gallery.py tests/pandora_daemon/test_routes_downloads.py tests/pandora_daemon/test_routes_library.py tests/pandora_daemon/test_ws.py -q
git diff --check
```

### Phase P3 — Build the Hermes skill package

**Objective:** Make Pandora usable by Hermes without remembering project-specific commands.

**Files likely to change/create:**

- `.agents/skills/pandora/SKILL.md`
- Optional create: `.agents/skills/pandora/references/cli-contract.md`
- Optional create: `.agents/skills/pandora/scripts/pandora_smoke.py`
- Optional mirror/export later: `integrations/hermes/pandora/SKILL.md`

**Tasks:**

1. Update skill overview:
   - Primary workflow is CLI JSON/NDJSON.
   - Daemon is required.
   - TUI is deprecated and not part of agent workflow.

2. Add a concise readiness check:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli status --json
```

3. Add common workflows:
   - Search galleries.
   - Fetch gallery detail.
   - Submit download.
   - Watch download as NDJSON.
   - Inspect retry/resume/page failures.
   - List local library.

4. Add pitfalls:
   - WebSocket event discriminator is `event`, not `type`.
   - `download_paused` is terminal for watchers.
   - Never put ExHentai cookies in Hermes memory or skill docs.
   - Use `uv`; do not use global `pip`.

5. Add verification command list.

**Verification:**

```bash
uv run python -m pytest tests/pandora_daemon/test_cli.py -q
git diff --check
```

### Phase P4 — Decide and execute TUI removal/deprecation

**Objective:** Remove or freeze the Rust TUI without losing API confidence.

**Decision gate:** Only proceed after P1 and P2 pass.

**Option A: freeze for one release**

- Keep `pandora-tui/` tracked.
- Add `pandora-tui/README.md` saying deprecated/frozen.
- Remove from main README Quick Start and default development checks.
- Do not update TUI dependencies unless a security/build issue blocks repo work.

**Option B: delete TUI**

Files to remove:

- `pandora-tui/Cargo.toml`
- `pandora-tui/Cargo.lock`
- `pandora-tui/src/**`

Docs to update:

- `README.md`
- `docs/architecture.md`
- `docs/api_reference.md` if TUI references remain
- `GEMINI.md`
- `.agents/skills/pandora/SKILL.md`
- any `docs/tui-*` docs moved to archive or removed

**Verification for either option:**

```bash
uv run python -m pytest -q
git diff --check
git ls-files 'pandora-tui/*'
```

If deleting, `git ls-files 'pandora-tui/*'` should return nothing after staged removal.

### Phase P5 — Optional Hermes plugin/toolset

**Objective:** If the skill-only workflow is not enough, expose first-class Hermes tools.

**Possible files:**

- `integrations/hermes/pandora_plugin/tools/pandora_tools.py`
- `integrations/hermes/pandora_plugin/README.md`
- tests for the plugin wrapper if the project owns them

**Initial tool list:**

- `pandora_health`
- `pandora_search`
- `pandora_gallery`
- `pandora_download_add`
- `pandora_download_list`
- `pandora_download_watch`
- `pandora_library_list`
- `pandora_tags_suggest`

**Design rules:**

- Keep wrappers thin.
- Prefer CLI subprocess calls with JSON parsing for portability.
- Requirement check should hide tools when `pandora` is unavailable or daemon is unreachable.
- No credentials in Hermes plugin config.

---

## 5. Implementation coordination with OpenCode

OpenCode is available and can be used, but Hermes should remain the coordinator and verifier.

Recommended pattern per phase:

1. Hermes creates/updates the plan and precise task prompt.
2. Run OpenCode for a bounded task only, e.g.:

```bash
opencode run 'Implement Phase P1 only: add /api/health, pandora health --json, pandora config --json, and tests. Do not touch web or TUI.'
```

3. Hermes inspects the diff with `git diff`.
4. Hermes runs targeted tests.
5. Hermes fixes any small issues directly or sends a narrow follow-up to OpenCode.
6. Only stage explicit files if/when committing; never `git add .`.

Do not run parallel OpenCode sessions in the same worktree. If parallel work is needed, create separate git worktrees first.

---

## 6. Risk register

High-risk files:

- `pandora_daemon/download.py`
  - Concurrency, persisted state, retry/resume semantics, terminal download statuses.

- `pandora_daemon/image_service.py`
  - Page URL resolution, prefetch, cache behavior, image limit/auth failures.

- `pandora_daemon/routes/gallery.py`
  - Gallery detail serialization, page image and thumbnail endpoints, history/bookmark side effects.

- `pandora_daemon/routes/library.py`
  - Filesystem path validation and local file serving.

- `pandora_daemon/config.py`
  - `load_config()` currently writes a default config when missing. Good for app startup, less ideal for read-only probes. Be careful if adding no-write health/config inspection.

- `pandora_daemon/cli.py`
  - This becomes the primary agent-facing interface; protect JSON/exit-code behavior with tests.

- `pandora_daemon/app.py`
  - Lifespan, exception handlers, CORS, router registration.

- `pandora_daemon/ws.py`
  - Download event stream reliability.

- `pandora-tui/src/client.rs` and `pandora-tui/src/models.rs`
  - Do not edit for new features, but use once as a reference for current REST/WS consumer expectations before deleting TUI.

---

## 7. Immediate next action recommendation

Start with Phase P1, because it unblocks both skill and plugin directions and makes the TUI decision safer.

Smallest useful P1 slice:

1. Add `GET /api/health` to `pandora_daemon/routes/config_routes.py` or a new `routes/health.py`.
2. Add `health` and `config` subcommands to `pandora_daemon/cli.py`.
3. Add tests in `tests/pandora_daemon/test_routes_config.py` and `tests/pandora_daemon/test_cli.py`.
4. Update `.agents/skills/pandora/SKILL.md` to match actual commands.
5. Run:

```bash
uv run python -m pytest tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_routes_config.py -q
git diff --check
```

After that, do Phase P0 docs alignment and decide whether to freeze or delete `pandora-tui/`.
