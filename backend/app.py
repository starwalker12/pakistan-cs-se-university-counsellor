"""
Pakistan CS & SE University Counsellor — FastAPI Backend

Endpoints:
  POST /counsel  — accepts student profile + question, returns counselling answer
  GET  /health   — health check
  GET  /providers — shows configured LLM providers

LLM Provider order:
  1. LM Studio (OpenAI-compatible endpoint)
  2. Ollama (local)
  3. Static fallback (no AI)
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
from sentence_transformers import SentenceTransformer
import chromadb

app = FastAPI(title="Pakistan CS & SE Counsellor")

# Allow frontend (any origin for local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Provider configuration (from environment)
# ──────────────────────────────────────────────

# LM Studio
LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")
LM_STUDIO_MODEL = os.environ.get("LM_STUDIO_MODEL", "gemma")

# Ollama
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:latest")

# Provider order (comma-separated, default: lm_studio,ollama,fallback)
PROVIDER_ORDER = os.environ.get("PROVIDER_ORDER", "lm_studio,ollama,fallback").split(",")

# ──────────────────────────────────────────────
# Chroma / RAG configuration
# ──────────────────────────────────────────────

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION_NAME = "pakistan_university_admissions"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

rag_model = None
rag_collection = None


def load_rag():
    global rag_model, rag_collection
    try:
        rag_model = SentenceTransformer(EMBEDDING_MODEL)
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        rag_collection = client.get_collection(COLLECTION_NAME)
        print(f"RAG loaded: {rag_collection.count()} chunks in Chroma")
    except Exception as e:
        print(f"RAG not available: {e}")
        rag_model = None
        rag_collection = None


def search_chroma(query: str, top_k: int = 5) -> list[str]:
    if rag_model is None or rag_collection is None:
        return []
    query_emb = rag_model.encode(query).tolist()
    results = rag_collection.query(
        query_embeddings=[query_emb],
        n_results=top_k,
    )
    contexts = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            contexts.append(
                f"[{meta.get('university_name', '?')} - {meta.get('category', '?')}]\n{doc}"
            )
    return contexts


# Load RAG on startup
load_rag()


# ──────────────────────────────────────────────
# Request / Response models
# ──────────────────────────────────────────────

class Profile(BaseModel):
    name: str = ""
    matric_marks: str = ""
    inter_marks: str = ""
    entry_test: str = ""
    preferred_field: str = ""
    city_preference: str = ""
    budget: str = ""


class CounselRequest(BaseModel):
    profile: Profile
    question: str


class CounselResponse(BaseModel):
    answer: str


# =============================================
# Helper: call LM Studio (OpenAI compatible)
# =============================================
async def call_lm_studio(prompt: str) -> str | None:
    """
    Send prompt to LM Studio's OpenAI-compatible endpoint.
    Returns the answer text, or None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(LM_STUDIO_URL, json={
                "model": LM_STUDIO_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful university counsellor for Pakistani students."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            })
            if resp.status_code != 200:
                return None
            data = resp.json()
            # OpenAI format: choices[0].message.content
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# =============================================
# Helper: call Ollama (local)
# =============================================
async def call_ollama(prompt: str) -> str | None:
    """
    Send prompt to Ollama chat API.
    Returns the answer text, or None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            })
            if resp.status_code != 200:
                return None
            data = resp.json()
            # Ollama chat format: message.content
            return data["message"]["content"].strip()
    except Exception:
        return None


# =============================================
# Helper: fallback response (no AI)
# =============================================
def fallback_response(prompt: str) -> str:
    """
    Static fallback when no LLM provider is available.
    Returns a simple FAQ-style answer.
    """
    return (
        "I'm sorry, but the AI providers (LM Studio and Ollama) are not "
        "currently available. Please make sure at least one of them is running.\n\n"
        "In the meantime, here is what you can do:\n"
        "- Start LM Studio, load a model, and start the local server on port 1234\n"
        "- Or start Ollama with: ollama serve\n\n"
        "Once either provider is running, restart the backend and try again."
    )


# =============================================
# Helper: get AI response (tries providers in order)
# =============================================
async def get_ai_response(prompt: str) -> str:
    """
    Try each provider in PROVIDER_ORDER and return the first successful response.
    """
    for provider in PROVIDER_ORDER:
        provider = provider.strip()

        if provider == "lm_studio":
            answer = await call_lm_studio(prompt)
            if answer:
                return answer

        elif provider == "ollama":
            answer = await call_ollama(prompt)
            if answer:
                return answer

        elif provider == "fallback":
            return fallback_response(prompt)

    # If no provider matched (shouldn't happen if fallback is in the list)
    return fallback_response(prompt)


# =============================================
# GET /health — simple health check
# =============================================
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "message": "Backend is running"
    }


# =============================================
# GET /providers — show configured providers
# =============================================
@app.get("/providers")
async def providers():
    return {
        "providers": {
            "lm_studio": {
                "url": LM_STUDIO_URL,
                "model": LM_STUDIO_MODEL,
                "active": "lm_studio" in PROVIDER_ORDER
            },
            "ollama": {
                "url": OLLAMA_URL,
                "model": OLLAMA_MODEL,
                "active": "ollama" in PROVIDER_ORDER
            },
            "fallback": {
                "active": "fallback" in PROVIDER_ORDER
            }
        },
        "provider_order": PROVIDER_ORDER
    }


# =============================================
# POST /counsel — main counselling endpoint (RAG)
# =============================================

@app.post("/counsel", response_model=CounselResponse)
async def counsel(request: CounselRequest):
    # Build a profile summary string
    profile_summary = (
        f"Name: {request.profile.name}, "
        f"Matric: {request.profile.matric_marks}%, "
        f"Intermediate: {request.profile.inter_marks}%, "
        f"Entry Test: {request.profile.entry_test}, "
        f"Preferred Field: {request.profile.preferred_field}, "
        f"City: {request.profile.city_preference}, "
        f"Budget: {request.profile.budget}"
    )

    user_query = (
        f"Student profile: {profile_summary}\n"
        f"Question: {request.question}"
    )

    retrieved = search_chroma(user_query, top_k=5)

    if retrieved:
        context = "\n\n---\n\n".join(retrieved)
    else:
        context = "No university admission data is currently available in the vector database."

    prompt = f"""You are a university counsellor for Pakistani students.
Use the following university admission information to answer the student's question.

Student Profile:
{profile_summary}

University Admission Information:
{context}

Student Question: {request.question}

Give a clear, helpful, and personalised answer based on the student's marks and preferences.
If the information provided does not fully answer the question, suggest the student check official university websites."""

    answer = await get_ai_response(prompt)

    return CounselResponse(answer=answer)


# =============================================
# GET /search — search Chroma vector DB
# =============================================

@app.get("/search")
async def search(q: str = Query(..., description="Search query")):
    results = search_chroma(q, top_k=5)
    items = []
    if results:
        for i, text in enumerate(results):
            items.append({"rank": i + 1, "text": text[:500]})
    return {
        "query": q,
        "results_count": len(items),
        "results": items
    }
