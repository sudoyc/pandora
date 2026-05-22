# Search Workflow

Use this workflow for keyword search and advanced search filters. For translated terms that should become ExHentai tag syntax, use [`tag-resolution.md`](tag-resolution.md) first.

## Basic Search

```bash
uv run python -m pandora_daemon.cli search "keyword" --page 0 --json
```

Installed equivalent:

```bash
pandora search "keyword" --page 0 --json
```

## Tag Search

Only use `--search-tags` when the query is already valid ExHentai tag syntax or the agent has selected a candidate through Scheme A.

```bash
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
```

Do not use `search "丝袜" --search-tags` as automatic translation. That is a literal tag query.

## Advanced Flags

```bash
uv run python -m pandora_daemon.cli search "stocking" \
  --page 0 \
  --category 1 \
  --min-rating 4 \
  --search-name \
  --search-tags \
  --search-description \
  --search-torrent \
  --search-low-power-tags \
  --disable-language-filter \
  --show-expunged \
  --min-pages 10 \
  --max-pages 30 \
  --json
```

`--category` is a Pandora include bitmask. The daemon converts it to ExHentai's exclude bitmask upstream.

## Result Handling

Search results follow [`../schemas/search-response.schema.json`](../schemas/search-response.schema.json). Use `gid`, `token`, `title`, `category`, `rating`, `pages`, and `url` for ranking or follow-up inspection.

## When To Use Tag Resolution

Use [`tag-resolution.md`](tag-resolution.md) when:

- The user provides Chinese, Japanese, or translated tag text.
- Multiple namespaces or candidates are possible.
- The agent needs to justify why `female:stockings` or another tag was selected.
