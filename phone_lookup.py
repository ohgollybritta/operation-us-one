"""
Phone Number Intelligence Lookup
Anti-human trafficking OSINT tool.

Scrapes validnumber.com for carrier, location, and type data
for every phone number in the database. Flags mismatches and
known trafficking hub registrations.

Usage:
    python3 phone_lookup.py              # Look up all phones in database
    python3 phone_lookup.py 352-221-3978 # Look up single number
"""

import requests
import sqlite3
import sys
import time
from bs4 import BeautifulSoup
from datetime import datetime

DB_PATH = "osint_data/ads.db"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Known Trafficking Hubs ────────────────────────────────────────────────────
# Cities known as major trafficking corridors or hubs.
# A phone registered here but posted elsewhere = strong red flag.

TRAFFICKING_HUBS = {
    # Midwest corridor
    "saint louis":      "I-44/I-70 Midwest hub",
    "st. louis":        "I-44/I-70 Midwest hub",
    "st louis":         "I-44/I-70 Midwest hub",
    "kansas city":      "I-70 Midwest hub",
    "chicago":          "I-90/I-94 Midwest hub",
    "indianapolis":     "I-65/I-70 crossroads hub",
    "cincinnati":       "I-71/I-75 Ohio hub",
    "cleveland":        "I-90 Ohio hub",
    "columbus":         "I-70/I-71 Ohio hub",
    "detroit":          "I-75/I-94 Michigan hub",
    # Southeast corridor
    "atlanta":          "I-75/I-85 Southeast hub",
    "charlotte":        "I-85/I-77 Southeast hub",
    "memphis":          "I-40/I-55 Mid-South hub",
    "nashville":        "I-40/I-65 Mid-South hub",
    "new orleans":      "I-10 Gulf Coast hub",
    "houston":          "I-10/I-45 Gulf Coast hub",
    "dallas":           "I-35/I-20 Texas hub",
    # East Coast corridor
    "new york":         "I-95 Northeast hub",
    "newark":           "I-95 Northeast hub",
    "philadelphia":     "I-95 Northeast hub",
    "baltimore":        "I-95 Mid-Atlantic hub",
    "washington":       "I-95 Mid-Atlantic hub",
    "richmond":         "I-95 Mid-Atlantic hub",
    # Florida
    "miami":            "I-95/I-75 Florida hub",
    "orlando":          "I-4 Florida hub",
    "tampa":            "I-75/I-4 Florida hub",
    "jacksonville":     "I-95/I-10 Florida hub",
    # Southwest
    "phoenix":          "I-10/I-17 Southwest hub",
    "tucson":           "I-10 Southwest border hub",
    "el paso":          "I-10 Border hub",
    "san antonio":      "I-35 Border corridor hub",
    "las vegas":        "I-15 Nevada hub",
    # West Coast
    "los angeles":      "I-5/I-10 West Coast hub",
    "san diego":        "I-5 Border hub",
    "portland":         "I-5 Pacific Northwest hub",
    "seattle":          "I-5 Pacific Northwest hub",
}

# ── State abbreviation map ────────────────────────────────────────────────────

STATE_MAP = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york",
    "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming", "DC": "washington dc",
}

# ── Database ──────────────────────────────────────────────────────────────────

