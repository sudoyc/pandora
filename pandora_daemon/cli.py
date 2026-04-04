"""Pandora CLI — minimal daemon client for downloading galleries."""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

from pandora_daemon.config import load_config


def parse_gallery_url(url: str) -> tuple[str, str]:
    """Extract (gid, token) from an exhentai/e-hentai gallery URL."""
    match = re.search(r"/g/(\d+)/([0-9a-f]{10})", url)
    if not match:
        raise ValueError(f"Invalid gallery URL: {url}")
    return match.group(1), match.group(2)


def build_daemon_url(host: str, port: int) -> str:
    """Build the daemon base URL from config."""
    return f"http://{host}:{port}"


async def download_command(url: str, daemon_url: str) -> int:
    """Submit a download and monitor progress via WebSocket. Returns exit code."""
    console = Console()

    try:
        gid, token = parse_gallery_url(url)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    # Check daemon is reachable
    try:
        async with httpx.AsyncClient(base_url=daemon_url, timeout=5.0) as client:
            await client.get("/api/config")
    except (httpx.ConnectError, httpx.TimeoutException):
        console.print(f"[red]Cannot connect to daemon at {daemon_url}[/red]")
        console.print("[dim]Start the daemon first: uv run python -m pandora_daemon[/dim]")
        return 1

    # Submit download
    async with httpx.AsyncClient(base_url=daemon_url, timeout=30.0) as client:
        try:
            resp = await client.post("/api/downloads", json={"gid": gid, "token": token})
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

    # Monitor via WebSocket
    ws_url = daemon_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
    try:
        import websockets
        async with websockets.connect(ws_url) as ws:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task_id = progress.add_task("Waiting...", total=None)

                async for message in ws:
                    event = json.loads(message)
                    if str(event.get("gid")) != gid:
                        continue

                    ev_type = event.get("event", "")
                    if ev_type == "download_progress":
                        phase = event.get("phase", "")
                        page = event.get("page", 0)
                        total = event.get("total", 0)
                        if total > 0:
                            progress.update(task_id, description=f"{phase}", completed=page, total=total)
                        else:
                            progress.update(task_id, description=f"{phase}...")
                    elif ev_type == "download_complete":
                        progress.update(task_id, description="Done", completed=100, total=100)
                        console.print(f"\n[bold green]Download complete:[/bold green] {event.get('path', '')}")
                        return 0
                    elif ev_type == "download_error":
                        console.print(f"\n[bold red]Download error:[/bold red] {event.get('error', 'unknown')}")
                        return 1
                    elif ev_type == "download_cancelled":
                        console.print("\n[yellow]Download cancelled[/yellow]")
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


def main():
    """Entry point for the `pandora` CLI command."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="pandora",
        description="Pandora CLI — ExHentai daemon client",
    )
    subparsers = parser.add_subparsers(dest="command")

    dl_parser = subparsers.add_parser(
        "download", aliases=["dl"],
        help="Download a gallery via daemon",
    )
    dl_parser.add_argument(
        "url",
        help="Gallery URL (e.g. https://exhentai.org/g/123456/abcdef0123/)",
    )

    args = parser.parse_args()

    if args.command in ("download", "dl"):
        config_path = Path("~/.config/pandora/config.toml").expanduser()
        config = load_config(config_path)
        daemon_url = build_daemon_url(config.server.host, config.server.port)
        exit_code = asyncio.run(download_command(args.url, daemon_url))
        sys.exit(exit_code)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
