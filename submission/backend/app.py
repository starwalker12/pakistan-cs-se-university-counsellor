"""
DigiCounsellor — FastAPI Backend

Endpoints:
  POST /counsel          — combined: structured recommendations + AI summary
  POST /recommend        — fast structured recommendations only
  POST /ai-summary       — local AI summary only (uses prior /recommend data)
  GET  /health           — health check
  GET  /providers        — shows configured LLM provider status
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
RELEVANCE_CACHE: dict[str, dict] = {}
LIVE_LOOKUP_CACHE: dict[str, str] = {}

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
ADMISSION_DATA = []

def load_local_data():
    global RANKINGS, ELIGIBILITY_RULES, UNIVERSITIES, SOURCE_LINKS, UNIVERSITY_BY_ID, SOURCE_LINKS_BY_ID, ADMISSION_DATA
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

    try:
        proc_path = os.path.join(PROCESSED_DIR, "university_admission_data.json")
        with open(proc_path, "r", encoding="utf-8") as f:
            ADMISSION_DATA = json.load(f)
        print(f"Loaded {len(ADMISSION_DATA)} processed admission records")
    except Exception as e:
        print(f"Could not load processed admission data: {e}")

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
    recent_context: bool = False

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

class RelevanceResult(BaseModel):
    allowed: bool = False
    intent: str = "irrelevant"
    reason: str = ""
    safe_reply: str = ""
    provider_used: str = "fallback"

class CounselResponse(BaseModel):
    answer: str
    sources: list[SourceItem] = Field(default_factory=list)
    recommended_universities: list[RecommendationItem] = Field(default_factory=list)
    safe_options: list[RecommendationItem] = Field(default_factory=list)
    difficult_options: list[RecommendationItem] = Field(default_factory=list)
    not_eligible_options: list[RecommendationItem] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    admission_links: list[AdmissionLink] = Field(default_factory=list)
    retrieved_count: int = 0
    provider_used: str = ""
    selected_model: str = ""
    selected_university: str = ""
    timing: TimingInfo | None = None
    relevance: RelevanceResult | None = None

class RecommendResponse(BaseModel):
    answer: str = ""
    sources: list[SourceItem] = Field(default_factory=list)
    recommended_universities: list[RecommendationItem] = Field(default_factory=list)
    safe_options: list[RecommendationItem] = Field(default_factory=list)
    difficult_options: list[RecommendationItem] = Field(default_factory=list)
    not_eligible_options: list[RecommendationItem] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    admission_links: list[AdmissionLink] = Field(default_factory=list)
    retrieved_count: int = 0
    provider_used: str = "data"
    selected_model: str = "structured scoring"
    selected_university: str = ""
    checked_universities_count: int = 0
    eligible_universities_count: int = 0
    not_eligible_count: int = 0
    timing: TimingInfo | None = None
    relevance: RelevanceResult | None = None

class AISummaryRequest(BaseModel):
    profile: Profile
    question: str
    selected_university: str | None = ""
    recent_context: bool = False
    recommended_universities: list[RecommendationItem] = Field(default_factory=list)
    safe_options: list[RecommendationItem] = Field(default_factory=list)
    difficult_options: list[RecommendationItem] = Field(default_factory=list)
    not_eligible_options: list[RecommendationItem] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)

class AISummaryResponse(BaseModel):
    answer: str = ""
    provider_used: str = ""
    selected_model: str = ""
    timing: TimingInfo | None = None
    relevance: RelevanceResult | None = None

class UniversityInfoRequest(BaseModel):
    profile: Profile
    question: str
    university_id: str | None = None
    info_type: str | None = None
    recent_context: bool = False

class UniversityInfoResponse(BaseModel):
    answer: str
    university_name: str = ""
    info_type: str = ""
    links: list[AdmissionLink] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)
    has_exact_data: bool = False
    data_source: str = "missing"
    source_url_used: str = ""
    relevance: RelevanceResult | None = None

GREETING_WORDS = frozenset({
    "hey", "hello", "hi", "salam", "assalam", "alaikum",
    "thanks", "thankyou", "thank you", "ok", "okay",
    "yes", "no", "thx", "thank u",
})

def is_greeting(text: str) -> bool:
    if not text:
        return True
    cleaned = text.strip().lower().rstrip(".!?, ")
    if cleaned in GREETING_WORDS:
        return True
    return False

def greeting_answer(profile: Profile) -> str:
    name = profile.name or "there"
    return f"Hi {name}, I am ready. Ask me which universities are best for you, or ask about eligibility, fees, or admission steps."

BLOCKED_REPLY = "I can only help with Computer Science and Software Engineering university admissions in Pakistan. Please ask about universities, eligibility, fees, merit, deadlines, entry tests, or admission steps."

ADMISSION_KEYWORDS = [
    "admission", "admissions", "university", "universities", "eligibility", "eligible",
    "fee", "fees", "merit", "deadline", "scholarship", "hostel", "campus",
    "entry test", "nts", "nat", "ecat", "net", "admission test",
    "requirement", "requirements", "criteria", "application", "portal",
    "computer science", "software engineering", "cs", "se",
    "apply", "how can i apply", "recommend", "suggest",
    "lahore", "islamabad", "karachi", "pakistan",
    "program", "degree", "bs", "bachelor",
    "matric", "intermediate", "a level", "o level",
    "percentage", "marks", "score",
    "safe option", "safe options", "best match", "best matches",
    "difficult option", "backup option", "not eligible", "next step", "next steps",
    "compare", "shortlist",
]

BLOCKED_TOPICS = [
    "cook", "recipe", "weather", "elon musk", "joke", "poem",
    "love poem", "teach me", "programming", "coding", "python",
    "c++", "javascript", "oop", "loop", "variables", "calculator",
    "wear", "outfit",
]

CONTEXTUAL_FOLLOW_UP_PHRASES = [
    "safe option", "safe options", "show safe", "best match", "best matches",
    "compare option", "compare options", "compare universities", "what should i do next",
    "what next", "next step", "next steps", "tell me more", "admission requirements",
    "requirements", "show requirements", "fee info", "fees", "admission link",
    "official link", "how can i apply", "how to apply", "difficult options",
    "not eligible", "backup options",
]

RELEVANCE_INTENTS = {
    "greeting", "recommendation", "follow_up", "university_info",
    "eligibility", "admission_link", "irrelevant",
}

UNIVERSITY_NAME_ALIASES = [
    "fast", "nuces", "nust", "comsats", "lums", "giki",
    "pieas", "uet", "itu", "air university", "bahria",
    "punjab university", "qau", "ned", "karachi university",
    "university of karachi", "ucp", "virtual university",
    "szabist", "iba", "ist", "habib", "pims", "lse", "nca",
    "beaconhouse",
]

def has_profile_context(profile: Profile | None) -> bool:
    if not profile:
        return False
    context_fields = [
        profile.preferred_field,
        profile.city_preference,
        profile.matric_percentage,
        profile.intermediate_percentage,
        profile.matric_marks,
        profile.inter_marks,
        profile.o_level_equivalence,
        profile.a_level_equivalence,
        profile.budget,
        profile.entry_test,
    ]
    return any(bool(str(value).strip()) for value in context_fields)

def fallback_relevance_guard(text: str, profile: Profile | None = None,
                             recent_context: bool = False) -> RelevanceResult:
    if not text or not text.strip():
        return RelevanceResult(
            allowed=False,
            intent="irrelevant",
            reason="Empty question",
            safe_reply="Please ask a question about CS or Software Engineering admissions in Pakistan.",
            provider_used="fallback",
        )

    lower = text.strip().lower()
    cleaned = lower.rstrip(".!?, ")
    profile_context = has_profile_context(profile)
    contextual = recent_context or profile_context

    if cleaned in GREETING_WORDS:
        return RelevanceResult(
            allowed=True,
            intent="greeting",
            reason="Greeting",
            provider_used="fallback",
        )

    if any(alias in lower for alias in UNIVERSITY_NAME_ALIASES):
        intent = "eligibility" if any(word in lower for word in ("eligible", "eligibility")) else "university_info"
        if any(word in lower for word in ("apply", "link", "portal", "admission page")):
            intent = "admission_link"
        return RelevanceResult(
            allowed=True,
            intent=intent,
            reason="Known university reference",
            provider_used="fallback",
        )

    if any(phrase in lower for phrase in CONTEXTUAL_FOLLOW_UP_PHRASES):
        return RelevanceResult(
            allowed=True,
            intent="follow_up" if contextual else "recommendation",
            reason="Admission follow-up phrase",
            provider_used="fallback",
        )

    if any(keyword in lower for keyword in ADMISSION_KEYWORDS):
        intent = "recommendation"
        if any(word in lower for word in ("eligible", "eligibility", "requirement", "requirements", "criteria")):
            intent = "eligibility"
        elif any(word in lower for word in ("apply", "link", "portal", "application")):
            intent = "admission_link"
        return RelevanceResult(
            allowed=True,
            intent=intent,
            reason="Admission-related wording",
            provider_used="fallback",
        )

    if any(topic in lower for topic in BLOCKED_TOPICS):
        return RelevanceResult(
            allowed=False,
            intent="irrelevant",
            reason="Obvious unrelated topic",
            safe_reply=BLOCKED_REPLY,
            provider_used="fallback",
        )

    return RelevanceResult(
        allowed=False,
        intent="irrelevant",
        reason="No admission context detected",
        safe_reply=BLOCKED_REPLY,
        provider_used="fallback",
    )

def is_admission_related(text: str) -> bool:
    return fallback_relevance_guard(text, Profile(), False).allowed

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

def parse_json_object(text: str | None) -> dict | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None

def relevance_cache_key(question: str, profile: Profile, recent_context: bool,
                        selected_university: str | None = "") -> str:
    payload = {
        "question": (question or "").strip().lower(),
        "profile_context": has_profile_context(profile),
        "preferred_field": (profile.preferred_field or "").strip().lower(),
        "city": (profile.city_preference or "").strip().lower(),
        "selected_university": (selected_university or "").strip().lower(),
        "recent_context": recent_context,
        "model": OLLAMA_MODEL,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))

def normalize_relevance_result(raw: dict, provider_used: str) -> RelevanceResult | None:
    if not isinstance(raw, dict) or "allowed" not in raw:
        return None
    intent = str(raw.get("intent") or "irrelevant").strip().lower()
    invalid_intent = intent not in RELEVANCE_INTENTS
    raw_allowed = raw.get("allowed")
    if isinstance(raw_allowed, bool):
        allowed = raw_allowed
    else:
        allowed = str(raw_allowed).strip().lower() in ("1", "true", "yes", "allowed")
    if invalid_intent:
        intent = "irrelevant" if not allowed else "follow_up"
    safe_reply = str(raw.get("safe_reply") or "").strip()
    if allowed:
        safe_reply = ""
    if not allowed and not safe_reply:
        safe_reply = BLOCKED_REPLY
    return RelevanceResult(
        allowed=allowed,
        intent=intent,
        reason=str(raw.get("reason") or "").strip()[:180],
        safe_reply=safe_reply[:500],
        provider_used=provider_used,
    )

def relevance_selected_model(provider_used: str) -> str:
    if provider_used == "ollama":
        return OLLAMA_MODEL
    if provider_used == "lm_studio":
        return LM_STUDIO_MODEL
    return "fallback relevance guard"

async def classify_question_relevance(user_message: str, profile: Profile,
                                      recent_context: bool = False,
                                      selected_university: str | None = "") -> RelevanceResult:
    """Classify scope before any RAG or answer generation is attempted."""
    selected_id = resolve_selected_id(selected_university)
    context_flag = bool(recent_context or selected_id or has_profile_context(profile))
    cache_key = relevance_cache_key(user_message, profile, context_flag, selected_id)
    cached = cache_get(RELEVANCE_CACHE, cache_key, RelevanceResult)
    if cached:
        return cached

    fallback = fallback_relevance_guard(user_message, profile, context_flag)
    prompt = f"""
