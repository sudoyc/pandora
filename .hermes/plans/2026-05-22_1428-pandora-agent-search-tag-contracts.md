# Pandora Agent Search/Tag Contracts Implementation Plan

> For Hermes: implement with OpenCode using strict TDD, then Hermes verifies diff/tests/review before commit.

Goal: Make Pandora CLI/daemon provide sufficient primitive interfaces for a future Hermes toolset to search galleries and maintain tag translations without embedding ambiguous decision logic in the CLI.

Architecture: Preserve scheme A. The CLI must not automatically rewrite Chinese user text into ExHentai tag queries. Agents should explicitly call `tags suggest` first, inspect candidates, then call `search` with an agent-chosen keyword such as `female:stockings`. The daemon remains the stateful boundary for tag DB cache/version/update and ExHentai search; CLI remains a thin, machine-readable daemon client.

Tech stack: Python 3.12, FastAPI, httpx, argparse CLI, pytest via `uv run python -m pytest`.

Current WIP constraints:
- Do not stage or alter unrelated pre-existing WIP unless necessary: `pandora-web/*`, `pandora-tui/Cargo.lock`, unrelated CORS hunk in `pandora_daemon/app.py`.
- Stage explicit files only.
- Do not add credentials or sensitive gallery data to tests/docs.

---

## Scope

Implement these primitive contracts:

1. Tag database maintenance primitives:
   - `GET /api/tags/status`
   - `POST /api/tags/refresh?force=false`
   - CLI: `pandora tags status --json`
   - CLI: `pandora tags refresh [--force] --json`
   - ETag-aware metadata and atomic cache writes.

2. Search parameter completeness:
   - Extend daemon `GET /api/search` to expose existing `SearchParams` fields safely.
   - Extend CLI `pandora search` flags to pass the same fields.
   - Keep default behavior unchanged.
   - No `search-tag` command and no automatic tag resolution.

3. Documentation/skill:
   - Update README/API docs/architecture/deployment as needed.
   - Update `.agents/skills/pandora/SKILL.md` to document scheme A workflow:
     `tags suggest` → agent decision → `search`.

---

## Task 1: Add failing tag database status/metadata tests

Objective: Define stable status and refresh behavior before production code.

Files:
- Modify: `tests/pandora_daemon/test_tag_database.py`

Test cases:
- `TagDatabase.status()` returns loaded=false, entries=0, source_url, cache_path, etag/head fields null before load.
- `load_from_dict(sample, cache_path=..., metadata={...})` or equivalent records entries count and upstream `repo`/`head.sha` if present.
- `download_and_load()` writes cache atomically and writes metadata including `etag`, `source_url`, `upstream_repo`, `upstream_sha`, `entries`.
- `refresh(force=False)` sends `If-None-Match` when metadata has ETag, handles 304 as updated=false while preserving loaded data.
- Failed refresh does not clear existing entries and records a last_error in status.

Run expected RED:
`uv run python -m pytest tests/pandora_daemon/test_tag_database.py -q`

---

## Task 2: Implement tag database metadata, atomic cache, refresh

Objective: Make the tests pass with minimal, robust implementation.

Files:
- Modify: `pandora_daemon/tag_database.py`

Implementation notes:
- Add metadata path default near cache path, for example `~/.cache/pandora/tags/metadata.json`.
- Preserve `download_and_load(cache_path=DEFAULT_CACHE_PATH)` public call compatibility.
- Add `status(cache_path=...) -> dict` with fields suitable for JSON.
- Add `refresh(cache_path=..., force=False) -> dict` returning an envelope, not bare bool:
  `{ok: true, updated: true|false, status: {...}}` or `{ok:false, updated:false, error:{code,message}, status:{...}}`.
- Keep `check_update()` as backward-compatible wrapper returning bool, but use the new refresh path.
- Use `If-None-Match` from metadata when force=false and ETag exists.
- Atomic writes: write to sibling `.tmp`, parse/load, then `replace()` cache and metadata.
- Extract upstream metadata from EhTagTranslation JSON shape:
  - root `repo`
  - root `head.sha`
- Avoid clearing existing `entries` until new JSON has been parsed and converted successfully.

Run GREEN:
`uv run python -m pytest tests/pandora_daemon/test_tag_database.py -q`

---

## Task 3: Add route tests for tag status/refresh

Objective: Define daemon JSON contract.

Files:
- Modify: `tests/pandora_daemon/test_routes_tags.py`

Test cases:
- `GET /api/tags/status` returns status with entries and loaded=true for fixture DB.
- `POST /api/tags/refresh` calls tag DB refresh with force=false and returns envelope.
- `POST /api/tags/refresh?force=true` passes force=true.

Use a fake or monkeypatch on `TagDatabase.refresh` if needed; avoid real network.

Run expected RED then GREEN after Task 4:
`uv run python -m pytest tests/pandora_daemon/test_routes_tags.py -q`

---

## Task 4: Implement tag status/refresh routes

Objective: Expose maintenance primitives to CLI/toolset.

Files:
- Modify: `pandora_daemon/routes/tags.py`

Add:
- `@router.get("/status")`
- `@router.post("/refresh")`

