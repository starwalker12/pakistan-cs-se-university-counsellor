"""
Pakistan CS & SE University Counsellor — FastAPI Backend

Endpoints:
  POST /counsel  — accepts student profile + question, returns counselling answer
  GET  /health   — health check
  GET  /providers — shows configured LLM providers
  GET  /search   — search Chroma vector DB

LLM Provider order:
  1. LM Studio (OpenAI-compatible endpoint)
  2. Ollama (local)
  3. Static fallback (rule-based answer from retrieved data)
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import json
from sentence_transformers import SentenceTransformer
import chromadb

app = FastAPI(title="Pakistan CS & SE Counsellor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Provider configuration
# ──────────────────────────────────────────────
LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")
LM_STUDIO_MODEL = os.environ.get("LM_STUDIO_MODEL", "gemma")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:latest")
PROVIDER_ORDER = os.environ.get("PROVIDER_ORDER", "lm_studio,ollama,fallback").split(",")

# ──────────────────────────────────────────────
# Chroma / RAG configuration
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "pakistan_university_admissions"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

rag_model = None
rag_collection = None

# ──────────────────────────────────────────────
# Load local data files
# ──────────────────────────────────────────────
RANKINGS = []
ELIGIBILITY_RULES = []


def load_local_data():
    global RANKINGS, ELIGIBILITY_RULES
    try:
        rankings_path = os.path.join(DATA_DIR, "university_rankings.json")
        with open(rankings_path, "r", encoding="utf-8") as f:
            RANKINGS = json.load(f)
        print(f"Loaded {len(RANKINGS)} ranking records")
    except Exception as e:
        print(f"Could not load rankings: {e}")

    try:
        rules_path = os.path.join(DATA_DIR, "eligibility_rules.json")
        with open(rules_path, "r", encoding="utf-8") as f:
            ELIGIBILITY_RULES = json.load(f)
        print(f"Loaded {len(ELIGIBILITY_RULES)} eligibility rules")
    except Exception as e:
        print(f"Could not load eligibility rules: {e}")


load_local_data()


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


class SourceItem(BaseModel):
    university_name: str = ""
    source_url: str = ""
    preview: str = ""


class CounselResponse(BaseModel):
    answer: str
    sources: list[SourceItem] = []
    retrieved_count: int = 0
    provider_used: str = ""


# =============================================
# Chroma search helpers
# =============================================

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


def search_chroma_detailed(query: str, top_k: int = 5) -> list[dict]:
    """
    Search Chroma and return full metadata + document for each result.
    """
    if rag_model is None or rag_collection is None:
        return []
    query_emb = rag_model.encode(query).tolist()
    results = rag_collection.query(
        query_embeddings=[query_emb],
        n_results=top_k,
    )
    items = []
    if results["documents"] and results["documents"][0]:
        for i in range(len(results["documents"][0])):
            meta = results["metadatas"][0][i]
            doc = results["documents"][0][i]
            items.append({
                "university_id": meta.get("university_id", ""),
                "university_name": meta.get("university_name", ""),
                "category": meta.get("category", ""),
                "source_url": meta.get("source_url", ""),
                "city": meta.get("city", ""),
                "field_type": meta.get("field_type", ""),
                "text": doc,
                "preview": doc[:200].replace("\n", " ").strip(),
            })
    return items


# =============================================
# Ranking and scoring helpers
# =============================================

def get_ranking(uni_id: str) -> dict | None:
    for r in RANKINGS:
        if r.get("university_id") == uni_id:
            return r
    return None


def get_eligibility(uni_id: str, field: str) -> dict | None:
    """
    Find the best matching eligibility rule for a given university and field.
    """
    candidates = [r for r in ELIGIBILITY_RULES if r.get("university_id") == uni_id]
    if not candidates:
        return None

    # Try to match program name to field
    for rule in candidates:
        prog = (rule.get("program") or "").lower()
        if field and field.lower() in prog:
            return rule

    # Fall back to first rule for this university
    return candidates[0]


def score_university(profile: Profile, uni_id: str) -> dict:
    """
    Score a university against the student profile.
    Returns a dict with score components.
    """
    ranking = get_ranking(uni_id)
    base_score = ranking.get("ranking_score", 50) if ranking else 50
    tier = ranking.get("rank_tier", 4) if ranking else 4

    city = profile.city_preference or ""
    field = profile.preferred_field or ""
    budget_str = profile.budget or ""
    try:
        budget_val = float(budget_str.replace(",", ""))
    except (ValueError, AttributeError):
        budget_val = None

    # City match bonus
    city_bonus = 0
    if city:
        city_lower = city.lower()
        # Search in chunks metadata later; for now simple check
        city_bonus = 5  # will be refined per university below

    # Field match bonus
    field_bonus = 0
    if field:
        field_bonus = 5

    # Marks fit from eligibility rules
    marks_fit = 0
    try:
        inter_pct = float(profile.inter_marks or 0)
        matric_pct = float(profile.matric_marks or 0)
    except (ValueError, AttributeError):
        inter_pct = 0
        matric_pct = 0

    elig = get_eligibility(uni_id, field)
    if elig:
        min_inter = elig.get("minimum_inter_percentage", 0)
        min_matric = elig.get("minimum_matric_percentage", 0)
        if inter_pct >= min_inter and matric_pct >= min_matric:
            marks_fit = 10
        elif inter_pct >= min_inter or matric_pct >= min_matric:
            marks_fit = 5

    total = base_score + city_bonus + field_bonus + marks_fit

    return {
        "university_id": uni_id,
        "base_score": base_score,
        "tier": tier,
        "city_bonus": city_bonus,
        "field_bonus": field_bonus,
        "marks_fit": marks_fit,
        "total_score": total,
    }


def get_city_from_chunks(uni_id: str, chunks: list[dict]) -> str:
    for c in chunks:
        if c.get("university_id") == uni_id and c.get("city"):
            return c["city"]
    return ""


# =============================================
# LLM provider helpers
# =============================================

async def call_lm_studio(prompt: str) -> str | None:
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
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


async def call_ollama(prompt: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            })
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data["message"]["content"].strip()
    except Exception:
        return None


def build_fallback_answer(scores: list[dict], chunks: list[dict], profile: Profile, question: str) -> str:
    """
    Build a rule-based answer when no LLM is available.
    Uses ranking scores and retrieved chunks.
    """
    field = profile.preferred_field or "Computer Science"
    city = profile.city_preference or "any city"

    lines = []
    lines.append(f"Here is a counselling overview for {profile.name or 'you'} in {field} (preferred city: {city}).\n")
    lines.append("Note: The AI provider (LM Studio / Ollama) is not running. This answer is based on our data only.\n")

    if scores:
        # Sort by total score descending
        sorted_scores = sorted(scores, key=lambda s: s["total_score"], reverse=True)

        best = sorted_scores[:3]
        lines.append("Best match universities based on your profile:")
        for s in best:
            uni_chunks = [c for c in chunks if c.get("university_id") == s["university_id"]]
            uni_name = uni_chunks[0]["university_name"] if uni_chunks else s["university_id"]
            lines.append(f"  - {uni_name} (score: {s['total_score']})")

        if len(sorted_scores) > 3:
            lines.append("\nOther options to consider:")
            for s in sorted_scores[3:]:
                uni_chunks = [c for c in chunks if c.get("university_id") == s["university_id"]]
                uni_name = uni_chunks[0]["university_name"] if uni_chunks else s["university_id"]
                lines.append(f"  - {uni_name} (score: {s['total_score']})")

    lines.append("\nNext steps:")
    lines.append("1. Review admission criteria on each university's official website")
    lines.append("2. Prepare for required entry tests")
    lines.append("3. Check application deadlines")
    lines.append("4. Apply to a mix of target and safe universities")

    lines.append("\nImportant: Eligibility depends on official admission policy and merit each year.")
    lines.append("Please verify all details from official university admission pages before applying.")

    return "\n".join(lines)


def format_sources(chunks: list[dict]) -> list[SourceItem]:
    seen = {}
    sources = []
    for c in chunks:
        key = c.get("university_name", "") + c.get("source_url", "")
        if key not in seen:
            seen[key] = True
            sources.append(SourceItem(
                university_name=c.get("university_name", ""),
                source_url=c.get("source_url", ""),
                preview=c.get("preview", ""),
            ))
    return sources[:5]


# =============================================
# Build the master prompt
# =============================================

def build_master_prompt(profile: Profile, question: str, context: str, scores: list[dict], chunks: list[dict]) -> str:
    field = profile.preferred_field or "Computer Science"
    city = profile.city_preference or "any city"
    budget_str = profile.budget or "not specified"

    # Build scored universities section
    sorted_scores = sorted(scores, key=lambda s: s["total_score"], reverse=True)
    scored_table = []
    for s in sorted_scores:
        uni_chunks = [c for c in chunks if c.get("university_id") == s["university_id"]]
        uni_name = uni_chunks[0]["university_name"] if uni_chunks else s["university_id"]
        tier_label = f"Tier {s['tier']}"
        scored_table.append(
            f"  - {uni_name} | Score: {s['total_score']} | {tier_label} | "
            f"Base: {s['base_score']} + City: {s['city_bonus']} + Field: {s['field_bonus']} + Marks: {s['marks_fit']}"
        )

    scored_section = "\n".join(scored_table) if scored_table else "  (No scoring data available)"

    return f"""You are a university counsellor for Pakistani students. Answer the student's question using ONLY the provided admission data and ranking information.

