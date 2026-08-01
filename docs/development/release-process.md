# Release Process

This runbook defines the repeatable internal release-candidate flow. It does
not create a tag or publish an artifact; those actions remain the `REL-02`
manual gate.

## Version Rules

- `pyproject.toml` `[project].version` is the single release version source.
- `uv.lock` must contain the same version for the editable `pandora` package.
- Supported versions are `X.Y.Z` and `X.Y.ZrcN`; the proposed Git tag is
  exactly `v<version>`.
- Increment patch for compatible fixes, minor for compatible features, and
  major for application/distribution breaking changes. Append `rcN` while a
  version is still a candidate; increment `N` for each replacement candidate.
- Add a dated `## [<version>] - YYYY-MM-DD` entry to `CHANGELOG.md` before
  building. Keep unreleased work under `[Unreleased]` until the next version is
  selected.
- The machine contract major is independent of the application version; a
  package bump does not silently change REST/CLI/WS compatibility.
- The Web package is a private consumer build and is not part of the Python
  wheel/sdist version or artifact set.

After changing the version, refresh the lock file and run the metadata check:

```bash
uv lock
uv run --frozen python scripts/release.py check --tag vVERSION
```

The check is also part of `scripts/check.py` and CI's Repository contracts job.

## Default Runtime Distribution

Per [ADR-010](../architecture/decisions.md#默认运行分发), the verified pure-Python
wheel installed into an isolated Python 3.12 venv is Pandora's only default
runtime distribution. The sdist remains a build-provenance and source-rollback
companion; it is not a second runtime installation path. One-directory bundles
and host-mutating service installers are not built or published.

The wheel verifier rejects unexpected or private paths, metadata version drift,
a `Requires-Python` value other than `>=3.12`, and changes to the `pandora` or
`pandora-daemon` console entry points. The optional Web client and frozen TUI
remain outside the runtime artifact.

## Internal Candidate

Use a new empty temporary directory. The command builds the sdist first, builds
the wheel from that sdist, rejects unexpected files or metadata drift, installs
the wheel into a temporary Python 3.12 environment, imports both Python
packages from outside the checkout, and runs `pandora --help`:

```bash
RC_DIR="$(mktemp -d -t pandora-release.XXXXXX)"
uv run --frozen python scripts/release.py candidate \
  --tag vVERSION \
  --out-dir "$RC_DIR"
```

The output directory contains only the wheel, source distribution, and the
non-artifact `.gitignore` marker created by `uv build`. The sdist contains the
two runtime packages and release metadata only; it does not contain tests,
documentation archives, the frozen TUI, Web `node_modules`/`dist`, caches,
downloads, or credentials. The command prints SHA-256 checksums for the two
artifacts. Repeat the command in another empty directory when a byte-for-byte
rebuild comparison is needed.

The installable runtime artifact from that directory is:

```text
pandora-VERSION-py3-none-any.whl
```

To verify artifacts that were copied from a candidate run without rebuilding:

```bash
uv run --frozen python scripts/release.py verify --dist-dir "$RC_DIR"
```

## Upgrade and Rollback Smoke

Keep the previous verified wheel alongside the candidate, then exercise the
complete lifecycle from the source checkout:

```bash
uv run --frozen python scripts/distribution_smoke.py \
  --previous-wheel "$PREVIOUS_WHEEL" \
  --candidate-wheel "$CANDIDATE_WHEEL"
```

The candidate version must be strictly newer. The script creates a temporary
Python 3.12 venv, HOME, config, cache, download directory, database, and
loopback port. An empty local tag fixture prevents an upstream tag fetch. It
installs and probes the previous wheel, upgrades and probes the candidate, then
reinstalls and probes the previous wheel as a planned rollback. Each probe runs
`health`, `config`, `readiness`, and `status`; the fixture deliberately has no
credentials, so the expected readiness result is `not_configured` with CLI exit
1.

Success exits 0 with a JSON lifecycle report. If candidate installation or
validation fails, the script automatically reinstalls and probes the previous
wheel before exiting 1. In that failure report,
`automatic_rollback_recovered: true` means recovery passed; `false` means the
rollback also failed. Reports omit subprocess logs, config contents, and
temporary paths.

This smoke proves the empty isolated-state lifecycle. It does not prove that an
older release can read state migrated by a newer release; keep compatible state
backups and follow the rollback rules below for a deployed instance.

## Manual Release Gate

`REL-02` may proceed only after `DIST-02` has completed installation, startup,
health/readiness, upgrade, and rollback smoke tests and an operator has granted
the release gate. Fixture CI is necessary but is not usability evidence. Before
creating a tag, run the candidate daemon with a read-only live session and run:

```bash
npm --prefix pandora-web run test:live
```

The live gate must report a valid session, a non-empty gallery feed, decodable
thumbnail/cover/reader pixels, no failed image responses, no direct browser
requests to upstream image hosts, and no browser runtime errors. Run it against
a controlled cold image cache for release evidence; a warm-cache rerun is only
diagnostic. Missing credentials or an unavailable upstream means the live gate
has no evidence and remains incomplete, not passed. See
[testing and usability acceptance](testing.md) for the evidence boundaries.

The operator then verifies a clean checkout, current `main`, the successful
hosted CI run, the proposed tag `vVERSION`, the live acceptance result, and the
recorded artifact checksums before creating or pushing any tag/release.
`REL-01` itself never performs those remote mutations.

## Rollback

Keep the previous verified wheel, its checksum, and the matching application
version available until the replacement has passed its smoke checks.

1. Stop the daemon and record the failing version and health output without
   including credentials or local paths in a report.
2. Preserve isolated backups of the daemon config, SQLite database, download
   state, and library metadata. Do not hand-edit state files or delete pages.
3. Install the previous verified wheel into the same environment, or restore
   the previous source commit using a normal revert/forward-fix workflow.
4. Start the daemon and verify `GET /api/health` reports the previous package
   version and contract major, then run the fixture readiness/status smoke.
5. Keep the backups until the replacement is either revalidated or explicitly
   abandoned. Never downgrade across an unsupported download-state schema;
   restore the application and state backup as a compatible pair.

For an installed wheel, the package rollback command is:

```bash
systemctl --user stop pandora.service
uv pip install --python "$VENV/bin/python" --reinstall "$PREVIOUS_WHEEL"
systemctl --user start pandora.service
"$VENV/bin/pandora" health --json
```

For a source deployment, create a normal revert commit for the bad application
change, rebuild a candidate from that new HEAD, and install its verified wheel:

```bash
git revert BAD_COMMIT
```

Do not reset or force-push shared history as a rollback mechanism.

Rollback is a recovery operation, not a release publication. Any state migration
or destructive cleanup requires a separate reviewed change.