Return tag_db status/envelope. Do not expose credentials.

---

## Task 5: Add failing route/CLI tests for complete search parameters

Objective: Ensure daemon and CLI pass primitive search flags without agent decision logic.

Files:
- Add or modify: `tests/pandora_daemon/test_routes_browse.py` if existing; otherwise add test file.
- Modify: `tests/pandora_daemon/test_cli.py`

Daemon route test:
- Mock `api.search` and assert SearchParams fields are set for query params:
  `keyword`, `page`, `category`, `min_rating`, `search_name`, `search_tags`, `search_description`, `search_torrent`, `search_low_power_tags`, `show_expunged`, `disable_language_filter`, `min_pages`, `max_pages`.
- Keep category as include bitmask semantics because `SearchParams.to_dict()` already inverts to ExHentai exclude mask.

CLI test:
- Parse and dispatch `pandora search stocking --page 2 --category 1 --min-rating 4 --search-tags --search-name --show-expunged --min-pages 10 --max-pages 30 --json --daemon-url http://daemon`.
- Assert request path `/api/search` and query params are forwarded.
- Ensure there is no automatic `tags suggest` request and no automatic rewrite.

Run expected RED:
`uv run python -m pytest tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_routes_browse.py -q`

---

## Task 6: Implement search parameter routing and CLI flags

Objective: Pass all search primitive flags through daemon and CLI.

Files:
- Modify: `pandora_daemon/routes/browse.py`
- Modify: `pandora_daemon/cli.py`

Daemon route additions:
- Add typed query params:
  - `category: Optional[int]`
  - `min_rating: Optional[int]`
  - `search_name: bool = False` → `f_sname`
  - `search_tags: bool = False` → `f_stags`
  - `search_description: bool = False` → `f_sdesc`
  - `search_torrent: bool = False` → `f_storr`
  - `search_low_power_tags: bool = False` → `f_sto`
  - `disable_language_filter: bool = False` → `f_sdt1`
  - `show_expunged: bool = False` → `f_sh`
  - `min_pages: Optional[int]` → set `f_sp=True`, `f_spf`
  - `max_pages: Optional[int]` → set `f_sp=True`, `f_spt`
- Set `advsearch=True` whenever an advanced field requiring advsearch is used.
- `f_sh` can be set without `advsearch`, but it is okay if advsearch is also true due other fields.
- Keep default `keyword/page` behavior unchanged.

CLI flags:
- `--category INT`
- `--min-rating INT`
- `--search-name`
- `--search-tags`
- `--search-description`
- `--search-torrent`
- `--search-low-power-tags`
- `--disable-language-filter`
- `--show-expunged`
- `--min-pages INT`
- `--max-pages INT`

Build params by including only set/true values. Continue outputting one JSON document.

---

## Task 7: Add CLI tests for tag status/refresh and implement

Objective: Provide machine-readable CLI primitives for agents.

Files:
- Modify: `tests/pandora_daemon/test_cli.py`
- Modify: `pandora_daemon/cli.py`

Tests:
- `pandora tags status --json --daemon-url http://daemon` calls `GET /api/tags/status`.
- `pandora tags refresh --json --daemon-url http://daemon` calls `POST /api/tags/refresh` with no force or `force=false`.
- `pandora tags refresh --force --json --daemon-url http://daemon` calls `POST /api/tags/refresh?force=true`.

Implementation:
- Add `tags status` and `tags refresh` subcommands.
- Add `--force` to refresh.
- Keep `tags suggest` unchanged.

---

## Task 8: Update docs and Pandora skill

Objective: Teach future Hermes/toolset use the primitive workflow.

Files likely:
- `README.md`
- `docs/api_reference.md`
- `docs/architecture.md`
- `.agents/skills/pandora/SKILL.md`

Required wording:
- Scheme A is intentional: CLI does not decide ambiguous tag resolution.
- Agent flow:
  1. `pandora tags status --json`
  2. `pandora tags refresh --json` if stale/unloaded
  3. `pandora tags suggest "丝袜" --json`
  4. agent chooses candidate, e.g. `female:stockings`
  5. `pandora search "female:stockings" --search-tags --json`
- Document advanced search flags and category include-bitmask semantics.

---

## Verification

Run after implementation:

1. Targeted tests:
`uv run python -m pytest tests/exhentai_api/test_search.py tests/pandora_daemon/test_tag_database.py tests/pandora_daemon/test_routes_tags.py tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_agent_contracts.py -q`

2. Full tests:
`uv run python -m pytest -q`

3. Diff checks:
`git diff --check`

4. Manual CLI smoke with unreachable daemon:
- `uv run python -m pandora_daemon.cli search stocking --search-tags --min-pages 10 --json --daemon-url http://127.0.0.1:9`
- `uv run python -m pandora_daemon.cli tags status --json --daemon-url http://127.0.0.1:9`
Expected: JSON error envelope, exit 1, no traceback.

5. Independent OpenCode review:
- Review diff for security, logic, API contract, TDD coverage.
- Fix blockers, then rerun tests.

6. Stage explicit files only; verify staged diff excludes unrelated WIP.

Commit message suggestion:
`feat: expose Pandora search and tag maintenance contracts`
