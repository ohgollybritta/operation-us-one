"""
callescort.org OSINT Scraper — Tor Edition
For anti-human trafficking research purposes only.
Collects publicly posted ad data: text, images, phone numbers, timestamps.
Routes all traffic through Tor to bypass IP blocks.
Stores everything in a local SQLite database.

Requirements:
    sudo apt install tor
    sudo systemctl start tor
    pip install requests[socks] --break-system-packages
"""

import requests
import sqlite3
import os
import time
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

# ── Configuration ────────────────────────────────────────────────────────────

BASE_URL  = "https://callescort.org"
OUTPUT_DIR = "osint_data"
IMAGE_DIR  = os.path.join(OUTPUT_DIR, "images")
DB_PATH    = os.path.join(OUTPUT_DIR, "ads.db")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Route all requests through local Tor SOCKS5 proxy
TOR_PROXIES = {
    "http":  "socks5h://127.0.0.1:9050",
    "https": "socks5h://127.0.0.1:9050",
}

# Cities to scrape — US-1 corridor + high-trafficking hubs
CITIES = [
    # Florida
    "orlando, florida",
    "miami, florida",
    "tampa, florida",
    "jacksonville, florida",
    "fort lauderdale, florida",
    "west palm beach, florida",
    "daytona beach, florida",
    "fort pierce, florida",
    "melbourne, florida",
    "homestead, florida",
    "key west, florida",
    "key largo, florida",
    # Georgia
    "savannah, georgia",
    "brunswick, georgia",
    # South Carolina
    "charleston, south carolina",
    "myrtle beach, south carolina",
    "columbia, south carolina",
    # North Carolina
    "wilmington, north carolina",
    "jacksonville, north carolina",
    "fayetteville, north carolina",
    # Virginia
    "norfolk, virginia",
    "virginia beach, virginia",
    "richmond, virginia",
]

# ── Tor Check ─────────────────────────────────────────────────────────────────

def check_tor():
    """Verify Tor is running and the connection works before scraping."""
    print("[Tor] Checking Tor connection...")
    try:
        r = requests.get(
            "https://check.torproject.org/api/ip",
            proxies=TOR_PROXIES,
            timeout=15
        )
        data = r.json()
        if data.get("IsTor"):
            print(f"[Tor] Connected. Exit IP: {data.get('IP')}")
            return True
        else:
            print(f"[Tor] WARNING: Not routing through Tor. IP: {data.get('IP')}")
            return False
    except Exception as e:
        print(f"[Tor] Connection failed: {e}")
        print("[Tor] Make sure Tor is running: sudo systemctl start tor")
        return False


# ── Database Setup ────────────────────────────────────────────────────────────

def init_db():
    """Create the SQLite database and tables if they don't exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            phone           TEXT,
            ad_url          TEXT UNIQUE,
            title           TEXT,
            ad_text         TEXT,
            location        TEXT,
            posted_time     TEXT,
            scraped_at      TEXT,
            thumbnail_url   TEXT,
            thumbnail_path  TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_id       INTEGER,
            image_url   TEXT UNIQUE,
            image_path  TEXT,
            image_hash  TEXT,
            FOREIGN KEY (ad_id) REFERENCES ads(id)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_page(url, retries=3, delay=2):
    """Fetch a URL via Tor with retries and polite delay."""
    for attempt in range(retries):
        try:
            time.sleep(delay)
            response = requests.get(
                url,
                headers=HEADERS,
                proxies=TOR_PROXIES,
                timeout=20
            )
            if response.status_code == 200:
                # Catch block page
                if "has been blocked" in response.text:
                    print(f"  [!] IP blocked by site on attempt {attempt+1}. Retrying...")
                    time.sleep(5)
                    continue
                return response
            else:
                print(f"  [!] HTTP {response.status_code} for {url}")
        except Exception as e:
            print(f"  [!] Request error (attempt {attempt+1}): {e}")
    return None


def download_image(url, folder, prefix=""):
    """Download an image via Tor and return its local path and hash."""
    try:
        resp = requests.get(
            url,
            headers=HEADERS,
            proxies=TOR_PROXIES,
            timeout=20
        )
        if resp.status_code != 200:
            return None, None

        image_hash = hashlib.md5(resp.content).hexdigest()
        ext = url.split(".")[-1].split("?")[0][:4]
        filename = f"{prefix}{image_hash}.{ext}"
        filepath = os.path.join(folder, filename)

        if not os.path.exists(filepath):
            with open(filepath, "wb") as f:
                f.write(resp.content)

        return filepath, image_hash
    except Exception as e:
        print(f"  [!] Image download failed: {e}")
        return None, None


# ── Scraping Logic ────────────────────────────────────────────────────────────

def get_listing_urls(city):
    """Get all ad URLs from a city's listing page (handles pagination)."""
    ad_links = []
    page = 1

    while True:
        url = f"{BASE_URL}/index.php?keyword=&location={city}&page={page}"
        print(f"  [Listings] Fetching page {page} for '{city}'...")
        resp = get_page(url)
        if not resp:
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("div", class_="product-thumb")

        if not cards:
            print(f"  [Listings] No more listings found on page {page}.")
            break

        for card in cards:
            href = card.get("data-href")
            if href:
                full_url = urljoin(BASE_URL, href)
                ad_links.append(full_url)

        next_btn = soup.find("a", string=lambda t: t and "next" in t.lower())
        if not next_btn:
            break
        page += 1

    print(f"  [Listings] Found {len(ad_links)} ads in '{city}'.")
    return ad_links


