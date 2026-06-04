# DigiCounsellor — Project Report

**Phase 1: Project Setup**

This phase set up the project structure, created starter files, and initialised Git.

## Folder Structure

```
├── frontend/
│   ├── index.html        # Main HTML page
│   ├── style.css         # Styling
│   └── script.js         # Frontend logic
├── backend/
│   ├── app.py            # FastAPI server
│   ├── scrape_universities.py  # Web scraper (placeholder)
│   ├── build_vector_db.py      # Chroma DB builder (placeholder)
│   ├── requirements.txt        # Python dependencies
│   └── data/
│       ├── raw/               # Raw scraped data
│       ├── processed/         # Cleaned / chunked data
│   └── chroma_db/             # Local vector database
├── docs/
│   ├── report.md              # This file
│   └── presentation-outline.md
└── README.md
```

## Technologies
- HTML / CSS / JavaScript (frontend)
- Python + FastAPI (backend)
- Ollama + Gemma (local LLM)
- sentence-transformers + Chroma (RAG vector DB)
- httpx + BeautifulSoup (scraping)
