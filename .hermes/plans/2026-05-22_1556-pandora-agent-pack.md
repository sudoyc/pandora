# Pandora Agent Pack Implementation Plan

> **For Hermes:** This plan may be executed with OpenCode or another bounded coding agent, but Hermes keeps architecture, verification, and commit hygiene ownership.

**Goal:** Reframe Pandora's agent integration from a Hermes-specific integration document into a generic, daemon-backed, composable Agent Pack that any agent can consume.

**Architecture:** Pandora keeps all durable state in `pandora-daemon`. Agents consume stable CLI JSON/NDJSON, REST, and WebSocket contracts plus copy-pasteable prompt/context blocks. Hermes skill becomes one packaging consumer of the generic Agent Pack rather than the source of truth or a state layer.

**Tech Stack:** Markdown docs, JSON Schema snippets, existing Python daemon/CLI tests via `uv run python -m pytest`, git exact-path staging.

---

## Boundaries

### In scope

- Add `docs/agent/` as the canonical agent-facing documentation tree.
- Add composable alignment/prompt snippets for multiple agent types.
- Add workflow documents for bootstrap, search, tag resolution, gallery inspection, downloads, library operations, and failure recovery.
- Add JSON schema files documenting stable machine-facing envelopes/events.
- Update README, architecture, deployment, and Hermes skill references so they point to the generic Agent Pack.
- Keep `docs/hermes_integration.md` as a short compatibility/consumer note or replace its body with a pointer to the generic Agent Pack.

### Out of scope

- No new stateful plugin/toolset package.
- No daemon behavior changes.
- No direct `exhentai_api` exposure for agent workflows.
- No changes to `pandora-tui/` or `pandora-web/` WIP.
- No credential/config mutation.

## Pre-existing WIP to preserve

Do not stage or edit:

- `pandora-web/*`
- `pandora-tui/Cargo.lock`
- unrelated hunks in `pandora_daemon/app.py`

## Target file layout

Create:

```text
docs/agent/
  README.md
  context-pack.md
  contract.md
  safety.md
  workflows/
    bootstrap.md
    search.md
    tag-resolution.md
    gallery-inspection.md
    download.md
    library.md
    failure-recovery.md
  snippets/
    minimal.md
    read-only-agent.md
    search-agent.md
    download-agent.md
    full-operator.md
  schemas/
    cli-error-envelope.schema.json
    search-response.schema.json
    download-event.schema.json
```

Modify:

```text
README.md
docs/architecture.md
docs/deployment.md
docs/hermes_integration.md
.agents/skills/pandora/SKILL.md
```

## Task 1: Create generic Agent Pack overview

**Objective:** Establish `docs/agent/README.md` and `docs/agent/context-pack.md` as the canonical source for multi-agent usage.

**Files:**
- Create: `docs/agent/README.md`
- Create: `docs/agent/context-pack.md`

**Content requirements:**
- Use the term `Pandora Agent Pack`.
- State that all durable state belongs to `pandora-daemon`.
- List allowed surfaces: CLI JSON/NDJSON, REST, WebSocket.
- List forbidden surfaces: direct `exhentai_api`, direct scraping, second state layer, credential persistence, human-output parsing when machine output exists.
- Explain that Hermes skill is one consumer, not the source of truth.
- Provide copy-pasteable base context blocks.

**Verification:**
- Search for `Hermes-only` or Hermes-as-source-of-truth phrasing; none should remain in these new docs.

## Task 2: Create contract and safety docs

**Objective:** Split reusable contract and safety guidance from Hermes-specific docs.

**Files:**
- Create: `docs/agent/contract.md`
- Create: `docs/agent/safety.md`
- Create: JSON schema files under `docs/agent/schemas/`

**Content requirements:**
- Document CLI error envelope exactly: `{"ok": false, "error": {"code": "...", "message": "..."}}`.
- Document known error codes.
- Document readiness probes.
- Document download event discriminator `event`, terminal events, and exit semantics.
- Document redaction/privacy invariants: no credentials in docs, prompts, plugin state, or logs; public config may expose `proxy_configured`, not proxy secrets.
- Keep schemas lightweight and stable enough for agents to validate outputs.

**Verification:**
- JSON schema files parse with Python `json.load`.

## Task 3: Create workflow documents

**Objective:** Make task-level workflows composable for multiple agents.

**Files:**
- Create all files under `docs/agent/workflows/`.

**Content requirements:**
- `bootstrap.md`: health/config/status/tags status readiness flow.
- `search.md`: keyword search, advanced search flags, category bitmask note, when to use tag workflow.
- `tag-resolution.md`: Scheme A only; agent chooses candidate; do not auto-rewrite translated text.
- `gallery-inspection.md`: gallery URL/gid-token inspection and redaction note.
- `download.md`: prefer `download run --ndjson`, event ordering, terminal event behavior, follow-up inspection commands.
- `library.md`: downloaded gallery list and file serving boundaries.
- `failure-recovery.md`: connect errors, usage errors, stale tag DB, WebSocket errors, auth/image limit/download paused states.

