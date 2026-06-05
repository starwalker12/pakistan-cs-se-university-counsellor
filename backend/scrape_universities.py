"""
DigiCounsellor — Official Data Collection Scraper (Playwright)

Reads source_links.json and opens each URL using Playwright.
Saves raw text and structured admission data for RAG processing.

Requirements:
  pip install playwright
  playwright install chromium

Usage:
  python backend/scrape_universities.py
"""

import json
import os
import time
import traceback
from datetime import datetime

from bs4 import BeautifulSoup

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

SOURCE_LINKS_PATH = os.path.join(DATA_DIR, "source_links.json")
ADMISSION_DATA_PATH = os.path.join(PROCESSED_DIR, "university_admission_data.json")
SCRAPING_LOG_PATH = os.path.join(PROCESSED_DIR, "scraping_log.json")

# Delay between page loads (seconds)
REQUEST_DELAY = 2.0


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    slug = f"{university_id}_{category}"
    path = os.path.join(RAW_DIR, slug + ext)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def build_admission_record(uni_meta, categories_text, university_id, source_urls):
    """Build a structured admission record from extracted text per category."""
    text_fields = {
        "eligibility": "Needs official verification",
        "entry_test": "Needs official verification",
        "merit": "Needs official verification",
        "fee": "Needs official verification",
        "deadline": "Needs official verification",
    }

    for category, text in categories_text.items():
        for key in text_fields:
            if key in category:
                text_fields[key] = text[:2000]
                break

    fields_from_meta = ", ".join(uni_meta.get("fields", []))

    return {
        "university_id": university_id,
        "university_name": uni_meta.get("name", ""),
        "program": "Multiple",
        "field_type": fields_from_meta,
        "city": uni_meta.get("city", ""),
        "eligibility_text": text_fields["eligibility"],
        "entry_test_text": text_fields["entry_test"],
        "merit_text": text_fields["merit"],
        "fee_text": text_fields["fee"],
        "deadline_text": text_fields["deadline"],
        "source_url": "; ".join(source_urls),
        "source_type": "html",
        "status": "fetched",
        "last_checked": datetime.now().isoformat(),
    }


async def run_scraper():
    """Main scraper orchestrator using Playwright."""
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    source_links = load_json(SOURCE_LINKS_PATH)

    # Build university metadata lookup from source_links
    uni_meta_lookup = {}
    for entry in source_links:
        uni_meta_lookup[entry["university_id"]] = entry

    admission_records = []
    scraping_log = {
        "started_at": datetime.now().isoformat(),
        "results": [],
        "summary": {
            "total_universities": len(source_links),
            "pages_attempted": 0,
            "pages_successful": 0,
            "pages_failed": 0,
            "universities_with_data": 0,
            "universities_needing_manual_check": 0,
        },
    }

    # Import Playwright only when running
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 1024},
        )

        for entry in source_links:
            uid = entry["university_id"]
            uni_name = entry.get("university", uid)
            links = entry.get("links", {})
            categories_text = {}
            pages_ok = 0
            pages_fail = 0
            fetched_urls = []

            print(f"\n{'='*50}")
            print(f"Processing: {uni_name} ({uid})")

            # Fetch each link category
            for category, link_info in links.items():
                url = link_info.get("url", "").strip()
                if not url or "TODO" in url:
                    print(f"  [SKIP] {category}: no valid URL")
                    continue

                # Skip categories that point to the same general homepage
                # to avoid duplicate content
                print(f"  [FETCH] {category}: {url}")
                scraping_log["summary"]["pages_attempted"] += 1
                fetched_urls.append(url)

                time.sleep(REQUEST_DELAY)

                try:
                    page = await context.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    # Wait a bit for JS to render
                    await page.wait_for_timeout(3000)
                    html = await page.content()
                    await page.close()

                    # Save raw HTML
                    save_raw_file(uid, category, html, ext=".html")
                    print(f"  [OK] {category}: saved raw HTML")

                    # Extract clean text
                    text = extract_text_from_html(html)
                    categories_text[category] = text

                    scraping_log["summary"]["pages_successful"] += 1
                    pages_ok += 1

                except Exception as e:
                    print(f"  [FAIL] {category}: {e}")
                    scraping_log["summary"]["pages_failed"] += 1
                    pages_fail += 1
                    categories_text[category] = "Needs official verification"
                    continue

            # Build structured record
            record = build_admission_record(
                entry, categories_text, uid, fetched_urls
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
                "status": record["status"],
            })

        await browser.close()

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
    import asyncio

    asyncio.run(run_scraper())
