# Pandora full-codebase review plan

Date: 2026-05-22 19:05 CST
Mode: read-only audit
Status: completed; findings were transferred to `2026-05-22_1950-pandora-fix-handoff.md`

## Goal
Perform a broad, detailed, multi-line review of the Pandora repository, with emphasis on:
- daemon + CLI + Agent Pack contracts
- runtime correctness and failure handling
- security / secret leakage / unsafe boundaries
- contract drift between docs, daemon, CLI, web, and archived TUI
- current state of optional web frontend and frozen TUI boundary

## Constraints
- Do not modify repository files during review.
- Preserve unrelated pre-existing WIP in pandora-web/*, pandora_daemon/app.py, pandora-tui/Cargo.lock.
- Use external reviewers where possible: OpenCode, Codex, Claude Code.

## Verification steps
1. Capture git status and recent commits.
2. Read authority docs: README, architecture, pyproject, agent docs.
3. Run safe checks:
   - Python tests
   - web build
   - web lint
   - repo metrics
4. Run independent external reviews:
   - OpenCode read-only review
   - Codex read-only review
   - Claude Code read-only review
5. Manual source review of key areas:
   - app / exception handlers / startup
   - CLI machine contracts and websocket lifecycle
   - download manager / ws contracts
   - library/pdf export
   - tag database and search flow
   - web frontend API/hooks/model alignment
6. Synthesize findings by severity with file:line evidence.
7. End with recommended fix order and decision buckets.

## Progress log
- Captured repo status and recent commits.
- Read README and pyproject.
- Ran Python tests: 504 passed.
- Ran web build: success.
- Ran web lint: success.
- Ran pygount summary.
- OpenCode smoke: OK.
- Codex smoke: OK, but reported .agents/skills/pandora/SKILL.md YAML parse issue.
- Claude Code smoke: timed out once; needs retry/diagnosis.
