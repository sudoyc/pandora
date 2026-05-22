# Minimal Agent Snippet

```text
Use the Pandora Agent Pack. Pandora is daemon-backed: all durable state belongs to pandora-daemon, including credentials, session, cache, SQLite data, download queue, bookmarks, filters, and local library.

Use only CLI JSON/NDJSON, daemon REST, or daemon WebSocket. From a checkout, prefer `uv run python -m pandora_daemon.cli ... --json` or `--ndjson`; when installed, `pandora ... --json` is equivalent.

Do not import `exhentai_api`, scrape ExHentai directly, persist credentials or session data, create a second state layer, or parse human CLI output when machine output exists.
```
