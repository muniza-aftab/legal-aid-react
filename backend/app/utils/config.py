"""
config.py — Central configuration for Pakistan AI Legal Aid Assistant
All constants, paths, and env-loaded secrets live here.
"""
import os
from dotenv import load_dotenv

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_BASE, ".env"), override=False)

# ── App Identity ───────────────────────────────────────────────────────────────
APP_TITLE    = "Pakistan Legal Aid AI Assistant"
APP_SUBTITLE = "RAG-powered multilingual legal guidance system"
APP_VERSION  = "2.0.0 – RAG + Groq"
APP_EMOJI    = "⚖️"

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR      = _BASE
DB_PATH       = os.path.abspath(os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "database.db")))
NGO_FILE      = os.path.join(BASE_DIR, "data", "ngos.json")
LAWS_DIR      = os.path.join(BASE_DIR, "data", "Laws")
FAISS_DIR     = os.path.join(BASE_DIR, "data", "faiss_index")
CHUNKS_FILE   = os.path.join(BASE_DIR, "data", "chunks.json")

CORS_ORIGINS = [origin.strip().rstrip("/") for origin in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,"
    "http://127.0.0.1:4173,https://legal-aid-react.vercel.app",
).split(",") if origin.strip() and origin.strip() != "*"]

# ── API Keys ───────────────────────────────────────────────────────────────────
GROQ_API_KEY:       str = os.getenv("GROQ_API_KEY", "")
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")

# Optional backup Groq keys (GROQ_API_KEY_2, GROQ_API_KEY_3, ...) — each must
# come from a SEPARATE Groq account, since keys on the same account share one
# quota pool. GROQ_API_KEYS lists every configured key, primary first, with
# duplicates and placeholder values removed; groq_client rotates through them
# automatically when the active key hits a 429 rate limit.
def _load_groq_api_keys() -> list[str]:
    keys = [GROQ_API_KEY]
    i = 2
    while True:
        extra = os.getenv(f"GROQ_API_KEY_{i}", "").strip()
        if not extra:
            break
        keys.append(extra)
        i += 1
    seen: set[str] = set()
    ordered: list[str] = []
    for k in keys:
        k = k.strip()
        if k and k != "your_groq_api_key_here" and k not in seen:
            seen.add(k)
            ordered.append(k)
    return ordered


GROQ_API_KEYS: list[str] = _load_groq_api_keys()

# ── Groq Model Config ─────────────────────────────────────────────────────────
GROQ_LLM_MODEL    = os.getenv("GROQ_LLM_MODEL", "openai/gpt-oss-120b")
GROQ_FAST_MODEL   = os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

# ── RAG Config ────────────────────────────────────────────────────────────────
# EMBED_MODEL       = "intfloat/multilingual-e5-base"  # Sentence-transformers model (fast, free)
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE        = 800                  # characters per chunk
CHUNK_OVERLAP     = 150                  # overlap between chunks
TOP_K_RETRIEVAL   = 8                    # number of chunks to retrieve (raised from 6)
SIMILARITY_THRESHOLD = 0.25             # base threshold (retrieval uses 0.40 primary internally)

# ── Input Validation ──────────────────────────────────────────────────────────
MAX_QUERY_LENGTH: int = int(os.getenv("MAX_QUERY_LENGTH", "2000"))
MIN_QUERY_LENGTH: int = int(os.getenv("MIN_QUERY_LENGTH", "15"))

# ── Languages ─────────────────────────────────────────────────────────────────
LANGUAGES = ["English", "Urdu"]

# ── Legal Categories ──────────────────────────────────────────────────────────
from app.utils.legal_taxonomy import LEGAL_CASE_TYPES

LEGAL_CATEGORIES = LEGAL_CASE_TYPES

# ── PDF Folder → Category mapping ────────────────────────────────────────────
FOLDER_CATEGORY_MAP = {
    "Civil": "Civil Law / Procedure",
    "Family": "Family Law",
    "Labour": "Labour Law",
    "Criminal": "Criminal Law",
    "Cybercrime": "Cybercrime",
    "Core": "Core",
    "Harassment": "Harassment",
}

