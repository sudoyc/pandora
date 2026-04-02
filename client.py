import httpx
import sys
from typing import Dict, Optional

class ExhentaiClient:
    def __init__(self, credentials_path: str = "credentials.txt"):
        self.cookies = self._load_credentials(credentials_path)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        # Use a single client session for connection pooling
        self.client = httpx.Client(cookies=self.cookies, headers=self.headers, timeout=30.0)

    def _load_credentials(self, filepath: str) -> Dict[str, str]:
        cookies = {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line:
                        key, value = line.split("=", 1)
                        cookies[key.strip()] = value.strip()
        except FileNotFoundError:
            print(f"Error: {filepath} not found.")
            print("Please create 'credentials.txt' with your cookies (ipb_member_id, ipb_pass_hash, igneous).")
            sys.exit(1)
        return cookies

    def get_html(self, url: str) -> str:
        """Fetches the HTML content of a URL."""
        response = self.client.get(url)
        response.raise_for_status()

        # Check for sad panda
        if 'inline; filename="sadpanda.jpg"' in response.headers.get("Content-Disposition", ""):
            raise Exception("Received Sad Panda. Your cookies might be invalid or your IP is blocked.")

        return response.text

    def download_file(self, url: str, output_path: str):
        """Downloads a binary file to the specified path."""
        # Use stream to handle large files efficiently
        with self.client.stream("GET", url) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()