STUDENT PROFILE:
Name: {profile.name}
Matric: {profile.matric_marks}%
Intermediate: {profile.inter_marks}%
Entry Test: {profile.entry_test}
Preferred Field: {field}
Preferred City: {city}
Budget: {budget_str}

STUDENT QUESTION:
{question}

RETRIEVED UNIVERSITY DATA:
{context}

UNIVERSITY RANKING SCORES (higher = better match):
{scored_section}

INSTRUCTIONS:
- Answer in simple English as a helpful student counsellor.
- Use ONLY the retrieved data above — do not invent admission facts.
- If information is missing, say: "Please verify this from the official university website."
- Structure your response with these sections:

1. **Short Summary** — 1-2 sentences addressing the student's main concern.
2. **Best Match Universities** — 2-3 universities that fit the student's profile well, with a short reason for each.
3. **Safe Options** — Universities where the student's marks meet/exceed minimum eligibility, with lower entry competition.
4. **Difficult Options** — Universities with very high merit or competitive entry (tier 1).
5. **Reason for Recommendation** — Based on marks, field match, city preference, budget, and university ranking.
6. **Next Steps** — Practical advice on entry tests, deadlines, and applications.
7. **Source Notes** — Mention that data comes from official university websites where available.

IMPORTANT:
- Never guarantee admission. Always say: "Eligibility depends on official admission policy and merit each year."
- If budget is under 200,000 PKR, recommend public universities.
- If the student has high marks (85%+ in Inter), they can consider tier 1 universities.
- If marks are moderate (60-75%), suggest tier 2-3 universities as primary options.
- End with: "Please verify all details from official university admission pages before applying."
"""


# =============================================
# GET /health
# =============================================

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Backend is running"}


# =============================================
# GET /providers
# =============================================

@app.get("/providers")
async def providers():
    return {
        "providers": {
            "lm_studio": {"url": LM_STUDIO_URL, "model": LM_STUDIO_MODEL, "active": "lm_studio" in PROVIDER_ORDER},
            "ollama": {"url": OLLAMA_URL, "model": OLLAMA_MODEL, "active": "ollama" in PROVIDER_ORDER},
            "fallback": {"active": "fallback" in PROVIDER_ORDER},
        },
        "provider_order": PROVIDER_ORDER
    }


# =============================================
# POST /counsel — main RAG counselling endpoint
# =============================================

@app.post("/counsel")
async def counsel(request: CounselRequest):
    profile = request.profile
    question = request.question

    # Build a rich search query from profile + question
    search_parts = [
        f"field: {profile.preferred_field}" if profile.preferred_field else "",
        f"city: {profile.city_preference}" if profile.city_preference else "",
        f"budget: {profile.budget}" if profile.budget else "",
        f"matric: {profile.matric_marks}% inter: {profile.inter_marks}%" if profile.matric_marks else "",
        f"entry test: {profile.entry_test}" if profile.entry_test else "",
        question,
    ]
    search_query = " ".join(p for p in search_parts if p)

    # Search Chroma
    chunks = search_chroma_detailed(search_query, top_k=7)
    retrieved_count = len(chunks)

    # Build context text for prompt
    # Truncate each chunk text to keep prompt manageable
    MAX_CHUNK_CHARS = 1500
    context_lines = []
    for c in chunks:
        truncated = c['text'][:MAX_CHUNK_CHARS]
        context_lines.append(
            f"[{c['university_name']} - {c['category']}]\n{truncated}"
        )
    context = "\n\n---\n\n".join(context_lines) if context_lines else ""

    # Score universities found in chunks
    uni_ids_seen = set()
    scores = []
    for c in chunks:
        uid = c.get("university_id")
        if uid and uid not in uni_ids_seen:
            uni_ids_seen.add(uid)
            s = score_university(profile, uid)
            # Apply city/field bonuses from actual chunk data
            city_match = profile.city_preference or ""
            if city_match and city_match.lower() in c.get("city", "").lower():
                s["city_bonus"] = 10
                s["total_score"] = s["base_score"] + 10 + s["field_bonus"] + s["marks_fit"]
            field_match = profile.preferred_field or ""
            if field_match and field_match.lower() in c.get("field_type", "").lower():
                s["field_bonus"] = 10
                s["total_score"] = s["base_score"] + s["city_bonus"] + 10 + s["marks_fit"]
            scores.append(s)

    # Try LLM providers in order
    answer = ""
    provider_used = "fallback"

    if context:
        prompt = build_master_prompt(profile, question, context, scores, chunks)

        for provider in PROVIDER_ORDER:
            provider = provider.strip()
            if provider == "lm_studio":
                result = await call_lm_studio(prompt)
                if result:
                    answer = result
                    provider_used = "lmstudio"
                    break
            elif provider == "ollama":
                result = await call_ollama(prompt)
                if result:
                    answer = result
                    provider_used = "ollama"
                    break
            elif provider == "fallback":
                answer = build_fallback_answer(scores, chunks, profile, question)
                provider_used = "fallback"
                break

    if not answer:
        answer = build_fallback_answer(scores, chunks, profile, question)
        provider_used = "fallback"

    # Build sources list
    sources = format_sources(chunks)

    return CounselResponse(
        answer=answer,
        sources=sources,
        retrieved_count=retrieved_count,
        provider_used=provider_used,
    )


# =============================================
# GET /search — search Chroma vector DB
# =============================================

@app.get("/search")
async def search(q: str = Query(..., description="Search query")):
    items = search_chroma_detailed(q, top_k=5)
    return {
        "query": q,
        "results_count": len(items),
        "results": items
    }
