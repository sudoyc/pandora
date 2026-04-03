import asyncio
import os
import re
import argparse
import httpx
import aiofiles
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

from exhentai_api.api import ExhentaiAPI

class GalleryDownloader:
    def __init__(self, output_dir: str = "downloads", client=None):
        self.output_dir = output_dir
        self.console = Console()
        self.api = ExhentaiAPI(client=client)

    def sanitize_filename(self, name: str) -> str:
        """Removes invalid characters from a filename."""
        return re.sub(r'[\\/*?:"<>|]', "", name)

    async def write_metadata_md(self, gallery_dir: str, details, url: str):
        """Saves gallery metadata as a Markdown file."""
        md_path = os.path.join(gallery_dir, "metadata.md")

        async with aiofiles.open(md_path, "w", encoding="utf-8") as f:
            await f.write(f"# {details.title or 'Unknown Title'}\n\n")

            if details.title_jpn:
                await f.write(f"**Japanese Title:** {details.title_jpn}\n\n")

            await f.write(f"**Uploader:** {details.uploader or 'Unknown'}\n")
            await f.write(f"**Category:** {details.category or 'Unknown'}\n")
            await f.write(f"**Pages:** {details.pages}\n")
            await f.write(f"**URL:** {url}\n\n")

            await f.write("## Tags\n")
            tags = details.tags or {}
            if tags:
                for namespace, items in tags.items():
                    await f.write(f"- **{namespace}**: {', '.join(items)}\n")
            else:
                await f.write("No tags found.\n")

    async def download_file(self, url: str, filepath: str):
        """Downloads a single file asynchronously."""
        async with httpx.AsyncClient() as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
            }
            for attempt in range(3):
                try:
                    async with client.stream("GET", url, headers=headers, timeout=30.0) as response:
                        response.raise_for_status()
                        async with aiofiles.open(filepath, "wb") as f:
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                await f.write(chunk)
                    return
                except Exception as e:
                    if attempt == 2:
                        raise e
                    await asyncio.sleep(1)

    async def download_gallery(self, url: str):
        """Orchestrates the entire downloading process."""
        self.console.print(f"[bold green]Fetching gallery metadata from:[/bold green] {url}")

        match = re.search(r"/(?:g|mpv)/(\d+)/([0-9a-f]{10})", url)
        if not match:
            self.console.print("[bold red]Invalid gallery URL format.[/bold red]")
            return

        gid, token = match.group(1), match.group(2)

        try:
            details = await self.api.get_gallery_details(gid, token)
            preview_urls = details.preview_urls

            # Fetch remaining preview pages if any
            if details.preview_pages > 1:
                self.console.print(f"Fetching {details.preview_pages - 1} more preview pages...")
                for p in range(1, details.preview_pages):
                    page_url = f"{url}?p={p}"
                    html = await self.api.client.get_html(page_url)
                    import bs4
                    soup = bs4.BeautifulSoup(html, "html.parser")
                    for gdt in soup.find_all(class_=["gdtm", "gdtl"]):
                        a_tag = gdt.find("a")
                        if a_tag and a_tag.get("href"):
                            preview_urls.append(a_tag.get("href"))

            title = details.title or "Unknown_Gallery"
            folder_name = f"{gid} - {self.sanitize_filename(title)}"
            gallery_dir = os.path.join(self.output_dir, folder_name)

            os.makedirs(gallery_dir, exist_ok=True)
            self.console.print(f"[bold blue]Saving to directory:[/bold blue] {gallery_dir}")

            await self.write_metadata_md(gallery_dir, details, url)
            self.console.print("[green]Metadata saved to metadata.md[/green]")

            total_images = len(preview_urls)
            self.console.print(f"[bold]Starting download of {total_images} images...[/bold]")
            if total_images == 0:
                self.console.print(f"[bold red]Warning: No images found to download. Preview URLs list is empty![/bold red]")

            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=self.console
            ) as progress:
                task_id = progress.add_task("Downloading...", total=total_images)

                current_nl = None
                for i, viewer_url in enumerate(preview_urls, 1):
                    # Fetch image details from viewer_url directly rather than trying to construct it
                    try:
                        viewer_html = await self.api.client.get_html(viewer_url)
                        from exhentai_api.parsers.image import parse_image_viewer
                        image_url, new_nl = parse_image_viewer(viewer_html)

                        img_url = image_url

                        if img_url:
                            ext = ".jpg"
                            if ".png" in img_url.lower(): ext = ".png"
                            elif ".gif" in img_url.lower(): ext = ".gif"

                            filename = f"{i:03d}{ext}"
                            filepath = os.path.join(gallery_dir, filename)

                            await self.download_file(img_url, filepath)
                        else:
                            self.console.print(f"[red]Could not get image URL for page {i}[/red]")
                    except Exception as e:
                        self.console.print(f"[red]Error downloading page {i}: {e}[/red]")

                    progress.update(task_id, advance=1)

            self.console.print("\n[bold green]Download Complete![/bold green]")

        except Exception as e:
            self.console.print(f"[bold red]Error downloading gallery:[/bold red] {e}")
        finally:
            await self.api.aclose()

async def main():
    parser = argparse.ArgumentParser(description="Simple CLI Exhentai Downloader")
    parser.add_argument("url", help="URL of the gallery to download")
    parser.add_argument("--dir", default="downloads", help="Output directory")
    args = parser.parse_args()

    # Read credentials if they exist
    igneous = ""
    ipb_member_id = ""
    if os.path.exists("credentials.txt"):
        with open("credentials.txt", "r") as f:
            for line in f:
                if line.startswith("igneous="):
                    igneous = line.strip().split("=")[1]
                elif line.startswith("ipb_member_id="):
                    ipb_member_id = line.strip().split("=")[1]

    from exhentai_api.client import ExhentaiClient
    client = ExhentaiClient(igneous=igneous, ipb_member_id=ipb_member_id)
    downloader = GalleryDownloader(output_dir=args.dir, client=client)
    await downloader.download_gallery(args.url)

if __name__ == "__main__":
    asyncio.run(main())