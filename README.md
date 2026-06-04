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

## Running the Full Local Demo

The full AI demo runs locally. Vercel can host the frontend only — the backend, LM Studio / Ollama, and Chroma must run on your laptop.

### Prerequisites

- Python 3.10+
- LM Studio (with a model loaded) OR Ollama (with Gemma installed)

### Step 1 — Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

### Step 2 — Start an LLM provider

**Option A — LM Studio (recommended)**
1. Open LM Studio
2. Load the Gemma model
3. Click the "Start Server" button (default port: 1234)
4. The backend will automatically use `http://localhost:1234/v1/chat/completions`

**Option B — Ollama (backup)**
```bash
ollama serve
```

### Step 3 — Start the FastAPI backend

```bash
cd backend
uvicorn app:app --reload --port 8000
```

The backend will try LM Studio first, then Ollama, then a static fallback.

### Step 4 — Open the frontend

Open `frontend/index.html` in your browser, or serve it:

```bash
python3 -m http.server 8080
# Open http://localhost:8080/frontend/index.html
```

### Environment Variables (optional)

| Variable | Default | Description |
|---|---|---|
| `LM_STUDIO_URL` | `http://localhost:1234/v1/chat/completions` | LM Studio endpoint |
| `LM_STUDIO_MODEL` | `gemma` | Model name for LM Studio |
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | Ollama endpoint |
| `OLLAMA_MODEL` | `gemma4:latest` | Model name for Ollama |
| `PROVIDER_ORDER` | `lm_studio,ollama,fallback` | Comma-separated provider priority |

Example with custom Ollama model:
```bash
OLLAMA_MODEL=gemma2:2b uvicorn app:app --reload --port 8000
```

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
uvicorn app:app --reload --port 8000
```

### RAG flow in /counsel endpoint

1. User submits profile + question
2. Backend searches Chroma for top-5 relevant chunks
3. Retrieved chunks are injected into the LLM prompt as context
4. LLM generates a personalised answer based on the retrieved data

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
