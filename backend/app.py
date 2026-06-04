"""
Pakistan CS & SE University Counsellor — FastAPI Backend

Endpoints:
  POST /counsel          — accepts student profile + question, returns counselling answer
  GET  /health           — health check
  GET  /providers        — shows configured LLM providers
  GET  /debug/providers  — tests provider reachability with detailed results
  GET  /search           — search Chroma vector DB

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
LM_STUDIO_MODELS_URL = os.environ.get("LM_STUDIO_MODELS_URL", "http://localhost:1234/v1/models")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:latest")
OLLAMA_TAGS_URL = os.environ.get("OLLAMA_TAGS_URL", "http://localhost:11434/api/tags")
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
    education_system: str = "matric"
    matric_marks: str = ""
    inter_marks: str = ""
    o_level_equivalence: str = ""
    a_level_equivalence: str = ""
    o_level_grade: str = ""
    a_level_grade: str = ""
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
    selected_model: str = ""

# ──────────────────────────────────────────────
# Academic profile normalisation
# ──────────────────────────────────────────────

def grade_to_pct(grade: str) -> float:
    mapping = {"A*": 95, "A": 90, "B": 80, "C": 70, "D": 60, "E": 50}
    return mapping.get(grade.strip(), 0)

def normalize_academic_profile(profile: Profile) -> dict:
    matric_eq = 0.0
    inter_eq = 0.0
    notes = []

    if profile.education_system in ("olevel",):
        o_equiv = profile.o_level_equivalence
        a_equiv = profile.a_level_equivalence
        o_grade = profile.o_level_grade
        a_grade = profile.a_level_grade

        if o_equiv:
            try:
                matric_eq = float(o_equiv)
                notes.append("O Level equivalence provided")
            except ValueError:
                matric_eq = 0
        elif o_grade:
            matric_eq = grade_to_pct(o_grade)
            notes.append(f"O Level grade {o_grade} mapped to {matric_eq}% (estimate)")

        if a_equiv:
            try:
                inter_eq = float(a_equiv)
                notes.append("A Level equivalence provided")
            except ValueError:
                inter_eq = 0
        elif a_grade:
            inter_eq = grade_to_pct(a_grade)
            notes.append(f"A Level grade {a_grade} mapped to {inter_eq}% (estimate)")

        if not matric_eq and not inter_eq:
            notes.append("No O/A Level data provided — please enter grades or equivalence")
    else:
        try:
            matric_eq = float(profile.matric_marks or 0)
        except ValueError:
            matric_eq = 0
        try:
            inter_eq = float(profile.inter_marks or 0)
        except ValueError:
            inter_eq = 0

    return {
        "matric_equivalent_pct": matric_eq,
        "inter_equivalent_pct": inter_eq,
        "academic_notes": "; ".join(notes) if notes else "",
    }

# ──────────────────────────────────────────────
# Chroma search helpers
# ──────────────────────────────────────────────

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

# ──────────────────────────────────────────────
# Ranking and scoring helpers
# ──────────────────────────────────────────────

def get_ranking(uni_id: str) -> dict | None:
    for r in RANKINGS:
        if r.get("university_id") == uni_id:
            return r
    return None

def get_eligibility(uni_id: str, field: str) -> dict | None:
    candidates = [r for r in ELIGIBILITY_RULES if r.get("university_id") == uni_id]
    if not candidates:
        return None
    for rule in candidates:
        prog = (rule.get("program") or "").lower()
        if field and field.lower() in prog:
            return rule
    return candidates[0]

def score_university(profile: Profile, uni_id: str, normalized: dict, chunks: list[dict]) -> dict:
    ranking = get_ranking(uni_id)
    base_score = ranking.get("ranking_score", 50) if ranking else 50
    tier = ranking.get("rank_tier", 4) if ranking else 4

    city = profile.city_preference or ""
    field = profile.preferred_field or ""

    inter_pct = normalized["inter_equivalent_pct"]
    matric_pct = normalized["matric_equivalent_pct"]

    city_bonus = 0
    city_match = city.lower()
    for c in chunks:
        if c.get("university_id") == uni_id and city_match in c.get("city", "").lower():
            city_bonus = 10
            break

    field_bonus = 0
    field_match = field.lower()
    for c in chunks:
        if c.get("university_id") == uni_id and field_match in c.get("field_type", "").lower():
            field_bonus = 10
            break

    marks_fit = 0
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

# ──────────────────────────────────────────────
# LLM provider helpers
# ──────────────────────────────────────────────

async def call_lm_studio(prompt: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(LM_STUDIO_URL, json={
                "model": LM_STUDIO_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful university counsellor for Pakistani students. Answer concisely."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
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
                "options": {
                    "temperature": 0.3,
                    "num_predict": 2048
                },
                "stream": False
            })
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data["message"]["content"].strip()
    except Exception:
        return None

def build_fallback_answer(scores: list[dict], chunks: list[dict], profile: Profile, question: str, normalized: dict, incomplete: bool = False) -> str:
    field = profile.preferred_field or "Computer Science"
    city = profile.city_preference or "any city"
    academic_note = normalized.get("academic_notes", "")

    lines = []
    lines.append(f"Here is a counselling overview for {profile.name or 'you'} in {field} (preferred city: {city}).")
    if academic_note:
        lines.append(f"\n{academic_note}")
    if incomplete:
        lines.append("\nNote: The AI provider tried but its response was incomplete. This answer is based on our data only.\n")
    else:
        lines.append("\nNote: The AI provider (LM Studio / Ollama) is not running. This answer is based on our data only.\n")

    if scores:
        sorted_scores = sorted(scores, key=lambda s: s["total_score"], reverse=True)
        best = sorted_scores[:3]
        lines.append("**Best match universities based on your profile:**")
        for s in best:
            uni_chunks = [c for c in chunks if c.get("university_id") == s["university_id"]]
            uni_name = uni_chunks[0]["university_name"] if uni_chunks else s["university_id"]
            lines.append(f"- {uni_name} (score: {s['total_score']})")

        if len(sorted_scores) > 3:
            lines.append("\n**Other options to consider:**")
            for s in sorted_scores[3:]:
                uni_chunks = [c for c in chunks if c.get("university_id") == s["university_id"]]
                uni_name = uni_chunks[0]["university_name"] if uni_chunks else s["university_id"]
                lines.append(f"- {uni_name} (score: {s['total_score']})")

    lines.append("\n**Next steps:**")
    lines.append("1. Review admission criteria on each university's official website")
    lines.append("2. Prepare for required entry tests")
    lines.append("3. Check application deadlines")
    lines.append("4. Apply to a mix of target and safe universities")
    lines.append("\n*This tool gives guidance only. Final admission depends on official university policy and merit.*")

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

# ──────────────────────────────────────────────
# Build the master prompt (shorter, faster)
# ──────────────────────────────────────────────

def build_master_prompt(profile: Profile, question: str, context: str, scores: list[dict],
                        chunks: list[dict], normalized: dict) -> str:
    field = profile.preferred_field or "Computer Science"
    city = profile.city_preference or "any city"
    budget_str = profile.budget or "not specified"
    academic_notes = normalized.get("academic_notes", "")

    inter_pct = normalized["inter_equivalent_pct"]
    matric_pct = normalized["matric_equivalent_pct"]

    sorted_scores = sorted(scores, key=lambda s: s["total_score"], reverse=True)
    scored_lines = []
    for s in sorted_scores:
        uni_chunks = [c for c in chunks if c.get("university_id") == s["university_id"]]
        uni_name = uni_chunks[0]["university_name"] if uni_chunks else s["university_id"]
        scored_lines.append(f"- {uni_name} (score: {s['total_score']}, tier: {s['tier']})")

    scored_section = "\n".join(scored_lines) if scored_lines else "(No scoring data)"

    return f"""You are a university counsellor for Pakistani students. Write a complete answer.

