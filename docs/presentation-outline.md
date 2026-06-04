# DigiCounsellor — Presentation Outline

## Slide 1 — Title
- Project: DigiCounsellor
- Team Members
- Course / Date

## Slide 2 — Problem
- Pakistani students struggle to find accurate admission info for CS / SE programs
- University websites have scattered, inconsistent data
- No personalised guidance based on student marks and budget

## Slide 3 — Solution
- RAG-based web app that answers admission questions
- Uses scraped university data stored in a local vector database
- Personalises answers using student profile (marks, field, budget)

## Slide 4 — System Architecture
- Frontend: HTML + CSS + JavaScript (no frameworks)
- Backend: Python FastAPI
- Vector DB: Chroma with sentence-transformers
- LLM: Ollama + Gemma (local)

## Slide 5 — Data Pipeline
1. Scrape university admission pages (httpx + BeautifulSoup)
2. Clean and chunk the text
3. Generate embeddings (sentence-transformers)
4. Store in Chroma vector DB

## Slide 6 — RAG Flow
1. User enters profile and question
2. Query embedding → Chroma retrieves top-k relevant docs
3. Profile + context → Ollama prompt
4. Ollama returns personalised answer

## Slide 7 — Demo
- Fill profile form
- Ask a question
- Show retrieved context
- Show LLM answer

## Slide 8 — Conclusion
- Works fully offline with local Ollama and Chroma
- Can deploy frontend on Vercel; backend stays local
- Easy to add more universities
