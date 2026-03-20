# Operation US One

OSINT intelligence tools for anti-human trafficking analysts. Built to identify, document, and support the investigation of trafficking activity along the US-1 corridor (East Coast, southern region).

> **Legal & Ethical Notice:** All data collected by these tools is publicly posted information. This project is intended strictly for anti-human trafficking research and to support law enforcement referrals. Do not use these tools for any other purpose.

---

## Overview

Trafficking operations along the US-1 corridor frequently use online escort advertising platforms to post victims. These ads contain valuable intelligence — phone numbers, photos, posting patterns, location inconsistencies — that can be correlated across platforms and over time to build investigative leads.

This toolkit automates the collection and analysis of that publicly posted data, extracting structured intelligence from unstructured ad text and images.

**Current focus corridor:**
Florida → Georgia → South Carolina → North Carolina → Virginia

---

## Setup

### System dependencies
```bash
sudo apt install tor cmake build-essential libopenblas-dev liblapack-dev -y
sudo systemctl enable tor
sudo systemctl start tor
```

### Python dependencies
```bash
pip3 install requests beautifulsoup4 face_recognition --break-system-packages
pip3 install requests[socks] --break-system-packages
```

---

## Tools

### `scraper.py`
Collects all escort ads, images, phone numbers, and timestamps from callescort.org for configured cities. No filters — collects everything for downstream analysis.

```bash
python3 scraper.py
```

> **Note:** Your home IP may be blocked by the target site. Use `scraper-tor.py` instead.

---

### `scraper-tor.py`
Identical to `scraper.py` but routes all traffic through Tor to bypass IP blocks. Verifies Tor connectivity before scraping begins.

```bash
# Make sure Tor is running first
sudo systemctl start tor

python3 scraper-tor.py
```

To scrape a single city for testing:
```python
from scraper-tor import run
run(cities=["orlando, florida"])
```

---

### `analyzer.py`
Reads collected ads from the database and extracts structured intelligence: names/aliases, ages, and phone numbers from ad text. Flags profiles of interest based on age indicators.

**Flag criteria:**
- Age 25 or under → `age_25_or_under`
- Age 17 or under → `minor_indicated`
- No age found in ad → `no_age_found`

```bash
python3 analyzer.py
```

Outputs two CSVs to `osint_data/reports/`:
- `all_ads_[timestamp].csv` — all ads with extracted fields
- `poi_flagged_[timestamp].csv` — persons of interest only

---

### `face_matcher.py`
Searches all collected ad images for faces matching a query image. Useful for identifying the same individual appearing across multiple ads, cities, or time periods.

```bash
python3 face_matcher.py path/to/image.jpg
```

---

### `area_code_detector.py`
Flags phone numbers whose area code origin does not match the city where the ad was posted. A phone number from rural Georgia posting in Miami is a strong indicator of trafficking movement.

```bash
python3 area_code_detector.py
```

---

### `phone_lookup.py`
Looks up carrier, registered location, and trafficking hub flags for collected phone numbers. Cross-references numbers against known high-trafficking area codes.

```bash
python3 phone_lookup.py              # All numbers in database
python3 phone_lookup.py 000-000-0000 # Single number lookup
```

---

### `dork_generator.py`
Generates targeted Google dork search URLs for phone numbers and names found in ads. Used to surface the same individuals across other platforms — social media, other ad sites, background check aggregators.

```bash
python3 dork_generator.py --phone 000-000-0000
python3 dork_generator.py --name "alias"
python3 dork_generator.py --phone 000-000-0000 --name "alias"
python3 dork_generator.py --all        # Run dorks for every entry in database
```

---

## Database

All collected data is stored locally in SQLite.

| Path | Contents |
|---|---|
| `osint_data/ads.db` | Ad text, phone numbers, URLs, timestamps, locations |
| `osint_data/images/` | Downloaded ad images (named by MD5 hash) |
| `osint_data/reports/` | CSV exports from analyzer.py |

The `osint_data/` directory is excluded from version control via `.gitignore`. **Never commit collected data to this repository.**

---

## Workflow

```
scraper-tor.py        ←  collect raw ads + images
      ↓
analyzer.py           ←  extract names, ages, phones / flag POIs
      ↓
area_code_detector.py ←  flag geographic inconsistencies
phone_lookup.py       ←  enrich phone number data
dork_generator.py     ←  pivot to open web / other platforms
face_matcher.py       ←  link identities across ads via photos
```

---

## Roadmap

- [ ] Multi-platform support (beyond callescort.org)
- [ ] Automated Tor circuit rotation between cities
- [ ] Timeline visualization — track individual phone numbers over time
- [ ] Export to law enforcement referral format (NCMEC CyberTipline compatible)
- [ ] Integration with known trafficking phone number databases

---

## Author

Designed by [@ohgollybritta](https://github.com/ohgollybritta)

OSINT analyst — anti-human trafficking / ICAC research
