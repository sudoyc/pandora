from __future__ import annotations

import json
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote, urlsplit

from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for
from markdown_it import MarkdownIt


ROOT = Path(__file__).resolve().parents[1]
_MARKDOWN = MarkdownIt("commonmark")
_HTML_ANCHOR = re.compile(r"\b(?:id|name)=[\"']([^\"']+)[\"']", re.IGNORECASE)


def _tracked_paths(root: Path, pathspec: str) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", pathspec],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [Path(value) for value in result.stdout.decode().split("\0") if value]


def _slugify_heading(heading: str) -> str:
    heading = re.sub(r"<[^>]+>", "", heading)
    heading = heading.strip().lower()
    characters = []
    for character in heading:
        category = unicodedata.category(character)
        if character.isspace():
            characters.append("-")
        elif character in {"-", "_"} or category[0] in {"L", "M", "N"}:
            characters.append(character)
    return re.sub(r"-+", "-", "".join(characters)).strip("-")


def _markdown_data(path: Path) -> tuple[list[tuple[int, str]], set[str]]:
    tokens = _MARKDOWN.parse(path.read_text(encoding="utf-8"))
    links = []
    anchors = set()
    counts: dict[str, int] = {}
    for index, token in enumerate(tokens):
        if token.type in {"html_block", "html_inline"}:
            anchors.update(anchor.lower() for anchor in _HTML_ANCHOR.findall(token.content))

        if token.type == "inline":
            line_number = token.map[0] + 1 if token.map else 1
            for child in token.children or []:
                if child.type == "link_open":
                    target = child.attrGet("href")
                    if target is not None:
                        links.append((line_number, target))
                elif child.type == "image":
                    target = child.attrGet("src")
                    if target is not None:
                        links.append((line_number, target))
                elif child.type == "html_inline":
                    anchors.update(
                        anchor.lower() for anchor in _HTML_ANCHOR.findall(child.content)
                    )

        if token.type == "heading_open" and index + 1 < len(tokens):
            inline = tokens[index + 1]
            heading = "".join(child.content for child in inline.children or [])
            base = _slugify_heading(heading)
            count = counts.get(base, 0)
            counts[base] = count + 1
            anchors.add(base if count == 0 else f"{base}-{count}")
    return links, anchors


def check_markdown_links(
    root: Path = ROOT,
    markdown_files: Iterable[Path] | None = None,
) -> list[str]:
    files = list(markdown_files) if markdown_files is not None else _tracked_paths(root, "*.md")
    errors = []
    anchor_cache: dict[Path, set[str]] = {}

    for relative_source in files:
        source = root / relative_source
        links, _ = _markdown_data(source)
        for line_number, raw_target in links:
            parsed = urlsplit(raw_target)
            if parsed.scheme or raw_target.startswith("//"):
                continue

            decoded_path = unquote(parsed.path)
            if decoded_path.startswith("/"):
                target = root / decoded_path.lstrip("/")
            elif decoded_path:
                target = source.parent / decoded_path
            else:
                target = source
            target = target.resolve()

            try:
                relative_target = target.relative_to(root.resolve())
            except ValueError:
                errors.append(
                    f"{relative_source}:{line_number}: local link escapes repository: {raw_target}"
                )
                continue

            if not target.exists():
                errors.append(
                    f"{relative_source}:{line_number}: missing local link: {raw_target}"
                )
                continue

            fragment = unquote(parsed.fragment).lower()
            if fragment and target.suffix.lower() == ".md":
                anchors = anchor_cache.setdefault(target, _markdown_data(target)[1])
                if fragment not in anchors:
                    errors.append(
                        f"{relative_source}:{line_number}: missing Markdown anchor: "
                        f"{relative_target}#{parsed.fragment}"
                    )
    return errors


def check_agent_schemas(
    root: Path = ROOT,
    schema_files: Iterable[Path] | None = None,
) -> list[str]:
    files = (
        list(schema_files)
        if schema_files is not None
        else _tracked_paths(root, "docs/agent/schemas/*.json")
    )
    errors = []
    for relative_path in files:
        path = root / relative_path
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            validator_for(schema).check_schema(schema)
        except json.JSONDecodeError as exc:
            errors.append(f"{relative_path}: invalid JSON: {exc}")
        except SchemaError as exc:
            errors.append(f"{relative_path}: invalid JSON Schema: {exc.message}")
    return errors


def main() -> int:
    errors = check_markdown_links() + check_agent_schemas()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Tracked Markdown links and Agent schemas are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
