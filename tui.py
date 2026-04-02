from textual.app import App, ComposeResult
from textual.widgets import Label, ListView, ListItem, Markdown, Footer
from textual.containers import Horizontal, VerticalScroll, Vertical, Container
from textual import work
from textual.binding import Binding
from rich.text import Text
import os
import parser
from client import ExhentaiClient
from downloader import GalleryDownloader

class GalleryItem(ListItem):
    """Custom widget for a gallery list item."""
    def __init__(self, index: int, gallery: dict):
        super().__init__(name=str(index))
        self.gallery = gallery
        self.idx = index

    def compose(self) -> ComposeResult:
        category = self.gallery.get('category', 'UNKNOWN')
        cat_upper = category.upper() if category else 'UNKNOWN'
        
        # Color mapping roughly matching typical EH/EX colors
        cat_colors = {
            "DOUJINSHI": "bold red",
            "MANGA": "bold dark_orange",
            "ARTIST CG": "bold yellow",
            "GAME CG": "bold green",
            "WESTERN": "bold green_yellow",
            "NON-H": "bold blue",
            "IMAGE SET": "bold dark_blue",
            "COSPLAY": "bold purple",
            "ASIAN PORN": "bold magenta",
            "MISC": "bold grey74"
        }
        
        cat_style = cat_colors.get(cat_upper, "bold white")
        title = self.gallery.get('title', 'Unknown Title')
        posted = self.gallery.get('posted', '')
        language = self.gallery.get('language', '')
        
        text = Text()
        # Title in bold (wrapping text)
        text.append(f"{title}\n", style="bold")
        # Placeholder for rating stars
        text.append("★" * 4 + "☆" + "\n", style="yellow")
        
        # Bottom row: [CATEGORY]     LANG    DATE
        text.append(f"[{cat_upper}]", style=f"{cat_style} on black")
        
        # Use simple spacing. In Textual it's tricky to right align parts of text in one Label without columns, 
        # but we can add some spaces.
        right_info = ""
        if language:
            right_info += f"  {language}"
        if posted:
            right_info += f"    {posted}"
            
        if right_info:
            text.append(right_info, style="dim")
             
        yield Label(text)

class LeftPane(VerticalScroll):
    """Pane for displaying the gallery list."""
    def compose(self) -> ComposeResult:
        yield ListView(id="gallery-list")

class MiddlePane(VerticalScroll):
    """Pane for displaying thumbnail pages of the selected gallery."""
    def compose(self) -> ComposeResult:
        yield ListView(id="page-list")

class RightPane(VerticalScroll):
    """Pane for displaying metadata/preview."""
    def compose(self) -> ComposeResult:
        yield Markdown("No gallery selected.", id="metadata-view")

