from __future__ import annotations

import argparse
import configparser
import hashlib
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:rc\d+)?$")
CHANGELOG_DATE_PATTERN = r"\d{4}-\d{2}-\d{2}"
SDIST_ROOT_FILES = {".gitignore", "CHANGELOG.md", "PKG-INFO", "README.md", "pyproject.toml"}
SOURCE_PACKAGES = {"pandora_daemon"}
FORBIDDEN_PATH_PARTS = {"__pycache__", "dist", "downloads", "node_modules"}
PRIVATE_FILE_NAMES = {".env", "cookie.txt", "credentials.txt", "downloads.json"}
REQUIRED_PYTHON = ">=3.12"
CONSOLE_SCRIPTS = {
    "pandora": "pandora_daemon.cli:main",
    "pandora-daemon": "pandora_daemon.__main__:main",
}


def project_version(root: Path = ROOT) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise ValueError("pyproject.toml project.version must use X.Y.Z or X.Y.ZrcN form")
    return version


def expected_tag(version: str) -> str:
    return f"v{version}"


def check_release_metadata(
    root: Path = ROOT,
    *,
    proposed_tag: str | None = None,
) -> list[str]:
    errors: list[str] = []
    try:
        version = project_version(root)
    except (KeyError, OSError, tomllib.TOMLDecodeError, ValueError) as exc:
        return [f"pyproject.toml: {exc}"]

    try:
        lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
        editable = [
            package
            for package in lock.get("package", [])
            if package.get("name") == "pandora"
            and package.get("source", {}).get("editable") == "."
        ]
        if len(editable) != 1:
            errors.append("uv.lock must contain exactly one editable pandora package")
        elif editable[0].get("version") != version:
            errors.append(
                f"uv.lock pandora version {editable[0].get('version')!r} does not match {version!r}"
            )
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"uv.lock: {exc}")

    try:
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        heading = re.compile(
            rf"^## \[{re.escape(version)}\] - {CHANGELOG_DATE_PATTERN}$",
            re.MULTILINE,
        )
        if not heading.search(changelog):
            errors.append(f"CHANGELOG.md must contain a dated [{version}] release heading")
    except OSError as exc:
        errors.append(f"CHANGELOG.md: {exc}")

    if proposed_tag is not None and proposed_tag != expected_tag(version):
        errors.append(
            f"proposed tag {proposed_tag!r} does not match expected tag {expected_tag(version)!r}"
        )
    return errors


def _metadata_errors(content: bytes, version: str, artifact: str) -> list[str]:
    metadata = BytesParser(policy=policy.default).parsebytes(content)
    errors = []
    if metadata.get("Name") != "pandora":
        errors.append(f"{artifact} metadata name must be 'pandora'")
    if metadata.get("Version") != version:
        errors.append(
            f"{artifact} metadata version {metadata.get('Version')!r} does not match {version!r}"
        )
    if metadata.get("Requires-Python") != REQUIRED_PYTHON:
        errors.append(
            f"{artifact} Requires-Python {metadata.get('Requires-Python')!r} "
            f"does not match {REQUIRED_PYTHON!r}"
        )
    return errors


def _entry_point_errors(content: bytes) -> list[str]:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(content.decode("utf-8"))
        scripts = dict(parser.items("console_scripts"))
    except (configparser.Error, KeyError, UnicodeDecodeError) as exc:
        return [f"wheel console scripts could not be read: {exc}"]
    if scripts != CONSOLE_SCRIPTS:
        return [f"wheel console scripts must be {CONSOLE_SCRIPTS!r}; found {scripts!r}"]
    return []


def _is_forbidden_path(parts: tuple[str, ...]) -> bool:
    return bool(FORBIDDEN_PATH_PARTS.intersection(parts)) or (
        bool(parts) and parts[-1].lower() in PRIVATE_FILE_NAMES
    )


def _wheel_errors(path: Path, version: str) -> list[str]:
    errors: list[str] = []
    dist_info = f"pandora-{version}.dist-info"
    metadata_path = f"{dist_info}/METADATA"
    entry_points_path = f"{dist_info}/entry_points.txt"
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            for name in names:
                parts = PurePosixPath(name).parts
                if (
                    not parts
                    or PurePosixPath(name).is_absolute()
                    or ".." in parts
                    or parts[0] not in SOURCE_PACKAGES | {dist_info}
                ):
                    errors.append(f"wheel contains unexpected path: {name}")
                if _is_forbidden_path(parts) or name.endswith((".pyc", ".pyo")):
                    errors.append(f"wheel contains forbidden path: {name}")
            for required in (
                "pandora_daemon/providers/exhentai/upstream/__init__.py",
                "pandora_daemon/__init__.py",
                metadata_path,
                entry_points_path,
            ):
                if required not in names:
                    errors.append(f"wheel is missing required path: {required}")
            if metadata_path in names:
                errors.extend(_metadata_errors(archive.read(metadata_path), version, "wheel"))
            if entry_points_path in names:
                errors.extend(_entry_point_errors(archive.read(entry_points_path)))
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"wheel could not be read: {exc}")
    return errors