You are a relevance checker for DigiCounsellor.
DigiCounsellor only helps with Computer Science and Software Engineering university admissions in Pakistan.
Allowed topics include admissions, eligibility, fees, merit, deadlines, entry tests, official links, universities, profile-based recommendations, best matches, safe options, difficult options, not eligible options, and next steps.
Contextual follow-up questions are allowed if they refer to previous recommendation results.
Examples of allowed follow-ups:
safe options
best matches
compare options
what should I do next
tell me more
admission requirements
Examples of not allowed:
teach me c++
teach me python
cook biryani
weather
Elon Musk
jokes
love poem
coding tutorial

Return only valid JSON using this exact shape:
{{"allowed": true, "intent": "recommendation", "reason": "short reason", "safe_reply": ""}}

Intent must be one of: greeting, recommendation, follow_up, university_info, eligibility, admission_link, irrelevant.
Do not answer the user question.
Do not include chain of thought.

Recent recommendation context exists: {str(context_flag).lower()}
Selected university id: {selected_id or "none"}
Profile field: {profile.preferred_field or "not provided"}
Profile city: {profile.city_preference or "not provided"}
User question: {user_message.strip()[:500]}
""".strip()

    result: RelevanceResult | None = None
    for provider in PROVIDER_ORDER:
        provider = provider.strip()
        if provider == "ollama":
            raw_text = await call_ollama(prompt, num_predict=220)
            result = normalize_relevance_result(parse_json_object(raw_text), "ollama")
            if result:
                break
        elif provider == "lm_studio":
            raw_text = await call_lm_studio(prompt, max_tokens=220)
            result = normalize_relevance_result(parse_json_object(raw_text), "lm_studio")
            if result:
                break

    if not result:
        result = fallback

    # Keep the showcase flow forgiving for contextual admission follow-ups and
    # strict for obvious unrelated examples if the classifier is ambiguous.
    if not result.allowed and fallback.allowed:
        result = fallback
        result.reason = "Fallback allowed a contextual admission follow-up"
    elif result.allowed and not fallback.allowed and fallback.reason == "Obvious unrelated topic":
        result = fallback
        result.reason = "Fallback blocked an obvious unrelated topic"

    if not result.allowed and not result.safe_reply:
        result.safe_reply = BLOCKED_REPLY

    cache_store(RELEVANCE_CACHE, cache_key, result)
    return result

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

def is_valid_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    cleaned = url.strip()
    if not cleaned:
        return False
    if cleaned == "#":
        return False
    if cleaned.lower().startswith("todo"):
        return False
    if "placeholder" in cleaned.lower():
        return False
    if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
        return False
    return True

def is_category_url_valid(key: str, url: str) -> bool:
    if not is_valid_url(url):
        return False
    lower = url.lower()
    is_fee = any(t in lower for t in ("fee", "tuition", "dues", "charges", "financial", "cost"))
    is_eligibility = any(t in lower for t in ("eligibility", "criteria", "requirement"))
    is_entry_test = any(t in lower for t in ("test", "nat", "net", "ecat", "sat", "pattern"))
    is_admissions = any(t in lower for t in ("admission", "apply", "more/"))
    is_program = any(t in lower for t in ("program", "degree"))
    is_schedule = any(t in lower for t in ("schedule", "deadline", "date"))
    key_lower = key.lower()
    if key_lower == "official_website":
        return True
    if "fee" in key_lower or "tuition" in key_lower:
        return is_fee
    if "eligibility" in key_lower:
        return is_eligibility
    if "entry_test" in key_lower or "test" in key_lower:
        return is_entry_test
    if "admission" in key_lower:
        if key_lower == "admissions_homepage":
            return True
        return is_admissions
    if "program" in key_lower:
        return is_program
    if "schedule" in key_lower:
        return is_schedule
    return True

def admission_links_for(uni_id: str) -> list[AdmissionLink]:
    record = SOURCE_LINKS_BY_ID.get(uni_id, {})
    links = record.get("links", {}) or {}
    label_map = {
        "official_website": "Official website",
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
        "official_website",
        "admissions", "admissions_homepage", "admissions_portal",
        "eligibility_criteria", "fee_structure", "tuition_fees",
        "entry_test", "admission_schedule", "admissions_schedule",
        "undergraduate_programs", "programs"
    ]
    ordered_keys = [k for k in preferred_order if k in links]
    ordered_keys.extend(k for k in links if k not in ordered_keys)
    result = []
    for key in ordered_keys:
        item = links.get(key, {})
        url = (item.get("url") or "").strip()
        if not is_category_url_valid(key, url):
            continue
        result.append(AdmissionLink(
            label=label_map.get(key, key.replace("_", " ").title()),
            url=url,
            note=item.get("note", "")
        ))
    return result[:5]

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
    status = "eligible"
    summary = f"Meets the approximate {min_inter:g}% Inter and {min_matric:g}% Matric minimums. {test_name} may still affect merit."

    if inter_pct < min_inter or matric_pct < min_matric:
        inter_gap = min_inter - inter_pct if min_inter > 0 else 0
        matric_gap = min_matric - matric_pct if min_matric > 0 else 0
        gap = max(inter_gap, matric_gap)

        if inter_pct < 50 and min_inter >= 60:
            status = "not_eligible"
            summary = f"Your marks ({inter_pct}%) are well below the {min_inter:g}% minimum. This university will not consider your application at this level."
        elif gap >= 15:
            status = "not_eligible"
            summary = f"Your marks fall {gap:g}% short of the {min_inter:g}% minimum guideline. Admission is not realistic at this point."
        elif inter_pct >= min_inter or matric_pct >= min_matric:
            status = "borderline"
            summary = f"Partly meets the approximate minimums; confirm equivalence, subjects, and merit formula."
        else:
            status = "difficult"
            summary = f"Below the approximate {min_inter:g}% Inter / {min_matric:g}% Matric guideline. Very difficult unless official rules differ significantly."
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
    if elig_status == "not_eligible":
        fit_level = "Not eligible"
    elif elig_status == "difficult":
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
    fit_level = score.get("fit_level", "")
    match_reason = "; ".join(score.get("match_reasons") or [])
    if fit_level == "Not eligible":
        match_reason = score.get("eligibility_summary", "Your marks are below this university's minimum requirements.")
    elif not match_reason:
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
                               question: str, selected_university: str = "") -> tuple:
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
    eligible_scores = [s for s in scores if s.get("fit_level") != "Not eligible"]
    not_eligible_scores = [s for s in scores if s.get("fit_level") == "Not eligible"]
    group_size = 6
    recommendations = [build_recommendation_item(s, profile, chunks, effective_city) for s in eligible_scores[:group_size]]
    safe = [
        build_recommendation_item(s, profile, chunks, effective_city)
        for s in eligible_scores
        if s.get("fit_level") in ("Safe", "Backup")
    ][:group_size]
    difficult = [
        build_recommendation_item(s, profile, chunks, effective_city)
        for s in eligible_scores
        if s.get("fit_level") == "Difficult"
    ][:group_size]
    not_eligible = [
        build_recommendation_item(s, profile, chunks, effective_city)
        for s in not_eligible_scores[:group_size]
    ]
    checked_count = len(candidate_ids)
    eligible_count = len(eligible_scores)
    not_eligible_count = len(not_eligible_scores)
    return recommendations, safe, difficult, not_eligible, selected_id, checked_count, eligible_count, not_eligible_count

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
                          not_eligible_options: list[RecommendationItem] | None = None,
                          question: str = "", normalized: dict | None = None,
                          incomplete: bool = False, fast_mode: bool = FAST_MODE) -> str:
    field = normalize_field(profile.preferred_field)
    city = profile.city_preference or "any city"
    academic_note = (normalized or {}).get("academic_notes", "")
    not_eligible = not_eligible_options or []

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
        if not_eligible:
            lines.append("\n**Not eligible right now**")
            for rec in not_eligible[:3]:
                lines.append(f"- {rec.short_name}: {rec.match_reason}")
        if recommendations:
            lines.append("\n**Next step**")
            lines.append("Select a university card to check fees, requirements, and official admission links before applying.")
        else:
            lines.append("\n**Next step**")
            lines.append("Add more profile details for a stronger shortlist.")
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

    if not_eligible:
        lines.append("\n**Not eligible right now**")
        for rec in not_eligible[:3]:
            lines.append(f"- {rec.short_name}: {rec.match_reason}")

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
                        not_eligible_options: list[RecommendationItem],
                        normalized: dict, selected_id: str = "",
                        fast_mode: bool = FAST_MODE,
                        prompt_mode: str = "recommendation") -> str:
    field = normalize_field(profile.preferred_field)
    city = profile.city_preference or "any city"
    budget_str = profile.budget or "not specified"
    academic_notes = normalized.get("academic_notes", "")
    is_olevel = profile.education_system == "olevel"
    level_label = "O/A Level" if is_olevel else "Matric/Inter"

    inter_pct = normalized["inter_equivalent_pct"]
    matric_pct = normalized["matric_equivalent_pct"]

    rec_limit = 3 if fast_mode else 5
    selected_line = f"Selected university focus: {selected_id}" if selected_id else "Selected university focus: none"

    student_block = (
        f"STUDENT:\n"
        f"Name: {profile.name}\n"
        f"Marks: {level_label} — {matric_pct}% / {inter_pct}%\n"
        f"Field: {field} | City: {city} | Budget: {budget_str} | University type: {profile.university_type}\n"
        f"Entry Test: {profile.entry_test or 'not specified'}\n"
        f"{selected_line}"
    )

    base_prompt = (
        f"You are DigiCounsellor, a university counsellor for Pakistani students applying to CS or Software Engineering.\n\n"
        f"{student_block}\n\n"
        f"QUESTION:\n{question}\n"
    )

    if prompt_mode == "follow_up":
        if selected_id and recommendations:
            focused = next((r for r in recommendations if r.university_id == selected_id), recommendations[0])
            base_prompt += (
                f"\nFOCUSED UNIVERSITY:\n"
                f"{focused.short_name} ({focused.city}) — {focused.fit_level}\n"
                f"Eligibility: {focused.eligibility_summary}\n"
                f"Reason: {focused.match_reason}\n"
            )
        base_prompt += (
            f"\nDATA NOTES:\n{context if context else '(No additional data)'}\n\n"
            f"Answer the question directly and concisely. Do not repeat the full list of universities. "
            f"Keep it under 80 words. Never guarantee admission. "
            f"End with: 'Eligibility depends on official policy and merit each year.'"
        )
        return base_prompt

    rec_lines = []
    for rec in recommendations[:rec_limit]:
        rec_lines.append(
            f"- {rec.short_name}: {rec.fit_level}; {rec.city}, {rec.university_type}; "
            f"eligibility: {rec.eligibility_summary}; reason: {rec.match_reason}"
        )
    rec_section = "\n".join(rec_lines) if rec_lines else "(No structured recommendations)"
    safe_section = ", ".join([r.short_name for r in safe_options]) or "None identified"
    difficult_section = ", ".join([r.short_name for r in difficult_options]) or "None identified"
    not_eligible_txt = ", ".join([f"{r.short_name} ({r.match_reason})" for r in not_eligible_options]) or "None identified"

    if fast_mode:
        return base_prompt + (
            f"\n\nSTRUCTURED SHORTLIST:\n{rec_section}\n\n"
            f"SAFE OPTIONS:\n{safe_section}\n\n"
            f"DIFFICULT OPTIONS:\n{difficult_section}\n\n"
            f"NOT ELIGIBLE RIGHT NOW:\n{not_eligible_txt}\n\n"
            f"DATA NOTES:\n{context}\n\n"
            f"Write a short counselling answer in 4 small sections:\n"
            f"Summary\nBest option\nSafe option\nNext step\n\n"
            f"Use simple English.\nDo not write a letter.\nDo not repeat all source text.\n"
            f"Keep it between 100 and 160 words.\n"
            f"Use the structured shortlist as the main truth.\n"
            f"Never guarantee admission. Mention that eligibility depends on official policy and merit each year.\n"
            f"Finish the Next step section with one complete sentence and a full stop."
        )

    return base_prompt + (
        f"\n{('Note: ' + academic_notes) if academic_notes else ''}\n\n"
        f"DATA:\n{context}\n\n"
        f"STRUCTURED SHORTLIST:\n{rec_section}\n\n"
        f"SAFE OPTIONS:\n{safe_section}\n\n"
        f"DIFFICULT OPTIONS:\n{difficult_section}\n\n"
        f"Write exactly 5 short sections. Do not write a letter or greeting. Do not mention JSON, retrieval, embeddings, or internal scores unless useful to the student.\n\n"
        f"1. **Summary** — 2 short sentences\n"
        f"2. **Best matches** — 2-3 universities with a clear reason for each\n"
        f"3. **Safe options** — practical safer choices from the shortlist\n"
        f"4. **Difficult options** — stronger or higher-merit choices to treat carefully\n"
        f"5. **Next steps** — 3 practical actions\n\n"
        f"Rules:\n"
        f"- Never guarantee admission. Include: \"Eligibility depends on official policy and merit each year.\"\n"
        f"- If budget is under 200,000 PKR, recommend public universities.\n"
        f"- End with: \"Please verify all details from official university admission pages before applying.\"\n"
        f"- Keep it under 450 words. Finish every section."
    )

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
    rec_tuple = build_recommendation_lists(
        profile, normalized, chunks, question, selected_id
    )
    recommendations, safe_options, difficult_options, not_eligible_options, selected_id = rec_tuple[:5]
    checked_count, eligible_count, not_eligible_count = rec_tuple[5:8]
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
        not_eligible_options=not_eligible_options,
        next_steps=next_steps,
        admission_links=admission_links,
        retrieved_count=retrieved_count,
        provider_used="data",
        selected_model="structured scoring",
        selected_university=selected_id,
        checked_universities_count=checked_count,
        eligible_universities_count=eligible_count,
        not_eligible_count=not_eligible_count,
        timing=timing,
    )
    return {
        "response": response,
        "normalized": normalized,
        "chunks": chunks,
        "context": build_context_from_chunks(chunks),
        "selected_id": selected_id,
    }

RECOMMENDATION_PHRASES = [
    "recommend", "best match", "safe option", "universities in",
    "options for me", "which universit", "suitable for me",
    "good for me", "suggest", "compare universit",
]

def is_rec_question(question: str) -> bool:
    lower = question.lower()
    for phrase in RECOMMENDATION_PHRASES:
        if phrase in lower:
            return True
    return False

async def generate_ai_summary(profile: Profile, question: str, selected_id: str,
                              recommendations: list[RecommendationItem],
                              safe_options: list[RecommendationItem],
                              difficult_options: list[RecommendationItem],
                              not_eligible_options: list[RecommendationItem],
                              normalized: dict, context: str) -> tuple[str, str, str, float]:
    if is_greeting(question):
        return greeting_answer(profile), "fallback", "rule-based guidance", 0.0

    prompt_mode = "recommendation" if is_rec_question(question) else "follow_up"
    prompt = build_master_prompt(
        profile, question, context, recommendations, safe_options,
        difficult_options, not_eligible_options, normalized, selected_id, True,
        prompt_mode
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
                    profile, not_eligible_options=not_eligible_options,
                    question=question, normalized=normalized, incomplete=True,
                    fast_mode=True
                )
                provider_used = "fallback"
                selected_model = "rule-based guidance"
                break
        elif provider == "fallback":
            answer = build_fallback_answer(
                recommendations, safe_options, difficult_options,
                profile, not_eligible_options=not_eligible_options,
                question=question, normalized=normalized, fast_mode=True
            )
            provider_used = "fallback"
            selected_model = "rule-based guidance"
            break

    llm_seconds = time.perf_counter() - llm_start
    if not answer:
        answer = build_fallback_answer(
            recommendations, safe_options, difficult_options,
            profile, not_eligible_options=not_eligible_options,
            question=question, normalized=normalized, fast_mode=True
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
    relevance = await classify_question_relevance(
        request.question,
        request.profile,
        request.recent_context,
        request.selected_university,
    )
    if relevance.intent == "greeting":
        total_seconds = time.perf_counter() - total_start
        return RecommendResponse(
            answer=greeting_answer(request.profile),
            provider_used="fallback",
            selected_model="rule-based greeting",
            timing=TimingInfo(total_seconds=round(total_seconds, 3), cached=False),
            relevance=relevance,
        )
    if not relevance.allowed:
        total_seconds = time.perf_counter() - total_start
        return RecommendResponse(
            answer=relevance.safe_reply or BLOCKED_REPLY,
            recommended_universities=[],
            safe_options=[],
            difficult_options=[],
            not_eligible_options=[],
            next_steps=[],
            admission_links=[],
            sources=[],
            retrieved_count=0,
            provider_used=relevance.provider_used,
            selected_model=relevance_selected_model(relevance.provider_used),
            selected_university="",
            checked_universities_count=0,
            eligible_universities_count=0,
            not_eligible_count=0,
            timing=TimingInfo(total_seconds=round(total_seconds, 3), cached=False),
            relevance=relevance,
        )
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
    response.relevance = relevance
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
    has_recommendation_context = bool(
        request.recent_context
        or request.selected_university
        or request.recommended_universities
        or request.safe_options
        or request.difficult_options
        or request.not_eligible_options
        or request.sources
    )
    relevance = await classify_question_relevance(
        request.question,
        request.profile,
        has_recommendation_context,
        request.selected_university,
    )
    if relevance.intent == "greeting":
        total_seconds = time.perf_counter() - total_start
        return AISummaryResponse(
            answer=greeting_answer(request.profile),
            provider_used="fallback",
            selected_model="rule-based greeting",
            timing=TimingInfo(total_seconds=round(total_seconds, 3), cached=False),
            relevance=relevance,
        )
    if not relevance.allowed:
        return AISummaryResponse(
            answer=relevance.safe_reply or BLOCKED_REPLY,
            provider_used=relevance.provider_used,
            selected_model=relevance_selected_model(relevance.provider_used),
            timing=TimingInfo(total_seconds=round(time.perf_counter() - total_start, 3), cached=False),
            relevance=relevance,
        )
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
    not_eligible_options = request.not_eligible_options
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
        not_eligible_options = rec_response.not_eligible_options
        context = rec_result["context"]
        rec_timing = rec_response.timing or TimingInfo()
        rag_seconds = rec_timing.rag_seconds
        scoring_seconds = rec_timing.scoring_seconds

    answer, provider_used, selected_model, llm_seconds = await generate_ai_summary(
        request.profile, request.question, selected_id, recommendations,
        safe_options, difficult_options, not_eligible_options, normalized, context
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
        relevance=relevance,
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
    relevance = await classify_question_relevance(
        request.question,
        request.profile,
        request.recent_context,
        request.selected_university,
    )
    if relevance.intent == "greeting":
        total_seconds = time.perf_counter() - total_start
        return CounselResponse(
            answer=greeting_answer(request.profile),
            provider_used="fallback",
            selected_model="rule-based greeting",
            timing=TimingInfo(total_seconds=round(total_seconds, 3), cached=False),
            relevance=relevance,
        )
    if not relevance.allowed:
        total_seconds = time.perf_counter() - total_start
        return CounselResponse(
            answer=relevance.safe_reply or BLOCKED_REPLY,
            provider_used=relevance.provider_used,
            selected_model=relevance_selected_model(relevance.provider_used),
            timing=TimingInfo(total_seconds=round(total_seconds, 3), cached=False),
            relevance=relevance,
        )
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
        rec_response.difficult_options, rec_response.not_eligible_options,
        rec_result["normalized"], rec_result["context"]
    )

    total_seconds = time.perf_counter() - total_start
    rec_timing = rec_response.timing or TimingInfo()
    response = CounselResponse(
        answer=answer,
        sources=rec_response.sources,
        recommended_universities=rec_response.recommended_universities,
        safe_options=rec_response.safe_options,
        difficult_options=rec_response.difficult_options,
        not_eligible_options=rec_response.not_eligible_options,
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
        relevance=relevance,
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

# ──────────────────────────────────────────────
# Info type detection helpers
# ──────────────────────────────────────────────

INFO_FEE = frozenset({"fee", "fees", "fee structure", "cost", "tuition", "semester fee", "total fee"})
INFO_ELIGIBILITY = frozenset({"eligibility", "eligible", "requirements", "criteria", "minimum marks", "am i eligible"})
INFO_ENTRY_TEST = frozenset({"entry test", "test", "nts", "nat", "ecat", "net", "admission test", "entry requirement"})
INFO_DEADLINE = frozenset({"deadline", "last date", "dates", "schedule", "closing date"})
INFO_ADMISSION_LINK = frozenset({"admission link", "apply", "application", "portal", "admission page", "how to apply"})
INFO_GENERAL = frozenset({"tell me about", "details", "info", "information about", "overview"})

def detect_info_type(question: str) -> str:
    if not question:
        return ""
    lower = question.lower()
    for phrase in INFO_FEE:
        if phrase in lower:
            return "fee"
    for phrase in INFO_ELIGIBILITY:
        if phrase in lower:
            return "eligibility"
    for phrase in INFO_ENTRY_TEST:
        if phrase in lower:
            return "entry_test"
    for phrase in INFO_DEADLINE:
        if phrase in lower:
            return "deadline"
    for phrase in INFO_ADMISSION_LINK:
        if phrase in lower:
            return "admission_links"
    for phrase in INFO_GENERAL:
        if phrase in lower:
            return "general"
    return ""

def detect_university_in_question(question: str) -> str:
    return resolve_university_id(question or "")

# ──────────────────────────────────────────────
# Build source-first university info answer
# ──────────────────────────────────────────────

def truncate_text(text: str, max_chars: int = 300) -> str:
    if not text:
        return ""
    cleaned = text.replace("\n", " ").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rsplit(" ", 1)[0] + "..."

def find_processed_record(uni_id: str) -> dict | None:
    for rec in ADMISSION_DATA:
        if rec.get("university_id") == uni_id:
            return rec
    return None

def matches_topic(text: str, info_type: str) -> bool:
    lower = text.lower()
    if info_type == "fee":
        if "fee" in lower or "fees" in lower or "tuition" in lower:
            return True
        count = sum(1 for k in ("cost", "charges", "semester", "financial aid") if k in lower)
        return count >= 2
    if info_type == "eligibility":
        count = sum(1 for k in ("eligibility", "criteria", "requirement", "requirements",
                                "minimum marks", "qualification", "admission criteria") if k in lower)
        return count >= 2
    if info_type == "entry_test":
        if "entry test" in lower or "admission test" in lower:
            return True
        count = sum(1 for k in ("test", "sat", "nat", "net", "ecat", "test pattern", "entry") if k in lower)
        return count >= 2
    if info_type == "deadline":
        keywords = ("deadline", "last date", "schedule", "closing date")
        return any(k in lower for k in keywords)
    return True

async def fetch_official_page(url: str, timeout: float = 8.0) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return None
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            cleaned = " ".join(text.split())
            return cleaned[:900]
    except Exception:
        return None

def live_cache_key(uni_id: str, info_type: str) -> str:
    return f"{uni_id}:{info_type}"

async def live_lookup_for(uni_id: str, info_type: str,
                          links: list[AdmissionLink]) -> tuple[str | None, str]:
    cache_key = live_cache_key(uni_id, info_type)
    if cache_key in LIVE_LOOKUP_CACHE:
        cached = LIVE_LOOKUP_CACHE[cache_key]
        if cached and matches_topic(cached, info_type):
            return cached, ""
        return None, ""
    target_url = ""
    if info_type == "fee":
        for ln in links:
            if any(t in (ln.label or "").lower() for t in ("fee", "tuition")):
                target_url = ln.url
                break
    elif info_type == "eligibility":
        for ln in links:
            if "eligibility" in (ln.label or "").lower():
                target_url = ln.url
                break
    elif info_type == "entry_test":
        for ln in links:
            if "test" in (ln.label or "").lower():
                target_url = ln.url
                break
    elif info_type == "deadline":
        for ln in links:
            if "schedule" in (ln.label or "").lower() or "schedule" in (ln.note or "").lower():
                target_url = ln.url
                break
    if not target_url:
        for ln in links:
            if "admission" in (ln.label or "").lower():
                target_url = ln.url
                break
    if not target_url:
        return None, ""
    text = await fetch_official_page(target_url)
    if text:
        LIVE_LOOKUP_CACHE[cache_key] = text
        if matches_topic(text, info_type):
            return text, target_url
        return None, target_url
    return None, ""

async def build_university_info_answer(question: str, profile: Profile,
                                       uni_id: str, info_type: str) -> UniversityInfoResponse:
    name = profile.name or ""
    university = UNIVERSITY_BY_ID.get(uni_id, {})
    uni_name = university.get("short_name", "") or university.get("name", uni_id)
    links = admission_links_for(uni_id)
    proc = find_processed_record(uni_id)
    has_exact = False
    data_source = "missing"
    source_url_used = ""
    answer_lines = []
    extracted = ""

    if name:
        answer_lines.append(f"{name},")

    field_label_map = {"fee": "fee", "eligibility": "eligibility", "entry_test": "entry test",
                       "deadline": "deadline", "admission_links": "admission links"}
    f_label = field_label_map.get(info_type, info_type)

    stored_text = ""
    if info_type == "fee":
        stored_text = (proc or {}).get("fee_text", "")
    elif info_type == "eligibility":
        stored_text = (proc or {}).get("eligibility_text", "")
    elif info_type == "entry_test":
        stored_text = (proc or {}).get("entry_test_text", "")
    elif info_type == "deadline":
        stored_text = (proc or {}).get("deadline_text", "")

    def is_stored_ok(t: str) -> bool:
        if not t:
            return False
        cleaned = t.strip()
        if not cleaned:
            return False
        lower = cleaned.lower()
        if lower.startswith("needs official") or lower.startswith("needs "):
            return False
        return True

    if info_type in ("fee", "eligibility", "entry_test", "deadline"):
        if is_stored_ok(stored_text):
            has_exact = True
            data_source = "stored"
            extracted = truncate_text(stored_text)
            answer_lines.append(f"here is what I found about {uni_name} {f_label} from stored official data:")
            answer_lines.append("")
            answer_lines.append(extracted)
            answer_lines.append("")
            answer_lines.append("Please confirm the latest details on the official page.")
        else:
            answer_lines.append(f"I do not have exact {f_label} text stored for {uni_name} yet.")
            live_text, live_url = await live_lookup_for(uni_id, info_type, links)
            if live_text:
                has_exact = True
                data_source = "live"
                source_url_used = live_url
                extracted = truncate_text(live_text)
                answer_lines.append("I found this from the official page during this session:")
                answer_lines.append("")
                answer_lines.append(extracted)
                answer_lines.append("")
                answer_lines.append("Confirm the latest details on the official page above.")
            elif live_url:
                answer_lines.append(f"I checked the official page, but it did not contain clear {f_label} details. Use the link below to check directly.")
            elif info_type == "entry_test":
                rule = get_eligibility(uni_id, profile.preferred_field)
                rule_test = (rule or {}).get("entry_test_name", "")
                if rule_test:
                    has_exact = True
                    data_source = "stored"
                    answer_lines.append(f"{uni_name} entry test: {rule_test}. Check the official page for the latest format and dates.")
                elif live_url:
                    answer_lines.append(f"I checked the official page, but it did not contain clear {f_label} details. Use the link below to check directly.")
                else:
                    answer_lines.append("I could not reach the official site right now. Use the link below to check directly.")

    elif info_type == "admission_links":
        if links:
            has_exact = True
            data_source = "stored"
            answer_lines.append(f"here are the official {uni_name} admission links I have:")
            answer_lines.append("")
            btn_label = next((l.label for l in links if "admission" in (l.label or "").lower()), "")
            source_url_used = next((l.url for l in links if "admission" in (l.label or "").lower()), "")
            for link in links[:5]:
                answer_lines.append(f"- {link.label}: {link.url}")
        else:
            answer_lines.append(f"I do not have admission links stored for {uni_name} yet.")
            website = university.get("website", "")
            if website:
                answer_lines.append(f"The official website is {website}.")

    else:
        answer_lines.append(f"here is what I know about {uni_name}.")
        website = university.get("website", "")
        if website:
            answer_lines.append(f"Official website: {website}")
        if links:
            name_list = ", ".join(l.label for l in links[:3])
            answer_lines.append(f"Available links: {name_list}")
        answer_lines.append("For specific details, ask about fees, eligibility, entry test, or deadlines.")

    answer = " ".join(answer_lines) if not extracted else "\n".join(answer_lines)
    return UniversityInfoResponse(
        answer=answer.strip(),
        university_name=uni_name,
        info_type=info_type or "general",
        links=links[:5],
        sources=[],
        has_exact_data=has_exact,
        data_source=data_source,
        source_url_used=source_url_used,
    )

# ──────────────────────────────────────────────
# GET /data-status — data coverage report
# ──────────────────────────────────────────────

@app.get("/data-status")
async def data_status():
    records = []
    for uni in UNIVERSITIES:
        uid = uni.get("id", "")
        proc = find_processed_record(uid)
        uni_links = SOURCE_LINKS_BY_ID.get(uid, {})
        slinks = uni_links.get("links", {}) or {}
        website = uni.get("website", "")

        has_eligibility_link = any(
            "eligibility" in (k or "").lower() for k in slinks
        )
        has_fee_link = any(
            k in ("fee_structure", "tuition_fees") for k in slinks
        )
        has_entry_test_link = any(
            "entry_test" in (k or "").lower() for k in slinks
        )
        has_admissions_link = any(
            k in ("admissions", "admissions_homepage", "admissions_portal") for k in slinks
        )
        has_official_website = any(
            k == "official_website" for k in slinks
        )

        valid_count = sum(
            1 for k, v in slinks.items()
            if is_category_url_valid(k, (v or {}).get("url", ""))
        ) if slinks else 0

        possibly_wrong = []
        for k, v in slinks.items():
            url = (v or {}).get("url", "")
            if is_valid_url(url) and not is_category_url_valid(k, url):
                possibly_wrong.append({"key": k, "url": url})

        def text_ok(field: str) -> bool:
            val = (proc or {}).get(field, "")
            cleaned = val.strip().lower() if val else ""
            if not cleaned:
                return False
            if cleaned.startswith("needs official") or cleaned.startswith("needs "):
                return False
            return True

        records.append({
            "university_id": uid,
            "university_name": uni.get("short_name", uni.get("name", uid)),
            "valid_links_count": valid_count,
            "has_website": bool(website),
            "has_official_website": has_official_website,
            "has_admissions_link": has_admissions_link,
            "has_eligibility_link": has_eligibility_link,
            "has_fee_link": has_fee_link,
            "has_entry_test_link": has_entry_test_link,
            "has_eligibility_text": text_ok("eligibility_text"),
            "has_fee_text": text_ok("fee_text"),
            "has_entry_test_text": text_ok("entry_test_text"),
            "has_deadline_text": text_ok("deadline_text"),
            "possibly_wrong_links": possibly_wrong,
        })

    return {
        "total_universities": len(records),
        "records": records,
    }

# ──────────────────────────────────────────────
# POST /university-info — source-first answer for specific questions
# ──────────────────────────────────────────────

@app.post("/university-info")
async def university_info(request: UniversityInfoRequest):
    question = request.question
    profile = request.profile

    relevance = await classify_question_relevance(
        question,
        profile,
        bool(request.recent_context or request.university_id),
        request.university_id,
    )
    if relevance.intent == "greeting":
        return UniversityInfoResponse(
            answer=greeting_answer(profile),
            data_source="relevance",
            relevance=relevance,
        )
    if not relevance.allowed:
        return UniversityInfoResponse(
            answer=relevance.safe_reply or BLOCKED_REPLY,
            data_source="relevance",
            relevance=relevance,
        )

    uni_id = request.university_id or detect_university_in_question(question)
    if not uni_id:
        return UniversityInfoResponse(
            answer=f"I could not find a specific university name in your question. Mention a university name like FAST, NUST, LUMS, or COMSATS.",
        )

    info_type = request.info_type or detect_info_type(question)
    if not info_type:
        info_type = "general"

    response = await build_university_info_answer(question, profile, uni_id, info_type)
    response.relevance = relevance
    return response
