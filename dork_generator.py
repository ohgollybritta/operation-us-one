"""
Google Dork Generator
Anti-human trafficking OSINT tool.

Generates targeted Google dork search URLs for a phone number,
name, or both. Open the URLs in your browser — no automation,
no accounts, no flags.

Usage:
    python3 dork_generator.py --phone 352-221-3978
    python3 dork_generator.py --name "Stacie Romano"
    python3 dork_generator.py --phone 352-221-3978 --name "Stacie Romano"
    python3 dork_generator.py --all   (runs against every phone in database)
"""

import argparse
import sqlite3
import urllib.parse

DB_PATH = "osint_data/ads.db"

# ── Dork Templates ────────────────────────────────────────────────────────────

def phone_dorks(phone):
    """Generate dork URLs for a phone number."""
    p = phone.strip()
    p_clean = p.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    p_dots = p.replace("-", ".")

    queries = [
        # Social media
        f'"{p}" site:facebook.com',
        f'"{p}" site:instagram.com',
        f'"{p}" site:twitter.com',
        f'"{p}" site:tiktok.com',
        f'"{p}" site:snapchat.com',
        f'"{p}" site:linkedin.com',
        # WhatsApp
        f'site:wa.me "{p_clean}"',
        f'"wa.me/{p_clean}"',
        # Cross-platform escort
        f'"{p}" -site:callescort.org escort',
        f'"{p}" skipthegames OR megapersonals OR bedpage OR eros',
        # General identity
        f'"{p}"',
        f'"{p_dots}"',
        # Phone lookup
        f'"{p}" name',
        f'"{p}" profile',
    ]
    return queries


def name_dorks(name):
    """Generate dork URLs for a name."""
    n = name.strip()

    queries = [
        # Social media
        f'"{n}" site:facebook.com',
        f'"{n}" site:instagram.com',
        f'"{n}" site:twitter.com',
        f'"{n}" site:tiktok.com',
        f'"{n}" site:linkedin.com',
        # Location based
        f'"{n}" Florida',
        f'"{n}" Orlando',
        f'"{n}" Miami',
        f'"{n}" Tampa',
        # General
        f'"{n}"',
        f'"{n}" escort',
        f'"{n}" missing',
    ]
    return queries


def combined_dorks(phone, name):
    """Generate dork URLs combining phone and name."""
    p = phone.strip()
    n = name.strip()

    queries = [
        f'"{p}" "{n}"',
        f'"{n}" "{p}" site:facebook.com',
        f'"{n}" Florida "{p}"',
        f'"{p}" OR "{n}" escort',
    ]
    return queries


def build_url(query):
    """Build a Google search URL from a query string."""
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.google.com/search?q={encoded}"


def print_dorks(queries, label):
    """Print dork queries and URLs."""
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")
    for q in queries:
        url = build_url(q)
        print(f"\n  Query: {q}")
        print(f"  URL:   {url}")


def get_all_phones():
    """Pull all phone numbers and locations from database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT phone, location, ad_url, posted_time FROM ads ORDER BY location")
    rows = c.fetchall()
    conn.close()
    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Google Dork Generator — OSINT tool")
    parser.add_argument("--phone", help="Phone number to search (e.g. 352-221-3978)")
    parser.add_argument("--name", help="Name to search (e.g. 'Stacie Romano')")
    parser.add_argument("--all", action="store_true", help="Generate dorks for all phones in database")
    args = parser.parse_args()

    if args.all:
        phones = get_all_phones()
        print(f"\n[*] Generating dorks for {len(phones)} phone numbers in database...\n")
        for phone, location, ad_url, posted_time in phones:
            print(f"\n{'#'*65}")
            print(f"  Phone: {phone} | Location: {location}")
            print(f"  Ad:    {ad_url}")
            print(f"  Posted: {posted_time}")
            print_dorks(phone_dorks(phone), f"PHONE DORKS: {phone}")
        return

    if not args.phone and not args.name:
        parser.print_help()
        return

    if args.phone:
        print_dorks(phone_dorks(args.phone), f"PHONE DORKS: {args.phone}")

    if args.name:
        print_dorks(name_dorks(args.name), f"NAME DORKS: {args.name}")

    if args.phone and args.name:
        print_dorks(combined_dorks(args.phone, args.name), f"COMBINED DORKS: {args.phone} + {args.name}")

    print(f"\n{'='*65}")
    print("  Copy any URL above and paste into your browser.")
    print("  No account needed. No automation. Just search.")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
