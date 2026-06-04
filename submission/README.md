# Pakistan CS & SE University Counsellor

A RAG-based student counsellor web app for Pakistani students who want admission in Computer Science or Software Engineering programs.

## How It Works

1. Student fills in their profile (name, marks, entry test score, preferred field, city, budget)
2. Student asks a question (e.g. "Which universities can I get into with 80% in FSC?")
3. The backend retrieves relevant university admission information from a local Chroma vector database
4. The backend sends the retrieved context plus the student profile to a local LLM (LM Studio or Ollama)
5. A personalised counselling answer is returned to the student

## Project Structure

```
├── frontend/
│   ├── index.html          # Main HTML page with profile form and chat
│   ├── style.css           # Green theme styling
│   └── script.js           # Frontend logic — sends profile + question to backend
├── backend/
│   ├── app.py              # FastAPI server with /counsel, /health, /providers endpoints
│   ├── scrape_universities.py  # Web scraper (placeholder)
│   ├── build_vector_db.py      # Chroma vector DB builder (placeholder)
│   ├── requirements.txt        # Python dependencies
│   └── data/
│       ├── universities.json           # 20 university metadata
│       ├── source_links.json           # Official source URL placeholders
│       ├── university_rankings.json    # Approximate ranking tiers and scores
│       ├── eligibility_rules.json      # Placeholder eligibility rules
│       ├── raw/                        # Raw scraped data
│       ├── processed/
│       │   ├── sample_admission_data.json  # Sample admission records (3 unis)
│       │   └── ...                        # Cleaned / chunked documents
│       └── chroma_db/                  # Local vector database (Chroma)
├── docs/
│   ├── report.md               # Project report
│   └── presentation-outline.md # Presentation outline
└── README.md
```

## Quick Demo Setup (5 minutes)

**Full AI RAG demo runs locally** because Ollama or LM Studio runs on your laptop. Vercel can show the frontend, but local AI needs the local backend.

### Step 1 — Install dependencies

```bash
cd /Users/sw12/Projects/ML-Project/backend
pip install -r requirements.txt
```

### Step 2 — Start an LLM provider

**Option A — Ollama (easiest)**
```bash
OLLAMA_ORIGINS=* ollama serve
```

**Option B — LM Studio**
1. Open LM Studio
2. Load a model (e.g. Gemma)
3. Click "Start Server" (default port 1234)

### Step 3 — Start the backend

```bash
cd /Users/sw12/Projects/ML-Project/backend
python3 -m uvicorn app:app --reload --port 8000
```

The backend loads Chroma on startup, then tries LM Studio first, Ollama second, and a static fallback last. Watch for:
```
Chroma loaded with 21 documents
Uvicorn running on http://localhost:8000
```

### Step 4 — Open the frontend

```bash
cd /Users/sw12/Projects/ML-Project
python3 -m http.server 8080
```

Open in your browser: **http://localhost:8080/frontend/index.html**

### Step 5 — Run a demo test

```bash
curl http://localhost:8000/health
```

Expected response: `{"status":"ok","chroma_docs":21,"ollama":true,"lm_studio":false}`

### Step 6 — Full RAG counsel test

```bash
curl -X POST http://localhost:8000/counsel \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "name": "Ali",
      "matric_marks": "90",
      "inter_marks": "82",
      "entry_test": "ECAT 150",
      "preferred_field": "CS",
      "city_preference": "Lahore",
      "budget": "500000"
    },
    "question": "Which universities are best for me?"
  }'
```

Expected response: JSON with `answer` (structured text), `sources` (array), `retrieved_count` (number), `provider_used` (string).

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Frontend shows "Backend is not running" | Start uvicorn in the backend folder |
| Answer says "Fallback (no AI)" | Start Ollama (`ollama serve`) or LM Studio |
| Search returns zero results | Rebuild Chroma: `cd backend && python build_vector_db.py` |
| Frontend is blank / not loading | Run `python3 -m http.server 8080` and open the URL above |
| Vercel deployed but no AI answers | Local AI cannot run on Vercel. The backend + LLM must run on a laptop |
| Ollama CORS error in browser | Start with `OLLAMA_ORIGINS=* ollama serve` |
| Chroma not found on startup | Run `cd backend && python build_vector_db.py` first |

