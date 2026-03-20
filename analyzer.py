"""
OSINT Ad Analyzer
Anti-human trafficking research tool.
Reads collected ads from ads.db, extracts names/ages/phones,
and flags profiles of interest (age <= 25 or no age found).
"""

import sqlite3
import re
import os
import csv
from datetime import datetime

DB_PATH = "osint_data/ads.db"
OUTPUT_DIR = "osint_data/reports"

# ── Name / Age / Phone Extraction ────────────────────────────────────────────

def extract_age(text):
    """
    Try to pull an age from ad text.
    Returns int or None.
    """
    if not text:
        return None

    patterns = [
        r'\bage[:\s]+(\d{2})\b',                          # "Age: 22", "age 22"
        r'\b(\d{2})\s*(?:years?\s*old|yo|yrs?)\b',        # "22 years old", "22yo"
        r"(?:i'?m|i am|im)\s+(\d{2})\b",                  # "I'm 22", "im 22"
        r'\b(\d{2})\s*(?:year|yr)\b',                      # "22 year"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            age = int(match.group(1))
            if 13 <= age <= 60:  # sanity check
                return age

    return None


def extract_names(text):
    """
    Try to pull a name or nickname from ad text.
    Returns list of candidate strings.
    """
    if not text:
        return []

    names = []

    # "Hi I'm Sofia", "call me Jasmine", "My name is Candy"
    intro_match = re.findall(
        r"(?:hi,?\s*i'?m|call me|my name is|i go by|known as)\s+([A-Z][a-z]{2,15})",
        text, re.IGNORECASE
    )
    names.extend(intro_match)

    # First capitalized word at the start of text (often the name/alias)
    start_match = re.match(r'^([A-Z][a-z]{2,15})', text.strip())
    if start_match:
        names.append(start_match.group(1))

    # Names wrapped in quotes: "Mia", 'Destiny'
    quoted = re.findall(r'["\']([A-Z][a-z]{2,15})["\']', text)
    names.extend(quoted)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            unique.append(n)

    return unique


def extract_phone(text, url_phone=None):
    """
    Extract phone from ad text. Falls back to the phone pulled from URL.
    Returns string or None.
    """
    if text:
        match = re.search(
            r'(\(?\d{3}\)?[\s\-\.\u2010\u2011\u2012\u2013\u2014]?\d{3}[\s\-\.]?\d{4})',
            text
        )
        if match:
            return re.sub(r'[^\d]', '', match.group(1))  # digits only

    return re.sub(r'[^\d]', '', url_phone) if url_phone else None


# ── Flag Logic ────────────────────────────────────────────────────────────────

def is_person_of_interest(age):
    """
    Flag if age <= 25 OR age couldn't be determined.
    """
    if age is None:
        return True, "no_age_found"
    if age <= 17:
        return True, "minor_indicated"
    if age <= 25:
        return True, "age_25_or_under"
    return False, None


# ── Main Analysis ─────────────────────────────────────────────────────────────

def analyze(db_path=DB_PATH):
    if not os.path.exists(db_path):
        print(f"[!] Database not found: {db_path}")
        print("    Run scraper.py first to collect data.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM ads")
    total = c.fetchone()[0]
    print(f"[DB] Total ads in database: {total}")

    if total == 0:
        print("[!] No ads found. The scraper may not have collected data yet.")
        print("    Check that the site is reachable and try running scraper.py on one city first.")
        conn.close()
        return

    c.execute("SELECT * FROM ads ORDER BY scraped_at DESC")
    rows = c.fetchall()

    results = []
    poi_count = 0
    minor_count = 0

    for row in rows:
        ad_text = row["ad_text"] or ""
        phone_from_url = row["phone"] or ""

        age = extract_age(ad_text)
        names = extract_names(ad_text)
        phone = extract_phone(ad_text, phone_from_url)
        flagged, reason = is_person_of_interest(age)

        if flagged:
            poi_count += 1
        if reason == "minor_indicated":
            minor_count += 1

        results.append({
            "id": row["id"],
            "phone": phone or phone_from_url,
            "names_found": ", ".join(names) if names else "",
            "age_found": age,
            "flagged": flagged,
            "flag_reason": reason or "",
            "location": row["location"] or "",
            "posted_time": row["posted_time"] or "",
            "ad_url": row["ad_url"] or "",
            "thumbnail_path": row["thumbnail_path"] or "",
            "ad_text_preview": ad_text[:200].replace("\n", " "),
        })

    conn.close()

    # ── Print Summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ANALYSIS SUMMARY")
    print(f"{'='*60}")
    print(f"  Total ads analyzed:        {total}")
    print(f"  Persons of interest (POI): {poi_count}  ({poi_count/total*100:.1f}%)")
    print(f"  Minor age indicated:       {minor_count}")
    print(f"{'='*60}\n")

    # ── Write full CSV ────────────────────────────────────────────────────────
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    all_csv = os.path.join(OUTPUT_DIR, f"all_ads_{timestamp}.csv")
    poi_csv = os.path.join(OUTPUT_DIR, f"poi_flagged_{timestamp}.csv")

    fieldnames = [
        "id", "phone", "names_found", "age_found", "flagged", "flag_reason",
        "location", "posted_time", "ad_url", "thumbnail_path", "ad_text_preview"
    ]

    with open(all_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # ── Write POI-only CSV ────────────────────────────────────────────────────
    poi_results = [r for r in results if r["flagged"]]
    with open(poi_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(poi_results)

    print(f"[Output] All ads CSV:    {os.path.abspath(all_csv)}")
    print(f"[Output] POI flagged CSV: {os.path.abspath(poi_csv)}")
    print(f"\n[Done] Analysis complete.")

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    analyze()
