import httpx
import sys
from bs4 import BeautifulSoup

def load_credentials(filepath="credentials.txt"):
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
        print("Please create 'credentials.txt' with your cookies in KEY=VALUE format.")
        print("Format example:")
        print("ipb_member_id=1234567")
        print("ipb_pass_hash=abcdef1234567890")
        print("igneous=your_igneous_value_here")
        sys.exit(1)

    required_keys = ["ipb_member_id", "ipb_pass_hash"]
    missing = [k for k in required_keys if k not in cookies]
    if missing:
        print(f"Warning: Missing standard required cookies: {', '.join(missing)}")

    return cookies

def verify_access():
    cookies = load_credentials()

    # Headers derived from the reference project's ChromeRequestBuilder
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    url = "https://exhentai.org/"

    print(f"Fetching {url}...")

    try:
        with httpx.Client(cookies=cookies, headers=headers) as client:
            response = client.get(url)

            print(f"Status Code: {response.status_code}")

            if response.status_code != 200:
                print("Failed to access successfully.")
                print(f"Response: {response.text[:200]}")
                return

            if 'inline; filename="sadpanda.jpg"' in response.headers.get("Content-Disposition", ""):
                print("Error: Received Sad Panda. Your cookies might be invalid or your IP is blocked.")
                return

            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string if soup.title else "No Title Found"

            print(f"\n--- SUCCESS ---")
            print(f"Page Title: {title}")
            print(f"First 150 chars of HTML: {response.text[:150].strip()}")

            if "gallery" in response.text.lower():
                print("Found 'gallery' keyword on the page. Access looks good!")

    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    verify_access()