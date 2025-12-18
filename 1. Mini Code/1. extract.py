import sys
import json
import re
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

def fetch_html(url, timeout=15):
    """Fetches the HTML content of a URL with a standard browser user-agent."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"[!] HTTP request failed: {e}")
        return None

def extract_from_sigi_state(html):
    """
    Attempts to find and parse the embedded JSON state (__SIGI_STATE__)
    from the initial HTML source of a TikTok page.
    """
    match = re.search(
        r'<script id="__SIGI_STATE__" type="application/json">(.*?)</script>', html
    )
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            print("[!] Failed to decode __SIGI_STATE__ JSON.")
            return None
    return None

def extract_video_urls_from_sigi(sigi_json):
    """
    Extracts video URLs from the parsed __SIGI_STATE__ JSON object.
    The structure often contains an 'ItemModule' with video details.
    """
    urls = []
    if not isinstance(sigi_json, dict):
        return urls

    item_module = sigi_json.get("ItemModule", {})
    for video_id, video_data in item_module.items():
        if isinstance(video_data, dict):
            author = video_data.get("author")
            if author and video_id.isdigit():
                url = f"https://www.tiktok.com/@{author}/video/{video_id}"
                urls.append(url)
    return list(dict.fromkeys(urls)) # Return unique URLs

def extract_urls_from_html_anchors(html, base_url):
    """A fallback method to extract video URLs from <a> tags in the HTML."""
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)
    urls = []
    for a in anchors:
        href = a["href"]
        # Look for the specific pattern of a TikTok video URL
        if "/video/" in href and "@" in href:
            full_url = urljoin(base_url, href)
            # Clean the URL by removing any query parameters
            cleaned_url = full_url.split("?")[0]
            urls.append(cleaned_url)
    return list(dict.fromkeys(urls)) # Return unique URLs

def playwright_render_and_extract(url):
    """
    Uses Playwright to fully render the page and AUTOMATICALLY SCROLLS DOWN
    to load all dynamically loaded videos before extracting URLs.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[!] Playwright not found.")
        print("    Please install it: pip install playwright")
        print("    And its browsers: python -m playwright install")
        return []

    print("[*] Launching browser with Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # Set headless=False to watch it work
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(url, timeout=60000, wait_until="networkidle")

            # --- NEW SCROLLING LOGIC ---
            print("[*] Scrolling down to load all videos. This might take a moment...")
            last_height = page.evaluate("document.body.scrollHeight")
            scroll_attempts = 0
            while scroll_attempts < 20: # Safety break after 20 scrolls
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2) # Wait for new content to load
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    print("[+] Reached the bottom of the collection.")
                    break
                last_height = new_height
                scroll_attempts += 1
                print(f"    ...scrolled, loading more ({scroll_attempts})")
            
            print("[*] Finished scrolling. Extracting all loaded URLs...")
            html = page.content()
            # --- END OF NEW LOGIC ---

        except Exception as e:
            print(f"[!] Playwright failed during execution: {e}")
            return []
        finally:
            browser.close()

    return extract_urls_from_html_anchors(html, url)

def main(collection_url):
    """Main function to orchestrate the extraction process."""
    print(f"[+] Starting extraction for collection: {collection_url}")
    urls = []

    # --- Method 1: Fast HTTP request and JSON parsing (will likely fail for collections) ---
    print("[*] Step 1: Trying fast HTML + JSON extraction...")
    html = fetch_html(collection_url)
    if html:
        sigi_data = extract_from_sigi_state(html)
        if sigi_data:
            urls = extract_video_urls_from_sigi(sigi_data)

    if urls:
        print(f"[+] Success! Found {len(urls)} URLs using the fast method.")
    else:
        print("[!] Fast method failed. The page requires JavaScript rendering and scrolling.")
        # --- Method 2: Fallback to Playwright for full rendering and scrolling ---
        print("\n[*] Step 2: Falling back to Playwright...")
        urls = playwright_render_and_extract(collection_url)
        if urls:
            print(f"[+] Success! Found {len(urls)} URLs using Playwright.")

    # --- Final Output ---
    if not urls:
        print("\n[!] ERROR: Could not find any video URLs after all attempts.")
        return

    print("\n" + "="*20)
    print(f"  EXTRACTED {len(urls)} VIDEO URLS")
    print("="*20)
    for url in urls:
        print(url)

    # Save the URLs to a file
    try:
        with open("tiktok_urls.txt", "w", encoding="utf-8") as f:
            for url in urls:
                f.write(url + "\n")
        print(f"\n[+] All {len(urls)} URLs have been saved to the file: tiktok_urls.txt")
    except IOError as e:
        print(f"\n[!] Could not write to file: {e}")


if __name__ == "__main__":
    # The URL is still hardcoded here.
    TIKTOK_COLLECTION_URL = "https://www.tiktok.com/@speechify01/collection/Database-7568797529941363457"
    
    main(TIKTOK_COLLECTION_URL)