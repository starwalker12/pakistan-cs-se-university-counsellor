"""
DigiCounsellor — FastAPI Backend

Endpoints:
  POST /counsel          — accepts student profile + question, returns counselling answer
  GET  /health           — health check
  GET  /providers        — shows configured LLM providers
  GET  /debug/providers  — tests provider reachability with detailed results
  GET  /search           — search Chroma vector DB

LLM Provider order:
  1. Ollama (local)
  2. LM Studio (OpenAI-compatible endpoint)
  3. Static fallback (rule-based answer from retrieved data)
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import os
import json
import time
from sentence_transformers import SentenceTransformer
import chromadb

app = FastAPI(title="DigiCounsellor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Provider configuration
# ──────────────────────────────────────────────
def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")

def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default

LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")
LM_STUDIO_MODEL = os.environ.get("LM_STUDIO_MODEL", "gemma")
LM_STUDIO_MODELS_URL = os.environ.get("LM_STUDIO_MODELS_URL", "http://localhost:1234/v1/models")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:latest")
OLLAMA_TAGS_URL = os.environ.get("OLLAMA_TAGS_URL", "http://localhost:11434/api/tags")
PROVIDER_ORDER = os.environ.get("PROVIDER_ORDER", "ollama,lm_studio,fallback").split(",")
FAST_MODE = env_bool("FAST_MODE", True)
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "45"))
OLLAMA_NUM_PREDICT = min(env_int("OLLAMA_NUM_PREDICT", 700 if FAST_MODE else 900), 900)
LM_STUDIO_MAX_TOKENS = min(env_int("LM_STUDIO_MAX_TOKENS", 700 if FAST_MODE else 900), 900)
AI_SUMMARY_NUM_PREDICT = min(env_int("AI_SUMMARY_NUM_PREDICT", 450), OLLAMA_NUM_PREDICT)
AI_SUMMARY_MAX_TOKENS = min(env_int("AI_SUMMARY_MAX_TOKENS", 450), LM_STUDIO_MAX_TOKENS)
CACHE_MAX_ITEMS = env_int("COUNSEL_CACHE_MAX_ITEMS", 80)
COUNSEL_CACHE: dict[str, dict] = {}
RECOMMEND_CACHE: dict[str, dict] = {}
AI_SUMMARY_CACHE: dict[str, dict] = {}

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
UNIVERSITIES = []
SOURCE_LINKS = []
UNIVERSITY_BY_ID = {}
SOURCE_LINKS_BY_ID = {}

def load_local_data():
    global RANKINGS, ELIGIBILITY_RULES, UNIVERSITIES, SOURCE_LINKS, UNIVERSITY_BY_ID, SOURCE_LINKS_BY_ID
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
    try:
        universities_path = os.path.join(DATA_DIR, "universities.json")
        with open(universities_path, "r", encoding="utf-8") as f:
            UNIVERSITIES = json.load(f)
        UNIVERSITY_BY_ID = {u.get("id", ""): u for u in UNIVERSITIES}
        print(f"Loaded {len(UNIVERSITIES)} university records")
    except Exception as e:
        print(f"Could not load universities: {e}")
    try:
        links_path = os.path.join(DATA_DIR, "source_links.json")
        with open(links_path, "r", encoding="utf-8") as f:
            SOURCE_LINKS = json.load(f)
        SOURCE_LINKS_BY_ID = {item.get("university_id", ""): item for item in SOURCE_LINKS}
        print(f"Loaded {len(SOURCE_LINKS)} source link records")
    except Exception as e:
        print(f"Could not load source links: {e}")

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
    matric_percentage: str = ""
    intermediate_percentage: str = ""
    o_level_equivalence: str = ""
    a_level_equivalence: str = ""
    o_level_grade: str = ""
    a_level_grade: str = ""
    entry_test: str = ""
    preferred_field: str = ""
    city_preference: str = ""
    budget: str = ""
    university_type: str = "either"

class CounselRequest(BaseModel):
    profile: Profile
    question: str
    selected_university: str | None = ""

class SourceItem(BaseModel):
    university_name: str = ""
    source_url: str = ""
    preview: str = ""

class AdmissionLink(BaseModel):
    label: str = ""
    url: str = ""
    note: str = ""

class RecommendationItem(BaseModel):
    university_id: str = ""
    university_name: str = ""
    short_name: str = ""
    city: str = ""
    campuses: list[str] = Field(default_factory=list)
    university_type: str = ""
    fields: list[str] = Field(default_factory=list)
    fit_level: str = ""
    fit_score: int = 0
    tier_label: str = ""
    match_reason: str = ""
    eligibility_summary: str = ""
    fee_summary: str = ""
    entry_test: str = ""
    admission_links: list[AdmissionLink] = Field(default_factory=list)
    source_preview: str = ""

class TimingInfo(BaseModel):
    total_seconds: float = 0.0
    rag_seconds: float = 0.0
    scoring_seconds: float = 0.0
    llm_seconds: float = 0.0
    cached: bool = False

class CounselResponse(BaseModel):
    answer: str
    sources: list[SourceItem] = Field(default_factory=list)
    recommended_universities: list[RecommendationItem] = Field(default_factory=list)
    safe_options: list[RecommendationItem] = Field(default_factory=list)
    difficult_options: list[RecommendationItem] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    admission_links: list[AdmissionLink] = Field(default_factory=list)
    retrieved_count: int = 0
    provider_used: str = ""
    selected_model: str = ""
    selected_university: str = ""
    timing: TimingInfo | None = None

class RecommendResponse(BaseModel):
    sources: list[SourceItem] = Field(default_factory=list)
    recommended_universities: list[RecommendationItem] = Field(default_factory=list)
    safe_options: list[RecommendationItem] = Field(default_factory=list)
    difficult_options: list[RecommendationItem] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    admission_links: list[AdmissionLink] = Field(default_factory=list)
    retrieved_count: int = 0
    provider_used: str = "data"
    selected_model: str = "structured scoring"
    selected_university: str = ""
    timing: TimingInfo | None = None

class AISummaryRequest(BaseModel):
    profile: Profile
    question: str
    selected_university: str | None = ""
    recommended_universities: list[RecommendationItem] = Field(default_factory=list)
    safe_options: list[RecommendationItem] = Field(default_factory=list)
    difficult_options: list[RecommendationItem] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)

class AISummaryResponse(BaseModel):
    answer: str = ""
    provider_used: str = ""
    selected_model: str = ""
    timing: TimingInfo | None = None

def model_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()

def request_cache_key(profile: Profile, question: str, selected_university: str | None,
                      extra: dict | None = None) -> str:
    payload = {
        "profile": model_dict(profile),
        "question": (question or "").strip().lower(),
        "selected_university": (selected_university or "").strip().lower(),
        "fast_mode": FAST_MODE,
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))

def counsel_cache_key(profile: Profile, question: str, selected_university: str | None) -> str:
    return request_cache_key(profile, question, selected_university, {"endpoint": "counsel"})

def recommend_cache_key(profile: Profile, question: str, selected_university: str | None) -> str:
    return request_cache_key(profile, question, selected_university, {"endpoint": "recommend"})

def ai_summary_cache_key(request: AISummaryRequest, selected_university: str | None) -> str:
    rec_ids = [r.university_id for r in request.recommended_universities[:5]]
    return request_cache_key(
        request.profile,
        request.question,
        selected_university,
        {
            "endpoint": "ai-summary",
            "model": OLLAMA_MODEL,
            "rec_ids": rec_ids,
        }
    )

def cache_get(cache: dict[str, dict], cache_key: str, model_cls):
    cached = cache.get(cache_key)
    if not cached:
        return None
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(cached)
    return model_cls.parse_obj(cached)

def cache_store(cache: dict[str, dict], cache_key: str, response: BaseModel) -> None:
    cache[cache_key] = model_dict(response)
    while len(cache) > CACHE_MAX_ITEMS:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key, None)

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
            matric_eq = float(profile.matric_marks or profile.matric_percentage or 0)
        except ValueError:
            matric_eq = 0
        try:
            inter_eq = float(profile.inter_marks or profile.intermediate_percentage or 0)
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

KNOWN_CITIES = [
    "Lahore", "Islamabad", "Rawalpindi", "Karachi", "Peshawar", "Quetta",
    "Multan", "Faisalabad", "Sialkot", "Gujranwala", "Hyderabad",
    "Bahawalpur", "Taxila", "Wah", "Abbottabad", "Jamshoro", "Sukkur",
    "Topi", "Vehari", "Sahiwal", "Attock", "Larkana"
]

def get_ranking(uni_id: str) -> dict | None:
    for r in RANKINGS:
        if r.get("university_id") == uni_id:
            return r
    return None

def normalize_field(field: str) -> str:
    value = (field or "").strip().lower()
    if value in ("se", "software engineering", "bs se"):
        return "Software Engineering"
    if value in ("cs", "computer science", "bs cs"):
        return "Computer Science"
    return field or "Computer Science"

def get_eligibility(uni_id: str, field: str) -> dict | None:
    candidates = [r for r in ELIGIBILITY_RULES if r.get("university_id") == uni_id]
    if not candidates:
        return None
    normalized_field = normalize_field(field).lower()
    for rule in candidates:
        prog = (rule.get("program") or "").lower()
        if normalized_field and normalized_field in prog:
            return rule
    return candidates[0]

def parse_budget_value(raw: str) -> float:
    if not raw:
        return 0.0
    digits = []
    current = []
    for ch in raw:
        if ch.isdigit():
            current.append(ch)
        elif current:
            digits.append("".join(current))
            current = []
    if current:
        digits.append("".join(current))
    values = [float(d) for d in digits if d]
    return max(values) if values else 0.0

def infer_city_from_text(text: str) -> str:
    lower = (text or "").lower()
    for city in KNOWN_CITIES:
        if city.lower() in lower:
            return city
    return ""

def resolve_university_id(text: str) -> str:
    lower = (text or "").lower()
    if not lower:
        return ""
    aliases = {
        "fast": "nuces-fast",
        "nuces": "nuces-fast",
        "nust": "nust",
        "comsats": "comsats",
        "lums": "lums",
        "giki": "giki",
        "pieas": "pieas",
        "uet lahore": "uet-lahore",
        "uet taxila": "uet-taxila",
        "itu": "itu-lahore",
        "air university": "air-university",
        "bahria": "bahria-university",
        "punjab university": "punjab-university",
        "qau": "qau",
        "ned": "ned-university",
        "karachi university": "university-of-karachi",
        "university of karachi": "university-of-karachi",
        "ucp": "ucp",
        "virtual university": "virtual-university",
        "szabist": "szabist",
        "iba": "iba-karachi",
        "ist": "ist",
    }
    for alias, uni_id in aliases.items():
        if alias in lower:
            return uni_id
    for uni in UNIVERSITIES:
        names = [
            uni.get("id", ""),
            uni.get("name", ""),
            uni.get("short_name", ""),
        ]
        if any(name and name.lower() in lower for name in names):
            return uni.get("id", "")
    return ""

def admission_links_for(uni_id: str) -> list[AdmissionLink]:
    record = SOURCE_LINKS_BY_ID.get(uni_id, {})
    links = record.get("links", {}) or {}
    label_map = {
        "admissions_homepage": "Admissions",
        "admissions_portal": "Admissions portal",
        "admissions": "Admissions",
        "eligibility_criteria": "Eligibility",
        "fee_structure": "Fee structure",
        "tuition_fees": "Tuition fees",
        "entry_test": "Entry test",
        "admission_schedule": "Schedule",
        "admissions_schedule": "Schedule",
        "undergraduate_programs": "Programs",
        "programs": "Programs",
    }
    preferred_order = [
        "admissions", "admissions_homepage", "admissions_portal",
        "eligibility_criteria", "fee_structure", "tuition_fees",
        "entry_test", "admission_schedule", "admissions_schedule",
        "undergraduate_programs", "programs"
    ]
    ordered_keys = [k for k in preferred_order if k in links]
    ordered_keys.extend(k for k in links if k not in ordered_keys)
    result = []
    for key in ordered_keys[:5]:
        item = links.get(key, {})
        result.append(AdmissionLink(
            label=label_map.get(key, key.replace("_", " ").title()),
            url=item.get("url", ""),
            note=item.get("note", "")
        ))
    return result

def chunk_preview_for(uni_id: str, chunks: list[dict], categories: tuple[str, ...] = ()) -> str:
    for chunk in chunks:
        if chunk.get("university_id") != uni_id:
            continue
        category = (chunk.get("category") or "").lower()
        if categories and not any(term in category for term in categories):
            continue
        preview = chunk.get("preview") or chunk.get("text", "")[:180]
        if preview:
            return preview[:220].replace("\n", " ").strip()
    return ""

def eligibility_summary(rule: dict | None, normalized: dict) -> tuple[str, str]:
    if not rule:
        return "unknown", "Eligibility needs official verification."
    inter_pct = normalized["inter_equivalent_pct"]
    matric_pct = normalized["matric_equivalent_pct"]
    min_inter = float(rule.get("minimum_inter_percentage", 0) or 0)
    min_matric = float(rule.get("minimum_matric_percentage", 0) or 0)
    test_name = rule.get("entry_test_name") or "Entry test"
    if inter_pct >= min_inter and matric_pct >= min_matric:
        status = "eligible"
        summary = f"Meets the approximate {min_inter:g}% Inter and {min_matric:g}% Matric minimums. {test_name} may still affect merit."
    elif inter_pct >= min_inter or matric_pct >= min_matric:
        status = "borderline"
        summary = f"Partly meets the approximate minimums; confirm equivalence, subjects, and merit formula."
    else:
        status = "difficult"
        summary = f"Below the approximate {min_inter:g}% Inter / {min_matric:g}% Matric guideline, so this is difficult unless official rules differ."
    return status, summary

def score_university(profile: Profile, uni_id: str, normalized: dict, effective_city: str = "") -> dict:
    university = UNIVERSITY_BY_ID.get(uni_id, {})
    ranking = get_ranking(uni_id)
    base_score = ranking.get("ranking_score", 50) if ranking else 50
    tier = ranking.get("rank_tier", 4) if ranking else 4
    tier_label = ranking.get("tier_label", "General") if ranking else "General"

    requested_city = effective_city or profile.city_preference or ""
    requested_field = normalize_field(profile.preferred_field)
    requested_type = (profile.university_type or "either").strip().lower()
    budget_value = parse_budget_value(profile.budget)

    city_bonus = 0
    city_penalty = 0
    reasons = []
    city_value = requested_city.strip().lower()
    cities = [c.lower() for c in university.get("cities", [])]
    if city_value and city_value != "any city":
        if any(city_value == c or city_value in c for c in cities):
            city_bonus = 12
            reasons.append(f"has a {requested_city} campus")
        else:
            city_penalty = -8

    field_bonus = 0
    fields = [f.lower() for f in university.get("fields", [])]
    if requested_field.lower() in fields:
        field_bonus = 12
        reasons.append(f"offers {requested_field}")
    elif requested_field.lower().startswith("software") and "computer science" in fields:
        field_bonus = 4
        reasons.append("has a related computing program")

    rule = get_eligibility(uni_id, requested_field)
    elig_status, elig_summary = eligibility_summary(rule, normalized)
    marks_fit = {"eligible": 12, "borderline": 4, "difficult": -8}.get(elig_status, 0)
    if elig_status == "eligible":
        reasons.append("meets the listed minimum marks")

    type_bonus = 0
    uni_type = (university.get("type") or "").lower()
    if requested_type in ("public", "private") and uni_type == requested_type:
        type_bonus = 8
        reasons.append(f"matches your {requested_type} preference")

    budget_bonus = 0
    if budget_value and budget_value < 250000:
        if uni_type == "public":
            budget_bonus = 8
            reasons.append("public-sector option suits a tighter budget")
        elif uni_type == "private":
            budget_bonus = -10

    total = int(base_score + city_bonus + city_penalty + field_bonus + marks_fit + type_bonus + budget_bonus)
    inter_pct = normalized["inter_equivalent_pct"]
    if elig_status == "difficult":
        fit_level = "Difficult"
    elif tier <= 2 and inter_pct < 82:
        fit_level = "Difficult"
    elif total >= 102:
        fit_level = "Best match"
    elif elig_status == "eligible" and (tier >= 3 or budget_bonus > 0):
        fit_level = "Safe"
    elif total < 72:
        fit_level = "Backup"
    else:
        fit_level = "Best match"

    return {
        "university_id": uni_id,
        "base_score": base_score,
        "tier": tier,
        "tier_label": tier_label,
        "city_bonus": city_bonus,
        "field_bonus": field_bonus,
        "marks_fit": marks_fit,
        "type_bonus": type_bonus,
        "budget_bonus": budget_bonus,
        "total_score": total,
        "fit_level": fit_level,
        "eligibility_status": elig_status,
        "eligibility_summary": elig_summary,
        "entry_test": rule.get("entry_test_name", "Check official policy") if rule else "Check official policy",
        "match_reasons": reasons,
    }

def build_recommendation_item(score: dict, profile: Profile, chunks: list[dict], effective_city: str = "") -> RecommendationItem:
    uni_id = score.get("university_id", "")
    university = UNIVERSITY_BY_ID.get(uni_id, {})
    ranking = get_ranking(uni_id) or {}
    city_pref = (effective_city or profile.city_preference or "").strip()
    campuses = university.get("cities", []) or []
    city = university.get("city", "")
    if city_pref and city_pref.lower() != "any city":
        for campus in campuses:
            if city_pref.lower() in campus.lower():
                city = campus
                break
    fee_preview = chunk_preview_for(uni_id, chunks, ("fee", "tuition"))
    if fee_preview:
        fee_summary = fee_preview
    elif (university.get("type") or "").lower() == "public":
        fee_summary = "Usually a lower public-sector fee bracket; verify the latest fee page."
    else:
        fee_summary = "Private-sector fees can be higher; verify the latest official fee page."
    match_reason = "; ".join(score.get("match_reasons") or [])
    if not match_reason:
        match_reason = ranking.get("ranking_basis") or university.get("notes", "Relevant option from the university data.")
    source_preview = chunk_preview_for(uni_id, chunks) or university.get("notes", "")
    return RecommendationItem(
        university_id=uni_id,
        university_name=university.get("name", uni_id),
        short_name=university.get("short_name", university.get("name", uni_id)),
        city=city,
        campuses=campuses,
        university_type=(university.get("type", "") or "").title(),
        fields=university.get("fields", []),
        fit_level=score.get("fit_level", ""),
        fit_score=score.get("total_score", 0),
        tier_label=score.get("tier_label", ""),
        match_reason=match_reason,
        eligibility_summary=score.get("eligibility_summary", ""),
        fee_summary=fee_summary,
        entry_test=score.get("entry_test", "Check official policy"),
        admission_links=admission_links_for(uni_id),
        source_preview=source_preview,
    )

def build_recommendation_lists(profile: Profile, normalized: dict, chunks: list[dict],
                               question: str, selected_university: str = "") -> tuple[list[RecommendationItem], list[RecommendationItem], list[RecommendationItem], str]:
    effective_city = profile.city_preference
    if not effective_city or effective_city.lower() == "any city":
        inferred_city = infer_city_from_text(question)
        if inferred_city:
            effective_city = inferred_city
    selected_id = selected_university or resolve_university_id(question)
    candidate_ids = [u.get("id", "") for u in UNIVERSITIES if u.get("id")]
    if not candidate_ids:
        candidate_ids = sorted({c.get("university_id", "") for c in chunks if c.get("university_id")})
    scores = [score_university(profile, uni_id, normalized, effective_city) for uni_id in candidate_ids]
    scores = sorted(scores, key=lambda s: s["total_score"], reverse=True)
    if selected_id and selected_id in candidate_ids:
        selected_score = score_university(profile, selected_id, normalized, effective_city)
        scores = [selected_score] + [s for s in scores if s.get("university_id") != selected_id]
    recommendations = [build_recommendation_item(s, profile, chunks, effective_city) for s in scores[:5]]
    safe = [
        build_recommendation_item(s, profile, chunks, effective_city)
        for s in scores
        if s.get("fit_level") in ("Safe", "Backup")
    ][:3]
    difficult = [
        build_recommendation_item(s, profile, chunks, effective_city)
        for s in scores
        if s.get("fit_level") == "Difficult"
    ][:3]
    return recommendations, safe, difficult, selected_id

def build_next_steps(recommendations: list[RecommendationItem], selected_id: str = "") -> list[str]:
    if selected_id and recommendations:
        chosen = recommendations[0]
        return [
            f"Review {chosen.short_name}'s official admissions and eligibility pages.",
            "Confirm merit formula, subjects, and entry test requirements for the current cycle.",
            "Compare this option with at least one safe university before applying.",
        ]
    if recommendations:
        return [
            "Shortlist one dream, two target, and two safe universities.",
            "Open the official admission links for deadlines, test dates, and fee updates.",
            "Ask DigiCounsellor to compare your top two options before finalizing applications.",
        ]
    return [
        "Share your preferred field, city, marks, and budget for a more focused shortlist.",
        "Verify every final decision through official university admission pages.",
    ]

# ──────────────────────────────────────────────
# LLM provider helpers
# ──────────────────────────────────────────────

async def call_lm_studio(prompt: str, max_tokens: int | None = None) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(LM_STUDIO_URL, json={
                "model": LM_STUDIO_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful university counsellor for Pakistani students. Answer concisely."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": max_tokens or LM_STUDIO_MAX_TOKENS,
                "stream": False
            })
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

async def call_ollama(prompt: str, num_predict: int | None = None) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": "You are DigiCounsellor. Write concise Pakistani CS/SE admission guidance. Never guarantee admission."},
                    {"role": "user", "content": prompt}
                ],
                "options": {
                    "temperature": 0.2,
                    "num_predict": num_predict or OLLAMA_NUM_PREDICT
                },
                "keep_alive": "10m",
                "think": False,
                "stream": False
            })
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data["message"]["content"].strip()
    except Exception:
        return None

def build_fallback_answer(recommendations: list[RecommendationItem], safe_options: list[RecommendationItem],
                          difficult_options: list[RecommendationItem], profile: Profile,
                          question: str, normalized: dict, incomplete: bool = False,
                          fast_mode: bool = FAST_MODE) -> str:
    field = normalize_field(profile.preferred_field)
    city = profile.city_preference or "any city"
    academic_note = normalized.get("academic_notes", "")

    if fast_mode:
        best = recommendations[0] if recommendations else None
        safe = safe_options[0] if safe_options else (recommendations[1] if len(recommendations) > 1 else None)
        provider_note = ""
        if incomplete:
            provider_note = " The local AI response was incomplete, so this uses fast data mode."
        elif not recommendations:
            provider_note = " Add more profile details for a stronger shortlist."

        lines = ["**Summary**"]
        lines.append(
            f"For {profile.name or 'you'}, the {field} shortlist is based on your marks, {city} preference, budget, and official university data. Eligibility depends on official policy and merit each year.{provider_note}"
        )
        if best:
            lines.append("\n**Best option**")
            lines.append(f"{best.short_name} looks strongest because {best.match_reason or best.eligibility_summary}")
        if safe:
            lines.append("\n**Safe option**")
            lines.append(f"{safe.short_name} is the safer route: {safe.eligibility_summary}")
        if difficult_options:
            lines.append("\n**Next step**")
            lines.append(f"Treat {difficult_options[0].short_name} as a higher-merit option, then select a university card to check fees, requirements, and official admission links.")
        else:
            lines.append("\n**Next step**")
            lines.append("Select a university card to check fees, requirements, and official admission links before applying.")
        return "\n".join(lines)

    lines = []
    lines.append(f"**Summary**")
    lines.append(f"For {profile.name or 'you'}, the strongest {field} options depend on marks, city, fee comfort, and entry test preparation. Eligibility depends on official policy and merit each year.")
    if academic_note:
        lines.append(f"\n{academic_note}")
    if incomplete:
        lines.append("\nNote: The local AI response was incomplete, so DigiCounsellor used the structured university data below.\n")
    else:
        lines.append("\nNote: The local AI provider is unavailable, so this answer is based on structured university data only.\n")

    if recommendations:
        lines.append("**Best matches**")
        for rec in recommendations[:3]:
            lines.append(f"- {rec.short_name}: {rec.fit_level}. {rec.match_reason}")

    if safe_options:
        lines.append("\n**Safe options**")
        for rec in safe_options[:3]:
            lines.append(f"- {rec.short_name}: {rec.eligibility_summary}")

    if difficult_options:
        lines.append("\n**Difficult options**")
        for rec in difficult_options[:3]:
            lines.append(f"- {rec.short_name}: strong reputation, but merit or fit may be tougher for this profile.")

    lines.append("\n**Next steps:**")
    lines.append("1. Open the official admission and eligibility links for the shortlisted universities.")
    lines.append("2. Prepare for each required entry test and check current deadlines.")
    lines.append("3. Keep a mix of dream, target, and safe options.")
    lines.append("\nPlease verify all details from official university admission pages before applying.")

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

def build_master_prompt(profile: Profile, question: str, context: str,
                        recommendations: list[RecommendationItem],
                        safe_options: list[RecommendationItem],
                        difficult_options: list[RecommendationItem],
                        normalized: dict, selected_id: str = "",
                        fast_mode: bool = FAST_MODE) -> str:
    field = normalize_field(profile.preferred_field)
    city = profile.city_preference or "any city"
    budget_str = profile.budget or "not specified"
    academic_notes = normalized.get("academic_notes", "")

    inter_pct = normalized["inter_equivalent_pct"]
    matric_pct = normalized["matric_equivalent_pct"]

    rec_limit = 3 if fast_mode else 5
    rec_lines = []
    for rec in recommendations[:rec_limit]:
        rec_lines.append(
            f"- {rec.short_name}: {rec.fit_level}; {rec.city}, {rec.university_type}; "
            f"eligibility: {rec.eligibility_summary}; reason: {rec.match_reason}"
        )
    rec_section = "\n".join(rec_lines) if rec_lines else "(No structured recommendations)"
    safe_section = ", ".join([r.short_name for r in safe_options]) or "None identified"
    difficult_section = ", ".join([r.short_name for r in difficult_options]) or "None identified"
    selected_line = f"Selected university focus: {selected_id}" if selected_id else "Selected university focus: none"

    if fast_mode:
        return f"""You are DigiCounsellor, a university counsellor for Pakistani students applying to CS or Software Engineering.

