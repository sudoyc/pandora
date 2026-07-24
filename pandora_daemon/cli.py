"""Pandora CLI — daemon client for browsing and download workflows."""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, NoReturn

import httpx
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

from pandora_daemon.config import load_config

_GALLERY_URL_RE = re.compile(r"/g/(\d+)/([0-9a-fA-F]{10})")


def parse_gallery_url(url: str) -> tuple[str, str]:
    """Extract (gid, token) from an ExHentai/E-Hentai gallery URL."""
    match = _GALLERY_URL_RE.search(url)
    if not match:
        raise ValueError(f"Invalid gallery URL: {url}")
    return match.group(1), match.group(2).lower()


def resolve_gallery_target(target: str, token: str | None = None) -> tuple[str, str]:
    """Accept either a gallery URL or a raw gid+token pair."""
    if token is not None:
        if not target.isdigit():
            raise ValueError("Gallery ID must be numeric when token is provided")
        if not token:
            raise ValueError("Gallery token is required")
        return target, token.lower()

    if target.startswith("http://") or target.startswith("https://"):
        return parse_gallery_url(target)

    raise ValueError("Gallery token is required when passing a raw gallery ID")


def build_daemon_url(host: str, port: int) -> str:
    """Build the daemon base URL from config."""
    return f"http://{host}:{port}"


