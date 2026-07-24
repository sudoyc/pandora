import json
from pathlib import Path
from types import SimpleNamespace

from scripts.check import CHECKS, run_checks
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
        "Web lock and install",
        "Markdown links and Agent schemas",
        "Python tests",
        "Web lint",
        "Web build",
        "Git whitespace",
    }
    assert plan["Python lock"] == ("uv", "lock", "--check")
    assert plan["Web lock and install"] == ("npm", "--prefix", "pandora-web", "ci")
    assert plan["Markdown links and Agent schemas"][-1] == "scripts.repo_checks"
    assert plan["Python tests"][-3:] == ("-m", "pytest", "-q")
    assert plan["Web lint"][-2:] == ("run", "lint")
    assert plan["Web build"][-2:] == ("run", "build")
    assert plan["Git whitespace"] == ("git", "diff", "--check")


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
