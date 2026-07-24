# Bug Fix Lifecycle

Use this workflow after triage has identified the failing layer and the user has authorized a fix.

## Goal

Land a minimal, regression-tested repair, verify it locally, then confirm the real bot/deployment path still works.

## Scope Rules

- Fix the root cause, not the symptom.
- Prefer the smallest change that makes the regression test pass.
- Keep `pandora-tui/` frozen unless the user explicitly reopens that decision.
- Do not mix unrelated WIP into the commit.

## Step 1: Write the regression test first

For daemon or contract bugs, add or update the most specific test available, usually under `tests/pandora_daemon/`.

Examples:

- CLI JSON/NDJSON envelope regression
- tag/search contract regression
- download state regression
- bot-facing prompt or workflow regression when the bug lives in docs/snippets rather than code

If the bug is purely workflow text, add the text change and a validation checklist instead of a code test.

## Step 2: Verify the failure

Run the targeted test or reproduction command and confirm it fails before changing code.

Examples:

```bash
uv run python -m pytest tests/pandora_daemon/test_agent_contracts.py -q
uv run python -m pytest tests/pandora_daemon/test_agent_contracts.py::test_name -q
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli search "keyword" --json
```

## Step 3: Implement the smallest fix

Typical repair targets:

- `pandora_daemon/routes/*.py`
- `pandora_daemon/cli.py`
- `pandora_daemon/tag_database.py`
- `docs/agent/workflows/*.md`
- `docs/agent/snippets/*.md`
- `.agents/skills/pandora/SKILL.md`

If the bug is in bot orchestration, fix the wrapper or prompt layer instead of changing daemon state ownership.

## Step 4: Run targeted verification

Run the exact regression test again, then adjacent smoke checks.

Suggested order:

```bash
uv run python -m pytest tests/pandora_daemon/test_agent_contracts.py -q
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli status --json
```

For search/tag fixes, also run:

```bash
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json
uv run python -m pandora_daemon.cli tags suggest "丝袜" --json
```

For download fixes, also run:

```bash
uv run python -m pandora_daemon.cli download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
```

## Step 5: Run the full project checks

Before declaring the fix done:

```bash
uv run python -m pytest -q
git diff --check
```

If the change touches only docs, still run `git diff --check` and the most relevant smoke command.

## Step 6: Validate the real bot/deployment path

After local verification, deploy or reload the bot environment and replay the original user steps.

Validate three things:

1. Original failing case now passes.
2. One or two adjacent cases still work.
3. Error handling still returns the documented machine envelope when expected.

## Step 7: Commit and push

Stage only the files for this bug.

```bash
git status --short
git add <explicit-files>
git commit -m "fix: <short bug summary>"
git push origin HEAD
```

## Step 8: Report back

Use this final shape:

```text
Root cause:
Files changed:
Tests added/updated:
Verification:
Deployment validation:
Residual risk:
```

## Common Failure Modes

- Fixing the symptom instead of the contract.
- Adding the fix before a regression test exists.
- Verifying only the local test and skipping the bot path.
- Staging unrelated WIP.
- Forgetting to update workflow docs when the bug came from a missing procedure.

## If the fix is in an agent workflow

When the bug is caused by an unclear or incomplete operating procedure, update the workflow docs or snippet so the same mistake cannot recur:

- `docs/agent/workflows/bug-triage.md`
- `docs/agent/workflows/bug-fix-lifecycle.md`
- `docs/agent/workflows/failure-recovery.md`
- `docs/agent/snippets/bug-fix-agent.md`
