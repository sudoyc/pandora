# Pandora Deployment

Pandora is deployed as a local daemon plus a CLI. Agent workflows should target the CLI in `--json` or `--ndjson` mode and follow the generic [Pandora Agent Pack](agent/README.md).

Hermes is one packaged consumer of the Agent Pack through `.agents/skills/pandora/SKILL.md`. There is no separate in-repo Hermes plugin/toolset package yet; future wrappers should stay thin and call the CLI or daemon instead of creating a parallel control plane.

## Prerequisites

- Linux, macOS, or another environment that can run Python 3.12+
- `uv`
- Valid ExHentai/E-Hentai session cookies in config when using authenticated endpoints
- Normal project dependencies installed by `uv`; `websockets` is required for `download run --ndjson` and `download watch --ndjson`

## Config Location

Default config path:

```text
~/.config/pandora/config.toml
```

Typical minimum credential setup:

```toml
[credentials]
igneous = "..."
ipb_member_id = "..."
ipb_pass_hash = "..."  # Optional; leave empty if your session does not use it.
```

Public/safe config behavior:

- `pandora config --json` omits credentials entirely.
- Proxy secrets are redacted; use `network.proxy_configured` instead of expecting the raw proxy URL.
- Public config still includes local non-secret paths such as download/cache directories; treat it as safe for local agents and scripts, not as output to publish publicly.

## Daemon Startup

From the repository root:

```bash
uv run python -m pandora_daemon
uv run pandora-daemon
```

CLI commands default to:

```text
http://127.0.0.1:7860
```

Override when needed:

```bash
uv run python -m pandora_daemon.cli health --json --daemon-url http://127.0.0.1:7860
```

## Readiness Checks

Use these before running agent workflows:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli tags status --json
```

Expected guidance:

- `health --json` is the minimal capability probe.
- `config --json` exposes local-agent-safe runtime config: credentials are omitted and proxy secrets are redacted, but local non-secret paths may appear.
- `readiness --json` checks authenticated homepage/search/popular/home capability without returning upstream content.
- `status --json` returns `{"tasks": [...]}` for queue inspection.
- `tags status --json` returns the EhTagTranslation cache status for search agents.

Run the first four commands in the shown order. `readiness --json` exits 1 when
the daemon answered but authenticated upstream work is not ready; its JSON still
uses the stable readiness schema. This differs from a CLI `connect_error`.

Machine-mode error contract:

```json
{"ok": false, "error": {"code": "connect_error", "message": "Cannot connect to daemon at http://127.0.0.1:7860"}}
```

Current error codes covered by CLI tests:

- `connect_error`
- `http_error`
- `invalid_gallery_target`
- `usage_error`
- `websocket_error`
- `websocket_dependency_missing`

## Systemd User Service

Example `~/.config/systemd/user/pandora.service`. Check the `uv` path first with `command -v uv` and adjust `ExecStart` if needed:

```ini
[Unit]
Description=Pandora daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/code/projects/pandora
ExecStart=/usr/bin/uv run python -m pandora_daemon
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

Enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now pandora.service
systemctl --user status pandora.service
```

Adjust `WorkingDirectory` and `ExecStart` to match your install location.

## CLI Smoke Tests

Read-only agent checks:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli search "tag" --page 0 --json
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
uv run python -m pandora_daemon.cli popular --json
uv run python -m pandora_daemon.cli toplist --tl 15 --json
uv run python -m pandora_daemon.cli watched --page 0 --json
uv run python -m pandora_daemon.cli favorites list --json
uv run python -m pandora_daemon.cli tags suggest "artist" --json
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json
uv run python -m pandora_daemon.cli library list --json
uv run python -m pandora_daemon.cli download report --json
```

For translated tag searches, Pandora intentionally uses scheme A. The CLI does not automatically resolve Chinese or other translated user text into ExHentai tag syntax. Agent flow: `tags status --json`, `tags refresh --json` if stale or unloaded, `tags suggest "丝袜" --json`, agent chooses a candidate such as `female:stockings`, then `search "female:stockings" --search-tags --json`.

Download lifecycle checks:

```bash
uv run python -m pandora_daemon.cli download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
uv run python -m pandora_daemon.cli download add "https://exhentai.org/g/123/abcdef0123/" --json
uv run python -m pandora_daemon.cli download list --json
uv run python -m pandora_daemon.cli download report --json
uv run python -m pandora_daemon.cli download pages 123 --json
uv run python -m pandora_daemon.cli download watch 123 --ndjson
uv run python -m pandora_daemon.cli download cancel 123 --json
uv run python -m pandora_daemon.cli download resume 123 --json
uv run python -m pandora_daemon.cli download retry 123 --json
```

Prefer `download run --ndjson` for bots and agents. It attaches to the WebSocket stream before submitting the download, emits `download_submitted` or `download_already_queued`, then watches until a terminal event. `download add` plus `download watch` is still useful for manual composition, but a watcher started later can miss events emitted immediately after submission.

Agent Pack bootstrap flow:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli tags status --json
```

Agent Pack Scheme A search flow:

```bash
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json   # if stale or unloaded
uv run python -m pandora_daemon.cli tags suggest "丝袜" --json
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
```

Agent Pack download flow:

```bash
uv run python -m pandora_daemon.cli download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
uv run python -m pandora_daemon.cli download report --json
uv run python -m pandora_daemon.cli download pages 123 --json
uv run python -m pandora_daemon.cli library list --json
```

Legacy human-oriented commands remain available:

```bash
uv run python -m pandora_daemon.cli download "https://exhentai.org/g/123/abcdef0123/"
uv run python -m pandora_daemon.cli status
```

## Safety Notes

- Prefer `--json` and `--ndjson` for agents and scripts.
- Treat `config --json` as public/runtime-safe output, not a credential export.
- `gallery` CLI output redacts `api_uid` and `api_key`; do not depend on those fields from CLI output.
- `download pages --json` uses public page state `completed`; internal daemon state may still use `done`.
- `download report --json` is read-only and omits task tokens and local paths; branch on `consistent` and issue codes.
- `search --category` uses Pandora include-bitmask semantics; the daemon converts to ExHentai's exclude bitmask upstream.
- Do not expose `~/.config/pandora/config.toml` or raw proxy credentials in logs.
- The Web frontend is optional and not required for deployment readiness.
- The Rust TUI is archived and not part of the active deployment path.
- Generic agent workflows, snippets, safety notes, and schemas live in [`docs/agent/`](agent/README.md).
