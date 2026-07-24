from __future__ import annotations

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
    if argv:
        print("usage: uv run --frozen python scripts/check.py", file=sys.stderr)
        return 2
    return run_checks()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
