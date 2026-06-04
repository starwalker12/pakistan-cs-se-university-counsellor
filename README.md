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
│       ├── raw/                # Raw scraped data
│       ├── processed/          # Cleaned / chunked documents
│       └── chroma_db/          # Local vector database (Chroma)
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

## Technologies

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| LLM | LM Studio (primary) / Ollama (backup) |
| Embeddings | sentence-transformers |
| Vector DB | Chroma (local) |
| Scraping | httpx, BeautifulSoup, pdfplumber |
