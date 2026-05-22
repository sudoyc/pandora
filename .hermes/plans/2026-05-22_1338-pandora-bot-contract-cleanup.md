# Pandora Bot Contract Cleanup Implementation Plan

> **For Hermes:** Use OpenCode for production/test/doc edits, then Hermes verifies, reviews, stages exact files, commits, and pushes.

**Goal:** Finish the bot-first contract cleanup after the successful live download test.

**Architecture:** Keep `exhentai_api` stateless, keep daemon as the only stateful auth/cache/download boundary, and make CLI/Hermes the primary automation surface. Do not expand Web/TUI/client-cache work.

**Tech Stack:** Python 3.12, FastAPI daemon, httpx CLI client, pytest, uv, OpenCode.

---

## Scope

In scope:
1. Formalize optional `ipb_pass_hash` support already proven by live smoke.
2. Add one bot-friendly atomic command: `pandora download run <url|gid> [token] --ndjson`.
3. Redact sensitive gallery detail fields from CLI machine output by default.
4. Normalize agent-facing page states so `download pages --json` reports `completed` instead of internal `done`.
5. Update README/API/deployment/Pandora skill docs for the bot-first path.
6. Verify with tests, opencode review, Hermes self-review, exact staging, commit, push.

Out of scope:
- Web frontend work.
- TUI deletion or maintenance.
- Cache strategy rewrite.
- Multi-site adapter abstraction.
- Downloading sensitive media as committed fixtures or tests.

---

## Current Known WIP Boundary

Pre-existing unrelated WIP must not be staged unless explicitly part of the task:
- `pandora-web/*`
- `pandora-tui/Cargo.lock`
- pre-existing parts of `pandora_daemon/app.py` unrelated to `ipb_pass_hash`

Use exact `git add <file>` and, for `pandora_daemon/app.py`, inspect diff carefully before staging.

---

## Task 1: Inspect and Preserve Scope

**Objective:** Establish the working tree baseline and distinguish current task changes from unrelated WIP.

**Commands:**
- `git status --short --branch`
- `git diff -- pandora_daemon/app.py`
- `git diff -- docs/deployment.md exhentai_api/client.py pandora_daemon/config.py tests/exhentai_api/test_client.py tests/pandora_daemon/test_config.py tests/pandora_daemon/test_app_lifespan.py`

**Expected:** Only task files are touched by this plan; Web/TUI remain unstaged.

---

## Task 2: TDD for Bot Contract Changes

**Objective:** Write failing tests before implementation.

**Tests to add/update:**
- `tests/pandora_daemon/test_cli.py`
  - parser exposes `download run`.
  - `download run <url> --ndjson` posts `/api/downloads`, emits queued/submitted line, then watches WS terminal events.
  - `download run` handles duplicate/existing task by treating HTTP 409 as attach-to-watch, not a hard failure.
  - gallery CLI output redacts `api_uid` and `api_key` by default.
  - page status output maps internal `done` to public `completed`.
- `tests/pandora_daemon/test_agent_contracts.py`
  - CLI gallery contract must not expose sensitive API identity/key fields.
  - download pages contract uses public page state values.
- Existing ipb_pass_hash tests must remain green.

**RED command:**
`uv run python -m pytest tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_agent_contracts.py -q`

---

## Task 3: Minimal Implementation

**Objective:** Make tests pass with the smallest bot-first implementation.

**Files likely modified:**
- `pandora_daemon/cli.py`
  - Add `download run` subcommand.
  - Add safe output sanitizer for gallery/detail CLI responses.
  - Add page-state public normalizer for `download pages` output.
  - Keep `download add/list/watch/pages` backward compatible.
- `pandora_daemon/config.py`, `exhentai_api/client.py`, `pandora_daemon/app.py`
  - Keep optional `ipb_pass_hash` support.

**GREEN commands:**
- `uv run python -m pytest tests/exhentai_api/test_client.py tests/pandora_daemon/test_config.py tests/pandora_daemon/test_app_lifespan.py -q`
- `uv run python -m pytest tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_agent_contracts.py -q`

---

## Task 4: Documentation and Skill Update

**Objective:** Make bot usage obvious and avoid reviving client/cache work.

**Files likely modified:**
- `README.md`
- `docs/api_reference.md`
- `docs/deployment.md`
- `docs/architecture.md`
- `.agents/skills/pandora/SKILL.md`

**Content:**
- Recommend `download run --ndjson` for bots.
- Explain `download add` + `watch` remains available but can miss earlier events if attached late.
- Mark Web/image proxy/cache/prefetch as optional human UI support, not bot primary path.
- Document `ipb_pass_hash` optional credential field.
- Document gallery CLI sensitive-field redaction.

---

## Task 5: Verification and Review

**Commands:**
- `uv run python -m pytest tests/exhentai_api/test_client.py tests/pandora_daemon/test_config.py tests/pandora_daemon/test_app_lifespan.py -q`
- `uv run python -m pytest tests/pandora_daemon/test_cli.py tests/pandora_daemon/test_agent_contracts.py tests/pandora_daemon/test_routes_config.py -q`
- `uv run python -m pytest -q`
- `git diff --check`
- secret scan over intended diff
- opencode review of intended diff
- Hermes self-review of scope and staging list

Manual smoke, no real credentials required:
- Use mock tests for `download run`.
- If live smoke is repeated, use temporary HOME and delete it immediately.

---

## Task 6: Commit and Push

**Stage exact files only.** Do not stage Web/TUI. If `app.py` contains unrelated hunks, use patch-mode staging or split by checkout/patching.

**Commit message:**
`feat: harden Pandora bot download contracts`

**Push:**
`git push origin HEAD`

**Final report:**
- commit SHA
- pushed status
- tests run
- review result
- files included/excluded