def _default_config_path() -> Path:
    return Path("~/.config/pandora/config.toml").expanduser()


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _json_line(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _machine_error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _redact_sensitive_cli_output(data: Any) -> Any:
    """Remove daemon-only API identity fields from machine-facing CLI output."""
    if isinstance(data, dict):
        return {
            key: _redact_sensitive_cli_output(value)
            for key, value in data.items()
            if key not in {"api_uid", "api_key"}
        }
    if isinstance(data, list):
        return [_redact_sensitive_cli_output(item) for item in data]
    return data


def _normalize_download_pages_output(data: Any) -> Any:
    if not isinstance(data, dict) or not isinstance(data.get("page_states"), dict):
        return data
    normalized = dict(data)
    normalized["page_states"] = {
        page: "completed" if state == "done" else state
        for page, state in data["page_states"].items()
    }
    return normalized


class PandoraArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that emits JSON errors when machine output is requested."""

    _current_argv: list[str] = []

    def parse_args(self, args=None, namespace=None):
        type(self)._current_argv = list(sys.argv[1:] if args is None else args)
        return super().parse_args(args, namespace)

    def error(self, message: str) -> NoReturn:
        argv = type(self)._current_argv
        machine_mode = "--json" in argv or "--ndjson" in argv
        ndjson = "--ndjson" in argv
        if machine_mode:
            payload = _machine_error("usage_error", message)
            print(_json_line(payload) if ndjson else _json_dump(payload))
            self.exit(2)
        super().error(message)


def _load_daemon_config(config_path: Path | str | None = None):
    return load_config(_default_config_path() if config_path is None else config_path)


async def _request_json(client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> Any:
    response = await client.request(method, path, **kwargs)
    response.raise_for_status()
    if not response.content:
        return None
    return response.json()


def _emit_machine_error(code: str, message: str, *, ndjson: bool = False) -> int:
    payload = _machine_error(code, message)
    print(_json_line(payload) if ndjson else _json_dump(payload))
    return 1


def _print_machine_event(payload: dict[str, Any], *, ndjson: bool) -> None:
    print(_json_line(payload) if ndjson else _json_dump(payload), flush=True)


def _is_machine_mode(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False) or getattr(args, "ndjson", False))


def _machine_ndjson(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "ndjson", False))


async def _download_statuses(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    data = await _request_json(client, "GET", "/api/downloads")
    return list(data or [])


_DOWNLOAD_SUCCESS_EVENTS = {"download_complete"}
_DOWNLOAD_FAILURE_EVENTS = {
    "download_complete_with_errors",
    "download_error",
    "download_cancelled",
    "download_paused",
    "download_auth_failed",
}
_DOWNLOAD_TERMINAL_EVENTS = _DOWNLOAD_SUCCESS_EVENTS | _DOWNLOAD_FAILURE_EVENTS


async def _consume_download_events(messages: Any, gid: str | None = None, ndjson: bool = False) -> int:
    async for message in messages:
        event = json.loads(message)
        if gid is not None and str(event.get("gid")) != gid:
            continue
        print(json.dumps(event, ensure_ascii=False) if ndjson else _json_dump(event), flush=True)
        event_name = event.get("event")
        if event_name in _DOWNLOAD_TERMINAL_EVENTS:
            return 0 if event_name in _DOWNLOAD_SUCCESS_EVENTS else 1
    return 0


async def _watch_download_events(
    daemon_url: str,
    gid: str | None = None,
    ndjson: bool = False,
    json_output: bool = False,
) -> int:
    ws_url = daemon_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
    try:
        import websockets

        async with websockets.connect(ws_url) as ws:
            return await _consume_download_events(ws, gid=gid, ndjson=ndjson)
    except KeyboardInterrupt:
        return 130
    except ImportError:
        if ndjson:
            return _emit_machine_error("websocket_dependency_missing", "websockets not installed", ndjson=True)
        if json_output:
            return _emit_machine_error("websocket_dependency_missing", "websockets not installed")
        Console().print("[red]websockets not installed[/red]")
        return 1
    except Exception as e:
        if ndjson:
            return _emit_machine_error("websocket_error", str(e), ndjson=True)
        if json_output:
            return _emit_machine_error("websocket_error", str(e))
        Console().print(f"[red]WebSocket error: {e}[/red]")
        return 1
    return 0


async def _run_download_run(client: httpx.AsyncClient, daemon_url: str, args: argparse.Namespace) -> int:
    gid, token = resolve_gallery_target(args.target, args.token)
    ndjson = bool(getattr(args, "ndjson", False))
    json_output = bool(getattr(args, "json", False))
    ws_url = daemon_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"

    try:
        import websockets

        async with websockets.connect(ws_url) as ws:
            response = await client.post("/api/downloads", json={"gid": gid, "token": token})

            if response.status_code == 409:
                detail = response.json().get("detail", response.text)
                _print_machine_event(
                    {
                        "event": "download_already_queued",
                        "gid": gid,
                        "status": "already_queued",
                        "detail": detail,
                    },
                    ndjson=ndjson,
                )
            else:
                response.raise_for_status()
                data = response.json()
                _print_machine_event(
                    {
                        "event": "download_submitted",
                        "gid": str(data.get("gid", gid)),
                        "status": data.get("status", "queued"),
                        "title": data.get("title", gid),
                    },
                    ndjson=ndjson,
                )

            return await _consume_download_events(ws, gid=gid, ndjson=ndjson)
    except KeyboardInterrupt:
        return 130
    except ImportError:
        if ndjson:
            return _emit_machine_error("websocket_dependency_missing", "websockets not installed", ndjson=True)
        if json_output:
            return _emit_machine_error("websocket_dependency_missing", "websockets not installed")
        Console().print("[red]websockets not installed[/red]")
        return 1
    except httpx.HTTPError:
        raise
    except Exception as e:
        if ndjson:
            return _emit_machine_error("websocket_error", str(e), ndjson=True)
        if json_output:
            return _emit_machine_error("websocket_error", str(e))
        Console().print(f"[red]WebSocket error: {e}[/red]")
        return 1


async def download_command(target: str, daemon_url: str, token: str | None = None) -> int:
    """Submit a download and monitor progress via WebSocket. Returns exit code."""
    console = Console()

    try:
        gid, resolved_token = resolve_gallery_target(target, token)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    try:
        async with httpx.AsyncClient(base_url=daemon_url, timeout=5.0) as client:
            await client.get("/api/config")
    except (httpx.ConnectError, httpx.TimeoutException):
        console.print(f"[red]Cannot connect to daemon at {daemon_url}[/red]")
        console.print("[dim]Start the daemon first: uv run python -m pandora_daemon[/dim]")
        return 1

    async with httpx.AsyncClient(base_url=daemon_url, timeout=30.0) as client:
        try:
            resp = await client.post("/api/downloads", json={"gid": gid, "token": resolved_token})
        except httpx.HTTPError as e:
            console.print(f"[red]HTTP error: {e}[/red]")
            return 1

        if resp.status_code == 409:
            console.print(f"[yellow]Already queued: {resp.json().get('detail', '')}[/yellow]")
        elif resp.status_code != 200:
            console.print(f"[red]Error {resp.status_code}: {resp.text}[/red]")
            return 1
        else:
            task_info = resp.json()
            console.print(f"[green]Queued:[/green] {task_info.get('title', gid)}")

    ws_url = daemon_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
    try:
        import websockets

        async with websockets.connect(ws_url) as ws:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                current_phase = ""
                task_id = progress.add_task("Waiting...", total=0, visible=True)

                async for message in ws:
                    event = json.loads(message)
                    if str(event.get("gid")) != gid:
                        continue

                    ev_type = event.get("event", "")
                    if ev_type == "download_progress":
                        phase = event.get("phase", "")
                        page = event.get("page", 0)
                        total = event.get("total", 0)

                        if phase != current_phase:
                            if current_phase:
                                progress.update(task_id, visible=False)
                            task_id = progress.add_task(phase, total=total if total > 0 else 0)
                            current_phase = phase

                        if total > 0:
                            progress.update(task_id, description=phase, completed=page, total=total)
                        else:
                            progress.update(task_id, description=f"{phase}...")
                    elif ev_type == "download_complete":
                        progress.update(task_id, visible=False)
                        console.print(f"[bold green]Download complete:[/bold green] {event.get('path', '')}")
                        return 0
                    elif ev_type == "download_complete_with_errors":
                        progress.update(task_id, visible=False)
                        console.print(
                            f"[bold yellow]Download completed with errors:[/bold yellow] "
                            f"failed pages {event.get('failed_pages', [])}"
                        )
                        return 1
                    elif ev_type == "download_error":
                        console.print(f"[bold red]Download error:[/bold red] {event.get('error', 'unknown')}")
                        return 1
                    elif ev_type == "download_auth_failed":
                        console.print(f"[bold red]Authentication failed:[/bold red] {event.get('error', 'unknown')}")
                        return 1
                    elif ev_type == "download_paused":
                        console.print(f"[yellow]Download paused:[/yellow] {event.get('reason', 'unknown')}")
                        return 1
                    elif ev_type == "download_cancelled":
                        console.print("[yellow]Download cancelled[/yellow]")
                        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        return 130
    except ImportError:
        console.print("[yellow]websockets not installed, cannot monitor progress[/yellow]")
        console.print("[dim]Download continues in background on the daemon.[/dim]")
        return 0
    except Exception as e:
        console.print(f"\n[red]WebSocket error: {e}[/red]")
        console.print("[dim]Download continues in background on the daemon.[/dim]")
        return 1

    return 0


async def status_command(daemon_url: str) -> int:
    """Show current download queue status."""
    console = Console()

    try:
        async with httpx.AsyncClient(base_url=daemon_url, timeout=5.0) as client:
            tasks = await _download_statuses(client)
    except (httpx.ConnectError, httpx.TimeoutException):
        console.print(f"[red]Cannot connect to daemon at {daemon_url}[/red]")
        return 1
    except httpx.HTTPError as e:
        console.print(f"[red]HTTP error: {e}[/red]")
        return 1

    if not tasks:
        console.print("[dim]No downloads in queue[/dim]")
        return 0

    active = [t for t in tasks if t.get("status") in ("queued", "downloading")]
    completed = [t for t in tasks if t.get("status") == "completed"]
    partial = [t for t in tasks if t.get("status") == "completed_with_errors"]
    paused = [t for t in tasks if t.get("status") == "paused"]
    failed = [t for t in tasks if t.get("status") == "failed"]
    cancelled = [t for t in tasks if t.get("status") == "cancelled"]

    if active:
        console.print(f"[bold]Active ({len(active)}):[/bold]")
        for t in active:
            pages = f"{t.get('downloaded_pages', 0)}/{t.get('total_pages', '?')}"
            console.print(f"  [{t['status']}] {t.get('title', t['gid'])}  pages: {pages}")

    if completed:
        console.print(f"\n[bold green]Completed ({len(completed)}):[/bold green]")
        for t in completed:
            console.print(f"  {t.get('title', t['gid'])}  → {t.get('output_dir', '')}")

    if partial:
        console.print(f"\n[bold yellow]Completed with errors ({len(partial)}):[/bold yellow]")
        for t in partial:
            console.print(f"  {t.get('title', t['gid'])}  failed pages: {t.get('failed_pages', [])}")

    if paused:
        console.print(f"\n[bold yellow]Paused ({len(paused)}):[/bold yellow]")
        for t in paused:
            console.print(f"  {t.get('title', t['gid'])}  reason: {t.get('error', '?')}")

    if failed:
        console.print(f"\n[bold red]Failed ({len(failed)}):[/bold red]")
        for t in failed:
            console.print(f"  {t.get('title', t['gid'])}  error: {t.get('error', '?')}")

    if cancelled:
        console.print(f"\n[bold yellow]Cancelled ({len(cancelled)}):[/bold yellow]")
        for t in cancelled:
            console.print(f"  {t.get('title', t['gid'])}")

    return 0


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--daemon-url", default=argparse.SUPPRESS, help="Daemon base URL")
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output JSON")
    parser.add_argument("--timeout", type=float, default=argparse.SUPPRESS, help="Request timeout in seconds")


_DOWNLOAD_SUBCOMMANDS = {
    "add", "run", "list", "report", "repair", "forget", "watch",
    "cancel", "resume", "retry", "pages",
}


def _normalize_argv(argv: list[str] | None = None) -> list[str]:
    """Rewrite legacy `download <url>` / `dl <url>` into `download legacy <url>`."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[0] not in {"download", "dl"}:
        return args

    idx = 1
    options_with_values = {"--daemon-url", "--timeout"}
    while idx < len(args) and args[idx].startswith("-"):
        option = args[idx]
        idx += 1
        if option in options_with_values and idx < len(args):
            idx += 1

    if idx < len(args) and args[idx] not in _DOWNLOAD_SUBCOMMANDS:
        return [*args[:idx], "legacy", *args[idx:]]
    return args


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = PandoraArgumentParser(
        prog="pandora",
        description="Pandora CLI — ExHentai daemon client",
    )
    subparsers = parser.add_subparsers(dest="command", parser_class=PandoraArgumentParser)

    download_parser = subparsers.add_parser(
        "download",
        aliases=["dl"],
        help="Manage gallery downloads",
    )
    download_subparsers = download_parser.add_subparsers(
        dest="download_command",
        parser_class=PandoraArgumentParser,
    )

    download_add = download_subparsers.add_parser("add", help="Submit a gallery download")
    download_add.add_argument("target", help="Gallery URL or gid")
    download_add.add_argument("token", nargs="?", help="Gallery token when using gid")
    _add_common_options(download_add)

    download_run = download_subparsers.add_parser("run", help="Submit and watch a gallery download")
    download_run.add_argument("target", help="Gallery URL or gid")
    download_run.add_argument("token", nargs="?", help="Gallery token when using gid")
    download_run.add_argument("--ndjson", action="store_true", help="Emit newline-delimited JSON events")
    _add_common_options(download_run)

    download_list = download_subparsers.add_parser("list", help="List download tasks")
    _add_common_options(download_list)

    download_report = download_subparsers.add_parser("report", help="Report task and library consistency")
    _add_common_options(download_report)

    for action_name in ("repair", "forget"):
        action_parser = download_subparsers.add_parser(
            action_name,
            help=f"Preview or apply download {action_name}",
        )
        action_parser.add_argument("gid", help="Gallery ID")
        action_parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the planned state change (default: preview only)",
        )
        _add_common_options(action_parser)

    download_watch = download_subparsers.add_parser("watch", help="Watch a download via WebSocket")
    download_watch.add_argument("gid", nargs="?", help="Gallery ID to filter events")
    download_watch.add_argument("--ndjson", action="store_true", help="Emit newline-delimited JSON events")
    _add_common_options(download_watch)

    download_legacy = download_subparsers.add_parser("legacy", help=argparse.SUPPRESS)
    download_legacy.add_argument("target", help="Gallery URL or gid")
    download_legacy.add_argument("token", nargs="?", help="Gallery token when using gid")
    _add_common_options(download_legacy)

    for action_name in ("cancel", "resume", "retry", "pages"):
        action_parser = download_subparsers.add_parser(action_name, help=f"{action_name.title()} a download task")
        action_parser.add_argument("gid", help="Gallery ID")
        _add_common_options(action_parser)

    # Keep common options on the parent too, so both `download --json list` and
    # `download list --json` are accepted.
    _add_common_options(download_parser)

    status_parser = subparsers.add_parser(
        "status",
        aliases=["st"],
        help="Show download queue status",
    )
    _add_common_options(status_parser)

    health_parser = subparsers.add_parser("health", help="Check daemon health")
    _add_common_options(health_parser)

    readiness_parser = subparsers.add_parser(
        "readiness",
        help="Check authenticated upstream readiness",
    )
    _add_common_options(readiness_parser)

    config_parser = subparsers.add_parser("config", help="Show daemon public config")
    _add_common_options(config_parser)

    search_parser = subparsers.add_parser("search", help="Search galleries")
    search_parser.add_argument("keyword", help="Search keyword")
    search_parser.add_argument("--page", type=int, default=0)
    search_parser.add_argument("--category", type=int)
    search_parser.add_argument("--min-rating", type=int)
    search_parser.add_argument("--search-name", action="store_true")
    search_parser.add_argument("--search-tags", action="store_true")
    search_parser.add_argument("--search-description", action="store_true")
    search_parser.add_argument("--search-torrent", action="store_true")
    search_parser.add_argument("--search-low-power-tags", action="store_true")
    search_parser.add_argument("--disable-language-filter", action="store_true")
    search_parser.add_argument("--show-expunged", action="store_true")
    search_parser.add_argument("--min-pages", type=int)
    search_parser.add_argument("--max-pages", type=int)
    _add_common_options(search_parser)

    gallery_parser = subparsers.add_parser("gallery", help="Show gallery detail")
    gallery_parser.add_argument("target", help="Gallery URL or gid")
    gallery_parser.add_argument("token", nargs="?", help="Gallery token when using gid")
    _add_common_options(gallery_parser)

    library_parser = subparsers.add_parser("library", help="List and export downloaded galleries")
    library_subparsers = library_parser.add_subparsers(dest="library_command", parser_class=PandoraArgumentParser)
    library_list = library_subparsers.add_parser("list", help="List downloaded galleries")
    _add_common_options(library_list)
    library_export_pdf = library_subparsers.add_parser("export-pdf", help="Export a downloaded gallery to PDF")
    library_export_pdf.add_argument("gid", help="Gallery ID")
    library_export_pdf.add_argument("--password", help="Optional PDF open password")
    library_export_pdf.add_argument("--output-name", help="Optional output PDF filename")
    library_export_pdf.add_argument("--include-cover", action="store_true", help="Include cover image as the first PDF page when present")
    _add_common_options(library_export_pdf)
    _add_common_options(library_parser)

    tags_parser = subparsers.add_parser("tags", help="Tag utilities")
    tags_subparsers = tags_parser.add_subparsers(dest="tags_command", parser_class=PandoraArgumentParser)
    tags_suggest = tags_subparsers.add_parser("suggest", help="Suggest tags")
    tags_suggest.add_argument("query")
    _add_common_options(tags_suggest)
    tags_status = tags_subparsers.add_parser("status", help="Show tag database status")
    _add_common_options(tags_status)
    tags_refresh = tags_subparsers.add_parser("refresh", help="Refresh tag database")
    tags_refresh.add_argument("--force", action="store_true")
    _add_common_options(tags_refresh)
    _add_common_options(tags_parser)

    favorites_parser = subparsers.add_parser("favorites", help="Favorite gallery list")
    favorites_parser.add_argument("subcommand", nargs="?", default="list")
    _add_common_options(favorites_parser)

    popular_parser = subparsers.add_parser("popular", help="List popular galleries")
    _add_common_options(popular_parser)

    toplist_parser = subparsers.add_parser("toplist", help="List toplist galleries")
    toplist_parser.add_argument("--tl", default="15")
    _add_common_options(toplist_parser)

    watched_parser = subparsers.add_parser("watched", help="List watched-tag galleries")
    watched_parser.add_argument("--page", type=int, default=0)
    _add_common_options(watched_parser)

    return parser


