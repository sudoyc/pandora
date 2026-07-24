# Pandora Deployment

Pandora is deployed as a local daemon plus a CLI. Agent workflows should target the CLI in `--json` or `--ndjson` mode and follow the generic [Pandora Agent Pack](agent/README.md).

Versioned build, internal release-candidate, and rollback steps live in the
[release process runbook](development/release-process.md); this deployment
guide does not create tags or publish artifacts.

Hermes is one packaged consumer of the Agent Pack through `.agents/skills/pandora/SKILL.md`. There is no separate in-repo Hermes plugin/toolset package yet; future wrappers should stay thin and call the CLI or daemon instead of creating a parallel control plane.

## Prerequisites

- Linux, macOS, or another environment that can run Python 3.12+
- `uv`
- A verified `pandora-VERSION-py3-none-any.whl` candidate
- Valid ExHentai/E-Hentai session cookies in config when using authenticated endpoints
- Network or package-index access for the wheel's declared dependencies during installation

## Default Wheel Installation

The verified wheel is the only default runtime distribution. On a POSIX host,
install it into a dedicated venv instead of a development checkout or the system
Python:

```bash
PANDORA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/pandora"
uv venv --python 3.12 "$PANDORA_HOME/venv"
uv pip install --python "$PANDORA_HOME/venv/bin/python" \
  --link-mode copy /path/to/pandora-VERSION-py3-none-any.whl
"$PANDORA_HOME/venv/bin/pandora" --help
```

The wheel provides both `pandora` and `pandora-daemon`. It contains the daemon,
CLI, and stateless API library, but not the optional Web client, frozen TUI,
credentials, cache, database, downloads, or other runtime state. Keep the wheel
and its recorded SHA-256 checksum for upgrades and rollback.

Source-checkout commands using `uv run` remain development conveniences. They
are not a second supported runtime distribution.

Before replacing an installed version, run the isolated upgrade and rollback
smoke from a source checkout with both verified wheels:

```bash
uv run --frozen python scripts/distribution_smoke.py \
  --previous-wheel "$PREVIOUS_WHEEL" \
  --candidate-wheel "$CANDIDATE_WHEEL"
```

