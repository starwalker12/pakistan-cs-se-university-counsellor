"""
Pakistan CS & SE University Counsellor — FastAPI Backend

Endpoints:
  POST /counsel  — accepts student profile + question, returns counselling answer

Flow:
  1. Receive profile + question from frontend
  2. Query Chroma vector DB for relevant university documents (RAG retrieval)
  3. Build prompt with profile + retrieved context
  4. Send prompt to local Ollama (Gemma) for final answer
  5. Return answer to frontend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os

app = FastAPI(title="Pakistan CS & SE Counsellor")

# Allow frontend (any origin for local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma4:latest"


# ──────────────────────────────────────────────
# Request / Response models
# ──────────────────────────────────────────────

class Profile(BaseModel):
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


# ──────────────────────────────────────────────
# In-memory university data (placeholder)
# Will be replaced with Chroma retrieval in Phase 2
# ──────────────────────────────────────────────

PLACEHOLDER_DOCS = [
    "Lahore University of Management Sciences (LUMS) offers BS Computer Science. "
    "Admission requires 60%+ in Intermediate, LUMS SBASSE test, and interview. "
    "Annual fee: approximately PKR 800,000. Location: Lahore.",

    "National University of Computer and Emerging Sciences (NUCES-FAST) offers "
    "BS Computer Science and BS Software Engineering. Admission based on "
    "Intermediate marks (65%+) and NTS / FAST entry test. "
    "Annual fee: approximately PKR 350,000. Campuses in Lahore, Islamabad, Karachi, Peshawar.",

    "University of Engineering and Technology (UET) Lahore offers BS Computer Science. "
    "Admission via UET entry test and Intermediate aggregate. "
    "Annual fee: approximately PKR 150,000. Location: Lahore.",
]


# ──────────────────────────────────────────────
# POST /counsel — main counselling endpoint
# ──────────────────────────────────────────────

@app.post("/counsel", response_model=CounselResponse)
async def counsel(request: CounselRequest):
    # Build a simple profile summary string
    profile_summary = (
        f"Matric: {request.profile.matric_marks}, "
        f"Intermediate: {request.profile.inter_marks}, "
        f"Entry Test: {request.profile.entry_test}, "
        f"Preferred Field: {request.profile.preferred_field}, "
        f"City: {request.profile.city_preference}, "
        f"Budget: {request.profile.budget}"
    )

    # Combine all placeholder docs into a single context block
    context = "\n\n".join(PLACEHOLDER_DOCS)

    # Build the prompt for Ollama
    prompt = f"""You are a university counsellor for Pakistani students.
Use the following university admission information to answer the student's question.

Student Profile:
{profile_summary}

University Information:
{context}

Student Question: {request.question}

Give a clear, helpful, and personalised answer based on the student's marks and preferences."""

    # Call local Ollama
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            })
            data = resp.json()
            answer = data.get("response", "").strip()
            if not answer:
                answer = "I could not generate an answer at this time."
    except Exception as e:
        answer = f"Ollama is not running. Start it with: ollama serve\n\nDebug: {str(e)}"

    return CounselResponse(answer=answer)


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "model": OLLAMA_MODEL}
