# DigiCounsellor — Presentation Outline

## Slide 1 — Title
- Project: DigiCounsellor
- Team Members: Raahim Adeel, Fardan Aatir, and Muhammad Ismail
- Course / Date

## Slide 2 — Problem
- Pakistani students struggle to find accurate admission info for CS / SE programs
- University websites have scattered, inconsistent data
- No personalised guidance based on student marks and budget

## Slide 3 — Solution
- RAG-based web app that answers admission questions
- Uses scraped university data stored in a local Chroma vector database
- Personalises answers using student profile (marks, field, budget)
- Blocks irrelevant questions (programming, cooking, weather, jokes)

## Slide 4 — System Architecture
- Frontend: HTML + CSS + JavaScript (no frameworks)
- Backend: Python FastAPI
- Vector DB: Chroma with sentence-transformers (stored in backend/chroma_db/)
- LLM: Ollama + Gemma (local) or LM Studio fallback
- Scraper: Playwright (headless Chromium) for JS-rendered pages

## Slide 5 — Data Pipeline
1. Scrape university admission pages using Playwright
2. Clean and chunk the text into categories (eligibility, fee, entry test, deadline, merit)
3. Generate embeddings using sentence-transformers/all-MiniLM-L6-v2
4. Store in Chroma vector DB (21 chunks across 20 universities)
5. Weekly GitHub Actions workflow automates steps 1–4 every Sunday

## Slide 6 — RAG Flow
1. User enters profile and question
2. Frontend checks relevance guard (blocks off-topic questions)
3. Query embedding → Chroma retrieves top-k relevant docs
4. Profile + context → ranking/scoring engine
5. Universities grouped into Best Match / Safe / Difficult / Not Eligible
6. Ollama generates personalised summary from structured data + context

## Slide 7 — Demo
- Fill profile form (name, marks, field, city, budget)
- Ask "Which universities are best for me?" → shows recommendation cards
- Ask "Am I eligible for FAST?" → shows eligibility info with source links
- Ask "teach me c++" → shows relevance guard blocked message
- Observe: only panels scroll, page stays fixed

## Slide 8 — Key Achievements
- 20 Pakistani universities with data from official .edu.pk sources
- Chroma vector DB with 21 admission text chunks
- 3-tier LLM provider chain (Ollama → LM Studio → rule-based)
- Playwright scraper handles JS-heavy university sites
- Relevance guard blocks off-topic questions (frontend + backend)
- Weekly GitHub Actions automation for data freshness
- Panel-only scrolling (page does not scroll)

## Slide 9 — Conclusion
- Works fully offline with local Ollama and Chroma
- Can deploy frontend on Vercel; backend stays local
- Students must verify all details from official university pages
- Easy to add more universities and data sources