# ── Filename → Category override ─────────────────────────────────────────────
FILENAME_CATEGORY_MAP = {
    "PAKISTAN PENAL CODE":              "Criminal Law",
    "CODE OF CRIMINAL PROCEDURE":       "Criminal Law",
    "CONSTITUTION":                     "Constitutional Law",
    "SUCCESSION":                       "Inheritance Law",
    "CONTRACT ACT":                     "Contract Law",
    "TRANSFER OF PROPERTY":             "Property Law",
    "SPECIFIC RELIEF":                  "Civil Law / Procedure",
    "LIMITATION ACT":                   "Civil Law / Procedure",
    "CODE OF CIVIL PROCEDURE":          "Civil Law / Procedure",
    "CONCILIATION COURTS":              "Civil Law / Procedure",
    "COURT-FEES":                       "Civil Law / Procedure",
    "MAJORITY ACT":                     "Civil Law / Procedure",
    "MUSLIM FAMILY LAWS":               "Family Law",
    "DISSOLUTION OF MUSLIM MARRIAGES":  "Family Law",
    "GUARDIANS AND WARDS":              "Family Law",
    "CHILD MARRIAGE":                   "Family Law",
    "DOWRY":                            "Family Law",
    "INDUSTRIAL RELATIONS":             "Labour Law",
    "PAYMENT OF WAGES":                 "Labour Law",
    "FACTORIES ACT":                    "Labour Law",
    "MINIMUM WAGES":                    "Labour Law",
    "WORKMEN":                          "Labour Law",
    "EMPLOYMENT OF CHILDREN":           "Labour Law",
    "OLD-AGE BENEFITS":                 "Labour Law",
    "EMPLOYEES":                        "Labour Law",
}

# ── NGO category mapping ──────────────────────────────────────────────────────
NGO_TYPE_TO_CATEGORY = {
    "Women Rights":                ["Family Law", "Harassment"],
    "Emergency / Social Services": ["General / Other"],
    "Legal Aid":                   ["General / Other", "Criminal Law", "Civil Law / Procedure"],
    "Human Rights":                ["Criminal Law", "Constitutional Law"],
    "Women & Child Rights":        ["Family Law", "Harassment"],
    "Child & Family Protection":   ["Family Law"],
    "Gender Violence":             ["Harassment", "Family Law"],
    "Labour Rights":               ["Labour Law"],
    "Youth & Labour Rights":       ["Labour Law"],
    "Cybercrime / Digital Rights": ["Cybercrime"],
}

# ── Emergency Contacts ────────────────────────────────────────────────────────
EMERGENCY_CONTACTS = [
    {"label": "Police",            "number": "15",   "icon": "🚔", "color": "#1a3a5c"},
    {"label": "Edhi Foundation",   "number": "115",  "icon": "🚑", "color": "#1d6b3a"},
    {"label": "Women Helpline",    "number": "1099", "icon": "👩", "color": "#7b2d5e"},
    {"label": "Cyber Crime (FIA)", "number": "9911", "icon": "🛡️", "color": "#2c4a7c"},
    {"label": "Rescue",            "number": "1122", "icon": "🔥", "color": "#9b2335"},
]

# ── Risk level config ─────────────────────────────────────────────────────────
RISK_COLORS = {
    "Low":      {"bg": "#e8f5e9", "border": "#1d6b3a", "text": "#1d6b3a", "icon": "🟢"},
    "Medium":   {"bg": "#fff8e1", "border": "#f9a825", "text": "#7a5c00", "icon": "🟡"},
    "High":     {"bg": "#fdecea", "border": "#c62828", "text": "#b71c1c", "icon": "🔴"},
    # Critical — reserved for threat-to-life / severe violence (set by groq_client)
    "Critical": {"bg": "#3a0c0c", "border": "#7a0000", "text": "#ffffff", "icon": "🚨"},
}

# ── Prompt injection blocklist ────────────────────────────────────────────────
INJECTION_PATTERNS = [
    "ignore previous", "ignore all instructions", "you are now",
    "forget everything", "act as", "pretend you are", "jailbreak",
    "dan mode", "do anything now", "disregard your", "override system",
    "system prompt", "ignore your", "new instructions",
]

# ── Pakistan cities ───────────────────────────────────────────────────────────
PAKISTAN_CITIES = [
    "Any City", "Karachi", "Lahore", "Islamabad", "Rawalpindi",
    "Peshawar", "Quetta", "Multan", "Faisalabad",
]

# ── App disclaimer ────────────────────────────────────────────────────────────
DISCLAIMER = (
    "⚠️ This tool provides legal information only and does not replace a licensed lawyer. "
    "Always consult a qualified legal professional for advice specific to your situation."
)
