from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from scripts.architecture_metrics import collect_static_metrics
from scripts.provider_swap_workload import run_provider_swap_workload


ROOT = Path(__file__).resolve().parents[1]

# Failures in the executable provider-swap path dominate static architecture
# smells. Static weights then reward removing concrete provider knowledge from
# the daemon without letting cosmetic renames hide a broken workload.
WEIGHTS: dict[str, int] = {
    "provider_import_edges": 12,
    "provider_symbol_leaks": 3,
    "concrete_provider_state_fields": 25,
    "provider_factory_calls": 20,
    "missing_provider_contract": 100,
    "missing_provider_registry": 80,
    "top_level_provider_packages": 30,
    "packaging_provider_leaks": 20,
    "route_module_naming_violations": 5,
    "product_naming_violations": 12,
    "architecture_doc_contradictions": 25,
    "swap_workload_failures": 200,
    "swap_contract_leaks": 40,
}


def score(metrics: Mapping[str, int]) -> int:
    """Return the lower-is-better architecture penalty."""
    return sum(metrics.get(name, 0) * weight for name, weight in WEIGHTS.items())


def collect_metrics(root: Path = ROOT) -> dict[str, int]:
    metrics = {
        **collect_static_metrics(root),
        **run_provider_swap_workload(),
    }
    expected = {*WEIGHTS, "swap_endpoints_passed"}
    if set(metrics) != expected:
        missing = sorted(expected - set(metrics))
        extra = sorted(set(metrics) - expected)
        raise RuntimeError(f"Invalid architecture metrics: missing={missing}, extra={extra}")
    if any(type(value) is not int or value < 0 for value in metrics.values()):
        raise RuntimeError("Architecture metrics must be nonnegative integers")
    return metrics


def main() -> int:
    metrics = collect_metrics()
    print(f"METRIC architecture_penalty={score(metrics)}")
    for name in sorted(metrics):
        print(f"METRIC {name}={metrics[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
