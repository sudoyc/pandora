import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import scripts.check as unified_check
from scripts.check import CHECK_GROUPS, CHECKS, run_checks
from scripts.repo_checks import check_agent_schemas, check_markdown_links


ROOT = Path(__file__).resolve().parents[2]


def test_markdown_links_accept_files_anchors_and_external_urls(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Install Guide\n", encoding="utf-8")
    (tmp_path / "docs" / "guide(advanced).md").write_text(
        "# Advanced Guide\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "image.png").write_bytes(b"fixture")
    (tmp_path / "README.md").write_text(
        "[Guide](docs/guide.md#install-guide)\n"
        "[Advanced][advanced]\n"
        "[advanced]: <docs/guide(advanced).md#advanced-guide>\n"
        "![Image](docs/image.png)\n"
        "[Website](https://example.test/docs)\n"
        "```md\n[Ignored example](missing.md)\n```\n",
        encoding="utf-8",
    )

    errors = check_markdown_links(
        tmp_path,
        [Path("README.md"), Path("docs/guide.md"), Path("docs/guide(advanced).md")],
    )

    assert errors == []


def test_markdown_links_report_missing_file_and_anchor(tmp_path):
    (tmp_path / "guide.md").write_text("# Existing\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[Missing file](missing.md)\n"
        "[Missing heading](guide.md#missing)\n",
        encoding="utf-8",
    )

    errors = check_markdown_links(tmp_path, [Path("README.md"), Path("guide.md")])

    assert any("missing.md" in error for error in errors)
    assert any("guide.md#missing" in error for error in errors)


def test_agent_schema_check_reports_invalid_schema(tmp_path):
    schema_path = Path("docs/agent/schemas/example.schema.json")
    absolute_path = tmp_path / schema_path
    absolute_path.parent.mkdir(parents=True)
    absolute_path.write_text(
        json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "not-a-type"}),
        encoding="utf-8",
    )

    errors = check_agent_schemas(tmp_path, [schema_path])

    assert len(errors) == 1
    assert str(schema_path) in errors[0]
    assert "invalid JSON Schema" in errors[0]


def test_current_repository_markdown_and_agent_schemas_pass():
    assert check_markdown_links(ROOT) == []
    assert check_agent_schemas(ROOT) == []


def test_unified_check_plan_covers_required_stages():
    plan = dict(CHECKS)

    assert set(plan) == {
        "Python lock",
        "Release metadata",
        "Web lock and install",
        "Markdown links and Agent schemas",
        "Python tests",
        "Web unit and component tests",
        "Web browser tests",
        "Web lint",
        "Web build",
        "Git whitespace",
    }
    assert plan["Python lock"] == ("uv", "lock", "--check")
    assert plan["Release metadata"][-2:] == ("scripts/release.py", "check")
    assert plan["Web lock and install"] == ("npm", "--prefix", "pandora-web", "ci")
    assert plan["Markdown links and Agent schemas"][-1] == "scripts.repo_checks"
    assert plan["Python tests"][-3:] == ("-m", "pytest", "-q")
    assert plan["Web unit and component tests"][-2:] == ("run", "test:unit")
    assert plan["Web browser tests"][-2:] == ("run", "test:browser")
    assert plan["Web lint"][-2:] == ("run", "lint")
    assert plan["Web build"][-2:] == ("run", "build")
    assert plan["Git whitespace"] == ("git", "diff", "--check")


def test_unified_check_groups_partition_required_stages():
    assert tuple(CHECK_GROUPS) == ("repository", "python", "web")
    assert [label for label, _ in CHECK_GROUPS["repository"]] == [
        "Python lock",
        "Release metadata",
        "Markdown links and Agent schemas",
        "Git whitespace",
    ]
    assert [label for label, _ in CHECK_GROUPS["python"]] == ["Python tests"]
    assert [label for label, _ in CHECK_GROUPS["web"]] == [
        "Web lock and install",
        "Web unit and component tests",
        "Web browser tests",
        "Web lint",
        "Web build",
    ]

    grouped_checks = [check for checks in CHECK_GROUPS.values() for check in checks]
    assert len(grouped_checks) == len(CHECKS)
    assert set(grouped_checks) == set(CHECKS)


def test_web_test_scripts_and_browser_config_exist():
    package = json.loads((ROOT / "pandora-web" / "package.json").read_text())

    assert package["scripts"]["test:unit"] == "vitest run"
    assert package["scripts"]["test:browser"] == "playwright test"
    assert (ROOT / "pandora-web" / "vitest.config.ts").is_file()
    assert (ROOT / "pandora-web" / "playwright.config.ts").is_file()


def test_unified_check_group_runs_only_selected_stages(monkeypatch):
    selected = []

    def fake_run_checks(checks):
        selected.extend(checks)
        return 0

    monkeypatch.setattr(unified_check, "run_checks", fake_run_checks)

    assert unified_check.main(["--group", "python"]) == 0
    assert selected == list(CHECK_GROUPS["python"])


def test_unified_check_rejects_unknown_group():
    with pytest.raises(SystemExit) as exc_info:
        unified_check.main(["--group", "unknown"])

    assert exc_info.value.code == 2


def test_ci_workflow_runs_fixture_only_unified_groups():
    workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)

    assert workflow["on"]["push"]["branches"] == ["main"]
    assert "pull_request" in workflow["on"]
    assert workflow["permissions"] == {"contents": "read"}

    jobs = workflow["jobs"]
    assert set(jobs) == {"repository", "python", "web"}
    for group, job in jobs.items():
        commands = [step.get("run") for step in job["steps"]]
        assert f"uv run --frozen python scripts/check.py --group {group}" in commands
        assert "environment" not in job
        uv_step = next(
            step for step in job["steps"] if step.get("uses") == "astral-sh/setup-uv@v9.0.0"
        )
        assert uv_step["with"]["cache-suffix"] == "${{ github.job }}"

    action_references = {
        step["uses"]
        for job in jobs.values()
        for step in job["steps"]
        if "uses" in step
    }
    assert action_references == {
        "actions/checkout@v7.0.1",
        "actions/setup-node@v7.0.0",
        "actions/setup-python@v7.0.0",
        "astral-sh/setup-uv@v9.0.0",
    }

    forbidden_references = (
        "secrets.",
        "igneous",
        "ipb_member_id",
        "ipb_pass_hash",
        "exhentai.org",
        "e-hentai.org",
    )
    assert not any(reference in workflow_text.lower() for reference in forbidden_references)


def test_unified_check_stops_at_named_failure(capsys, tmp_path):
    calls = []

    def runner(command, cwd):
        calls.append(tuple(command))
        return SimpleNamespace(returncode=1 if command[0] == "fail" else 0)

    checks = (
        ("First", ("pass",)),
        ("Target stage", ("fail",)),
        ("Never reached", ("pass",)),
    )

    result = run_checks(checks, runner=runner, root=tmp_path)

    assert result == 1
    assert calls == [("pass",), ("fail",)]
    assert "[FAIL] Target stage" in capsys.readouterr().err
