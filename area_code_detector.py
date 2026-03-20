"""
Area Code Mismatch Detector
Anti-human trafficking OSINT tool.

Usage:
    python3 area_code_detector.py
"""

import sqlite3
import math

DB_PATH = "osint_data/ads.db"

AREA_CODES = {
    "239": ("Southwest Florida", 26.1420, -81.7948),
    "305": ("Miami, Florida", 25.7617, -80.1918),
    "321": ("Orlando/Brevard, Florida", 28.5383, -81.3792),
    "352": ("Gainesville, Florida", 29.6516, -82.3248),
    "386": ("Daytona Beach, Florida", 29.2108, -81.0228),
    "407": ("Orlando, Florida", 28.5383, -81.3792),
    "561": ("West Palm Beach, Florida", 26.7153, -80.0534),
    "689": ("Orlando, Florida", 28.5383, -81.3792),
    "727": ("St. Petersburg, Florida", 27.7676, -82.6403),
    "754": ("Fort Lauderdale, Florida", 26.1224, -80.1373),
    "772": ("Fort Pierce, Florida", 27.4467, -80.3256),
    "786": ("Miami, Florida", 25.7617, -80.1918),
    "813": ("Tampa, Florida", 27.9506, -82.4572),
    "850": ("Tallahassee, Florida", 30.4518, -84.2807),
    "863": ("Lakeland, Florida", 28.0395, -81.9498),
    "904": ("Jacksonville, Florida", 30.3322, -81.6557),
    "941": ("Sarasota, Florida", 27.3364, -82.5307),
    "954": ("Fort Lauderdale, Florida", 26.1224, -80.1373),
    "229": ("Albany, Georgia", 31.5785, -84.1557),
    "404": ("Atlanta, Georgia", 33.7490, -84.3880),
    "470": ("Atlanta, Georgia", 33.7490, -84.3880),
    "478": ("Macon, Georgia", 32.8407, -83.6324),
    "678": ("Atlanta, Georgia", 33.7490, -84.3880),
    "706": ("Augusta, Georgia", 33.4735, -82.0105),
    "762": ("Augusta, Georgia", 33.4735, -82.0105),
    "770": ("Atlanta suburbs, Georgia", 33.7490, -84.3880),
    "912": ("Savannah, Georgia", 32.0835, -81.0998),
    "803": ("Columbia, South Carolina", 34.0007, -81.0348),
    "843": ("Charleston, South Carolina", 32.7765, -79.9311),
    "864": ("Greenville, South Carolina", 34.8526, -82.3940),
    "252": ("Greenville, North Carolina", 35.6127, -77.3664),
    "336": ("Greensboro, North Carolina", 36.0726, -79.7920),
    "704": ("Charlotte, North Carolina", 35.2271, -80.8431),
    "828": ("Asheville, North Carolina", 35.5951, -82.5515),
    "910": ("Fayetteville, North Carolina", 35.0527, -78.8784),
    "919": ("Raleigh, North Carolina", 35.7796, -78.6382),
    "980": ("Charlotte, North Carolina", 35.2271, -80.8431),
    "276": ("Bristol, Virginia", 36.5957, -82.1882),
    "434": ("Charlottesville, Virginia", 38.0293, -78.4767),
    "540": ("Roanoke, Virginia", 37.2710, -79.9414),
    "571": ("Northern Virginia", 38.8816, -77.1084),
    "703": ("Northern Virginia", 38.8816, -77.1084),
    "757": ("Norfolk, Virginia", 36.8508, -76.2859),
    "804": ("Richmond, Virginia", 37.5407, -77.4360),
    "212": ("Manhattan, New York", 40.7128, -74.0060),
    "315": ("Syracuse, New York", 43.0481, -76.1474),
    "347": ("New York City", 40.7128, -74.0060),
    "516": ("Nassau County, New York", 40.7282, -73.7949),
    "518": ("Albany, New York", 42.6526, -73.7562),
    "585": ("Rochester, New York", 43.1566, -77.6088),
    "631": ("Suffolk County, New York", 40.9176, -72.6673),
    "646": ("Manhattan, New York", 40.7128, -74.0060),
    "716": ("Buffalo, New York", 42.8864, -78.8784),
    "718": ("New York City boroughs", 40.7128, -74.0060),
    "845": ("Hudson Valley, New York", 41.7004, -74.0060),
    "914": ("Westchester, New York", 41.0534, -73.7629),
    "917": ("New York City", 40.7128, -74.0060),
    "929": ("New York City", 40.7128, -74.0060),
    "201": ("Jersey City, New Jersey", 40.7178, -74.0431),
    "609": ("Trenton, New Jersey", 40.2171, -74.7429),
    "732": ("Edison, New Jersey", 40.5188, -74.4121),
    "856": ("Camden, New Jersey", 39.9259, -75.1196),
    "862": ("Newark, New Jersey", 40.7357, -74.1724),
    "908": ("Elizabeth, New Jersey", 40.6640, -74.2107),
    "973": ("Newark, New Jersey", 40.7357, -74.1724),
    "215": ("Philadelphia, Pennsylvania", 39.9526, -75.1652),
    "267": ("Philadelphia, Pennsylvania", 39.9526, -75.1652),
    "412": ("Pittsburgh, Pennsylvania", 40.4406, -79.9959),
    "484": ("Allentown, Pennsylvania", 40.6084, -75.4902),
    "570": ("Scranton, Pennsylvania", 41.4090, -75.6624),
    "610": ("Allentown, Pennsylvania", 40.6084, -75.4902),
    "717": ("Harrisburg, Pennsylvania", 40.2732, -76.8867),
    "814": ("Erie, Pennsylvania", 42.1292, -80.0851),
    "240": ("Rockville, Maryland", 39.0840, -77.1528),
    "301": ("Rockville, Maryland", 39.0840, -77.1528),
    "410": ("Baltimore, Maryland", 39.2904, -76.6122),
    "443": ("Baltimore, Maryland", 39.2904, -76.6122),
    "202": ("Washington, DC", 38.9072, -77.0369),
    "314": ("Saint Louis, Missouri", 38.6270, -90.1994),
    "816": ("Kansas City, Missouri", 39.0997, -94.5786),
    "812": ("Southern Indiana", 38.5201, -85.7500),
    "317": ("Indianapolis, Indiana", 39.7684, -86.1581),
    "312": ("Chicago, Illinois", 41.8781, -87.6298),
    "773": ("Chicago, Illinois", 41.8781, -87.6298),
}