def _finalize_common_option_defaults(args: argparse.Namespace) -> argparse.Namespace:
    if not hasattr(args, "daemon_url"):
        args.daemon_url = None
    if not hasattr(args, "json"):
        args.json = False
    if not hasattr(args, "timeout"):
        args.timeout = 30.0
    return args


def _resolve_daemon_url(args: argparse.Namespace) -> str:
    if args.daemon_url:
        return args.daemon_url
    config = _load_daemon_config()
    return build_daemon_url(config.server.host, config.server.port)


def _dispatch_json(payload: Any) -> int:
    print(_json_dump(payload))
    return 0


def _client_timeout(args: argparse.Namespace) -> httpx.Timeout:
    return httpx.Timeout(args.timeout)


def _resolve_command_name(command: str | None) -> str | None:
    if command in {"dl"}:
        return "download"
    if command in {"st"}:
        return "status"
    return command


def _handle_local_passthrough(args: argparse.Namespace) -> int:
    console = Console()
    if args.command == "favorites":
        console.print("[yellow]favorites list is provided by the daemon API, not the CLI yet[/yellow]")
        return 1
    if args.command == "toplist":
        console.print("[yellow]toplist is temporarily unavailable in the CLI[/yellow]")
        return 1
    if args.command == "watched":
        console.print("[yellow]watched is temporarily unavailable in the CLI[/yellow]")
        return 1
    return 1


