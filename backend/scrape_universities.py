"""
Pakistan CS & SE University Counsellor — Official Data Collection Scraper

Reads universities.json and source_links.json.
Fetches official admission pages from Pakistani university websites.
Saves raw text and structured data for later RAG processing.

Usage:
  python backend/scrape_universities.py
"""

import json
import os
import time
import re
import traceback
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

UNIVERSITIES_PATH = os.path.join(DATA_DIR, "universities.json")
SOURCE_LINKS_PATH = os.path.join(DATA_DIR, "source_links.json")
ADMISSION_DATA_PATH = os.path.join(PROCESSED_DIR, "university_admission_data.json")
SCRAPING_LOG_PATH = os.path.join(PROCESSED_DIR, "scraping_log.json")

# ──────────────────────────────────────────────
# HTTP config
# ──────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
REQUEST_DELAY = 1.0  # seconds between requests
TIMEOUT = 20.0


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_todo(url_or_note):
    return "todo" in (url_or_note or "").lower()


def make_slug(university_id, category):
    return f"{university_id}_{category}"


def fetch_page(url):
    """
    Fetch a URL and return the raw text content.
    Returns None on failure.
    """
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "pdf" in content_type:
                return save_pdf_raw(url, resp.content)
            return resp.text
    except Exception as e:
        return None


def extract_text_from_html(html_text):
    """Extract clean visible text from HTML using BeautifulSoup."""
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def save_raw_file(university_id, category, content, ext=".txt"):
    """Save raw content to a file in RAW_DIR."""
    os.makedirs(RAW_DIR, exist_ok=True)
    slug = make_slug(university_id, category)
    path = os.path.join(RAW_DIR, slug + ext)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def build_admission_record(uni_meta, categories_text, university_id):
    """
    Build a structured admission record from extracted text.
    Each category's text is mapped to the appropriate field.
    """
    fields_from_meta = ", ".join(uni_meta.get("fields", []))

    eligibility_text = "Needs official verification"
    entry_test_text = "Needs official verification"
    merit_text = "Needs official verification"
    fee_text = "Needs official verification"
    deadline_text = "Needs official verification"

    for category, text in categories_text.items():
        if "eligibility" in category:
            eligibility_text = text[:2000]
        elif "entry_test" in category or "entry test" in category:
            entry_test_text = text[:2000]
        elif "merit" in category:
            merit_text = text[:2000]
        elif "fee" in category:
            fee_text = text[:2000]
        elif "admissions" in category:
            deadline_text = text[:2000]

    return {
        "university_id": university_id,
        "university_name": uni_meta.get("name", ""),
        "program": "Multiple",
        "field_type": fields_from_meta,
        "city": uni_meta.get("city", ""),
        "eligibility_text": eligibility_text,
        "entry_test_text": entry_test_text,
        "merit_text": merit_text,
        "fee_text": fee_text,
        "deadline_text": deadline_text,
        "source_url": "",
        "source_type": "html",
        "status": "fetched",
        "last_checked": datetime.now().isoformat()
    }


def run_scraper():
    """Main scraper orchestrator."""
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    universities = load_json(UNIVERSITIES_PATH)
    source_links = load_json(SOURCE_LINKS_PATH)

    # Build lookup: university_id -> university meta
    uni_meta_lookup = {u["id"]: u for u in universities}

    # Build lookup: university_id -> source links
    source_lookup = {s["university_id"]: s["links"] for s in source_links}

    admission_records = []
    scraping_log = {
        "started_at": datetime.now().isoformat(),
        "results": [],
        "summary": {
            "total_universities": len(universities),
            "pages_attempted": 0,
            "pages_successful": 0,
            "pages_failed": 0,
            "universities_with_data": 0,
            "universities_needing_manual_check": 0
        }
    }

    for uni in universities:
        uid = uni["id"]
        uni_name = uni.get("name", uid)
        links = source_lookup.get(uid, {})
        categories_text = {}
        pages_ok = 0
        pages_fail = 0

        print(f"\n{'='*50}")
        print(f"Processing: {uni_name} ({uid})")

        # Try to fetch each link category
        for category, link_info in links.items():
            url = link_info.get("url", "")
            note = link_info.get("note", "")

            # Skip TODO links
            if is_todo(url) or is_todo(note):
                print(f"  [SKIP] {category}: TODO marker")
                continue

            print(f"  [FETCH] {category}: {url}")
            scraping_log["summary"]["pages_attempted"] += 1

            time.sleep(REQUEST_DELAY)
            raw = fetch_page(url)

            if raw is None:
                print(f"  [FAIL] {category}")
                scraping_log["summary"]["pages_failed"] += 1
                pages_fail += 1
                categories_text[category] = "Needs official verification"
                continue

            # Save raw HTML
            save_raw_file(uid, category, raw, ext=".html")
            print(f"  [OK] {category}: saved raw HTML")

            # Extract clean text
            text = extract_text_from_html(raw)
            categories_text[category] = text

            scraping_log["summary"]["pages_successful"] += 1
            pages_ok += 1

        # Build structured record
        record = build_admission_record(uni, categories_text, uid)
        record["source_url"] = "; ".join(
            info["url"] for info in links.values()
            if not is_todo(info.get("url", ""))
        )

        if pages_ok == 0:
            record["status"] = "needs_manual_check"
            record["source_type"] = "none"
            scraping_log["summary"]["universities_needing_manual_check"] += 1
        else:
            scraping_log["summary"]["universities_with_data"] += 1

        admission_records.append(record)

        scraping_log["results"].append({
            "university_id": uid,
            "university_name": uni_name,
            "pages_ok": pages_ok,
            "pages_fail": pages_fail,
            "status": record["status"]
        })

    # Save structured admission data
    with open(ADMISSION_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(admission_records, f, indent=2, ensure_ascii=False)
    print(f"\nSaved admission data: {ADMISSION_DATA_PATH}")

    # Save scraping log
    scraping_log["finished_at"] = datetime.now().isoformat()
    with open(SCRAPING_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(scraping_log, f, indent=2, ensure_ascii=False)
    print(f"Saved scraping log: {SCRAPING_LOG_PATH}")

    # Summary
    s = scraping_log["summary"]
    print(f"\n{'='*50}")
    print("SCRAPING SUMMARY")
    print(f"  Universities processed: {s['total_universities']}")
    print(f"  Pages attempted: {s['pages_attempted']}")
    print(f"  Pages successful: {s['pages_successful']}")
    print(f"  Pages failed: {s['pages_failed']}")
    print(f"  Universities with data: {s['universities_with_data']}")
    print(f"  Universities needing manual check: {s['universities_needing_manual_check']}")
    print(f"{'='*50}")

    return scraping_log


if __name__ == "__main__":
    run_scraper()
