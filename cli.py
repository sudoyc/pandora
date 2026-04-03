import argparse
import sys
import asyncio
from client import ExhentaiClient
from exhentai_api.api import ExhentaiAPI
from exhentai_api.models.search import SearchParams
from downloader import GalleryDownloader
from rich.console import Console
from rich.table import Table

async def download_command_async(args, console):
    """Async handler for the 'download' subcommand."""
    console.print(f"[bold cyan]Exhentai Downloader[/bold cyan]")
    console.print("Initializing client...")

    try:
        with ExhentaiClient(credentials_path=args.credentials) as client:
            downloader = GalleryDownloader(client=client, output_dir=args.output)
            await downloader.download_gallery(args.url)

    except KeyboardInterrupt:
        console.print("\n[bold red]Download interrupted by user.[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
        sys.exit(1)

def download_command(args, console):
    asyncio.run(download_command_async(args, console))

async def search_command_async(args, console):
    """Async handler for the 'search' subcommand."""
    console.print(f"[bold cyan]Exhentai Search[/bold cyan]")

    try:
        with ExhentaiClient(credentials_path=args.credentials) as client:
            api = ExhentaiAPI(client=client)
            params = SearchParams(f_search=args.query)

            console.print(f"Searching for: '{args.query}' (Page {args.page})...")
            galleries = await api.search(params, page=args.page)

            if not galleries:
                console.print("[yellow]No galleries found.[/yellow]")
                return

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID", style="dim", width=12)
            table.add_column("Category", width=12)
            table.add_column("Title")
            table.add_column("Uploader")

            for g in galleries:
                # We can construct the URL from gid and token
                url = f"https://exhentai.org/g/{g.gid}/{g.token}/"
                table.add_row(
                    g.gid,
                    g.category,
                    f"[link={url}]{g.title}[/link]",
                    g.uploader
                )

            console.print(table)
            console.print(f"\nFound {len(galleries)} galleries on this page.")

    except KeyboardInterrupt:
        console.print("\n[bold red]Search interrupted by user.[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
        sys.exit(1)

def search_command(args, console):
    asyncio.run(search_command_async(args, console))

async def favorites_command_async(args, console):
    """Async handler for the 'favorites' subcommand."""
    console.print(f"[bold cyan]Exhentai Favorites[/bold cyan]")

    try:
        with ExhentaiClient(credentials_path=args.credentials) as client:
            api = ExhentaiAPI(client=client)

            console.print(f"Fetching favorites (Category {args.category}, Page {args.page})...")
            response = await api.get_favorites(favcat=args.category, page=args.page)

            if response.categories:
                cat_table = Table(title="Favorite Categories", show_header=True, header_style="bold blue")
                cat_table.add_column("Slot", style="dim")
                cat_table.add_column("Name")
                cat_table.add_column("Count", justify="right")

                for cat in response.categories:
                    cat_table.add_row(str(cat.slot), cat.name, str(cat.count))
                console.print(cat_table)
                console.print()

            galleries = response.galleries
            if not galleries:
                console.print("[yellow]No galleries found in this favorites list.[/yellow]")
                return

            table = Table(title=f"Favorites", show_header=True, header_style="bold magenta")
            table.add_column("ID", style="dim", width=12)
            table.add_column("Category", width=12)
            table.add_column("Title")
            table.add_column("Uploader")

            for g in galleries:
                url = f"https://exhentai.org/g/{g.gid}/{g.token}/"
                table.add_row(
                    g.gid,
                    g.category,
                    f"[link={url}]{g.title}[/link]",
                    g.uploader
                )

            console.print(table)

    except KeyboardInterrupt:
        console.print("\n[bold red]Operation interrupted by user.[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
        sys.exit(1)

def favorites_command(args, console):
    asyncio.run(favorites_command_async(args, console))

def verify_command(args, console):
    """Handler for the 'verify' subcommand (the original basic access test)."""
    console.print(f"[bold cyan]Exhentai Connection Verifier[/bold cyan]")
    try:
        with ExhentaiClient(credentials_path=args.credentials) as client:
            url = "https://exhentai.org/"
            console.print(f"Fetching {url}...")

            response = client.client.get(url)
            console.print(f"Status Code: {response.status_code}")

            if response.status_code != 200:
                console.print("[red]Failed to access successfully.[/red]")
                return

            if 'inline; filename="sadpanda.jpg"' in response.headers.get("Content-Disposition", ""):
                console.print("[red]Error: Received Sad Panda. Your cookies might be invalid or your IP is blocked.[/red]")
                return

            console.print("\n[bold green]--- SUCCESS ---[/bold green]")
            if "gallery" in response.text.lower():
                console.print("Found 'gallery' keyword on the page. Access looks good!")

    except Exception as e:
         console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
         sys.exit(1)


def default_command(args, console):
    """Launch the TUI if no subcommand is provided."""
    from tui import ExhentaiApp
    app = ExhentaiApp(credentials_path=args.credentials)
    app.run()

def main():
    console = Console()

    # Main parser
    parser = argparse.ArgumentParser(description="Exhentai CLI Tool")

    # Global arguments
    parser.add_argument("--credentials", "-c", default="credentials.txt", help="Path to credentials file (default: credentials.txt)")

    # Subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'download' subcommand
    download_parser = subparsers.add_parser("download", help="Download a gallery and its metadata")
    download_parser.add_argument("url", help="The URL of the gallery to download (e.g., https://exhentai.org/g/1234567/a1b2c3d4e5/)")
    download_parser.add_argument("--output", "-o", default="downloads", help="Output directory (default: downloads)")
    download_parser.set_defaults(func=download_command)

    # 'verify' subcommand
    verify_parser = subparsers.add_parser("verify", help="Verify access to the homepage using credentials")
    verify_parser.set_defaults(func=verify_command)

    # 'search' subcommand
    search_parser = subparsers.add_parser("search", help="Search for galleries")
    search_parser.add_argument("query", help="The search query")
    search_parser.add_argument("--page", "-p", type=int, default=0, help="Page number (0-indexed)")
    search_parser.set_defaults(func=search_command)

    # 'favorites' subcommand
    favorites_parser = subparsers.add_parser("favorites", aliases=["favs"], help="List your favorite galleries")
    favorites_parser.add_argument("--category", "-cat", type=int, default=-1, help="Favorite category slot (0-9). Default is all (-1)")
    favorites_parser.add_argument("--page", "-p", type=int, default=0, help="Page number (0-indexed)")
    favorites_parser.set_defaults(func=favorites_command)

    args = parser.parse_args()

    # Call the appropriate handler function based on the selected subcommand
    if hasattr(args, 'func'):
        args.func(args, console)
    else:
        # Launch TUI by default
        default_command(args, console)

if __name__ == "__main__":
    main()