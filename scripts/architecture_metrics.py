from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path


_STATIC_METRIC_KEYS = (
    "provider_import_edges",
    "provider_symbol_leaks",
    "concrete_provider_state_fields",
    "provider_factory_calls",
    "uncontracted_provider_calls",
    "adapter_surface_leaks",
    "untyped_provider_dependencies",
    "missing_provider_contract",
    "missing_provider_registry",
    "top_level_provider_packages",
    "packaging_provider_leaks",
    "route_module_naming_violations",
    "product_naming_violations",
    "architecture_doc_contradictions",
)
_EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "docs",
    "node_modules",
    "pandora-tui",
    "scripts",
    "tests",
}
_GENERIC_PROVIDER_MODULES = {
    "__init__.py",
    "base.py",
    "contracts.py",
    "errors.py",
    "models.py",
    "protocol.py",
    "registry.py",
    "types.py",
}
_PROVIDER_SPECIFIC_IDENTIFIERS = {
    "advsearch",
    "api_key",
    "api_uid",
    "f_cats",
    "f_search",
    "f_sdesc",
    "f_sdt1",
    "f_sh",
    "f_sname",
    "f_sp",
    "f_spf",
    "f_spt",
    "f_sr",
    "f_srdd",
    "f_stags",
    "f_sto",
    "f_storr",
    "igneous",
    "ipb_member_id",
    "ipb_pass_hash",
    "parse_gallery_detail",
    "parse_image_viewer",
    "preview_pages",
    "search_params",
    "thumb_sprites",
    "thumb_urls",
    "viewer_urls",
}
_PROVIDER_HOST_MARKERS = (
    "e-hentai.org",
    "ehgt.org",
    "exhentai.org",
    "hath.network",
)
_REGISTRY_MAPPING_NAMES = {
    "factories",
    "providerfactories",
    "providerregistry",
    "providers",
    "registry",
}


