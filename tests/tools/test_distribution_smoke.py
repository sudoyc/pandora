from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

import scripts.distribution_smoke as distribution_smoke
from scripts.distribution_smoke import (
    SmokeError,
    _install_command,
    _validate_lifecycle_versions,
    _validate_probes,
    _wheel_version,
)


def _write_wheel(path: Path, version: str, *, name: str = "pandora") -> None:
    dist_info = f"{name}-{version}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{dist_info}/METADATA",
            "Metadata-Version: 2.4\n"
            f"Name: {name}\n"
            f"Version: {version}\n",
        )


def test_wheel_version_reads_pandora_metadata(tmp_path):
    wheel = tmp_path / "pandora-1.2.3-py3-none-any.whl"
    _write_wheel(wheel, "1.2.3")

    assert _wheel_version(wheel) == "1.2.3"

    wrong_project = tmp_path / "other-1.2.3-py3-none-any.whl"
    _write_wheel(wrong_project, "1.2.3", name="other")
    with pytest.raises(SmokeError, match="Pandora wheel"):
        _wheel_version(wrong_project)


@pytest.mark.parametrize(
    ("previous", "candidate"),
    [("1.2.3", "1.2.3"), ("1.2.4", "1.2.3"), ("1.2.3", "1.2.3rc1")],
)
def test_lifecycle_requires_a_strict_version_upgrade(previous, candidate):
    with pytest.raises(SmokeError, match="newer"):
        _validate_lifecycle_versions(previous, candidate)

    _validate_lifecycle_versions("1.2.3rc1", "1.2.3")
    _validate_lifecycle_versions("1.2.3", "1.3.0")


def test_install_command_marks_upgrade_and_rollback_as_reinstalls(tmp_path):
    python = tmp_path / "venv" / "bin" / "python"
    wheel = tmp_path / "pandora-1.2.3-py3-none-any.whl"

    assert _install_command("uv", python, wheel, reinstall=False) == [
        "uv", "pip", "install", "--python", str(python), "--link-mode", "copy", str(wheel),
    ]
    assert _install_command("uv", python, wheel, reinstall=True) == [
        "uv", "pip", "install", "--python", str(python), "--link-mode", "copy",
        "--reinstall", str(wheel),
    ]


def test_probe_validation_requires_isolated_no_credentials_result():
    results = {
        "health": (0, {
            "ok": True,
            "version": "1.2.3",
            "contract_version": "1",
            "service": "pandora-daemon",
            "auth_configured": False,
        }),
        "config": (0, {"server": {"host": "127.0.0.1", "port": 43123}}),
        "readiness": (1, {
            "ready": False,
            "auth_configured": False,
            "session": "not_configured",
            "checks": {
                "homepage": "not_checked",
                "search": "not_checked",
                "popular": "not_checked",
                "home": "not_checked",
            },
        }),
        "status": (0, {"tasks": []}),
    }

    assert _validate_probes(results, expected_version="1.2.3", expected_port=43123) == "1"

    results["readiness"] = (0, {"ready": True, "auth_configured": True})
    with pytest.raises(SmokeError, match="readiness"):
        _validate_probes(results, expected_version="1.2.3", expected_port=43123)


@pytest.mark.parametrize(
    ("error", "message", "recovered"),
    [
        (
            SmokeError(
                "candidate validation failed and automatic rollback passed",
                recovered=True,
            ),
            "candidate validation failed and automatic rollback passed",
            True,
        ),
        (
            OSError("private detail from a temporary path"),
            "unexpected distribution smoke failure",
            False,
        ),
    ],
)
def test_main_reports_failures_as_sanitized_json(
    monkeypatch,
    capsys,
    error,
    message,
    recovered,
):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(distribution_smoke, "run_smoke", fail)

    assert distribution_smoke.main(
        [
            "--previous-wheel", "previous.whl",
            "--candidate-wheel", "candidate.whl",
        ]
    ) == 1
    output = capsys.readouterr()
    payload = json.loads(output.out)

    assert payload == {
        "ok": False,
        "error": {"code": "distribution_smoke_failed", "message": message},
        "automatic_rollback_recovered": recovered,
    }
    assert output.err == ""
    assert "private detail" not in output.out
