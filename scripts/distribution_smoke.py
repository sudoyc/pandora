from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Sequence


VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:rc(\d+))?$")
READINESS_WITHOUT_CREDENTIALS = {
    "ready": False,
    "auth_configured": False,
    "session": "not_configured",
    "checks": {
        "homepage": "not_checked",
        "search": "not_checked",
        "popular": "not_checked",
        "home": "not_checked",
    },
}
LIFECYCLE_PHASES = [
    "install_previous",
    "probe_previous",
    "upgrade_candidate",
    "probe_candidate",
    "rollback_previous",
    "probe_rollback",
]


class SmokeError(RuntimeError):
    def __init__(self, message: str, *, recovered: bool = False) -> None:
        super().__init__(message)
        self.recovered = recovered


def _wheel_version(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_paths = [
                name for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_paths) != 1:
                raise SmokeError("Pandora wheel must contain exactly one metadata file")
            metadata = BytesParser(policy=policy.default).parsebytes(
                archive.read(metadata_paths[0])
            )
    except (OSError, zipfile.BadZipFile) as exc:
        raise SmokeError("Pandora wheel could not be read") from exc

    if metadata.get("Name") != "pandora":
        raise SmokeError("Pandora wheel metadata name must be 'pandora'")
    version = metadata.get("Version")
    if not isinstance(version, str) or VERSION_PATTERN.fullmatch(version) is None:
        raise SmokeError("Pandora wheel version must use X.Y.Z or X.Y.ZrcN")
    return version


def _version_key(version: str) -> tuple[int, int, int, int, int]:
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise SmokeError("Pandora wheel version must use X.Y.Z or X.Y.ZrcN")
    major, minor, patch, rc = match.groups()
    return (int(major), int(minor), int(patch), 1 if rc is None else 0, int(rc or 0))


def _validate_lifecycle_versions(previous: str, candidate: str) -> None:
    if _version_key(candidate) <= _version_key(previous):
        raise SmokeError("candidate wheel version must be newer than previous wheel version")


def _install_command(
    uv: str,
    python: Path,
    wheel: Path,
    *,
    reinstall: bool,
) -> list[str]:
    command = [
        uv,
        "pip",
        "install",
        "--python",
        str(python),
        "--link-mode",
        "copy",
    ]
    if reinstall:
        command.append("--reinstall")
    command.append(str(wheel))
    return command


def _validate_probes(
    results: dict[str, tuple[int, dict[str, Any]]],
    *,
    expected_version: str,
    expected_port: int,
) -> str:
    health_exit, health = results.get("health", (-1, {}))
    if (
        health_exit != 0
        or health.get("ok") is not True
        or health.get("service") != "pandora-daemon"
        or health.get("version") != expected_version
        or health.get("auth_configured") is not False
        or not isinstance(health.get("contract_version"), str)
    ):
        raise SmokeError("health probe did not match the installed isolated daemon")

    config_exit, config = results.get("config", (-1, {}))
    if (
        config_exit != 0
        or "credentials" in config
        or config.get("server") != {"host": "127.0.0.1", "port": expected_port}
    ):
        raise SmokeError("config probe exposed state or used the wrong isolated endpoint")

    readiness_exit, readiness = results.get("readiness", (-1, {}))
    if readiness_exit != 1 or readiness != READINESS_WITHOUT_CREDENTIALS:
        raise SmokeError("readiness probe did not preserve the no-credentials result")

    status_exit, status = results.get("status", (-1, {}))
    if status_exit != 0 or status != {"tasks": []}:
        raise SmokeError("status probe did not use an empty isolated download state")
    return health["contract_version"]


def _validate_isolated_state(config_path: Path, expected_config: bytes) -> None:
    if config_path.read_bytes() != expected_config:
        raise SmokeError("isolated config changed across the lifecycle")
    if not (config_path.parent / "pandora.db").is_file():
        raise SmokeError("isolated daemon database was not created")


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    phase: str,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise SmokeError(f"{phase} command could not start") from exc
    if result.returncode != 0:
        raise SmokeError(f"{phase} failed with exit code {result.returncode}")
    return result


def _venv_executable(venv: Path, name: str) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / f"{name}.exe"
    return venv / "bin" / name


def _free_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def _write_isolated_state(root: Path, port: int) -> tuple[dict[str, str], Path]:
    home = root / "home"
    config_dir = home / ".config" / "pandora"
    cache_dir = home / ".cache" / "pandora"
    config_dir.mkdir(parents=True)
    (cache_dir / "tags").mkdir(parents=True)
    downloads = root / "downloads"
    images = cache_dir / "images"
    config_path = config_dir / "config.toml"
    config_path.write_text(
        "[credentials]\n"
        'igneous = ""\n'
        'ipb_member_id = ""\n'
        'ipb_pass_hash = ""\n\n'
        "[server]\n"
        'host = "127.0.0.1"\n'
        f"port = {port}\n\n"
        "[download]\n"
        f"path = {json.dumps(str(downloads))}\n\n"
        "[cache]\n"
        f"image_dir = {json.dumps(str(images))}\n"
        "eviction_interval_seconds = 60\n\n"
        "[network]\n"
        "timeout = 1\n",
        encoding="utf-8",
    )
    (cache_dir / "tags" / "db.text.json").write_text(
        json.dumps({"repo": "fixture", "head": {"sha": "fixture"}, "data": []}),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "XDG_CACHE_HOME": str(root / "xdg-cache"),
        "XDG_CONFIG_HOME": str(root / "xdg-config"),
        "XDG_DATA_HOME": str(root / "xdg-data"),
        "PYTHONNOUSERSITE": "1",
        "UV_CACHE_DIR": str(root / "uv-cache"),
    })
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    return env, config_path


