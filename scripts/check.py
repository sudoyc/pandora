from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
Check = tuple[str, tuple[str, ...]]
Runner = Callable[..., subprocess.CompletedProcess]

CHECKS: tuple[Check, ...] = (
    ("Python lock", ("uv", "lock", "--check")),
    ("Web lock and install", ("npm", "--prefix", "pandora-web", "ci")),
    (
        "Markdown links and Agent schemas",
        ("uv", "run", "--frozen", "python", "-m", "scripts.repo_checks"),
    ),
    ("Python tests", ("uv", "run", "--frozen", "python", "-m", "pytest", "-q")),
    ("Web lint", ("npm", "--prefix", "pandora-web", "run", "lint")),
    ("Web build", ("npm", "--prefix", "pandora-web", "run", "build")),
    ("Git whitespace", ("git", "diff", "--check")),
)
CHECK_GROUPS: dict[str, tuple[Check, ...]] = {
    "repository": (CHECKS[0], CHECKS[2], CHECKS[6]),
    "python": (CHECKS[3],),
    "web": (CHECKS[1], CHECKS[4], CHECKS[5]),
}


def run_checks(
    checks: Iterable[Check] = CHECKS,
    *,
    runner: Runner = subprocess.run,
    root: Path = ROOT,
) -> int:
    for label, command in checks:
        print(f"[CHECK] {label}", flush=True)
        try:
            result = runner(list(command), cwd=root)
        except FileNotFoundError as exc:
            print(f"[FAIL] {label}: command not found: {exc.filename}", file=sys.stderr)
            return 1
        if result.returncode != 0:
            print(f"[FAIL] {label}", file=sys.stderr)
            return result.returncode
        print(f"[PASS] {label}", flush=True)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Pandora repository checks.",
        prog="uv run --frozen python scripts/check.py",
    )
    parser.add_argument(
        "--group",
        choices=CHECK_GROUPS,
        help="run one CI check group instead of the complete local suite",
    )
    args = parser.parse_args(argv)
    checks = CHECK_GROUPS[args.group] if args.group else CHECKS
    return run_checks(checks)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
