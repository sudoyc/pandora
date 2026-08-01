#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
export LC_ALL=C.UTF-8
export PYTHONHASHSEED=0
export TZ=UTC

exec uv run --frozen --no-sync python scripts/architecture_benchmark.py