def _installed_version(
    python: Path,
    *,
    cwd: Path,
    env: dict[str, str],
) -> str:
    result = _run(
        [
            str(python),
            "-c",
            "from importlib.metadata import version; print(version('pandora'))",
        ],
        cwd=cwd,
        env=env,
        phase="installed version check",
    )
    return result.stdout.strip()


def _install(
    uv: str,
    python: Path,
    wheel: Path,
    expected_version: str,
    *,
    reinstall: bool,
    cwd: Path,
    env: dict[str, str],
    phase: str,
) -> None:
    _run(
        _install_command(uv, python, wheel.resolve(), reinstall=reinstall),
        cwd=cwd,
        env=env,
        phase=phase,
    )
    if _installed_version(python, cwd=cwd, env=env) != expected_version:
        raise SmokeError(f"{phase} installed an unexpected version")


def _stop_daemon(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _cli_probe(
    cli: Path,
    command: str,
    daemon_url: str,
    *,
    cwd: Path,
    env: dict[str, str],
) -> tuple[int, dict[str, Any]]:
    try:
        result = subprocess.run(
            [
                str(cli),
                command,
                "--json",
                "--daemon-url",
                daemon_url,
                "--timeout",
                "1",
            ],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise SmokeError(f"{command} probe command could not start") from exc
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"{command} probe did not return JSON") from exc
    if not isinstance(payload, dict):
        raise SmokeError(f"{command} probe did not return a JSON object")
    return result.returncode, payload


def _probe_daemon(
    daemon: Path,
    cli: Path,
    expected_version: str,
    port: int,
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
) -> str:
    try:
        process = subprocess.Popen(
            [str(daemon)],
            cwd=cwd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise SmokeError("daemon command could not start") from exc

    daemon_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise SmokeError("daemon exited before the health probe succeeded")
            try:
                exit_code, payload = _cli_probe(
                    cli, "health", daemon_url, cwd=cwd, env=env
                )
            except SmokeError:
                exit_code, payload = -1, {}
            if exit_code == 0 and payload.get("service") == "pandora-daemon":
                break
            time.sleep(0.2)
        else:
            raise SmokeError("daemon health probe timed out")

        results = {
            command: _cli_probe(cli, command, daemon_url, cwd=cwd, env=env)
            for command in ("health", "config", "readiness", "status")
        }
        return _validate_probes(
            results,
            expected_version=expected_version,
            expected_port=port,
        )
    finally:
        _stop_daemon(process)


def run_smoke(
    previous_wheel: Path,
    candidate_wheel: Path,
    *,
    python_version: str = "3.12",
    timeout: float = 20.0,
    uv: str = "uv",
) -> dict[str, Any]:
    previous_version = _wheel_version(previous_wheel)
    candidate_version = _wheel_version(candidate_wheel)
    _validate_lifecycle_versions(previous_version, candidate_version)

    with tempfile.TemporaryDirectory(prefix="pandora-distribution-smoke-") as raw_root:
        root = Path(raw_root)
        port = _free_port()
        env, config_path = _write_isolated_state(root, port)
        expected_config = config_path.read_bytes()
        venv = root / "venv"
        _run(
            [uv, "venv", "--python", python_version, str(venv)],
            cwd=root,
            env=env,
            phase="isolated environment creation",
        )
        python = _venv_executable(venv, "python")
        daemon = _venv_executable(venv, "pandora-daemon")
        cli = _venv_executable(venv, "pandora")

        _install(
            uv,
            python,
            previous_wheel,
            previous_version,
            reinstall=False,
            cwd=root,
            env=env,
            phase="previous wheel installation",
        )
        contract_version = _probe_daemon(
            daemon,
            cli,
            previous_version,
            port,
            cwd=root,
            env=env,
            timeout=timeout,
        )
        _validate_isolated_state(config_path, expected_config)

        try:
            _install(
                uv,
                python,
                candidate_wheel,
                candidate_version,
                reinstall=True,
                cwd=root,
                env=env,
                phase="candidate wheel upgrade",
            )
            candidate_contract = _probe_daemon(
                daemon,
                cli,
                candidate_version,
                port,
                cwd=root,
                env=env,
                timeout=timeout,
            )
            if candidate_contract != contract_version:
                raise SmokeError("machine contract version changed during upgrade")
            _validate_isolated_state(config_path, expected_config)
        except Exception as upgrade_error:
            try:
                _install(
                    uv,
                    python,
                    previous_wheel,
                    previous_version,
                    reinstall=True,
                    cwd=root,
                    env=env,
                    phase="automatic rollback",
                )
                rollback_contract = _probe_daemon(
                    daemon,
                    cli,
                    previous_version,
                    port,
                    cwd=root,
                    env=env,
                    timeout=timeout,
                )
                if rollback_contract != contract_version:
                    raise SmokeError("machine contract version changed after automatic rollback")
                _validate_isolated_state(config_path, expected_config)
            except Exception as rollback_error:
                raise SmokeError(
                    "candidate validation and automatic rollback both failed"
                ) from rollback_error
            raise SmokeError(
                "candidate validation failed and automatic rollback passed",
                recovered=True,
            ) from upgrade_error

        _install(
            uv,
            python,
            previous_wheel,
            previous_version,
            reinstall=True,
            cwd=root,
            env=env,
            phase="planned rollback",
        )
        rollback_contract = _probe_daemon(
            daemon,
            cli,
            previous_version,
            port,
            cwd=root,
            env=env,
            timeout=timeout,
        )
        if rollback_contract != contract_version:
            raise SmokeError("machine contract version changed after planned rollback")
        _validate_isolated_state(config_path, expected_config)

    return {
        "ok": True,
        "previous_version": previous_version,
        "candidate_version": candidate_version,
        "contract_version": contract_version,
        "phases": LIFECYCLE_PHASES,
        "readiness": "not_configured",
        "isolated_state_preserved": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test Pandora wheel install, upgrade, and rollback",
    )
    parser.add_argument("--previous-wheel", type=Path, required=True)
    parser.add_argument("--candidate-wheel", type=Path, required=True)
    parser.add_argument("--python", default="3.12")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)

    try:
        report = run_smoke(
            args.previous_wheel,
            args.candidate_wheel,
            python_version=args.python,
            timeout=args.timeout,
        )
    except SmokeError as exc:
        print(json.dumps({
            "ok": False,
            "error": {"code": "distribution_smoke_failed", "message": str(exc)},
            "automatic_rollback_recovered": exc.recovered,
        }, sort_keys=True))
        return 1
    except Exception:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "distribution_smoke_failed",
                "message": "unexpected distribution smoke failure",
            },
            "automatic_rollback_recovered": False,
        }, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
