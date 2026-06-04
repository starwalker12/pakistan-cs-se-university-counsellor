"""
Pakistan CS & SE University Counsellor — Web Scraper

Scrapes admission data from Pakistani university websites.
Stores raw HTML/text in backend/data/raw/ for later processing.

Target universities (CS / SE programs):
  - LUMS
  - NUCES-FAST
  - UET Lahore
  - NUST
  - COMSATS
  - PUCIT
  - University of the Punjab
  - Habib University
  - GIKI
  - ITU Lahore

Usage (future phase):
  python scrape_universities.py
"""

import json
import os

RAW_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")

# Placeholder — real HTTP fetching will be added in Phase 2
UNIVERSITIES = [
    {
        "name": "LUMS",
        "url": "https://lums.edu.pk/admissions",
        "programs": ["BS Computer Science"],
    },
    {
        "name": "NUCES-FAST",
        "url": "https://nu.edu.pk/admissions",
        "programs": ["BS Computer Science", "BS Software Engineering"],
    },
    {
        "name": "UET Lahore",
        "url": "https://uet.edu.pk/admissions",
        "programs": ["BS Computer Science"],
    },
]


def scrape_all():
    """Iterate over universities and save raw data."""
    os.makedirs(RAW_DIR, exist_ok=True)
    for uni in UNIVERSITIES:
        slug = uni["name"].lower().replace(" ", "_")
        out_path = os.path.join(RAW_DIR, f"{slug}.json")
        with open(out_path, "w") as f:
            json.dump(uni, f, indent=2)
        print(f"Saved placeholder: {out_path}")


if __name__ == "__main__":
    scrape_all()
