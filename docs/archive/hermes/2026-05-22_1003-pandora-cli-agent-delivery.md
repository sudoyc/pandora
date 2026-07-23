# Pandora CLI Agent-Ready Delivery Plan

> For Hermes: execute this plan with strict TDD, use OpenCode for code-writing phases, and independently verify every diff, test result, and final git state before push.

**Goal:** bring Pandora to a directly deployable, agent-ready state centered on daemon + CLI + Hermes skill, then push the finished work upstream without mixing unrelated WIP.

**Architecture:** keep `exhentai_api` stateless, keep `pandora_daemon` as the only stateful boundary, and make the CLI the single stable automation surface. Hermes skill/deployment docs should describe exact CLI/daemon workflows rather than inventing a parallel integration layer.

**Tech stack:** Python 3.12, FastAPI, httpx, websockets, SQLite, uv, pytest, Git, Hermes in-repo skill, optional systemd user service docs.

---

## Scope lock

This round includes only:
- CLI completion and hardening
- agent/deployment-facing docs
- repo-local Pandora skill updates
- tests and verification
- clean scoped commit(s) and push to `origin`

This round explicitly excludes:
- new Web work
- TUI revival
- full Hermes plugin/toolset implementation
- unrelated pre-existing WIP in `pandora-web/*`, `pandora_daemon/app.py`, `pandora-tui/Cargo.lock`

---

## Read-only audit summary

Current facts confirmed before implementation:
- Branch is `main`, ahead of `origin/main` by one commit.
- There is unrelated dirty work in `pandora-web/*`, `pandora_daemon/app.py`, and `pandora-tui/Cargo.lock`.
- `gh` is not installed, so push flow should use plain `git push origin HEAD`.
- `opencode 1.15.3` is installed and authenticated.
- CLI already exposes most agent-facing commands, but behavior is not yet fully production-grade for deployment automation.
- Current repo-local skill `.agents/skills/pandora/SKILL.md` documents workflows, but deployment guidance is still too thin.
- There is no dedicated deployment document for daemon startup, readiness, config path, and service-mode operation.

Primary gaps from audit:
1. CLI success shapes exist, but failure paths are not consistently machine-readable.
2. CLI logic is monolithic in `pandora_daemon/cli.py`; request/error handling is duplicated.
3. CLI test coverage is too shallow for a “fully deliverable to agents” claim.
4. Deployment docs are incomplete: no dedicated systemd/service examples, no clear startup/verification playbook.
5. Repo-local skill is usable but not yet a full deploy/runbook for autonomous agents.
6. Metadata/docs still partially describe Pandora as “multi-frontend” instead of CLI/agent-first.

---

## Target end state

At the end of this round, Pandora should provide:

1. A stable CLI surface for agents
- `health`, `config`, `status`
- `search`, `gallery`, `popular`, `toplist`, `watched`
- `favorites list`, `library list`, `tags suggest`
- `download add/list/watch/pages/cancel/resume/retry`
- clear exit codes
- JSON/NDJSON success output for automation
- consistent JSON error output when `--json` or `--ndjson` is used in machine-facing commands

2. A deployable daemon workflow
- exact config path and config file shape
- exact daemon start command
- exact readiness checks
- systemd user-service example
- smoke-test command set

3. A deployable repo-local Pandora skill
- prerequisites
- configuration steps
- daemon startup/check flow
- common browse/download flows
- recovery/failure handling
- verification commands

4. Clean repository delivery
- scoped tests passing
- full pytest passing
- `git diff --check` clean
- scoped commit(s) only
- pushed upstream without unrelated WIP

---

## Task 1: Harden CLI contract design

**Objective:** define and implement the final machine-facing contract before changing behavior.

**Files:**
- Modify: `pandora_daemon/cli.py`
- Modify: `tests/pandora_daemon/test_cli.py`
- Modify: `tests/pandora_daemon/test_agent_contracts.py`
- Possibly modify: `README.md`, `docs/api_reference.md`

**Work items:**
1. Audit all command paths in `pandora_daemon/cli.py`.
2. Identify machine-facing commands that must return structured errors.
3. Introduce shared helpers for:
   - JSON output
   - JSON error output
   - daemon URL resolution
   - HTTP request handling / exception mapping
4. Decide final error envelope shape for CLI automation. Prefer:
   ```json
   {
     "ok": false,
     "error": {
       "code": "connect_error",
       "message": "Cannot connect to daemon at http://127.0.0.1:7860"
     }
   }
   ```
5. Keep legacy human-friendly `pandora download <url>` flow working.

**TDD sequence:**
- Write failing tests for JSON error output and exit-code behavior first.
- Run targeted tests to confirm failure.
- Implement minimal helpers to make them pass.
- Re-run full CLI tests.