CITY_COORDS = {
    "orlando, florida": (28.5383, -81.3792),
    "miami, florida": (25.7617, -80.1918),
    "tampa, florida": (27.9506, -82.4572),
    "jacksonville, florida": (30.3322, -81.6557),
    "fort lauderdale, florida": (26.1224, -80.1373),
    "west palm beach, florida": (26.7153, -80.0534),
    "daytona beach, florida": (29.2108, -81.0228),
    "fort pierce, florida": (27.4467, -80.3256),
    "melbourne, florida": (28.0836, -80.6081),
    "homestead, florida": (25.4687, -80.4776),
    "key west, florida": (24.5551, -81.7800),
    "key largo, florida": (25.0865, -80.4473),
    "savannah, georgia": (32.0835, -81.0998),
    "brunswick, georgia": (31.1499, -81.4915),
    "charleston, south carolina": (32.7765, -79.9311),
    "myrtle beach, south carolina": (33.6891, -78.8867),
    "columbia, south carolina": (34.0007, -81.0348),
    "wilmington, north carolina": (34.2257, -77.9447),
    "jacksonville, north carolina": (34.7540, -77.4302),
    "fayetteville, north carolina": (35.0527, -78.8784),
    "norfolk, virginia": (36.8508, -76.2859),
    "virginia beach, virginia": (36.8529, -75.9780),
    "richmond, virginia": (37.5407, -77.4360),
}

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def get_area_code(phone):
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) >= 3:
        return digits[:3]
    return None

def get_all_ads():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT phone, location, ad_url, posted_time FROM ads")
    rows = c.fetchall()
    conn.close()
    return rows

def run():
    ads = get_all_ads()
    print(f"\n[*] Analyzing {len(ads)} ads for area code mismatches...\n")
    mismatches = []
    unknown = []

    for phone, location, ad_url, posted_time in ads:
        area_code = get_area_code(phone)
        if not area_code:
            continue
        ac_info = AREA_CODES.get(area_code)
        city_coords = CITY_COORDS.get(location.lower() if location else "")
        if not ac_info:
            unknown.append((phone, area_code, location))
            continue
        ac_name, ac_lat, ac_lon = ac_info
        if city_coords:
            city_lat, city_lon = city_coords
            distance = haversine(ac_lat, ac_lon, city_lat, city_lon)
            if distance > 100:
                mismatches.append({
                    "phone": phone, "posted_in": location,
                    "area_code": area_code, "ac_origin": ac_name,
                    "distance_miles": round(distance),
                    "ad_url": ad_url, "posted_time": posted_time
                })

    mismatches.sort(key=lambda x: x["distance_miles"], reverse=True)

    print("=" * 65)
    print(f"  AREA CODE MISMATCH REPORT")
    print(f"  {len(mismatches)} mismatches | {len(unknown)} unknown area codes")
    print("=" * 65)

    for m in mismatches:
        print(f"\n  [!] MISMATCH: {m['phone']}")
        print(f"       Posted in:   {m['posted_in']}")
        print(f"       Area code:   {m['area_code']} → {m['ac_origin']}")
        print(f"       Distance:    {m['distance_miles']} miles")
        print(f"       Posted:      {m['posted_time']}")
        print(f"       Ad URL:      {m['ad_url']}")

    print("\n" + "=" * 65)
    print(f"\n  SUMMARY BY ORIGIN REGION:")
    origins = {}
    for m in mismatches:
        key = m["ac_origin"]
        origins[key] = origins.get(key, 0) + 1
    for origin, count in sorted(origins.items(), key=lambda x: x[1], reverse=True):
        print(f"  {count:3d} ads  ←  {origin}")
    print()

if __name__ == "__main__":
    run()
