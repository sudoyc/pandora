import os
import re
from typing import Dict, Any

from client import ExhentaiClient
import parser
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

class GalleryDownloader:
    def __init__(self, client: ExhentaiClient, output_dir: str = "downloads"):
        self.client = client
        self.output_dir = output_dir
        self.console = Console()

    def sanitize_filename(self, name: str) -> str:
        """Removes invalid characters from a filename."""
        return re.sub(r'[\\/*?:"<>|]', "", name)

    def write_metadata_md(self, gallery_dir: str, details: Dict[str, Any], url: str):
        """Saves gallery metadata as a Markdown file."""
        md_path = os.path.join(gallery_dir, "metadata.md")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {details.get('title', 'Unknown Title')}\n\n")

            if details.get('title_jpn'):
                f.write(f"**Japanese Title:** {details['title_jpn']}\n\n")

            f.write(f"**Uploader:** {details.get('uploader', 'Unknown')}\n")
            f.write(f"**Category:** {details.get('category', 'Unknown')}\n")
            f.write(f"**Pages:** {details.get('pages', 0)}\n")
            f.write(f"**URL:** {url}\n\n")

            f.write("## Tags\n")
            tags = details.get('tags', {})
            if tags:
                for namespace, items in tags.items():
                    f.write(f"- **{namespace}**: {', '.join(items)}\n")
            else:
                f.write("No tags found.\n")

    def download_gallery(self, url: str):
        """Orchestrates the entire downloading process."""
        self.console.print(f"[bold green]Fetching gallery metadata from:[/bold green] {url}")

        try:
            # 1. Fetch main gallery page
            html = self.client.get_html(url)
            details = parser.parse_gallery_detail(html)

            # Fetch additional preview pages if necessary (if there are multiple pages of thumbnails)
            preview_urls = details["preview_urls"]
            current_page_html = html
            while True:
                next_url = parser.parse_next_page_url(current_page_html)
                if not next_url:
                    break
                # Only fetch if we haven't already got all pages
                if len(preview_urls) >= details["pages"]:
                    break

                self.console.print(f"Fetching next thumbnail page: {next_url}")
                current_page_html = self.client.get_html(next_url)
                page_details = parser.parse_gallery_detail(current_page_html)
                preview_urls.extend(page_details["preview_urls"])

            # 2. Create Directory
            title = details.get("title", "Unknown_Gallery")
            gallery_info = parser.parse_gallery_url(url)
            gid = gallery_info["gid"] if gallery_info else "000000"
            folder_name = f"{gid} - {self.sanitize_filename(title)}"
            gallery_dir = os.path.join(self.output_dir, folder_name)

            os.makedirs(gallery_dir, exist_ok=True)
            self.console.print(f"[bold blue]Saving to directory:[/bold blue] {gallery_dir}")

            # 3. Write Metadata
            self.write_metadata_md(gallery_dir, details, url)
            self.console.print("[green]Metadata saved to metadata.md[/green]")

            # 4. Download Images
            total_images = len(preview_urls)
            self.console.print(f"[bold]Starting download of {total_images} images...[/bold]")

            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=self.console
            ) as progress:
                task_id = progress.add_task("Downloading...", total=total_images)

                for i, viewer_url in enumerate(preview_urls, start=1):
                    # Fetch viewer page HTML
                    viewer_html = self.client.get_html(viewer_url)
                    image_url = parser.parse_image_viewer_page(viewer_html)

                    if image_url:
                        # Determine file extension (defaulting to jpg if unknown)
                        ext = ".jpg"
                        if ".png" in image_url.lower(): ext = ".png"
                        elif ".gif" in image_url.lower(): ext = ".gif"

                        filename = f"{i:03d}{ext}"
                        filepath = os.path.join(gallery_dir, filename)

                        # Actually download the file
                        self.client.download_file(image_url, filepath)
                    else:
                        self.console.print(f"[red]Warning: Could not find image URL on viewer page: {viewer_url}[/red]")

                    progress.update(task_id, advance=1)

            self.console.print("\n[bold green]Download Complete![/bold green]")

        except Exception as e:
            self.console.print(f"[bold red]Error downloading gallery:[/bold red] {e}")