---

## Task 2: Expand CLI behavior coverage

**Objective:** make “fully usable” defensible via tests.

**Files:**
- Modify: `tests/pandora_daemon/test_cli.py`
- Possibly create: `tests/pandora_daemon/test_cli_main.py` or extend existing file

**Coverage targets:**
- `health --json`
- `config --json`
- `status --json`
- `search --json`
- `gallery --json`
- `library list --json`
- `favorites list --json`
- `popular --json`
- `toplist --json`
- `watched --json`
- `tags suggest --json`
- `download add/list/pages/cancel/resume/retry`
- `download watch --ndjson` terminal events and exit codes
- invalid gallery target handling
- daemon connection failure handling
- HTTP status error handling
- `main()` exit semantics where practical

**TDD sequence:**
- Add failing tests command-by-command.
- Confirm failures before implementation.
- Implement only the behavior necessary to satisfy tests.

---

## Task 3: Improve deployment ergonomics

**Objective:** make daemon setup and operation straightforward for an autonomous agent.

**Files:**
- Create: `docs/deployment.md`
- Modify: `README.md`
- Modify: `.agents/skills/pandora/SKILL.md`
- Possibly modify: `docs/api_reference.md`
- Possibly modify: `pyproject.toml`

**Content requirements:**
- install prerequisites with `uv`
- config file location and sample TOML
- daemon entrypoints:
  - `uv run python -m pandora_daemon`
  - `uv run pandora-daemon`
- readiness checks:
  - `pandora health --json`
  - `pandora config --json`
  - `pandora status --json`
- systemd user service example
- smoke-test workflow
- notes on credentials safety and what public config does not expose

**Important:** documentation must describe only workflows that are actually verified in code.

---

## Task 4: Upgrade repo-local Pandora skill to deployment-grade

**Objective:** ensure a fresh agent can use the in-repo skill as an operational runbook.

**Files:**
- Modify: `.agents/skills/pandora/SKILL.md`

**Required improvements:**
- clarify trigger: use when operating/deploying Pandora for daemon+CLI workflows
- add deployment prerequisites
- add config file template and location
- add daemon startup instructions
- add readiness checks and expected outcomes
- add common command recipes
- add recovery section:
  - daemon not running
  - auth not configured
  - download paused/auth failed
  - JSON/NDJSON expectations
- add git hygiene section reminding agents not to stage unrelated web/TUI WIP

---

## Task 5: Align top-level metadata and docs

**Objective:** remove obvious documentation drift that would confuse deployers/agents.

**Files:**
- Modify: `README.md`
- Modify: `docs/api_reference.md`
- Possibly modify: `docs/architecture.md`
- Possibly modify: `pyproject.toml`

**Target changes:**
- shift wording from “multi-frontend” to “daemon + CLI + agent workflows”
- make CLI examples precise and consistent
- point to new deployment doc
- ensure docs match actual health/config/privacy behavior

---

## Task 6: Verification and review

**Objective:** independently prove the delivery is real.

**Files:**
- No intentional source changes except any review-driven fixes

**Verification commands:**
```bash
uv run python -m pytest tests/pandora_daemon/test_cli.py -q
uv run python -m pytest tests/pandora_daemon/test_routes_config.py tests/pandora_daemon/test_agent_contracts.py -q
uv run python -m pytest -q
git diff --check
git status --short
```

**Review procedure:**
1. Self-review scoped diff.
2. Independent review via fresh agent/subagent.
3. Fix findings only if material.
4. Re-run verification.

---

## Task 7: Commit and push cleanly

**Objective:** ship only the intended work.

**Files:**
- Stage explicit files only.

**Rules:**
- Do not stage `pandora-web/*`, `pandora_daemon/app.py`, or `pandora-tui/Cargo.lock` unless explicitly modified for this scope and re-verified.
- Commit message should reflect CLI/agent delivery, not generic cleanup.
- Push with:
  ```bash
  git push origin HEAD
  ```

---

## Expected touched files

Very likely:
- `pandora_daemon/cli.py`
- `tests/pandora_daemon/test_cli.py`
- `tests/pandora_daemon/test_agent_contracts.py`
- `.agents/skills/pandora/SKILL.md`
- `README.md`
- `docs/api_reference.md`
- `docs/deployment.md`

Possible but not guaranteed:
- `pyproject.toml`
- `docs/architecture.md`

---

## Definition of done

Pandora is “agent-ready and directly deployable” only if all are true:
- all intended CLI commands behave consistently for machine use
- CLI failure paths are structured enough for agents to consume
- deployment steps are documented end-to-end
- repo-local Pandora skill is sufficient as an operational runbook
- tests pass, review passes, diff check passes
- changes are pushed upstream without unrelated WIP mixed in