async def _run_http_command(args: argparse.Namespace) -> int:
    _finalize_common_option_defaults(args)
    command = _resolve_command_name(args.command)
    daemon_url = _resolve_daemon_url(args)
    machine_mode = _is_machine_mode(args)
    machine_ndjson = _machine_ndjson(args)

    try:
        async with httpx.AsyncClient(base_url=daemon_url, timeout=_client_timeout(args)) as client:
            if command == "health":
                data = await _request_json(client, "GET", "/api/health")
                if args.json:
                    return _dispatch_json(data)
                Console().print(f"[green]OK[/green] {data.get('service', 'pandora-daemon')}")
                return 0

            if command == "readiness":
                data = await _request_json(client, "GET", "/api/readiness")
                if args.json:
                    _dispatch_json(data)
                elif data.get("ready") is True:
                    Console().print("[green]READY[/green] authenticated upstream")
                else:
                    Console().print(
                        f"[yellow]NOT READY[/yellow] session={data.get('session', 'unknown')}"
                    )
                return 0 if data.get("ready") is True else 1

            if command == "config":
                data = await _request_json(client, "GET", "/api/config")
                return _dispatch_json(data)

            if command == "status":
                tasks = await _download_statuses(client)
                if args.json:
                    return _dispatch_json({"tasks": tasks})
                return await status_command(daemon_url)

            if command == "download":
                download_command_name = getattr(args, "download_command", None)
                if download_command_name is None:
                    raise ValueError("download requires a gallery URL, gid+token, or a subcommand")

                if download_command_name == "legacy":
                    if args.json:
                        gid, token = resolve_gallery_target(args.target, args.token)
                        response = await client.post("/api/downloads", json={"gid": gid, "token": token})
                        response.raise_for_status()
                        return _dispatch_json(response.json())
                    return await download_command(args.target, daemon_url, args.token)

                if download_command_name == "add":
                    gid, token = resolve_gallery_target(args.target, args.token)
                    data = await _request_json(client, "POST", "/api/downloads", json={"gid": gid, "token": token})
                    return _dispatch_json(data)

                if download_command_name == "run":
                    return await _run_download_run(client, daemon_url, args)

                if download_command_name == "list":
                    tasks = await _download_statuses(client)
                    return _dispatch_json({"tasks": tasks} if args.json else tasks)

                if download_command_name == "report":
                    data = await _request_json(client, "GET", "/api/downloads/report")
                    return _dispatch_json(data)

                if download_command_name in {"repair", "forget"}:
                    data = await _request_json(
                        client,
                        "POST",
                        f"/api/downloads/{args.gid}/{download_command_name}",
                        json={"apply": args.apply},
                    )
                    return _dispatch_json(data)

                if download_command_name == "watch":
                    return await _watch_download_events(daemon_url, args.gid, args.ndjson, args.json)

                if download_command_name == "cancel":
                    data = await _request_json(client, "DELETE", f"/api/downloads/{args.gid}")
                    return _dispatch_json(data)

                if download_command_name in {"resume", "retry"}:
                    data = await _request_json(client, "POST", f"/api/downloads/{args.gid}/{download_command_name}")
                    return _dispatch_json(data)

                if download_command_name == "pages":
                    data = await _request_json(client, "GET", f"/api/downloads/{args.gid}/pages")
                    return _dispatch_json(_normalize_download_pages_output(data))

            if command == "search":
                params: dict[str, Any] = {"keyword": args.keyword, "page": args.page}
                for name in (
                    "category",
                    "min_rating",
                    "min_pages",
                    "max_pages",
                ):
                    value = getattr(args, name, None)
                    if value is not None:
                        params[name] = value
                for name in (
                    "search_name",
                    "search_tags",
                    "search_description",
                    "search_torrent",
                    "search_low_power_tags",
                    "disable_language_filter",
                    "show_expunged",
                ):
                    if getattr(args, name, False):
                        params[name] = "true"
                data = await _request_json(client, "GET", "/api/search", params=params)
                return _dispatch_json(data) if args.json else _dispatch_json(data)

            if command == "gallery":
                gid, token = resolve_gallery_target(args.target, args.token)
                data = await _request_json(client, "GET", f"/api/gallery/{gid}/{token}")
                return _dispatch_json(_redact_sensitive_cli_output(data))

            if command == "library":
                library_command = getattr(args, "library_command", None) or "list"
                if library_command == "list":
                    data = await _request_json(client, "GET", "/api/library")
                    return _dispatch_json(data) if args.json else _dispatch_json(data)
                if library_command == "export-pdf":
                    body = {}
                    if getattr(args, "password", None):
                        body["password"] = args.password
                    if getattr(args, "output_name", None):
                        body["output_name"] = args.output_name
                    if getattr(args, "include_cover", False):
                        body["include_cover"] = True
                    data = await _request_json(client, "POST", f"/api/library/{args.gid}/export/pdf", json=body)
                    return _dispatch_json(data) if args.json else _dispatch_json(data)

            if command == "tags" and getattr(args, "tags_command", None) == "suggest":
                data = await _request_json(client, "GET", "/api/tags/suggest", params={"q": args.query})
                return _dispatch_json(data) if args.json else _dispatch_json(data)

            if command == "tags" and getattr(args, "tags_command", None) == "status":
                data = await _request_json(client, "GET", "/api/tags/status")
                return _dispatch_json(data) if args.json else _dispatch_json(data)

            if command == "tags" and getattr(args, "tags_command", None) == "refresh":
                params = {"force": "true"} if args.force else None
                data = await _request_json(client, "POST", "/api/tags/refresh", params=params)
                _dispatch_json(data)
                return 0 if not isinstance(data, dict) or data.get("ok", True) else 1

            if command == "favorites":
                data = await _request_json(client, "GET", "/api/favorites", params={"slot": -1, "page": 0})
                return _dispatch_json(data) if args.json else _dispatch_json(data)

            if command == "popular":
                data = await _request_json(client, "GET", "/api/popular")
                return _dispatch_json(data) if args.json else _dispatch_json(data)

            if command == "toplist":
                data = await _request_json(client, "GET", "/api/toplist", params={"tl": args.tl})
                return _dispatch_json(data) if args.json else _dispatch_json(data)

            if command == "watched":
                data = await _request_json(client, "GET", "/api/watched", params={"page": args.page})
                return _dispatch_json(data) if args.json else _dispatch_json(data)
    except (httpx.ConnectError, httpx.TimeoutException):
        if machine_mode:
            return _emit_machine_error("connect_error", f"Cannot connect to daemon at {daemon_url}", ndjson=machine_ndjson)
        Console().print(f"[red]Cannot connect to daemon at {daemon_url}[/red]")
        return 1
    except httpx.HTTPStatusError as e:
        message = f"{e.response.status_code} {e.response.text}"
        if machine_mode:
            return _emit_machine_error("http_error", message, ndjson=machine_ndjson)
        Console().print(f"[red]HTTP error: {message}[/red]")
        return 1
    except ValueError as e:
        code = "invalid_gallery_target" if command in {"gallery", "download"} else "invalid_argument"
        if machine_mode:
            return _emit_machine_error(code, str(e), ndjson=machine_ndjson)
        Console().print(f"[red]{e}[/red]")
        return 1

    return _handle_local_passthrough(args)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args(_normalize_argv())
    _finalize_common_option_defaults(args)

    if not getattr(args, "command", None):
        parser.print_help()
        raise SystemExit(0)

    exit_code = asyncio.run(_run_http_command(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