This command uses temporary no-credential state and a loopback daemon. It does
not contact authenticated upstream endpoints or modify the deployed config,
database, cache, or downloads. Exit 0 confirms previous install, candidate
upgrade, and planned rollback probes. On candidate failure, exit 1 with
`automatic_rollback_recovered: true` confirms that the previous wheel was
automatically reinstalled and probed. See the
[release process runbook](development/release-process.md#upgrade-and-rollback-smoke)
for the exact probe and state boundaries.

For contract checks from a development checkout, the equivalent diagnostic
sequence is:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli status --json
```

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

From the default wheel installation:

```bash
"$PANDORA_HOME/venv/bin/pandora-daemon"
```

From a development checkout:

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
"$PANDORA_HOME/venv/bin/pandora" health --json --daemon-url http://127.0.0.1:7860
```

## Download State Recovery

The daemon exclusively owns `~/.config/pandora/downloads.json`. Its current
internal format is a version 1 envelope with `schema_version` and `tasks`.

- Existing unversioned task mappings migrate to version 1 with an atomic temp-file replace.
- Truncated JSON, invalid envelopes, and invalid task entries are preserved as `downloads.json.corrupt`, then `.corrupt.1`, and so on. The active file is rebuilt with every task that parsed successfully.
- An explicit unsupported schema version aborts daemon startup before download workers start and leaves the file unchanged. Run a compatible Pandora version instead of editing or downgrading the file by hand.

Use `download report --json` for task/library consistency. Agents and wrappers
must not read or modify the state file or its recovery backups directly.

For a complete unregistered library entry or stale inactive task, preview the
daemon-owned recovery action before applying it:

```bash
"$PANDORA_HOME/venv/bin/pandora" download repair GID --json
"$PANDORA_HOME/venv/bin/pandora" download repair GID --apply --json
"$PANDORA_HOME/venv/bin/pandora" download forget GID --json
"$PANDORA_HOME/venv/bin/pandora" download forget GID --apply --json
```

Repair/forget only update the versioned task state. They never remove metadata,
pages, or library directories.

## Readiness Checks

Use these before running agent workflows:

```bash
"$PANDORA_HOME/venv/bin/pandora" health --json
"$PANDORA_HOME/venv/bin/pandora" config --json
"$PANDORA_HOME/venv/bin/pandora" readiness --json
"$PANDORA_HOME/venv/bin/pandora" status --json
"$PANDORA_HOME/venv/bin/pandora" tags status --json
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
- `invalid_argument`
- `invalid_gallery_target`
- `usage_error`
- `websocket_error`
- `websocket_dependency_missing`

`GET /api/health` exposes machine `contract_version: "1"` independently of the
application version. CLI exits are 0 for success, 1 for recognized negative
results or runtime failures, 2 for parser usage errors, and 130 for Ctrl-C.
`refresh_failed` is specific to the `tags refresh` result and is not a generic
CLI error-envelope code.

## Systemd User Service

Example `~/.config/systemd/user/pandora.service` for the default wheel location:

```ini
[Unit]
Description=Pandora daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%h/.local/share/pandora/venv/bin/pandora-daemon
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

Adjust `ExecStart` when `XDG_DATA_HOME` or the install location differs. The
service unit is a deployment recipe for the installed wheel, not a separate
distribution artifact.

## CLI Smoke Tests

Read-only agent checks:

```bash
"$PANDORA_HOME/venv/bin/pandora" health --json
"$PANDORA_HOME/venv/bin/pandora" config --json
"$PANDORA_HOME/venv/bin/pandora" readiness --json
"$PANDORA_HOME/venv/bin/pandora" status --json
"$PANDORA_HOME/venv/bin/pandora" search "tag" --page 0 --json
"$PANDORA_HOME/venv/bin/pandora" search "female:stockings" --search-tags --json
"$PANDORA_HOME/venv/bin/pandora" popular --json
"$PANDORA_HOME/venv/bin/pandora" toplist --tl 15 --json
"$PANDORA_HOME/venv/bin/pandora" watched --page 0 --json
"$PANDORA_HOME/venv/bin/pandora" favorites list --json
"$PANDORA_HOME/venv/bin/pandora" tags suggest "artist" --json
"$PANDORA_HOME/venv/bin/pandora" tags status --json
"$PANDORA_HOME/venv/bin/pandora" tags refresh --json
"$PANDORA_HOME/venv/bin/pandora" library list --json
"$PANDORA_HOME/venv/bin/pandora" download report --json
```

For translated tag searches, Pandora intentionally uses scheme A. The CLI does not automatically resolve Chinese or other translated user text into ExHentai tag syntax. Agent flow: `tags status --json`, `tags refresh --json` if stale or unloaded, `tags suggest "丝袜" --json`, agent chooses a candidate such as `female:stockings`, then `search "female:stockings" --search-tags --json`.

Download lifecycle checks:

```bash
"$PANDORA_HOME/venv/bin/pandora" download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
"$PANDORA_HOME/venv/bin/pandora" download add "https://exhentai.org/g/123/abcdef0123/" --json
"$PANDORA_HOME/venv/bin/pandora" download list --json
"$PANDORA_HOME/venv/bin/pandora" download report --json
"$PANDORA_HOME/venv/bin/pandora" download pages 123 --json
"$PANDORA_HOME/venv/bin/pandora" download watch 123 --ndjson
"$PANDORA_HOME/venv/bin/pandora" download cancel 123 --json
"$PANDORA_HOME/venv/bin/pandora" download resume 123 --json
"$PANDORA_HOME/venv/bin/pandora" download retry 123 --json
```

Prefer `download run --ndjson` for bots and agents. It attaches to the WebSocket stream before submitting the download, emits `download_submitted` or `download_already_queued`, then watches until a terminal event. `download add` plus `download watch` is still useful for manual composition, but a watcher started later can miss events emitted immediately after submission.

Agent Pack bootstrap flow:

```bash
"$PANDORA_HOME/venv/bin/pandora" health --json
"$PANDORA_HOME/venv/bin/pandora" config --json
"$PANDORA_HOME/venv/bin/pandora" readiness --json
"$PANDORA_HOME/venv/bin/pandora" status --json
"$PANDORA_HOME/venv/bin/pandora" tags status --json
```

Agent Pack Scheme A search flow:

```bash
"$PANDORA_HOME/venv/bin/pandora" tags status --json
"$PANDORA_HOME/venv/bin/pandora" tags refresh --json   # if stale or unloaded
"$PANDORA_HOME/venv/bin/pandora" tags suggest "丝袜" --json
"$PANDORA_HOME/venv/bin/pandora" search "female:stockings" --search-tags --json
```

Agent Pack download flow:

```bash
"$PANDORA_HOME/venv/bin/pandora" download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
"$PANDORA_HOME/venv/bin/pandora" download report --json
"$PANDORA_HOME/venv/bin/pandora" download pages 123 --json
"$PANDORA_HOME/venv/bin/pandora" library list --json
```

Legacy human-oriented commands remain available:

```bash
"$PANDORA_HOME/venv/bin/pandora" download "https://exhentai.org/g/123/abcdef0123/"
"$PANDORA_HOME/venv/bin/pandora" status
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
