# Gallery Inspection Workflow

Use this workflow to inspect gallery metadata without downloading.

## Inputs

Accepted gallery targets:

- Full gallery URL: `https://exhentai.org/g/123/abcdef0123/`
- `gid token` pair: `123 abcdef0123`

## Commands

```bash
uv run python -m pandora_daemon.cli gallery "https://exhentai.org/g/123/abcdef0123/" --json
uv run python -m pandora_daemon.cli gallery 123 abcdef0123 --json
```

Installed equivalents:

```bash
pandora gallery "https://exhentai.org/g/123/abcdef0123/" --json
pandora gallery 123 abcdef0123 --json
```

## Use The Output For

- Title, category, uploader, rating, page count, size, posted date.
- Tags and namespaces.
- Favorite slot and counts.
- Comment summaries.
- Thumbnail and cover URLs through daemon-backed proxy flows when needed.

## Redaction Boundary

CLI `gallery --json` redacts `api_uid` and `api_key` by default. Use gallery detail for user-facing metadata and route identifiers only. Daemon-internal helper fields from REST detail responses, including `api_uid`, `api_key`, `viewer_urls`, `thumb_urls`, and `thumb_sprites`, are internal-only and should not be persisted or exposed.

## Follow-Up Workflows

- Search related galleries: [`search.md`](search.md)
- Download the gallery: [`download.md`](download.md)
- Inspect local copy after download: [`library.md`](library.md)