def _sdist_errors(path: Path, version: str) -> list[str]:
    errors: list[str] = []
    root_name = f"pandora-{version}"
    metadata_path = f"{root_name}/PKG-INFO"
    names: set[str] = set()
    try:
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                name = member.name.rstrip("/")
                names.add(name)
                parts = PurePosixPath(name).parts
                if (
                    not parts
                    or PurePosixPath(name).is_absolute()
                    or parts[0] != root_name
                    or ".." in parts
                ):
                    errors.append(f"sdist contains invalid path: {member.name}")
                    continue
                relative = parts[1:]
                if relative:
                    allowed = relative[0] in SOURCE_PACKAGES or (
                        len(relative) == 1 and relative[0] in SDIST_ROOT_FILES
                    )
                    if not allowed:
                        errors.append(f"sdist contains unexpected path: {member.name}")
                    if _is_forbidden_path(relative) or name.endswith((".pyc", ".pyo")):
                        errors.append(f"sdist contains forbidden path: {member.name}")
                if not member.isfile() and not member.isdir():
                    errors.append(f"sdist contains unsupported member type: {member.name}")

            for required in (
                f"{root_name}/README.md",
                f"{root_name}/CHANGELOG.md",
                f"{root_name}/pyproject.toml",
                f"{root_name}/pandora_daemon/providers/exhentai/upstream/__init__.py",
                f"{root_name}/pandora_daemon/__init__.py",
                metadata_path,
            ):
                if required not in names:
                    errors.append(f"sdist is missing required path: {required}")
            if metadata_path in names:
                member = archive.getmember(metadata_path)
                metadata_file = archive.extractfile(member)
                if metadata_file is None:
                    errors.append("sdist PKG-INFO is not a regular file")
                else:
                    errors.extend(_metadata_errors(metadata_file.read(), version, "sdist"))
    except (OSError, tarfile.TarError) as exc:
        errors.append(f"sdist could not be read: {exc}")
    return errors


def verify_artifacts(dist_dir: Path, version: str) -> list[str]:
    expected_wheel = dist_dir / f"pandora-{version}-py3-none-any.whl"
    expected_sdist = dist_dir / f"pandora-{version}.tar.gz"
    expected = {expected_wheel.name, expected_sdist.name}
    allowed = expected | {".gitignore"}
    try:
        actual = {path.name for path in dist_dir.iterdir()}
    except OSError as exc:
        return [f"artifact directory: {exc}"]

    errors = []
    if not expected.issubset(actual) or not actual.issubset(allowed):
        errors.append(
            f"artifact directory must contain only {sorted(expected)!r} and the optional uv marker; "
            f"found {sorted(actual)!r}"
        )
    if expected_wheel.is_file():
        errors.extend(_wheel_errors(expected_wheel, version))
    if expected_sdist.is_file():
        errors.extend(_sdist_errors(expected_sdist, version))
    return errors


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"command exited {result.returncode}: {' '.join(command)}")


def _smoke_install(wheel: Path, version: str, python_version: str) -> None:
    with tempfile.TemporaryDirectory(prefix="pandora-release-smoke-") as raw_temp_dir:
        temp_dir = Path(raw_temp_dir)
        venv = temp_dir / "venv"
        _run(["uv", "venv", "--python", python_version, str(venv)], cwd=temp_dir)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        pandora = venv / ("Scripts/pandora.exe" if os.name == "nt" else "bin/pandora")
        _run(
            [
                "uv",
                "pip",
                "install",
                "--link-mode",
                "copy",
                "--python",
                str(python),
                str(wheel.resolve()),
            ],
            cwd=temp_dir,
        )
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        smoke = (
            "from importlib.metadata import version; "
            "import pandora_daemon.providers.exhentai.upstream, pandora_daemon; "
            f"assert version('pandora') == {version!r}"
        )
        _run([str(python), "-c", smoke], cwd=temp_dir, env=env)
        _run([str(pandora), "--help"], cwd=temp_dir, env=env)


def _print_checksums(dist_dir: Path) -> None:
    for path in sorted(dist_dir.iterdir()):
        if not path.is_file() or not path.name.endswith((".whl", ".tar.gz")):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"sha256:{digest}  {path.name}")


def build_candidate(
    out_dir: Path,
    *,
    proposed_tag: str,
    python_version: str = "3.12",
    root: Path = ROOT,
) -> None:
    errors = check_release_metadata(root, proposed_tag=proposed_tag)
    if errors:
        raise ValueError("; ".join(errors))
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError(f"candidate output directory is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    version = project_version(root)
    _run(["uv", "build", "--out-dir", str(out_dir.resolve())], cwd=root)
    errors = verify_artifacts(out_dir, version)
    if errors:
        raise ValueError("; ".join(errors))
    _smoke_install(out_dir / f"pandora-{version}-py3-none-any.whl", version, python_version)
    _print_checksums(out_dir)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and build Pandora release candidates")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="validate version metadata")
    check_parser.add_argument("--tag", help="proposed release tag to validate")

    verify_parser = subparsers.add_parser("verify", help="verify existing artifacts")
    verify_parser.add_argument("--dist-dir", type=Path, required=True)

    candidate_parser = subparsers.add_parser("candidate", help="build and install-smoke an RC")
    candidate_parser.add_argument("--out-dir", type=Path, required=True)
    candidate_parser.add_argument("--tag", required=True, help="proposed tag; no tag is created")
    candidate_parser.add_argument("--python", default="3.12", help="Python for install smoke")

    args = parser.parse_args(argv)
    try:
        version = project_version()
        if args.command == "check":
            errors = check_release_metadata(proposed_tag=args.tag)
        elif args.command == "verify":
            errors = verify_artifacts(args.dist_dir, version)
        else:
            build_candidate(
                args.out_dir,
                proposed_tag=args.tag,
                python_version=args.python,
            )
            errors = []
    except (OSError, RuntimeError, ValueError) as exc:
        errors = [str(exc)]

    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    print(f"[PASS] Pandora release metadata/artifacts match version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
