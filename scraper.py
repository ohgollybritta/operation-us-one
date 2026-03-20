"""
callescort.org OSINT Scraper
For anti-human trafficking research purposes only.
Collects publicly posted ad data: text, images, phone numbers, timestamps.
Filters for ads claiming age 25 or younger.
Stores everything in a local SQLite database.
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import os
import time
import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin

# ── Configuration ────────────────────────────────────────────────────────────

BASE_URL = "https://callescort.org"
OUTPUT_DIR = "osint_data"
IMAGE_DIR = os.path.join(OUTPUT_DIR, "images")
DB_PATH = os.path.join(OUTPUT_DIR, "ads.db")

MAX_AGE = 25  # Only collect ads claiming this age or younger

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

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

# ── Age Extraction ────────────────────────────────────────────────────────────

def extract_age(text):
    """
    Extract age from ad text. Returns integer age or None.
    Catches patterns like:
      Age: 22 | age22 | 22yo | 22 y/o | im 22 | I'm 22 | 22 years
    """
    if not text:
        return None

    patterns = [
        r'\bage[:\s]*(\d{1,2})\b',       # Age: 22 or age22
        r'\b(\d{1,2})\s*yo\b',            # 22yo
        r'\b(\d{1,2})\s*y/?o\b',          # 22 y/o
        r'\bim\s+(\d{1,2})\b',            # im 22
        r"\bi'm\s+(\d{1,2})\b",           # i'm 22
        r'\b(\d{1,2})\s*years?\s*old\b',  # 22 years old
        r'\byear\s*(\d{1,2})\b',          # year 22
    ]

    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            age = int(match.group(1))
            if 14 <= age <= 60:  # Sanity check
                return age
    return None


def is_age_of_interest(text):
    """Return True if ad claims age <= MAX_AGE or has no age listed."""
    age = extract_age(text)
    if age is None:
        return True  # No age listed — include for manual review
    return age <= MAX_AGE


# ── Database Setup ────────────────────────────────────────────────────────────

def init_db():
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
            thumbnail_path  TEXT,
            claimed_age     INTEGER
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
    for attempt in range(retries):
        try:
            time.sleep(delay)
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                return response
            else:
                print(f"  [!] HTTP {response.status_code} for {url}")
        except Exception as e:
            print(f"  [!] Request error (attempt {attempt+1}): {e}")
    return None


def download_image(url, folder, prefix=""):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
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
            print(f"  [Listings] No more listings on page {page}.")
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

    # ── Age filter ───────────────────────────────────────────────────────────
    claimed_age = extract_age(ad_text) or extract_age(title)

    if claimed_age and claimed_age > MAX_AGE:
        print(f"  [Skip] Age {claimed_age} > {MAX_AGE}: {phone}")
        return

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
            (phone, ad_url, title, ad_text, location, posted_time, scraped_at,
             thumbnail_url, thumbnail_path, claimed_age)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (phone, ad_url, title, ad_text, location, posted_time, scraped_at,
          thumb_url, thumb_path, claimed_age))
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
    age_str = f"age {claimed_age}" if claimed_age else "age unknown"
    print(f"  [+] Saved: {phone} | {age_str} | {image_count} images | '{title[:40]}'")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(cities=None):
    if cities is None:
        cities = CITIES

    init_db()
    conn = sqlite3.connect(DB_PATH)

    skipped_age = 0
    saved = 0

    for city in cities:
        print(f"\n[City] Scraping: {city}")
        ad_urls = get_listing_urls(city)

        for ad_url in ad_urls:
            scrape_ad_page(ad_url, city, conn)

    conn.close()
    print("\n[Done] Scrape complete.")
    print(f"[Done] Only ads claiming age {MAX_AGE} or younger were saved.")
    print(f"[Done] Data saved to: {os.path.abspath(OUTPUT_DIR)}")


if __name__ == "__main__":
    run()
