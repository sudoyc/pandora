# Library Workflow

Use this workflow to inspect downloaded galleries through daemon-backed local library APIs.

## List Library

```bash
uv run python -m pandora_daemon.cli library list --json
```

Installed equivalent:

```bash
pandora library list --json
```

Library items include stable fields such as `gid`, `token`, `title`, `pages`, and `thumb_url`.

## File Serving Boundary

The daemon serves local files through:

```text
GET /api/library/{gid}/file?path=...
```

Agents should use daemon paths/URLs for local file serving instead of scanning download directories as a second library index. The daemon handles path validation and special-character lookup.

## Related Commands

Inspect download queue:

```bash
uv run python -m pandora_daemon.cli download list --json
uv run python -m pandora_daemon.cli download pages 123 --json
```

## State Boundary

Do not persist a separate library catalog. If an agent needs the latest local gallery list, call `library list --json` again.