### Environment Variables (optional)

| Variable | Default | Description |
|---|---|---|
| `LM_STUDIO_URL` | `http://localhost:1234/v1/chat/completions` | LM Studio endpoint |
| `LM_STUDIO_MODEL` | `gemma` | Model name for LM Studio |
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | Ollama endpoint |
| `OLLAMA_MODEL` | `gemma4:latest` | Model name for Ollama |
| `PROVIDER_ORDER` | `lm_studio,ollama,fallback` | Comma-separated provider priority |

Example:
```bash
OLLAMA_MODEL=gemma2:2b python3 -m uvicorn app:app --reload --port 8000
```

---

## Deployment Note

- **Frontend**: can be deployed on Vercel as a static site
- **Backend**: cannot run on Vercel — it needs local Python, Chroma, and an LLM provider
- The full RAG + AI flow works only when everything runs locally on your laptop

## Phase 4 Data Plan

The RAG system answers admission questions using data that ultimately comes from official university sources. Here is the data pipeline plan:

### Data Files

| File | Purpose |
|---|---|
| `backend/data/universities.json` | Metadata for 20 Pakistani universities that offer CS / SE programs |
| `backend/data/source_links.json` | Official source URL placeholders per university (admissions, fee, eligibility, entry test, merit) |
| `backend/data/university_rankings.json` | Approximate ranking tiers and scores for 20 universities |
| `backend/data/eligibility_rules.json` | Placeholder eligibility rules (minimum marks, entry test requirements) |
| `backend/data/processed/sample_admission_data.json` | Sample admission records (FAST NUCES, NUST, COMSATS) — clearly marked as sample, not final |
| `backend/data/processed/university_admission_data.json` | Scraped admission data from official university websites (12 of 20 universities) |
| `backend/data/processed/scraping_log.json` | Scraping run log with status per university |
| `backend/data/raw/` | Raw HTML files fetched from university pages |

## Phase 5 Official Data Collection

Admission data comes from official university `.edu.pk` websites where available. The scraper (`scrape_universities.py`) reads `universities.json` and `source_links.json`, then fetches each page using httpx and extracts text with BeautifulSoup.

### Summary (latest run)

| Metric | Count |
|---|---|
| Universities processed | 20 |
| Pages attempted | 35 |
| Pages successfully fetched | 27 |
| Pages failed | 8 |
| Universities with data | 12 |
| Universities needing manual check | 8 |

### Universities with scraped data

FAST NUCES, COMSATS, LUMS, PIEAS, ITU Lahore, Air University, Bahria University, Punjab University, QAU, University of Karachi, UCP, IBA Karachi

### Universities needing manual check

NUST (403 blocked), GIKI (SSL error), UET Lahore (503), NED (DNS), UET Taxila (timeout), Virtual University (SSL error), SZABIST (SSL error), IST (no page found)

### Notes

1. Data comes from official university pages where available
2. Missing data is marked as "Needs official verification" or "needs_manual_check"
3. This data will later be chunked and stored in Chroma for RAG retrieval
4. The system is for counselling help, not final admission confirmation
5. Students should verify all details from official university admission pages before applying

### Ranking Plan

The system will rank and recommend universities using these factors:

1. **University ranking score** — from `university_rankings.json` (tiers and scores based on CS/SE reputation)
2. **Student marks** — Matric and Intermediate percentages compared against eligibility minimums
3. **Entry test score** — Whether the student has taken a relevant entry test
4. **Selected field** — Filter universities that offer the student's preferred field (CS or SE)
5. **City preference** — Filter or prioritize universities in the student's preferred city
6. **Budget range** — Public universities are lower fee; private universities are higher fee

**Important**: This is not final admission advice. All eligibility criteria and merit cutoffs vary each year. Students must verify from official university admission pages before applying.

### Data Principles

1. **Official sources only** — all data should come from `.edu.pk` university websites, not blogs or third-party aggregators
2. **Verifiable** — every piece of admission info should be traceable back to an official source link
3. **Sample before scraped** — `sample_admission_data.json` contains illustrative records that will be replaced once scraping is implemented
4. **Placeholder before scraped** — `eligibility_rules.json` values are approximate placeholders and must be updated with real scraped data
5. **Rankings are approximate** — `university_rankings.json` scores are project-level approximations based on known reputation, not official HEC or QS rankings

