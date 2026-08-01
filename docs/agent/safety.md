# Agent Safety

Pandora is daemon-backed. Safety depends on preserving one durable state owner and keeping credentials out of agent artifacts.

## State Ownership

Only `pandora-daemon` owns durable state:

- Credentials and authenticated session material.
- Image cache and gallery detail cache.
- SQLite data: history, local favorites, bookmarks, quick searches, filters, and tag cache.
- Download queue, page state, retry/resume state, and local library metadata.
- Runtime config.

Agents and wrappers may hold ephemeral in-memory command results for the current task only. They must not persist a parallel database, cache, download queue, session jar, bookmark list, or library index.
They must not read or edit `downloads.json` or its recovery backups; use daemon
status/report and recovery commands instead.

## Credential Rules

- Do not read, print, summarize, or persist `~/.config/pandora/config.toml` credentials.
- Do not copy cookies, `igneous`, `ipb_member_id`, `ipb_pass_hash`, API keys, or proxy credentials into prompts, logs, docs, plugin state, test fixtures, or generated files.
- `pandora config --json` omits credentials and redacts proxy secrets. It may still include local non-secret paths; do not publish it publicly.
- Use `network.proxy_configured` instead of expecting raw proxy URLs.

## Surface Rules

Allowed:

- CLI JSON/NDJSON.
- Daemon REST.
- Daemon WebSocket.

Forbidden:

- Direct provider-adapter or upstream-implementation imports for user workflows.
- Direct upstream scraping in agents or wrappers.
- Human-output parsing when machine output exists.
- Stateful plugin/toolset control planes that mirror daemon state.

## Mutation Rules

- Read-only agents must not call download, repair, forget, comment, rating, vote, favorite mutation, tag mutation, config update, bookmark delete, history delete, filter mutation, or quick-search mutation commands.
- Download agents may submit/cancel/resume/retry downloads only when the user asks for download operations. Repair/forget additionally require preview inspection before explicit apply.
- Repair/forget may change daemon task state but must never modify or delete library metadata, pages, or directories.
- Config changes require explicit user instruction and should use daemon config endpoints only.
- Do not silently retry operations that can create duplicate side effects, except `download run --ndjson`, which handles active duplicate queue submissions through `download_already_queued`.

## Output Rules

- Prefer `--json` and `--ndjson`.
- Preserve the CLI error envelope in reports when a machine command fails.
- Treat WebSocket `event` as the discriminator. Do not use `type`.
- Treat `download_paused` and `download_auth_failed` as terminal for the current automation step.

## Repository Rules

- Do not modify `pandora-web/` or `pandora-tui/` for agent-pack documentation work unless explicitly requested.
- Do not commit downloaded galleries, caches, credentials, generated files, or local config.
- Use `uv` for Python commands in this repository.
