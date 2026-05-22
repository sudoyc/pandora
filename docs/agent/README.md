# Pandora Agent Pack

The Pandora Agent Pack is the canonical, generic agent-facing documentation for operating Pandora from automation. It is usable by Hermes, OpenCode, Codex, Claude, MCP-style wrappers, shell scripts, and future thin plugins.

Pandora keeps all durable state in `pandora-daemon`: credentials, session, cache, SQLite data, bookmarks, filters, download queue, and local library. Agents consume daemon-backed contracts and must not create a second state layer.

Allowed integration surfaces:

- CLI machine output: `pandora ... --json`, `pandora ... --ndjson`, or `uv run python -m pandora_daemon.cli ...` from a checkout.
- Daemon REST endpoints under `http://127.0.0.1:7860/api/...`.
- Daemon WebSocket events from `WS /ws`.

Forbidden integration surfaces:

- Direct `exhentai_api` imports for user workflows.
- Direct ExHentai/E-Hentai scraping from agents or wrappers.
- A second credential, session, cache, bookmark, library, filter, or download queue store.
- Credential persistence in prompts, plugin state, logs, docs, or generated artifacts.
- Parsing human CLI output when JSON or NDJSON machine output exists.

Hermes is one packaged consumer of this Agent Pack through `.agents/skills/pandora/SKILL.md`. The Hermes skill is not the source of truth for the contract and must remain a thin wrapper around the same daemon-backed surfaces.

## Pack Contents

- [`context-pack.md`](context-pack.md) gives copy-pasteable base context for agents.
- [`contract.md`](contract.md) documents stable CLI, REST, WebSocket, and machine-output contracts.
- [`safety.md`](safety.md) documents credentials, privacy, state, and mutation boundaries.
- [`workflows/`](workflows/) contains task-level runbooks.
- [`snippets/`](snippets/) contains standalone prompt blocks.
- [`snippets/library-export-agent.md`](snippets/library-export-agent.md) is the PDF export-specific agent prompt block.
- [`schemas/`](schemas/) contains lightweight JSON Schemas for common machine envelopes.

When adding a new bot-visible capability or hook, document it in the Agent Pack first (`contract.md`, relevant workflow, and schema/snippet as needed). The Hermes/Pandora skill may summarize it, but should not be the only delivery surface.

## Quick Agent Bootstrap

From the repository root, start the daemon if needed:

```bash
uv run python -m pandora_daemon
```

Probe readiness:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli tags status --json
```

Prefer installed `pandora ...` commands when Pandora is installed as a CLI package. Prefer `uv run python -m pandora_daemon.cli ...` from a checkout.

## Common Workflows

- Bootstrap: [`workflows/bootstrap.md`](workflows/bootstrap.md)
- Search: [`workflows/search.md`](workflows/search.md)
- Translated tag resolution: [`workflows/tag-resolution.md`](workflows/tag-resolution.md)
- Gallery inspection: [`workflows/gallery-inspection.md`](workflows/gallery-inspection.md)
- Downloads: [`workflows/download.md`](workflows/download.md)
- Library: [`workflows/library.md`](workflows/library.md)
- Failure recovery: [`workflows/failure-recovery.md`](workflows/failure-recovery.md)
- Bug triage: [`workflows/bug-triage.md`](workflows/bug-triage.md)
- Bug fix lifecycle: [`workflows/bug-fix-lifecycle.md`](workflows/bug-fix-lifecycle.md)
- Bug fix snippet: [`snippets/bug-fix-agent.md`](snippets/bug-fix-agent.md)

## Core Rule

Do not bypass `pandora-daemon`. If an agent needs data, state, or side effects, it should call the CLI, REST API, or WebSocket contract documented here.