STUDENT:
Name: {profile.name}
Marks: Matric {matric_pct}%, Inter {inter_pct}%
Entry Test: {profile.entry_test}
Field: {field} | City: {city} | Budget: {budget_str}
{("Note: " + academic_notes) if academic_notes else ""}

QUESTION:
{question}

DATA:
{context}

SCORES (higher = better match):
{scored_section}

Write exactly 5 sections below. Do NOT write a letter or greeting. Go straight into the sections:

1. **Summary** — 2-3 sentences summarising the student's situation and main recommendation
2. **Best matches** — 2-3 universities that fit well, with a short reason for each
3. **Safe options** — universities where marks meet minimums and entry is less competitive
4. **Difficult options** — high merit universities that are harder to get into
5. **Next steps** — practical advice on entry tests, deadlines, and applications

Rules:
- Never guarantee admission. Say: "Eligibility depends on official policy and merit each year."
- If budget is under 200,000 PKR, recommend public universities.
- If the student has high marks (85%+ in Inter), they can consider tier 1 universities.
- If marks are moderate (60-75%), suggest tier 2-3 universities as primary options.
- End with: "Please verify all details from official university admission pages before applying."
- Write complete sentences. Finish every section before moving to the next."""

# ──────────────────────────────────────────────
# GET /health
# ──────────────────────────────────────────────

@app.get("/health")
async def health():
    docs = rag_collection.count() if rag_collection else 0
    lm_studio = False
    ollama = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(LM_STUDIO_MODELS_URL)
            lm_studio = r.status_code == 200
    except Exception:
        pass
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(OLLAMA_TAGS_URL)
            ollama = r.status_code == 200
    except Exception:
        pass
    return {
        "status": "ok",
        "chroma_docs": docs,
        "lm_studio": lm_studio,
        "ollama": ollama
    }

# ──────────────────────────────────────────────
# GET /providers
# ──────────────────────────────────────────────

@app.get("/providers")
async def providers():
    lm_studio_ok = False
    lm_studio_err = ""
    ollama_ok = False
    ollama_err = ""
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(LM_STUDIO_MODELS_URL)
            lm_studio_ok = r.status_code == 200
            if not lm_studio_ok:
                lm_studio_err = f"HTTP {r.status_code}"
    except Exception as e:
        lm_studio_err = str(e)

    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(OLLAMA_TAGS_URL)
            ollama_ok = r.status_code == 200
            if not ollama_ok:
                ollama_err = f"HTTP {r.status_code}"
    except Exception as e:
        ollama_err = str(e)

    return {
        "providers": {
            "lm_studio": {
                "url": LM_STUDIO_URL,
                "model": LM_STUDIO_MODEL,
                "active": "lm_studio" in PROVIDER_ORDER,
                "reachable": lm_studio_ok,
                "error": lm_studio_err
            },
            "ollama": {
                "url": OLLAMA_URL,
                "model": OLLAMA_MODEL,
                "active": "ollama" in PROVIDER_ORDER,
                "reachable": ollama_ok,
                "error": ollama_err
            },
            "fallback": {
                "active": "fallback" in PROVIDER_ORDER
            }
        },
        "provider_order": PROVIDER_ORDER
    }

# ──────────────────────────────────────────────
# GET /debug/providers — detailed provider testing
# ──────────────────────────────────────────────

@app.get("/debug/providers")
async def debug_providers():
    lm_studio_reachable = False
    lm_studio_models = []
    lm_studio_err = ""
    ollama_reachable = False
    ollama_models = []
    ollama_err = ""

    # Test LM Studio models endpoint
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(LM_STUDIO_MODELS_URL)
            if r.status_code == 200:
                lm_studio_reachable = True
                data = r.json()
                if "data" in data:
                    lm_studio_models = [m.get("id", "") for m in data["data"]]
                else:
                    lm_studio_models = ["(no model list returned)"]
            else:
                lm_studio_err = f"HTTP {r.status_code}"
    except Exception as e:
        lm_studio_err = str(e)

    # Test LM Studio chat endpoint
    lm_studio_chat = False
    if lm_studio_reachable:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.post(LM_STUDIO_URL, json={
                    "model": LM_STUDIO_MODEL,
                    "messages": [{"role": "user", "content": "Say hi"}],
                    "max_tokens": 10,
                    "stream": False
                })
                lm_studio_chat = r.status_code == 200
        except Exception:
            lm_studio_chat = False

    # Test Ollama tags endpoint
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(OLLAMA_TAGS_URL)
            if r.status_code == 200:
                ollama_reachable = True
                data = r.json()
                if "models" in data:
                    ollama_models = [m.get("name", "") for m in data["models"]]
                else:
                    ollama_models = ["(no model list returned)"]
            else:
                ollama_err = f"HTTP {r.status_code}"
    except Exception as e:
        ollama_err = str(e)

    # Test Ollama chat endpoint
    ollama_chat = False
    if ollama_reachable:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.post(OLLAMA_URL, json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": "Say hi"}],
                    "options": {"num_predict": 10},
                    "stream": False
                })
                ollama_chat = r.status_code == 200
        except Exception:
            ollama_chat = False

    return {
        "lm_studio": {
            "reachable": lm_studio_reachable,
            "url": LM_STUDIO_URL,
            "models_url": LM_STUDIO_MODELS_URL,
            "models": lm_studio_models,
            "chat_reachable": lm_studio_chat,
            "error": lm_studio_err
        },
        "ollama": {
            "reachable": ollama_reachable,
            "url": OLLAMA_URL,
            "tags_url": OLLAMA_TAGS_URL,
            "models": ollama_models,
            "chat_reachable": ollama_chat,
            "error": ollama_err
        }
    }

def is_complete_answer(text: str) -> bool:
    if not text:
        return False
    cleaned = text.strip()
    if len(cleaned) < 100:
        return False
    last_char = cleaned[-1]
    if last_char in (".", "!", "?"):
        return True
    if len(cleaned) > 200:
        return True
    return False


# ──────────────────────────────────────────────
# POST /counsel — main RAG counselling endpoint
# ──────────────────────────────────────────────

@app.post("/counsel")
async def counsel(request: CounselRequest):
    profile = request.profile
    question = request.question

    # Normalize academic profile
    normalized = normalize_academic_profile(profile)

    # Build a rich search query from profile + question
    search_parts = [
        f"field: {profile.preferred_field}" if profile.preferred_field else "",
        f"city: {profile.city_preference}" if profile.city_preference else "",
        f"budget: {profile.budget}" if profile.budget else "",
        f"matric: {normalized['matric_equivalent_pct']}% inter: {normalized['inter_equivalent_pct']}%" if normalized['matric_equivalent_pct'] else "",
        f"entry test: {profile.entry_test}" if profile.entry_test else "",
        question,
    ]
    search_query = " ".join(p for p in search_parts if p)

    chunks = search_chroma_detailed(search_query, top_k=5)
    retrieved_count = len(chunks)

    MAX_CHUNK_CHARS = 1200
    context_lines = []
    for c in chunks:
        truncated = c['text'][:MAX_CHUNK_CHARS]
        context_lines.append(
            f"[{c['university_name']} - {c['category']}]\n{truncated}"
        )
    context = "\n\n---\n\n".join(context_lines) if context_lines else ""

    uni_ids_seen = set()
    scores = []
    for c in chunks:
        uid = c.get("university_id")
        if uid and uid not in uni_ids_seen:
            uni_ids_seen.add(uid)
            s = score_university(profile, uid, normalized, chunks)
            scores.append(s)

    answer = ""
    provider_used = "fallback"
    selected_model = ""

    if context:
        prompt = build_master_prompt(profile, question, context, scores, chunks, normalized)

        for provider in PROVIDER_ORDER:
            provider = provider.strip()
            if provider == "lm_studio":
                result = await call_lm_studio(prompt)
                if result and is_complete_answer(result):
                    answer = result
                    provider_used = "lmstudio"
                    selected_model = LM_STUDIO_MODEL
                    break
            elif provider == "ollama":
                result = await call_ollama(prompt)
                if result and is_complete_answer(result):
                    answer = result
                    provider_used = "ollama"
                    selected_model = OLLAMA_MODEL
                    break
                elif result and not is_complete_answer(result):
                    answer = build_fallback_answer(scores, chunks, profile, question, normalized, incomplete=True)
                    provider_used = "fallback_after_incomplete"
                    selected_model = ""
                    break
            elif provider == "fallback":
                answer = build_fallback_answer(scores, chunks, profile, question, normalized)
                provider_used = "fallback"
                break

    if not answer:
        answer = build_fallback_answer(scores, chunks, profile, question, normalized)
        provider_used = "fallback"

    sources = format_sources(chunks)

    return CounselResponse(
        answer=answer,
        sources=sources,
        retrieved_count=retrieved_count,
        provider_used=provider_used,
        selected_model=selected_model,
    )

# ──────────────────────────────────────────────
# GET /search — search Chroma vector DB
# ──────────────────────────────────────────────

@app.get("/search")
async def search(q: str = Query(..., description="Search query")):
    items = search_chroma_detailed(q, top_k=5)
    return {
        "query": q,
        "results_count": len(items),
        "results": items
    }