## Phase 6 RAG Database

The RAG vector database is built from scraped university admission data. Here is the pipeline:

1. **Chunking** — Each scraped admission record is split into category-based chunks (eligibility, entry_test, merit, fee, deadline)
2. **Embeddings** — Chunks are embedded using `sentence-transformers/all-MiniLM-L6-v2` (free, local model)
3. **Chroma storage** — Embeddings + text + metadata are stored locally in `backend/chroma_db/`
4. **Retrieval** — When a user asks a question, the backend searches Chroma for the most relevant chunks and sends them to the LLM as context

### Commands

```bash
# Step 1: Build the vector database
cd backend
python build_vector_db.py

# Step 2: Test the RAG search
python test_rag_search.py

# Step 3: Start the backend (loads Chroma on startup)
python3 -m uvicorn app:app --reload --port 8000
```

### RAG flow in /counsel endpoint

1. User submits profile + question
2. Backend builds a rich search query from profile fields
3. Chroma is searched for top 7 relevant chunks
4. Ranking data and eligibility rules are loaded
5. Each university in the results is scored against the student's profile
6. A master prompt is built with: chunks, ranking scores, and profile
7. Prompt is sent to LM Studio first, then Ollama, then fallback
8. The LLM generates a structured answer with sections:
   - Short Summary
   - Best Match Universities
   - Safe Options
   - Difficult Options
   - Reason for Recommendation
   - Next Steps
   - Source Notes
9. Response includes the answer, sources list, and provider info

### Test command

```bash
curl -X POST http://localhost:8000/counsel \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "name": "Ali",
      "matric_marks": "90",
      "inter_marks": "82",
      "entry_test": "ECAT 150",
      "preferred_field": "Computer Science",
      "city_preference": "Lahore",
      "budget": "500000"
    },
    "question": "Which universities are best for me?"
  }'
```

### Response format

```json
{
  "answer": "...",
  "sources": [
    {"university_name": "...", "source_url": "...", "preview": "..."}
  ],
  "retrieved_count": 7,
  "provider_used": "ollama"
}
```

### Search endpoint

`GET /search?q=question` — returns top 5 chunks from Chroma with university name, category, and text preview.

## Technologies

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| LLM | LM Studio (primary) / Ollama (backup) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector DB | Chroma (local) |
| Scraping | httpx, BeautifulSoup, pdfplumber |

---

## Project Summary

**Pakistan CS & SE University Counsellor** is a complete RAG-based student counselling web app. It answers admission questions for 20 Pakistani universities using official scraped data, a local vector database, and a local LLM — all running on a laptop with no internet dependency after setup.

### What was built

| Phase | What | Status |
|---|---|---|
| 1 | Project structure, starter files | Complete |
| 2 | UI — hero, student form, chat, responsive | Complete |
| 3 | LLM providers — LM Studio + Ollama + fallback | Complete |
| 4 | 20 universities with rankings and eligibility rules | Complete |
| 5 | Web scraper — 12 universities scraped, 8 need manual data | Complete |
| 6 | Chroma vector DB — 21 chunks from admission data | Complete |
| 7 | RAG pipeline — retrieval + scoring + structured LLM response | Complete |
| 8 | Frontend polish — badge, steps, samples, sources, provider | Complete |
| 9 | Demo script + testing checklist + docs | Complete |

### Key achievements

- **12 universities** with real admission data from official `.edu.pk` websites
- **21 chunks** in Chroma vector database, each with category metadata
- **3-tier provider chain** — LM Studio → Ollama → fallback (no cloud APIs)
- **Ranking + eligibility scoring** — combines ranking score, city, field, and marks fit
- **Structured LLM response** — Short Summary, Best Match, Safe Options, Difficult Options, Reason, Next Steps, Source Notes
- **Clean responsive UI** — works on laptop and mobile with sample questions, source cards, and provider badge

### Team

Raahim Adeel, Fardan Aatir, and Muhammad Ismail

### Related documents

- `docs/demo-script.md` — step-by-step demo script for department event
- `docs/testing-checklist.md` — 14-point testing checklist
- `docs/report.md` — project report
- `docs/presentation-outline.md` — presentation outline
