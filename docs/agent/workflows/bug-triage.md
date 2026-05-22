# Bug Triage Workflow

Use this workflow when a deployed bot, agent, or CLI report shows unexpected behavior and you need to identify the failing layer before making a fix.

## Goal

Turn a live symptom into a reproducible root cause with a clearly scoped owner and a minimal repair plan.

## When To Use

- A user reports a bug through a bot or messaging platform.
- A CLI or daemon command returns the wrong result, hangs, or emits an unexpected machine error.
- You suspect the issue may be in the bot adapter, agent prompt, daemon contract, or upstream site.

If the failure is already a machine-mode JSON/NDJSON error, start with [`failure-recovery.md`](failure-recovery.md).

## Intake Checklist

Capture these before touching code:

- deployment target and host name
- Pandora version or commit
- Hermes/OpenCode profile, if relevant
- exact user message or CLI command
- exact bot reply, error, or terminal event
- whether the bug reproduces in CLI, daemon, or only in the bot
- relevant logs, request/response snippets, and session IDs
- whether you are allowed to diagnose only, patch code, or deploy

## Triage Steps

### 1. Freeze the current state

Do not patch anything yet. Record the symptom in a short, copyable form.

### 2. Reproduce at the narrowest surface

Prefer this order:

1. Pandora CLI
2. Pandora daemon REST/WS
3. Bot adapter or gateway

Example probes:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli tags status --json
```

For search-related issues:

```bash
uv run python -m pandora_daemon.cli search "keyword" --json
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
```

For download-related issues:

```bash
uv run python -m pandora_daemon.cli download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
```

### 3. Classify the failing layer

Use the first layer that clearly differs between expected and actual behavior:

- Platform adapter: Telegram/Discord/QQ/etc. message delivery, session mapping, permissions
- Agent orchestration: prompt, tool choice, context, session reuse, wrapper logic
- Agent Pack: workflow doc, snippet, contract text, prompt block
- Pandora daemon/CLI: REST, WebSocket, JSON/NDJSON envelope, queue state, tag DB
- Upstream: ExHentai page change, auth failure, limit, or site-side behavior

### 4. Collect evidence

Keep evidence concrete:

- exact command or message
- expected vs actual output
- raw machine output, not a paraphrase
- logs from the runtime that observed the failure
- relevant file paths or contract names
- any deployment hash or version marker

### 5. Form a root-cause hypothesis

State one narrow hypothesis, for example:

- "The bot adapter is dropping the final NDJSON event."
- "The agent is skipping tag resolution and issuing a literal search query."
- "The daemon contract returns the right data, but the wrapper is parsing human output."

## Output Format

Return this structure to the human or supervising agent:

```text
Bug summary:
Root cause hypothesis:
Affected layer:
Reproduction path:
Evidence collected:
Recommended fix scope:
Needs code change: yes/no
Needs deployment: yes/no
Residual risks:
```

## Rules

- Do not patch before reproduction.
- Do not guess the layer from the symptom alone.
- Do not bypass the daemon to "test quickly".
- Do not add a fix that cannot be regression-tested.
- Keep unrelated WIP out of the task.
