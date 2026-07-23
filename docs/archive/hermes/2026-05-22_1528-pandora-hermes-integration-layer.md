# Pandora Hermes Integration Layer Plan

> For Hermes: use OpenCode for bounded implementation, then Hermes performs diff inspection, testing, review, and precise staging.

Goal: make Pandora immediately consumable from Hermes as a repo-shipped skill workflow, while keeping the future plugin/toolset layer thin and strictly built on the stable daemon/CLI contract.

Architecture: do not build a heavyweight Hermes plugin inside Pandora yet. First ship a strong in-repo Pandora skill + helper docs/examples that standardize the agent workflow around `pandora` CLI JSON/NDJSON commands. If a thin plugin/toolset shim is added now, it should only wrap existing CLI entrypoints or shared pure helpers and must not introduce new business logic or bypass the daemon.

Tech Stack: Python 3.12, Pandora CLI/daemon, in-repo SKILL.md docs, pytest, uv, git, optional OpenCode for coding execution.

---

## Problem Statement

Pandora's CLI/daemon contract is now strong enough for agent use, but the Hermes integration surface is still mostly documentation-oriented. We need the next layer so Hermes can reliably operate Pandora with minimal per-session steering, without prematurely coupling Pandora to Hermes internals or inventing a parallel API surface.

The user explicitly chose scheme A:
- agent performs `tags status -> tags refresh? -> tags suggest -> choose candidate -> search`
- Pandora should expose primitives, not embed ambiguous decision logic

This means the next deliverable should optimize for:
1. reusable agent workflow
2. stable machine-readable commands
3. minimal integration code
4. future migration path to a thin toolset/plugin

## Current State Inventory

Confirmed now:
- `pandora` CLI exists via `pyproject.toml` script entrypoint
- `.agents/skills/pandora/SKILL.md` exists and documents core agent workflows
- daemon/CLI contracts cover search/tag/download flows with JSON/NDJSON
- no in-repo Hermes plugin/toolset package exists yet
- repo still has unrelated pre-existing WIP in `pandora-web/*`, `pandora_daemon/app.py`, `pandora-tui/Cargo.lock`

Implication:
- fastest safe next step is to harden the repo-shipped Hermes skill and add explicit tool-facing workflow guidance/examples/tests/docs
- if any code shim is added, it should be a tiny wrapper/helper layer around existing CLI semantics, not a second control plane

## Target Deliverable

Produce a “Hermes-ready Pandora integration layer” that includes:
- a polished, repo-shipped Pandora skill for agent operation
- clear workflow docs for search/tag/download orchestration under scheme A
- optional tiny helper surface in Python only if it reduces agent ambiguity without duplicating daemon logic
- regression tests/doc checks for any new code behavior

Non-goals:
- no new frontend work
- no TUI revival
- no direct ExHentai access from Hermes wrappers
- no automatic translated-tag resolution
- no broad plugin framework unless it is truly thin and zero-logic

---

## Task 1: Inspect current Hermes-facing repo surface

Objective: identify every existing Pandora artifact relevant to Hermes integration before changing anything.

Files:
- Read: `.agents/skills/pandora/SKILL.md`
- Read: `README.md`
- Read: `docs/architecture.md`
- Read: `docs/deployment.md`
- Read: `pyproject.toml`
- Search: repo for `hermes`, `skill`, `plugin`, `toolset`

Step 1: record which artifacts already define the agent contract.
Step 2: record missing pieces needed for “usable from Hermes with little steering”.
Step 3: explicitly confirm no existing plugin package/tool module should be reused.

Verification:
- written implementation notes mention skill path, CLI entrypoint, and absence/presence of plugin code

## Task 2: Decide the minimal integration shape

Objective: lock the implementation scope before coding.

Decision rules:
- Prefer skill-first integration
- Add code only if it removes repeated ambiguity for agent usage
- Any code must remain daemon/CLI-thin and machine-oriented

Expected output:
- either “skill/docs only”
- or “skill/docs + tiny helper module/command with tests”

Verification:
- implementation notes clearly say why this is the minimal safe path

## Task 3: Add or refine the Hermes-facing Pandora workflow surface

Objective: make the integration directly usable by an agent.

Possible files depending on findings:
- Modify: `.agents/skills/pandora/SKILL.md`
- Modify: `README.md`
- Modify: `docs/deployment.md`
- Modify: `docs/architecture.md`
- Optional create/modify: small helper module under `pandora_daemon/` only if truly needed
- Optional tests under `tests/pandora_daemon/`

Required content:
- explicit scheme A search flow
- explicit daemon lifecycle/readiness flow
- explicit download orchestration flow
- explicit machine-mode failure semantics
- explicit note that future Hermes plugin/toolset must stay thin and call CLI/daemon, not bypass daemon state
- if helper code is added, examples for exact usage and JSON output

If code is added, use TDD:
1. write failing tests
2. run targeted pytest red
3. implement minimal code
4. run targeted pytest green

Verification:
- skill/docs examples are copy-pasteable
- any new helper code has tests

## Task 4: Add “future thin plugin/toolset boundary” documentation

Objective: prevent future drift into a parallel control plane.

Files:
- Modify: `docs/architecture.md`
- Modify: `README.md`
- Optional: new small doc `docs/hermes_integration.md`

Document these rules:
- Hermes integration boundary = CLI/daemon contract
- plugin/toolset may wrap CLI/shared pure helpers only
- no daemon bypass for auth/cache/download/session logic
- prefer JSON/NDJSON contracts over ad-hoc text parsing
- complex decision logic stays in the agent, not Pandora

Verification:
- docs contain a short section naming this boundary explicitly

## Task 5: Verification and acceptance

Objective: prove the new integration layer is truly usable.

Run as applicable:
```bash
uv run python -m pytest tests/pandora_daemon/test_cli.py -q
uv run python -m pytest tests/pandora_daemon/test_agent_contracts.py -q
uv run python -m pytest -q
git diff --check
```

Manual smoke expectations:
- repo docs/skill clearly tell Hermes how to operate Pandora
- no examples suggest bypassing the daemon
- no examples rely on the archived TUI
- any helper code emits machine-readable output and stable exit codes

## Acceptance Criteria

Ship only when all are true:
- Pandora is clearly usable from Hermes through repo-shipped guidance and/or tiny wrapper code
- scheme A is documented consistently everywhere
- future plugin/toolset boundary is explicit and thin
- no unrelated WIP is touched or staged
- targeted/full tests pass
- resulting state is ready for a later thin Hermes plugin/toolset with minimal new design work

## Commit Strategy

Single commit if scope stays small and coherent:
```bash
git add <exact files>
git commit -m "feat: prepare Pandora Hermes integration layer"
```

If a helper module is added and materially separate from docs, two commits are acceptable:
1. `feat: add Pandora Hermes helper surface`
2. `docs: document Pandora Hermes integration workflows`

## Pitfalls

1. Do not create a second stateful layer outside the daemon.
2. Do not add automatic tag-choice logic; that violates scheme A.
3. Do not mix pandora-web or TUI cleanup into this task.
4. Do not expose credentials in skill examples.
5. Do not add a plugin that depends on brittle human-readable CLI output.
6. If a helper surface is unnecessary, do not invent one just to “have plugin code”.

## Verification Checklist

- [ ] Scope stayed inside intended Hermes integration files
- [ ] Skill/docs now make agent usage operationally obvious
- [ ] Any new code is thin, tested, and daemon-backed
- [ ] `uv run python -m pytest -q` passes
- [ ] `git diff --check` passes
- [ ] only intended files are staged