def scrape_ad_page(ad_url, location, conn):
    """Scrape a single ad page and save to database."""
    c = conn.cursor()

    c.execute("SELECT id FROM ads WHERE ad_url = ?", (ad_url,))
    if c.fetchone():
        print(f"  [Skip] Already in database: {ad_url}")
        return

    resp = get_page(ad_url)
    if not resp:
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    phone = ad_url.rstrip("/").split("/")[-1]

    title_tag = soup.find("h1") or soup.find("h2") or soup.find("h3")
    title = title_tag.get_text(strip=True) if title_tag else ""

    ad_text = ""
    inner = soup.find("div", class_="product-inner")
    if inner:
        ad_text = inner.get_text(separator=" ", strip=True)

    time_tag = soup.find("span", class_="product-time")
    posted_time = time_tag.get_text(strip=True) if time_tag else ""

    thumb_tag = soup.find("header", class_="product-header")
    thumb_url = ""
    thumb_path = ""
    if thumb_tag:
        img = thumb_tag.find("img")
        if img and img.get("src"):
            thumb_url = urljoin(BASE_URL, img["src"])
            thumb_path, _ = download_image(thumb_url, IMAGE_DIR, prefix="thumb_")

    scraped_at = datetime.utcnow().isoformat()

    c.execute("""
        INSERT OR IGNORE INTO ads
            (phone, ad_url, title, ad_text, location, posted_time, scraped_at, thumbnail_url, thumbnail_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (phone, ad_url, title, ad_text, location, posted_time, scraped_at, thumb_url, thumb_path))
    conn.commit()
    ad_id = c.lastrowid

    image_count = 0
    main_col = soup.find("div", class_="col-md-9")
    if main_col:
        row_wrap = main_col.find("div", class_="row-wrap")
        if row_wrap:
            imgs = row_wrap.find_all("img")
            for img in imgs:
                src = img.get("src") or img.get("data-src")
                if src:
                    img_url = urljoin(BASE_URL, src)
                    img_path, img_hash = download_image(img_url, IMAGE_DIR, prefix="ad_")
                    if img_path:
                        c.execute("""
                            INSERT OR IGNORE INTO images (ad_id, image_url, image_path, image_hash)
                            VALUES (?, ?, ?, ?)
                        """, (ad_id, img_url, img_path, img_hash))
                        image_count += 1

    conn.commit()
    print(f"  [+] Saved: {phone} | {image_count} images | '{title[:40]}'")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(cities=None):
    if cities is None:
        cities = CITIES

    if not check_tor():
        print("[!] Aborting — Tor not confirmed. Start Tor and retry.")
        return

    init_db()
    conn = sqlite3.connect(DB_PATH)

    for city in cities:
        print(f"\n[City] Scraping: {city}")
        ad_urls = get_listing_urls(city)
        for ad_url in ad_urls:
            scrape_ad_page(ad_url, city, conn)

    conn.close()
    print("\n[Done] Scrape complete.")
    print(f"[Done] Data saved to: {os.path.abspath(OUTPUT_DIR)}")


if __name__ == "__main__":
    # Single city test:
    # run(cities=["orlando, florida"])
    # Full corridor run:
    run()
