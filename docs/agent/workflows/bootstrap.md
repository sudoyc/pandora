# Bootstrap Workflow

Use this workflow before agent automation.

## Steps

1. Confirm the working directory is the Pandora repository root.
2. Start the daemon if it is not already running.
3. Run readiness probes.
4. For search/tag work, check tag database status.
5. Use the default daemon URL unless the user provides another one.

## Commands

Start daemon:

```bash
uv run python -m pandora_daemon
```

Readiness:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli tags status --json
```

Installed CLI equivalents:

```bash
pandora health --json
pandora config --json
pandora readiness --json
pandora status --json
pandora tags status --json
```

## Expected Interpretation

- `health --json` confirms daemon availability and safe capabilities.
- `config --json` confirms runtime config without credentials.
- `readiness --json` checks authenticated upstream capabilities without returning upstream content.
- `status --json` confirms the download queue can be inspected.
- `tags status --json` confirms whether translated-tag suggestions are loaded, stale, or need refresh.

## Failure Handling

Run `health`, `config`, `readiness`, and `status` in that order. Readiness exit 1
is a valid structured not-ready result; a machine error such as `connect_error`
uses the failure envelope and should follow [`failure-recovery.md`](failure-recovery.md).
Do not read credential files to diagnose readiness.