**Verification:**
- Commands use `uv run python -m pandora_daemon.cli ...` examples and mention `pandora ...` can be used when installed.

## Task 4: Create prompt snippets

**Objective:** Provide directly composable alignment text for arbitrary agents.

**Files:**
- Create all files under `docs/agent/snippets/`.

**Content requirements:**
- `minimal.md`: shortest safe base block.
- `read-only-agent.md`: only read endpoints/commands, no mutation/download/comment/rating/config changes.
- `search-agent.md`: includes Scheme A and candidate-evidence requirement.
- `download-agent.md`: includes daemon-backed queue, NDJSON watch, terminal event handling.
- `full-operator.md`: combines read/search/download/library with explicit safety limits.

**Verification:**
- Snippets are standalone text blocks that can be pasted into a system/developer prompt.

## Task 5: Refactor Hermes-specific docs to consume Agent Pack

**Objective:** Keep Hermes support, but make it a packaging layer over the generic docs.

**Files:**
- Modify: `docs/hermes_integration.md`
- Modify: `.agents/skills/pandora/SKILL.md`

**Content requirements:**
- `docs/hermes_integration.md` should say Hermes consumes `docs/agent/` and should not duplicate the whole generic contract.
- The skill should point to `docs/agent/context-pack.md`, `docs/agent/contract.md`, and relevant workflows/snippets.
- The skill can retain concise command examples, verification commands, and repo-specific git hygiene.
- Remove phrasing that implies Hermes is the only or primary stateful integration target.

**Verification:**
- Skill remains valid Markdown with frontmatter.
- It still contains core Pandora commands and verification checklist.

## Task 6: Update main documentation references

**Objective:** Align README, architecture, and deployment docs with agent-pack-first design.

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/deployment.md`

**Content requirements:**
- Replace `Hermes integration first` wording with `Agent Pack first` or `agent-facing integration`.
- Explain that Hermes skill is the first packaged consumer.
- Link to `docs/agent/README.md` and keep `docs/hermes_integration.md` as Hermes-specific packaging guidance.
- Preserve TUI archived/frozen status.

**Verification:**
- Search for stale `Hermes plugin/toolset first` phrasing and update where needed.

## Task 7: Verify and review

**Commands:**

```bash
uv run python - <<'PY'
import json
from pathlib import Path
for p in Path('docs/agent/schemas').glob('*.json'):
    json.load(open(p))
    print(p)
PY
uv run python -m pytest tests/pandora_daemon/test_agent_contracts.py -q
git diff --check
```

**Review:**
- Run an independent review of the diff focused on multi-agent state boundaries, security, credentials, stale route names, and clarity.
- Fix blockers and any low-effort clarity issues.

## Task 8: Commit and push

**Staging:**

Stage exact files only:

```bash
git add \
  .hermes/plans/2026-05-22_1556-pandora-agent-pack.md \
  README.md \
  docs/architecture.md \
  docs/deployment.md \
  docs/hermes_integration.md \
  .agents/skills/pandora/SKILL.md \
  docs/agent/README.md \
  docs/agent/context-pack.md \
  docs/agent/contract.md \
  docs/agent/safety.md \
  docs/agent/workflows/bootstrap.md \
  docs/agent/workflows/search.md \
  docs/agent/workflows/tag-resolution.md \
  docs/agent/workflows/gallery-inspection.md \
  docs/agent/workflows/download.md \
  docs/agent/workflows/library.md \
  docs/agent/workflows/failure-recovery.md \
  docs/agent/snippets/minimal.md \
  docs/agent/snippets/read-only-agent.md \
  docs/agent/snippets/search-agent.md \
  docs/agent/snippets/download-agent.md \
  docs/agent/snippets/full-operator.md \
  docs/agent/schemas/cli-error-envelope.schema.json \
  docs/agent/schemas/search-response.schema.json \
  docs/agent/schemas/download-event.schema.json
```

**Commit message:**

```text
docs: introduce generic Pandora Agent Pack
```

**Push:**

```bash
git push origin HEAD
```

## Acceptance criteria

- Agent docs are generic and usable by Hermes/OpenCode/Codex/Claude/MCP-style wrappers.
- No new stateful plugin/toolset is introduced.
- Hermes skill clearly consumes the generic Agent Pack.
- Existing daemon/CLI contract tests still pass.
- JSON schemas parse successfully.
- Pre-existing WIP remains unstaged and untouched.
