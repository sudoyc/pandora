# Bug Fix Agent Snippet

```text
You are fixing a Pandora bug.

Follow this exact order:
1. Triage and reproduce the bug.
2. Identify the failing layer.
3. Write or update a regression test first.
4. Implement the smallest fix.
5. Run targeted verification, then full verification.
6. Validate the real bot/deployment path if available.
7. Report root cause, files changed, tests, verification, and residual risk.

Rules:
- Do not guess the layer from the symptom alone.
- Do not patch before reproduction.
- Do not bypass pandora-daemon.
- Do not create a second state layer.
- Do not mix unrelated WIP into the commit.
```
