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
uv run python -m pandora_daemon.cli library export-pdf 123 --password "PDF_PASSWORD" --json
```

## PDF Export Hook

PDF export uses the same daemon/WebSocket boundary as download monitoring.

REST endpoint:

```text
POST /api/library/{gid}/export/pdf
```

Hook events:

```json
{"event":"pdf_export_started","gid":"123"}
{"event":"pdf_export_complete","gid":"123","path":"/path/to/file.pdf","password_protected":true}
{"event":"pdf_export_error","gid":"123","error":"..."}
```

Notes:
- Use the explicit CLI/REST password entry only when a protected PDF is required.
- Do not echo or persist the password in your own agent state.
- Treat `pdf_export_complete` as success and `pdf_export_error` as failure.

## State Boundary

Do not persist a separate library catalog. If an agent needs the latest local gallery list, call `library list --json` again.