STUDENT:
Name: {profile.name}
Marks: Matric {matric_pct}%, Inter {inter_pct}%
Field: {field} | City: {city} | Budget: {budget_str} | University type: {profile.university_type}
Entry Test: {profile.entry_test or "not specified"}
{selected_line}

QUESTION:
{question}

STRUCTURED SHORTLIST:
{rec_section}

SAFE OPTIONS:
{safe_section}

DIFFICULT OPTIONS:
{difficult_section}

DATA NOTES:
{context}

Write a short counselling answer in 4 small sections:
Summary
Best option
Safe option
Next step

Use simple English.
Do not write a letter.
Do not repeat all source text.
Keep it between 100 and 160 words.
Use the structured shortlist as the main truth.
Never guarantee admission. Mention that eligibility depends on official policy and merit each year.
Finish the Next step section with one complete sentence and a full stop."""

    return f"""You are DigiCounsellor, a university counsellor for Pakistani students applying to CS or Software Engineering. Write a concise, complete answer.

STUDENT:
Name: {profile.name}
Marks: Matric {matric_pct}%, Inter {inter_pct}%
Entry Test: {profile.entry_test}
Field: {field} | City: {city} | Budget: {budget_str} | University type: {profile.university_type}
{("Note: " + academic_notes) if academic_notes else ""}