def _normalized(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _contains_provider_name(value: str) -> bool:
    normalized = _normalized(value)
    return "exhentai" in normalized or "ehentai" in normalized


def _is_provider_module(module: str) -> bool:
    if _contains_provider_name(module):
        return True
    parts = module.lower().split(".")
    return any(part in {"exhentai", "ehentai"} for part in parts)


def _is_provider_specific_identifier(identifier: str) -> bool:
    if _contains_provider_name(identifier):
        return True
    normalized = _normalized(identifier)
    return any(normalized == _normalized(candidate) for candidate in _PROVIDER_SPECIFIC_IDENTIFIERS)


def _is_explicit_provider_adapter(relative_path: Path) -> bool:
    parts = relative_path.parts
    if parts and (_contains_provider_name(parts[0]) or parts[0].endswith("_api")):
        return True
    try:
        provider_index = parts.index("providers")
    except ValueError:
        return False
    remainder = parts[provider_index + 1 :]
    return len(remainder) >= 2 or bool(
        remainder and remainder[0] not in _GENERIC_PROVIDER_MODULES
    )


def _production_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        relative_path = path.relative_to(root)
        if any(part in _EXCLUDED_PARTS for part in relative_path.parts):
            continue
        if _is_explicit_provider_adapter(relative_path):
            continue
        files.append(path)
    return sorted(files)


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _annotation_text(node: ast.expr | None) -> str:
    return ast.unparse(node) if node is not None else ""


def _is_provider_registry_mapping(
    node: ast.Assign | ast.AnnAssign,
    relative_path: Path,
) -> bool:
    path_parts = set(relative_path.parts)
    if not ({"provider", "providers"} & path_parts) and "registry" not in relative_path.stem:
        return False

    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    target_names = {
        _normalized(target.id)
        for target in targets
        if isinstance(target, ast.Name)
    }
    if not target_names & _REGISTRY_MAPPING_NAMES:
        return False

    annotation = node.annotation if isinstance(node, ast.AnnAssign) else None
    annotation_name = _normalized(_annotation_text(annotation))
    value = node.value
    call_name = _normalized(_call_name(value.func)) if isinstance(value, ast.Call) else ""
    return (
        isinstance(value, ast.Dict)
        or "dict" in annotation_name
        or "mapping" in annotation_name
        or call_name in {"defaultdict", "dict", "mappingproxytype"}
    )


def _is_api_client_escape(node: ast.Attribute) -> bool:
    if node.attr != "client" or not isinstance(node.value, ast.Attribute):
        return False
    return node.value.attr in {"api", "_api", "provider", "_provider"}


def _collect_python_metrics(root: Path) -> tuple[dict[str, int], bool, bool, int]:
    counts = {
        "provider_import_edges": 0,
        "provider_symbol_leaks": 0,
        "concrete_provider_state_fields": 0,
        "provider_factory_calls": 0,
    }
    has_provider_contract = False
    has_provider_registry = False
    product_path_violations: set[Path] = set()

    for path in _production_python_files(root):
        relative_path = path.relative_to(root)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(relative_path))

        if _contains_provider_name(relative_path.as_posix()):
            product_path_violations.add(relative_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if _is_provider_module(module):
                    counts["provider_import_edges"] += len(node.names)
            elif isinstance(node, ast.Import):
                counts["provider_import_edges"] += sum(
                    1 for alias in node.names if _is_provider_module(alias.name)
                )

            if isinstance(node, (ast.Name, ast.Attribute, ast.arg)):
                identifier = (
                    node.id
                    if isinstance(node, ast.Name)
                    else node.attr
                    if isinstance(node, ast.Attribute)
                    else node.arg
                )
                if _is_provider_specific_identifier(identifier):
                    counts["provider_symbol_leaks"] += 1
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if _is_provider_specific_identifier(node.name):
                    counts["provider_symbol_leaks"] += 1
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if _contains_provider_name(node.value) or any(
                    marker in node.value.lower() for marker in _PROVIDER_HOST_MARKERS
                ):
                    counts["provider_symbol_leaks"] += 1

            if isinstance(node, ast.Attribute) and _is_api_client_escape(node):
                counts["provider_symbol_leaks"] += 1

            if isinstance(node, ast.Call) and _contains_provider_name(_call_name(node.func)):
                counts["provider_factory_calls"] += 1

            if isinstance(node, ast.ClassDef):
                bases = {_normalized(_annotation_text(base)) for base in node.bases}
                if node.name.endswith("Provider") and any(
                    base.endswith("protocol") or base.endswith("abc") for base in bases
                ):
                    has_provider_contract = True
                if node.name == "AppState":
                    for statement in node.body:
                        if isinstance(statement, ast.AnnAssign) and _contains_provider_name(
                            _annotation_text(statement.annotation)
                        ):
                            counts["concrete_provider_state_fields"] += 1


            if isinstance(node, (ast.Assign, ast.AnnAssign)) and _is_provider_registry_mapping(
                node, relative_path
            ):
                has_provider_registry = True

    return counts, has_provider_contract, has_provider_registry, len(product_path_violations)


def _provider_contract_methods(root: Path) -> set[str]:
    contracts_path = root / "pandora_daemon" / "providers" / "contracts.py"
    if not contracts_path.is_file():
        return set()
    tree = ast.parse(
        contracts_path.read_text(encoding="utf-8"),
        filename=str(contracts_path.relative_to(root)),
    )
    methods: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {_normalized(_annotation_text(base)) for base in node.bases}
        if not any(base.endswith("protocol") for base in bases):
            continue
        methods.update(
            statement.name
            for statement in node.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
    return methods


def _uncontracted_provider_calls(root: Path) -> int:
    routes_path = root / "pandora_daemon" / "routes"
    if not routes_path.is_dir():
        return 0
    route_calls: set[str] = set()
    for path in sorted(routes_path.glob("*.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path.relative_to(root)),
        )
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and "provider" in _normalized(node.func.value.id)
            ):
                route_calls.add(node.func.attr)
    return len(route_calls - _provider_contract_methods(root))


def _adapter_surface_leaks(root: Path) -> int:
    adapters_path = root / "pandora_daemon" / "providers"
    if not adapters_path.is_dir():
        return 0
    contract_methods = _provider_contract_methods(root)
    leaks = 0
    for path in sorted(adapters_path.glob("*/adapter.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path.relative_to(root)),
        )
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or not node.name.endswith("Provider"):
                continue
            leaks += sum(
                1
                for statement in node.body
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not statement.name.startswith("_")
                and statement.name not in contract_methods
            )
    return leaks


def _is_provider_dependency(default: ast.expr | None) -> bool:
    if not isinstance(default, ast.Call) or _call_name(default.func) != "Depends":
        return False
    dependencies = [*default.args, *(keyword.value for keyword in default.keywords)]
    return any(
        isinstance(dependency, (ast.Name, ast.Attribute))
        and _call_name(dependency) == "get_gallery_provider"
        for dependency in dependencies
    )


def _untyped_provider_dependencies(root: Path) -> int:
    routes_path = root / "pandora_daemon" / "routes"
    if not routes_path.is_dir():
        return 0
    violations = 0
    for path in sorted(routes_path.glob("*.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path.relative_to(root)),
        )
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            positional = [*node.args.posonlyargs, *node.args.args]
            positional_defaults = [None] * (
                len(positional) - len(node.args.defaults)
            ) + list(node.args.defaults)
            arguments = [
                *zip(positional, positional_defaults, strict=True),
                *zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True),
            ]
            for argument, default in arguments:
                if not _is_provider_dependency(default):
                    continue
                annotation = _normalized(_annotation_text(argument.annotation))
                violations += int(not annotation.endswith("galleryprovider"))
    return violations


def _top_level_provider_packages(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(
        1
        for path in root.iterdir()
        if path.is_dir()
        and not path.name.startswith(".")
        and (_contains_provider_name(path.name) or path.name.endswith("_api"))
    )


def _packaging_provider_leaks(root: Path) -> int:
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        return 0
    with pyproject_path.open("rb") as file:
        config = tomllib.load(file)
    hatch = config.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {})
    wheel_packages = hatch.get("wheel", {}).get("packages", [])
    sdist_includes = hatch.get("sdist", {}).get("include", [])
    entries = [*wheel_packages, *sdist_includes]
    return sum(
        1
        for entry in entries
        if isinstance(entry, str)
        and (_contains_provider_name(entry) or Path(entry.lstrip("/")).parts[0].endswith("_api"))
    )


def _route_module_naming_violations(root: Path) -> int:
    routes = root / "pandora_daemon" / "routes"
    if not routes.is_dir():
        return 0
    return sum(
        1
        for path in routes.glob("*_routes.py")
        if path.is_file() and path.name != "__init__.py"
    )


def _product_metadata_violations(root: Path, path_violations: int) -> int:
    violations = path_violations
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.is_file():
        with pyproject_path.open("rb") as file:
            description = tomllib.load(file).get("project", {}).get("description", "")
        if isinstance(description, str) and _contains_provider_name(description):
            violations += 1

    readme_path = root / "README.md"
    if readme_path.is_file():
        introduction: list[str] = []
        for line in readme_path.read_text(encoding="utf-8").splitlines()[1:]:
            if line.startswith("## "):
                break
            introduction.append(line)
        if _contains_provider_name("\n".join(introduction)):
            violations += 1
    return violations


def _architecture_doc_contradictions(root: Path) -> int:
    path = root / "docs" / "architecture" / "system-overview.md"
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    chinese = re.findall(r"不追求[:：]?[^。]{0,300}(?:多站点|多平台)[^。]{0,80}", text)
    english = re.findall(
        r"(?:does not|doesn't|not)\s+pursue[^.]{0,200}(?:multi[- ]site|multi[- ]platform)",
        text,
        flags=re.IGNORECASE,
    )
    return len(chinese) + len(english)


def collect_static_metrics(root: Path) -> dict[str, int]:
    """Measure provider coupling and naming structure without executing production code."""
    root = Path(root)
    python_counts, has_contract, has_registry, product_path_violations = (
        _collect_python_metrics(root)
    )
    metrics = {
        **python_counts,
        "uncontracted_provider_calls": _uncontracted_provider_calls(root),
        "adapter_surface_leaks": _adapter_surface_leaks(root),
        "untyped_provider_dependencies": _untyped_provider_dependencies(root),
        "missing_provider_contract": int(not has_contract),
        "missing_provider_registry": int(not has_registry),
        "top_level_provider_packages": _top_level_provider_packages(root),
        "packaging_provider_leaks": _packaging_provider_leaks(root),
        "route_module_naming_violations": _route_module_naming_violations(root),
        "product_naming_violations": _product_metadata_violations(
            root, product_path_violations
        ),
        "architecture_doc_contradictions": _architecture_doc_contradictions(root),
    }
    if tuple(metrics) != _STATIC_METRIC_KEYS:
        raise RuntimeError("Static architecture metric contract changed")
    return metrics
