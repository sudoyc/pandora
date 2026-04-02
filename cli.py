import argparse
import sys
from client import ExhentaiClient
from downloader import GalleryDownloader
from rich.console import Console

def download_command(args, console):
    """Handler for the 'download' subcommand."""
    console.print(f"[bold cyan]Exhentai Downloader[/bold cyan]")
    console.print("Initializing client...")

    try:
        with ExhentaiClient(credentials_path=args.credentials) as client:
            downloader = GalleryDownloader(client=client, output_dir=args.output)
            downloader.download_gallery(args.url)

    except KeyboardInterrupt:
        console.print("\n[bold red]Download interrupted by user.[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
        sys.exit(1)

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

    args = parser.parse_args()

    # Call the appropriate handler function based on the selected subcommand
    if hasattr(args, 'func'):
        args.func(args, console)
    else:
        # Launch TUI by default
        default_command(args, console)

if __name__ == "__main__":
    main()