QUESTION:
{question}
{selected_line}

DATA:
{context}

STRUCTURED SHORTLIST:
{rec_section}

SAFE OPTIONS:
{safe_section}

DIFFICULT OPTIONS:
{difficult_section}

Write exactly 5 short sections. Do not write a letter or greeting. Do not mention JSON, retrieval, embeddings, or internal scores unless useful to the student.

1. **Summary** — 2 short sentences
2. **Best matches** — 2-3 universities with a clear reason for each
3. **Safe options** — practical safer choices from the shortlist
4. **Difficult options** — stronger or higher-merit choices to treat carefully
5. **Next steps** — 3 practical actions

Rules:
- Never guarantee admission. Include: "Eligibility depends on official policy and merit each year."
- If budget is under 200,000 PKR, recommend public universities.
- End with: "Please verify all details from official university admission pages before applying."
- Keep it under 450 words. Finish every section."""

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
        "ollama": ollama,
        "default_provider": "ollama",
        "ollama_model": OLLAMA_MODEL,
        "fast_mode": FAST_MODE,
        "ollama_num_predict": OLLAMA_NUM_PREDICT
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
        "provider_order": PROVIDER_ORDER,
        "fast_mode": FAST_MODE,
        "ollama_num_predict": OLLAMA_NUM_PREDICT
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
            async with httpx.AsyncClient(timeout=20.0) as c:
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
            async with httpx.AsyncClient(timeout=25.0) as c:
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
    return cleaned[-1] in (".", "!", "?")

def normalize_summary_answer(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if cleaned[-1] not in (".", "!", "?"):
        cleaned = cleaned.rstrip(" ,;:-") + "."
    return cleaned

def is_usable_summary(text: str) -> bool:
    cleaned = (text or "").strip()
    if len(cleaned) < 90:
        return False
    lower = cleaned.lower()
    return "summary" in lower and ("best" in lower or "safe" in lower or "next" in lower)

def resolve_selected_id(selected_university: str | None) -> str:
    selected_input = (selected_university or "").strip()
    if not selected_input:
        return ""
    return selected_input if selected_input in UNIVERSITY_BY_ID else resolve_university_id(selected_input)

def build_search_query(profile: Profile, question: str, normalized: dict, selected_id: str = "") -> str:
    search_parts = [
        f"field: {normalize_field(profile.preferred_field)}" if profile.preferred_field else "",
        f"city: {profile.city_preference}" if profile.city_preference else "",
        f"type: {profile.university_type}" if profile.university_type else "",
        f"budget: {profile.budget}" if profile.budget else "",
        f"matric: {normalized['matric_equivalent_pct']}% inter: {normalized['inter_equivalent_pct']}%" if normalized['matric_equivalent_pct'] else "",
        f"entry test: {profile.entry_test}" if profile.entry_test else "",
        f"selected university: {UNIVERSITY_BY_ID.get(selected_id, {}).get('name', selected_id)}" if selected_id else "",
        question,
    ]
    return " ".join(p for p in search_parts if p)

def collect_admission_links(recommendations: list[RecommendationItem]) -> list[AdmissionLink]:
    admission_links = []
    seen_link_urls = set()
    for rec in recommendations[:4]:
        for link in rec.admission_links:
            if link.url and link.url not in seen_link_urls:
                seen_link_urls.add(link.url)
                admission_links.append(link)
    return admission_links[:8]

def build_context_from_chunks(chunks: list[dict]) -> str:
    max_chunk_chars = 260 if FAST_MODE else 1200
    context_lines = []
    for c in chunks:
        text_source = c.get("preview") if FAST_MODE else c.get("text", "")
        truncated = (text_source or "")[:max_chunk_chars]
        context_lines.append(f"[{c.get('university_name', '')} - {c.get('category', '')}]\n{truncated}")
    return "\n\n---\n\n".join(context_lines) if context_lines else ""

def build_context_from_sources(sources: list[SourceItem]) -> str:
    if not sources:
        return ""
    lines = []
    for source in sources[:3]:
        preview = (source.preview or "")[:220]
        lines.append(f"[{source.university_name}]\n{preview}")
    return "\n\n---\n\n".join(lines)

def build_recommendation_result(profile: Profile, question: str,
                                selected_university: str | None = "") -> dict:
    total_start = time.perf_counter()
    selected_id = resolve_selected_id(selected_university)

    normalized = normalize_academic_profile(profile)
    search_query = build_search_query(profile, question, normalized, selected_id)

    rag_start = time.perf_counter()
    chunks = search_chroma_detailed(search_query, top_k=3 if FAST_MODE else 8)
    rag_seconds = time.perf_counter() - rag_start
    retrieved_count = len(chunks)

    scoring_start = time.perf_counter()
    recommendations, safe_options, difficult_options, selected_id = build_recommendation_lists(
        profile, normalized, chunks, question, selected_id
    )
    next_steps = build_next_steps(recommendations, selected_id)
    admission_links = collect_admission_links(recommendations)
    scoring_seconds = time.perf_counter() - scoring_start

    total_seconds = time.perf_counter() - total_start
    timing = TimingInfo(
        total_seconds=round(total_seconds, 3),
        rag_seconds=round(rag_seconds, 3),
        scoring_seconds=round(scoring_seconds, 3),
        llm_seconds=0.0,
        cached=False,
    )
    response = RecommendResponse(
        sources=format_sources(chunks),
        recommended_universities=recommendations,
        safe_options=safe_options,
        difficult_options=difficult_options,
        next_steps=next_steps,
        admission_links=admission_links,
        retrieved_count=retrieved_count,
        provider_used="data",
        selected_model="structured scoring",
        selected_university=selected_id,
        timing=timing,
    )
    return {
        "response": response,
        "normalized": normalized,
        "chunks": chunks,
        "context": build_context_from_chunks(chunks),
        "selected_id": selected_id,
    }

async def generate_ai_summary(profile: Profile, question: str, selected_id: str,
                              recommendations: list[RecommendationItem],
                              safe_options: list[RecommendationItem],
                              difficult_options: list[RecommendationItem],
                              normalized: dict, context: str) -> tuple[str, str, str, float]:
    prompt = build_master_prompt(
        profile, question, context, recommendations, safe_options,
        difficult_options, normalized, selected_id, True
    )
    llm_start = time.perf_counter()
    answer = ""
    provider_used = "fallback"
    selected_model = "rule-based guidance"

    for provider in PROVIDER_ORDER:
        provider = provider.strip()
        if provider == "lm_studio":
            result = await call_lm_studio(prompt, max_tokens=AI_SUMMARY_MAX_TOKENS)
            if result and (is_complete_answer(result) or is_usable_summary(result)):
                answer = normalize_summary_answer(result)
                provider_used = "lm_studio"
                selected_model = LM_STUDIO_MODEL
                break
        elif provider == "ollama":
            result = await call_ollama(prompt, num_predict=AI_SUMMARY_NUM_PREDICT)
            if result and (is_complete_answer(result) or is_usable_summary(result)):
                answer = normalize_summary_answer(result)
                provider_used = "ollama"
                selected_model = OLLAMA_MODEL
                break
            if result:
                answer = build_fallback_answer(
                    recommendations, safe_options, difficult_options,
                    profile, question, normalized, incomplete=True,
                    fast_mode=True
                )
                provider_used = "fallback"
                selected_model = "rule-based guidance"
                break
        elif provider == "fallback":
            answer = build_fallback_answer(
                recommendations, safe_options, difficult_options,
                profile, question, normalized, fast_mode=True
            )
            provider_used = "fallback"
            selected_model = "rule-based guidance"
            break

    llm_seconds = time.perf_counter() - llm_start
    if not answer:
        answer = build_fallback_answer(
            recommendations, safe_options, difficult_options,
            profile, question, normalized, fast_mode=True
        )
        provider_used = "fallback"
        selected_model = "rule-based guidance"
    return answer, provider_used, selected_model, llm_seconds


# ──────────────────────────────────────────────
# POST /recommend — fast structured recommendation endpoint
# ──────────────────────────────────────────────

@app.post("/recommend")
async def recommend(request: CounselRequest):
    total_start = time.perf_counter()
    selected_id = resolve_selected_id(request.selected_university)
    cache_key = recommend_cache_key(request.profile, request.question, selected_id)
    cached_response = cache_get(RECOMMEND_CACHE, cache_key, RecommendResponse)
    if cached_response:
        total_seconds = time.perf_counter() - total_start
        cached_response.timing = TimingInfo(total_seconds=round(total_seconds, 3), cached=True)
        print(f"[recommend] cache hit total={total_seconds:.3f}s question={request.question[:80]!r}")
        return cached_response

    result = build_recommendation_result(request.profile, request.question, selected_id)
    response = result["response"]
    cache_store(RECOMMEND_CACHE, cache_key, response)
    timing = response.timing or TimingInfo()
    print(
        f"[recommend] timing fast_mode={FAST_MODE} "
        f"rag={timing.rag_seconds:.3f}s scoring={timing.scoring_seconds:.3f}s "
        f"total={timing.total_seconds:.3f}s"
    )
    return response

# ──────────────────────────────────────────────
# POST /ai-summary — local AI summary only
# ──────────────────────────────────────────────

@app.post("/ai-summary")
async def ai_summary(request: AISummaryRequest):
    total_start = time.perf_counter()
    selected_id = resolve_selected_id(request.selected_university)
    cache_key = ai_summary_cache_key(request, selected_id)
    cached_response = cache_get(AI_SUMMARY_CACHE, cache_key, AISummaryResponse)
    if cached_response:
        total_seconds = time.perf_counter() - total_start
        cached_response.timing = TimingInfo(total_seconds=round(total_seconds, 3), cached=True)
        print(f"[ai-summary] cache hit total={total_seconds:.3f}s question={request.question[:80]!r}")
        return cached_response

    normalized = normalize_academic_profile(request.profile)
    recommendations = request.recommended_universities
    safe_options = request.safe_options
    difficult_options = request.difficult_options
    context = build_context_from_sources(request.sources)
    rag_seconds = 0.0
    scoring_seconds = 0.0

    if not recommendations:
        rec_result = build_recommendation_result(request.profile, request.question, selected_id)
        rec_response = rec_result["response"]
        normalized = rec_result["normalized"]
        selected_id = rec_result["selected_id"]
        recommendations = rec_response.recommended_universities
        safe_options = rec_response.safe_options
        difficult_options = rec_response.difficult_options
        context = rec_result["context"]
        rec_timing = rec_response.timing or TimingInfo()
        rag_seconds = rec_timing.rag_seconds
        scoring_seconds = rec_timing.scoring_seconds

    answer, provider_used, selected_model, llm_seconds = await generate_ai_summary(
        request.profile, request.question, selected_id, recommendations,
        safe_options, difficult_options, normalized, context
    )
    total_seconds = time.perf_counter() - total_start
    response = AISummaryResponse(
        answer=answer,
        provider_used=provider_used,
        selected_model=selected_model,
        timing=TimingInfo(
            total_seconds=round(total_seconds, 3),
            rag_seconds=round(rag_seconds, 3),
            scoring_seconds=round(scoring_seconds, 3),
            llm_seconds=round(llm_seconds, 3),
            cached=False,
        ),
    )
    cache_store(AI_SUMMARY_CACHE, cache_key, response)
    print(
        f"[ai-summary] timing provider={provider_used} "
        f"llm={llm_seconds:.3f}s total={total_seconds:.3f}s"
    )
    return response

# ──────────────────────────────────────────────
# POST /counsel — combined compatibility endpoint
# ──────────────────────────────────────────────

@app.post("/counsel")
async def counsel(request: CounselRequest):
    total_start = time.perf_counter()
    selected_id = resolve_selected_id(request.selected_university)
    cache_key = counsel_cache_key(request.profile, request.question, selected_id)
    cached_response = cache_get(COUNSEL_CACHE, cache_key, CounselResponse)
    if cached_response:
        total_seconds = time.perf_counter() - total_start
        cached_response.timing = TimingInfo(total_seconds=round(total_seconds, 3), cached=True)
        print(f"[counsel] cache hit total={total_seconds:.3f}s question={request.question[:80]!r}")
        return cached_response

    rec_result = build_recommendation_result(request.profile, request.question, selected_id)
    rec_response = rec_result["response"]
    answer, provider_used, selected_model, llm_seconds = await generate_ai_summary(
        request.profile, request.question, rec_result["selected_id"],
        rec_response.recommended_universities, rec_response.safe_options,
        rec_response.difficult_options, rec_result["normalized"], rec_result["context"]
    )

    total_seconds = time.perf_counter() - total_start
    rec_timing = rec_response.timing or TimingInfo()
    response = CounselResponse(
        answer=answer,
        sources=rec_response.sources,
        recommended_universities=rec_response.recommended_universities,
        safe_options=rec_response.safe_options,
        difficult_options=rec_response.difficult_options,
        next_steps=rec_response.next_steps,
        admission_links=rec_response.admission_links,
        retrieved_count=rec_response.retrieved_count,
        provider_used=provider_used,
        selected_model=selected_model,
        selected_university=rec_response.selected_university,
        timing=TimingInfo(
            total_seconds=round(total_seconds, 3),
            rag_seconds=rec_timing.rag_seconds,
            scoring_seconds=rec_timing.scoring_seconds,
            llm_seconds=round(llm_seconds, 3),
            cached=False,
        ),
    )
    cache_store(COUNSEL_CACHE, cache_key, response)
    print(
        f"[counsel] timing fast_mode={FAST_MODE} provider={provider_used} "
        f"rag={rec_timing.rag_seconds:.3f}s scoring={rec_timing.scoring_seconds:.3f}s "
        f"llm={llm_seconds:.3f}s total={total_seconds:.3f}s"
    )
    return response

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
