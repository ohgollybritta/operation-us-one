"""
Face Similarity Search
Anti-human trafficking OSINT tool.
Uses face_recognition (dlib) — no TensorFlow required.

Usage:
    python3 face_matcher.py path/to/query_image.jpg
"""

import os
import sys
import sqlite3
import face_recognition

DB_PATH = "osint_data/ads.db"
TOLERANCE = 0.5

def get_all_images():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT i.image_path, a.phone, a.ad_url, a.location, a.posted_time
        FROM images i
        JOIN ads a ON i.ad_id = a.id
        WHERE i.image_path IS NOT NULL
    """)
    rows = c.fetchall()
    conn.close()
    return rows

def load_face_encoding(image_path):
    try:
        img = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(img)
        if encodings:
            return encodings[0]
    except:
        pass
    return None

def find_matches(query_image_path):
    if not os.path.exists(query_image_path):
        print(f"[!] File not found: {query_image_path}")
        sys.exit(1)

    print(f"\n[*] Loading query image: {query_image_path}")
    query_encoding = load_face_encoding(query_image_path)

    if query_encoding is None:
        print("[!] No face detected in query image. Try a clearer photo.")
        sys.exit(1)

    print(f"[*] Face detected. Scanning database...")
    all_images = get_all_images()
    print(f"[*] Checking {len(all_images)} images...\n")

    matches = []
    no_face = 0
    errors = 0

    for idx, (img_path, phone, ad_url, location, posted_time) in enumerate(all_images):
        if idx % 50 == 0 and idx > 0:
            print(f"  [Progress] {idx}/{len(all_images)} scanned | {len(matches)} matches...")
        if not img_path or not os.path.exists(img_path):
            continue
        encoding = load_face_encoding(img_path)
        if encoding is None:
            no_face += 1
            continue
        try:
            distance = face_recognition.face_distance([query_encoding], encoding)[0]
            if distance <= TOLERANCE:
                matches.append({
                    "distance": distance,
                    "confidence": round((1 - distance) * 100, 1),
                    "image_path": img_path,
                    "phone": phone,
                    "ad_url": ad_url,
                    "location": location,
                    "posted_time": posted_time
                })
        except:
            errors += 1

    matches.sort(key=lambda x: x["distance"])
    return matches, no_face, errors, len(all_images)

def print_results(matches, no_face, errors, total):
    print("\n" + "="*60)
    print(f"  RESULTS: {len(matches)} match(es) found")
    print(f"  Total scanned: {total} | No face: {no_face} | Errors: {errors}")
    print("="*60)
    if not matches:
        print("\n  No matches found.")
        print("  Try raising TOLERANCE in the script (e.g. 0.6)")
        return
    for i, m in enumerate(matches, 1):
        print(f"\n  [{i}] Confidence: {m['confidence']}%  (distance: {round(m['distance'], 4)})")
        print(f"       Phone:    {m['phone']}")
        print(f"       Location: {m['location']}")
        print(f"       Posted:   {m['posted_time']}")
        print(f"       Ad URL:   {m['ad_url']}")
        print(f"       Image:    {m['image_path']}")
    print("\n" + "="*60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 face_matcher.py path/to/image.jpg")
        sys.exit(1)
    query = sys.argv[1]
    matches, no_face, errors, total = find_matches(query)
    print_results(matches, no_face, errors, total)
