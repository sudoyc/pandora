# Tag Resolution Workflow

Pandora uses Scheme A for translated tag searches. The daemon and CLI provide primitive tag database operations; the agent chooses the candidate and explains the evidence.

## Steps

1. Check tag database status.
2. Refresh if the database is stale or unloaded.
3. Request suggestions for the user's translated or original text.
4. Choose the best candidate using namespace, tag, translation, and user intent.
5. Search the selected ExHentai tag syntax with `--search-tags`.

## Commands

```bash
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json
uv run python -m pandora_daemon.cli tags suggest "丝袜" --json
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
```

Installed equivalent:

```bash
pandora tags status --json
pandora tags refresh --json
pandora tags suggest "丝袜" --json
pandora search "female:stockings" --search-tags --json
```

## Candidate Evidence Requirement

When reporting the selected query, include the candidate evidence briefly:

```text
Selected `female:stockings` because tag suggestions matched translation `丝袜` in namespace `female` with tag `stockings`.
```

## Do Not Auto-Rewrite

Do not collapse Scheme A into:

```bash
uv run python -m pandora_daemon.cli search "丝袜" --search-tags --json
```

That command sends an untranslated literal tag query. It is only correct if the user explicitly wants literal tag syntax.
