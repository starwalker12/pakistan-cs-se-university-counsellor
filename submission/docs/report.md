# DigiCounsellor — Project Report

**Team:** Raahim Adeel, Fardan Aatir, and Muhammad Ismail

## Project Purpose

DigiCounsellor is a RAG-based student counselling web app for Pakistani applicants. It combines a saved student profile, local university admission data, ranking/eligibility logic, Chroma vector retrieval, and a local LLM to guide students through CS/SE university admissions in Pakistan.

## System Architecture

```
┌──────────────┐    ┌─────────────────────────────────────────────┐
│   Browser    │    │              FastAPI Backend                 │
│  (frontend)  │───▶│  /counsel  /recommend  /ai-summary           │
│              │    │  /university-info  /health  /data-status     │
│  HTML+CSS+JS │    │                                              │
│              │◀───│  Chroma DB  │  Ollama/LM Studio  │  Ranking  │
└──────────────┘    └─────────────────────────────────────────────┘
                          │
                          ▼
                   Playwright Scraper
                   (weekly via GitHub Actions)
```

## Technologies

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| LLM | Ollama (primary) / LM Studio (optional) / rule-based fallback |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector DB | Chroma (local, stored in backend/chroma_db/) |
| Scraping | Playwright (headless Chromium) — replaces httpx for JS-rendered pages |
| CI/CD | GitHub Actions (weekly scheduled scrape + vector DB rebuild) |

## What Was Built

| Phase | Feature | Status |
|---|---|---|
| 1–9 | Project setup, UI, LLM providers, 20 universities, Chroma DB, RAG pipeline | Complete |
| 13–22 | Product UI, natural chat flow, strict eligibility, intent-based routing, link validation, source-first answers, live official lookup, category link validation | Complete |
| 23 | Topic-aware live lookup (matches_topic) prevents accepting generic page text as fee/eligibility data | Complete |
| 24 | Logo branding, Poppins/Inter typography, favicon update | Complete |
| 25 | AI relevance routing — backend classifies admission scope before RAG/LLM and frontend no longer blocks valid follow-ups | Complete |
| 26 | Screen scroll fix — page does not scroll; only panels scroll inside | Complete |
| 27 | Playwright scraper — headless Chromium scraping replaces httpx-only approach for JS-heavy sites | Complete |
| 28 | Weekly GitHub Actions schedule — automated scrape + vector DB rebuild every Sunday | Complete |

## Key Features

- **20 Pakistani universities** with admission data from official `.edu.pk` websites
- **Chroma vector DB** stored in `backend/chroma_db/` with 21 text chunks (eligibility, fee, entry test, merit, deadline)
- **3-tier LLM provider chain**: Ollama → LM Studio → rule-based fallback (no cloud APIs)
- **AI relevance routing**: `classify_question_relevance()` on the backend checks scope before Chroma/RAG or answer generation. Valid admission follow-ups are allowed with saved profile or recommendation context
- **Playwright scraper**: Uses headless Chromium to scrape JS-rendered university pages that httpx cannot handle. Outputs structured admission data to `university_admission_data.json`
- **Weekly automation**: GitHub Actions workflow runs every Sunday at 6 AM UTC — scrapes latest data and rebuilds Chroma DB
- **Screen scroll fix**: Body does not scroll; only the profile panel and chat messages area scroll inside their containers
- **Structured recommendations**: Universities grouped into Best Match, Safe, Difficult, and Not Eligible with clear reasons
- **Intent-based routing**: Frontend detects greeting, recommendation, university info, and follow-up intents; routes to the right endpoint without card duplication

## How to Run

```bash
# 1. Install dependencies
cd backend && pip install -r requirements.txt && playwright install chromium

# 2. Start Ollama (or LM Studio)
OLLAMA_ORIGINS=* ollama serve

# 3. Start backend
cd /Users/sw12/Projects/ML-Project/backend
FAST_MODE=true OLLAMA_MODEL=gemma4:latest python3 -m uvicorn app:app --port 8000

# 4. Start frontend
cd /Users/sw12/Projects/ML-Project && python3 -m http.server 8080

# 5. Open in browser
# http://localhost:8080/frontend/index.html
```

## Data Pipeline

1. **Scrape**: `python backend/scrape_universities.py` — uses Playwright to fetch official admission pages
2. **Build DB**: `python backend/build_vector_db.py` — chunks text, generates embeddings, stores in Chroma
3. **Serve**: Backend loads Chroma on startup and retrieves relevant chunks for each user question
4. **Automate**: GitHub Actions runs steps 1–2 every Sunday automatically

## AI Relevance Routing

Before `/recommend`, `/ai-summary`, `/counsel`, or `/university-info` performs RAG or answer generation, the backend asks the local AI provider for a JSON relevance decision. Allowed topics include Pakistani CS/SE admissions, eligibility, fees, merit, deadlines, entry tests, official links, safe/difficult options, and next steps.

Contextual follow-ups such as "safe options", "best matches", "compare options", "tell me more", and "what should I do next" are allowed when a saved profile or recent recommendation context exists. Irrelevant questions such as programming tutorials, cooking, weather, jokes, poems, and general celebrity questions are refused before retrieval. If the local AI classifier is unavailable, a fallback guard allows greetings, known university names, admission terms, and contextual follow-ups while blocking obvious unrelated topics.

## Disclaimer

This is guidance only, not final admission advice. All eligibility criteria, merit cutoffs, and fee structures vary each year. Students must verify all details from official university admission pages before applying.
