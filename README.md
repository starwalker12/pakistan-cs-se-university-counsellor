# Pakistan CS & SE University Counsellor

A RAG-based student counsellor web app for Pakistani students who want admission in Computer Science or Software Engineering programs.

## How It Works

1. Student fills in their profile (matric marks, intermediate marks, entry test score, preferred field, city, budget)
2. Student asks a question (e.g. "Which universities can I get into with 80% in FSC?")
3. The backend retrieves relevant university admission information from a local Chroma vector database
4. The backend sends the retrieved context plus the student profile to a local Ollama LLM (Gemma)
5. A personalised counselling answer is returned to the student

## Project Structure

```
├── frontend/
│   ├── index.html          # Main HTML page with profile form and chat
│   ├── style.css           # Green theme styling
│   └── script.js           # Frontend logic — sends profile + question to backend
├── backend/
│   ├── app.py              # FastAPI server with /counsel endpoint
│   ├── scrape_universities.py  # Web scraper (placeholder for Phase 2)
│   ├── build_vector_db.py      # Chroma vector DB builder (placeholder for Phase 2)
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

## Running Locally (Full RAG Demo)

The full RAG demo runs locally because Ollama and Chroma are local. Vercel can host the frontend only, but the local backend and Ollama must run on the laptop during the demo.

### Prerequisites
- Python 3.10+
- Ollama with Gemma model installed
  ```bash
  ollama pull gemma4:latest
  ```

### Step 1 — Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 2 — Start the Ollama server
```bash
ollama serve
```

### Step 3 — Start the FastAPI backend
```bash
cd backend
uvicorn app:app --reload --port 8000
```

### Step 4 — Open the frontend
Open `frontend/index.html` in your browser, or serve it:
```bash
python3 -m http.server 8080
# Open http://localhost:8080/frontend/index.html
```

## Deployment Note

The frontend can be deployed on Vercel as a static site. However:
- The Python backend (FastAPI + Chroma + Ollama) must run locally
- Ollama runs only on your laptop — it cannot run on Vercel
- The full RAG flow only works when both frontend and backend are running locally

## Technologies

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| LLM | Ollama + Gemma (local) |
| Embeddings | sentence-transformers |
| Vector DB | Chroma (local) |
| Scraping | httpx, BeautifulSoup, pdfplumber |