def init_lookup_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS phone_intel (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            phone           TEXT UNIQUE,
            carrier         TEXT,
            phone_type      TEXT,
            city            TEXT,
            state           TEXT,
            zip_code        TEXT,
            county          TEXT,
            is_hub          INTEGER DEFAULT 0,
            hub_note        TEXT,
            raw_text        TEXT,
            looked_up_at    TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_all_phones():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT phone, location FROM ads ORDER BY location")
    rows = c.fetchall()
    conn.close()
    return rows


def already_looked_up(phone):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM phone_intel WHERE phone = ?", (phone,))
    result = c.fetchone()
    conn.close()
    return result is not None


def save_intel(phone, carrier, phone_type, city, state, zip_code, county,
               is_hub, hub_note, raw_text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO phone_intel
            (phone, carrier, phone_type, city, state, zip_code, county,
             is_hub, hub_note, raw_text, looked_up_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (phone, carrier, phone_type, city, state, zip_code, county,
          is_hub, hub_note, raw_text, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


# ── Scraping ──────────────────────────────────────────────────────────────────

def lookup_phone(phone):
    digits = ''.join(filter(str.isdigit, phone))
    url = f"https://validnumber.com/phone-number/{digits}/"

    try:
        time.sleep(2)
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"  [!] HTTP {r.status_code} for {phone}")
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        carrier = ""
        phone_type = ""
        city = ""
        state = ""
        zip_code = ""
        county = ""

        if "Carrier:" in text:
            carrier = text.split("Carrier:")[1].split("UID:")[0].strip()
        if "Type:" in text:
            phone_type = text.split("Type:")[1].split("City")[0].strip()
        if "City, State:" in text:
            city_state = text.split("City, State:")[1].split("County")[0].strip()
            parts = city_state.split(",")
            if len(parts) >= 2:
                city = parts[0].strip()
                state = parts[1].strip()
        if "ZIP Code:" in text:
            zip_code = text.split("ZIP Code:")[1].split("Carrier")[0].strip()
        if "County/Parish:" in text:
            county = text.split("County/Parish:")[1].split("ZIP")[0].strip()

        # Check if registered city is a known trafficking hub
        is_hub = 0
        hub_note = ""
        city_lower = city.lower()
        for hub_city, hub_desc in TRAFFICKING_HUBS.items():
            if hub_city in city_lower:
                is_hub = 1
                hub_note = hub_desc
                break

        return {
            "carrier": carrier[:100],
            "phone_type": phone_type[:50],
            "city": city[:100],
            "state": state[:50],
            "zip_code": zip_code[:20],
            "county": county[:100],
            "is_hub": is_hub,
            "hub_note": hub_note,
            "raw_text": text[:500]
        }

    except Exception as e:
        print(f"  [!] Error looking up {phone}: {e}")
        return None


# ── Output ────────────────────────────────────────────────────────────────────

def print_intel(phone, ad_location, intel):
    print(f"\n  Phone:      {phone}")
    print(f"  Ad posted:  {ad_location}")
    print(f"  Type:       {intel['phone_type']}")
    print(f"  Carrier:    {intel['carrier']}")
    print(f"  Registered: {intel['city']}, {intel['state']} {intel['zip_code']}")

    if intel['is_hub']:
        print(f"  [***] TRAFFICKING HUB: {intel['hub_note']}")

    registered_state = STATE_MAP.get(intel['state'].strip().upper() if intel['state'] else "", "").lower()
    if registered_state and ad_location and registered_state not in ad_location.lower():
        print(f"  [!!!] LOCATION MISMATCH: Registered in {intel['state']} — posted in {ad_location}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run_single(phone):
    print(f"\n[*] Looking up: {phone}")
    intel = lookup_phone(phone)
    if intel:
        print_intel(phone, "unknown", intel)
        save_intel(phone, intel['carrier'], intel['phone_type'],
                   intel['city'], intel['state'], intel['zip_code'],
                   intel['county'], intel['is_hub'], intel['hub_note'],
                   intel['raw_text'])
    else:
        print("  [!] No data returned.")


def run_all():
    init_lookup_table()
    phones = get_all_phones()
    print(f"\n[*] Looking up {len(phones)} phone numbers...\n")
    print("=" * 65)

    done = 0
    skipped = 0
    mismatches = []
    hubs = []

    for phone, ad_location in phones:
        if already_looked_up(phone):
            skipped += 1
            continue

        intel = lookup_phone(phone)
        if not intel:
            continue

        print_intel(phone, ad_location, intel)
        save_intel(phone, intel['carrier'], intel['phone_type'],
                   intel['city'], intel['state'], intel['zip_code'],
                   intel['county'], intel['is_hub'], intel['hub_note'],
                   intel['raw_text'])

        registered_state = STATE_MAP.get(
            intel['state'].strip().upper() if intel['state'] else "", "").lower()

        if registered_state and ad_location and registered_state not in ad_location.lower():
            mismatches.append({
                "phone": phone,
                "posted_in": ad_location,
                "registered_in": f"{intel['city']}, {intel['state']}",
                "carrier": intel['carrier']
            })

        if intel['is_hub']:
            hubs.append({
                "phone": phone,
                "posted_in": ad_location,
                "registered_in": f"{intel['city']}, {intel['state']}",
                "hub_note": intel['hub_note']
            })

        done += 1

    print(f"\n{'='*65}")
    print(f"  COMPLETE: {done} looked up | {skipped} already cached")
    print(f"{'='*65}")

    if hubs:
        print(f"\n  [***] TRAFFICKING HUB REGISTRATIONS: {len(hubs)}")
        print(f"  {'='*61}")
        for h in hubs:
            print(f"\n  Phone:        {h['phone']}")
            print(f"  Posted in:    {h['posted_in']}")
            print(f"  Registered:   {h['registered_in']}")
            print(f"  Hub type:     {h['hub_note']}")

    if mismatches:
        print(f"\n  [!!!] LOCATION MISMATCHES: {len(mismatches)}")
        print(f"  {'='*61}")
        for m in mismatches:
            print(f"\n  Phone:        {m['phone']}")
            print(f"  Posted in:    {m['posted_in']}")
            print(f"  Registered:   {m['registered_in']}")
            print(f"  Carrier:      {m['carrier']}")

    print()


if __name__ == "__main__":
    init_lookup_table()
    if len(sys.argv) > 1:
        run_single(sys.argv[1])
    else:
        run_all()
