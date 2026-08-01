# Pandora Hermes Integration

Hermes consumes the generic [Pandora Agent Pack](agent/README.md). This document is only Hermes-specific packaging guidance; it does not redefine the contract.

Canonical agent documentation:

- Context pack: [`agent/context-pack.md`](agent/context-pack.md)
- Contract: [`agent/contract.md`](agent/contract.md)
- Safety: [`agent/safety.md`](agent/safety.md)
- Workflows: [`agent/workflows/`](agent/workflows/)
- Prompt snippets: [`agent/snippets/`](agent/snippets/)
- JSON schemas: [`agent/schemas/`](agent/schemas/)

## Hermes Shape

The repo-shipped Hermes consumer is `.agents/skills/pandora/SKILL.md`. It should stay a thin skill/runbook over Agent Pack contracts.

There is no separate in-repo Hermes plugin or toolset package today. If one is added later, it must wrap only:

- `pandora` CLI JSON/NDJSON commands.
- `uv run python -m pandora_daemon.cli ...` from a checkout.
- Daemon REST endpoints under `http://127.0.0.1:7860/api/...`.
- Daemon WebSocket events from `WS /ws`.

Hermes must not import provider adapters or their upstream implementations for user workflows, access an upstream directly, persist credentials, or maintain a second credential/session/cache/download/bookmark/library state layer.

## Hermes Bootstrap

Use the Agent Pack bootstrap workflow: [`agent/workflows/bootstrap.md`](agent/workflows/bootstrap.md).

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli tags status --json
```

Run the first four commands in order. `config --json` omits credentials and
redacts proxy secrets, but local non-secret paths may appear. Readiness exit 1
is a structured upstream not-ready result, not a daemon connection failure.

## Hermes Search

Use generic search workflows:

- [`agent/workflows/search.md`](agent/workflows/search.md)
- [`agent/workflows/tag-resolution.md`](agent/workflows/tag-resolution.md)

Scheme A remains mandatory for translated tag search:

```bash
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json   # if stale or unloaded
uv run python -m pandora_daemon.cli tags suggest "丝袜" --json
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
```

Hermes should choose the candidate and preserve evidence. Pandora does not automatically rewrite Chinese or other translated text into ExHentai tag syntax.

## Hermes Downloads

Use the generic download workflow: [`agent/workflows/download.md`](agent/workflows/download.md).

```bash
uv run python -m pandora_daemon.cli download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
```

Follow-up inspection:

```bash
uv run python -m pandora_daemon.cli download list --json
uv run python -m pandora_daemon.cli download report --json
uv run python -m pandora_daemon.cli download pages 123 --json
uv run python -m pandora_daemon.cli library list --json
```

`download report --json` is a read-only daemon comparison; use its issue codes
instead of reading state or library files. Daemon WebSocket events use `event`
as the discriminator, not `type`. Terminal event and exit semantics are defined
in [`agent/contract.md`](agent/contract.md).

When the user requests recovery, preview `download repair <gid> --json` or
`download forget <gid> --json`, inspect `actions`, then repeat the selected
command with `--apply`. Both commands preserve library files and keep task state
inside the daemon.

## Skill Maintenance

When updating `.agents/skills/pandora/SKILL.md`:

- Link to the Agent Pack rather than duplicating the full generic contract.
- Keep concise command examples and repository verification commands.
- Preserve daemon-backed no-second-state-layer boundaries.
- Keep credentials out of prompts, logs, plugin state, and docs.