class ExhentaiApp(App):
    """A Yazi-style, keyboard-centric TUI for Exhentai browsing & downloads."""

    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #main-container {
        layout: horizontal;
        height: 1fr;
    }

    LeftPane {
        width: 30%;
        border-right: solid $accent;
        height: 100%;
    }

    MiddlePane {
        width: 40%;
        border-right: solid $accent;
        height: 100%;
    }

    RightPane {
        width: 30%;
        height: 100%;
        padding: 1;
    }
    
    ListView {
        height: 100%;
        border: none;
    }
    
    GalleryItem {
        padding: 1 1;
        border-bottom: solid $primary-background;
        height: auto;
    }
    
    GalleryItem:focus {
        background: $primary;
    }
    
    ListItem {
        padding: 0 1;
    }
    
    ListItem:focus {
        background: $primary;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "download", "Download Gallery"),
        Binding("enter", "enter_pane", "Enter"),
        Binding("escape", "leave_pane", "Back"),
        Binding("h", "leave_pane", "Left"),
        Binding("l", "enter_pane", "Right"),
    ]

    def __init__(self, credentials_path="credentials.txt"):
        super().__init__()
        self.credentials_path = credentials_path
        self.galleries = []
        self.current_gallery_details = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Horizontal(
            LeftPane(id="pane-left"),
            MiddlePane(id="pane-middle"),
            RightPane(id="pane-right"),
            id="main-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        self.gallery_list = self.query_one("#gallery-list", ListView)
        self.page_list = self.query_one("#page-list", ListView)
        self.metadata_view = self.query_one("#metadata-view", Markdown)
        self.fetch_homepage()

    @work(thread=True)
    def fetch_homepage(self):
        self.call_from_thread(self.metadata_view.update, "Fetching homepage...")
        try:
            with ExhentaiClient(credentials_path=self.credentials_path) as client:
                html = client.get_html("https://exhentai.org/")
                self.galleries = parser.parse_gallery_list(html)
                
                self.call_from_thread(self._populate_galleries)
        except Exception as e:
            self.call_from_thread(self.metadata_view.update, f"Error: {e}")

    def _populate_galleries(self):
        self.gallery_list.clear()
        for i, g in enumerate(self.galleries):
            self.gallery_list.append(GalleryItem(i, g))
        if len(self.galleries) > 0:
            self.gallery_list.focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        if event.list_view.id == "gallery-list":
            if event.item:
                idx = int(event.item.name)
                gallery = self.galleries[idx]
                
                md = f"# {gallery['title']}\n\n"
                md += f"**Category:** {gallery.get('category', 'Unknown')}\n"
                md += f"**Uploader:** {gallery['uploader']}\n"
                md += f"**Thumb:** {gallery['thumb_url']}\n"
                md += f"**URL:** {gallery['url']}\n"
                self.metadata_view.update(md)
                
                # Debounce fetching gallery detail
                self.fetch_gallery_detail(gallery['url'])
                
        elif event.list_view.id == "page-list":
            if event.item and self.current_gallery_details:
                idx = int(event.item.name)
                if idx < len(self.current_gallery_details['preview_urls']):
                    preview_url = self.current_gallery_details['preview_urls'][idx]
                    
                    md = f"# Page {idx + 1}\n\n"
                    md += f"**Preview URL:** {preview_url}\n\n"
                    md += "Currently, downloading individual pages is not supported. Press `d` to download the entire gallery."
                    self.metadata_view.update(md)


    @work(thread=True, exclusive=True)
    def fetch_gallery_detail(self, url: str):
        self.call_from_thread(self.page_list.clear)
        self.call_from_thread(self.page_list.append, ListItem(Label("Loading pages...")))
        try:
            with ExhentaiClient(credentials_path=self.credentials_path) as client:
                html = client.get_html(url)
                details = parser.parse_gallery_detail(html)
                
                self.call_from_thread(self._populate_pages, details)
        except Exception as e:
            pass

    def _populate_pages(self, details):
        self.current_gallery_details = details
        self.page_list.clear()
        
        md = f"# {details['title']}\n\n"
        md += f"**Uploader:** {details['uploader']}\n"
        md += f"**Category:** {details['category']}\n"
        md += f"**Pages:** {details['pages']}\n\n"
        md += "## Tags\n"
        for ns, tags in details['tags'].items():
            md += f"- **{ns}**: {', '.join(tags)}\n"
        self.metadata_view.update(md)
        
        for i, url in enumerate(details["preview_urls"]):
            self.page_list.append(ListItem(Label(f"Page {i+1}"), name=str(i)))

    def action_enter_pane(self):
        if self.gallery_list.has_focus and len(self.page_list.children) > 0:
            self.page_list.focus()
            
    def action_leave_pane(self):
        if self.page_list.has_focus:
            self.gallery_list.focus()
            
    def action_refresh(self):
        if self.gallery_list.has_focus:
            self.fetch_homepage()
            
    @work(thread=True)
    def action_download(self):
        idx = -1
        if self.gallery_list.highlighted_child:
            idx = int(self.gallery_list.highlighted_child.name)
            
        if idx >= 0:
            gallery = self.galleries[idx]
            url = gallery['url']
            
            self.call_from_thread(self.metadata_view.update, f"# Downloading...\n\nStarting download for {gallery['title']}...\nPlease wait.")
            
            try:
                with ExhentaiClient(credentials_path=self.credentials_path) as client:
                    downloader = GalleryDownloader(client=client, output_dir="downloads")
                    downloader.download_gallery(url)
                
                self.call_from_thread(self.metadata_view.update, f"# Done!\n\nDownloaded: {gallery['title']}")
            except Exception as e:
                self.call_from_thread(self.metadata_view.update, f"# Error\n\nFailed to download: {e}")

if __name__ == "__main__":
    app = ExhentaiApp()
    app.run()
