"""
rag_engine.py — FAISS index builder + retrieval engine.

Build:   build_index(chunks) → saves FAISS index + metadata to FAISS_DIR
Retrieve: retrieve(query, top_k) → list of relevant chunk dicts with scores

Index files written:
  data/faiss_index/index.bin      — FAISS flat inner-product index
  data/faiss_index/metadata.json  — parallel array of chunk metadata
"""
from __future__ import annotations
import os
import re
import json
import logging
import numpy as np
import faiss
import functools  # streamlit removed

from utils.config import FAISS_DIR, TOP_K_RETRIEVAL, SIMILARITY_THRESHOLD
from utils.embeddings import encode_texts, encode_query

logger = logging.getLogger(__name__)

_INDEX_PATH    = os.path.join(FAISS_DIR, "index.bin")
_METADATA_PATH = os.path.join(FAISS_DIR, "metadata.json")

# Module-level cache
_index:    faiss.IndexFlatIP | None = None
_metadata: list[dict]               = []


# ── Query preprocessor ─────────────────────────────────────────────────────────



# Urdu script → expand with English legal synonyms appended
_URDU_LEGAL_EXPANSIONS = {
    # Family Law
    'طلاق':         'divorce talaq',
    'خلع':          'khula divorce dissolution of marriage at instance of wife',
    'نکاح':         'marriage nikah',
    'مہر':          'dower mehr marriage gift',
    'نان نفقہ':     'maintenance alimony support of wife and children',
    'حضانت':        'custody guardianship of minor children',
    'تحویل':        'custody guardianship possession',
    'گھریلو تشدد':  'domestic violence',
    'جہیز':         'dowry',
    # Natural ways users describe domestic abuse without the formal compound
    # term above (e.g. "میرے شوہر نے مجھ پر تشدد کیا" / "میرا شوہر مجھے مارتا ہے")
    'تشدد':         'domestic violence cruelty abuse',
    'مار پیٹ':      'beating physical assault domestic violence battery',
    'مارتا ہے':     'beats hits physical violence domestic abuse assault',
    'پیٹتا ہے':     'beats hits physical violence domestic abuse assault',
    'مارتا پیٹتا':  'beats hits physical violence domestic abuse assault',

    # Inheritance
    'وراثت':        'inheritance succession',
    'وصیت':         'will testament bequest legacy',

    # Property / Tenancy
    'زمین':         'land property',
    'جائیداد':      'property estate assets',
    'مکان':         'house property rent',
    'کرایہ':        'rent tenancy',
    'قبضہ':         'possession encroachment trespass illegal occupation',
    'انتقال':       'mutation transfer of property registration',
    # Natural landlord-tenant phrasing — bridges to TPA §§105-116 (leases)
    'کرایہ دار':    'lessee tenant lease immoveable property',
    'مالک مکان':    'lessor landlord notice to quit',
    'کرایہ نامہ':   'lease of immoveable property duration term',
    'سیکیورٹی ڈپازٹ': 'security deposit refund tenancy',
    'خالی کرنا':    'determination of lease notice to quit vacation premises',
    'بے دخل':       'eviction unlawful ejection illegal dispossession',
    'بے دخلی':      'eviction unlawful dispossession illegal ejection',

    # Labour
    'تنخواہ':       'salary wages payment',
    'اجرت':         'wages remuneration payment',
    'مزدور':        'worker labourer',
    'ملازمت':       'employment job',
    'نوکری':        'job employment service',
    'برطرفی':       'termination dismissal from employment removal from service',
    'نکال دیا':     'termination dismissal removal from job without notice',

    # Criminal Law
    'گرفتاری':      'arrest detention',
    'قتل':          'murder homicide qatl',
    'اغوا':         'kidnapping abduction',
    'چوری':         'theft stealing',
    'ڈکیتی':        'robbery dacoity armed robbery',
    'دھوکہ دہی':    'fraud cheating deception',
    'جعل سازی':     'forgery counterfeiting',
    'رشوت':         'bribery corruption illegal gratification',
    'ہتک عزت':      'defamation harm to reputation',
    'زیادتی':       'abuse oppression sexual assault rape excess of power',

    # Cybercrime
    'ہیک':          'hacking unauthorized access to data',
    'ہیکنگ':        'hacking unauthorized access to data',
    'بلیک میلنگ':   'blackmail extortion',
    'جعلی اکاؤنٹ':  'fake account identity theft impersonation unauthorized use of identity information',

    # Harassment
    'ہراسانی':      'harassment',
    'جنسی ہراسانی': 'sexual harassment',
    'ظلم':          'oppression harassment violence cruelty',

    # Civil Law / Procedure
    'دعوی':         'claim lawsuit civil suit',
    'حکم امتناعی':  'injunction stay order restraining order',
    'ڈگری':         'decree judgment court order',

    # Contract Law
    'معاہدہ':       'contract agreement',
    'خلاف ورزی':    'breach of contract violation of agreement',

    # Consumer Rights
    'صارف':         'consumer rights consumer protection',
    'ناقص سامان':   'defective goods substandard products faulty merchandise',

    # Constitutional Law
    'بنیادی حقوق':  'fundamental rights constitution',
    'آئین':         'constitution constitutional law',

    # Finance / Cheques / Debt
    'چیک':          'cheque dishonour of cheque bounced cheque',
    'فراڈ':         'fraud cheating financial crime',
    'قرض':          'debt loan recovery',

    # Bail / Custody
    'ضمانت':        'bail bond surety release on bail admission to bail',
    'ضمانتی':       'bail bond surety guarantor',
    'حراست':        'custody detention remand',
    'حوالات':       'lockup detention custody',
    'پیشگی ضمانت':  'anticipatory bail pre-arrest bail',
    'رہائی':        'release discharge',

    # General / Court
    'عدالت':        'court tribunal',
    'وکیل':         'lawyer advocate',
    'حق':           'right entitlement',
    'حقوق':         'rights entitlements',
    'بچہ':          'child minor custody',
    'معاوضہ':       'compensation damages',
}

# English colloquial phrasing → legal terminology. Bridges the vocabulary gap
# between how users describe a problem ("fake account pretending to be me")
# and the statutory language that actually names it ("unauthorized use of
# identity information" / "offences against dignity") — phrasing that embeds
# nowhere near the relevant section text on its own.
_ENGLISH_LEGAL_EXPANSIONS = {
    'fake account':         'identity theft impersonation unauthorized use of identity information',
    'fake accounts':        'identity theft impersonation unauthorized use of identity information',
    'fake profile':         'identity theft impersonation unauthorized use of identity information',
    'fake profiles':        'identity theft impersonation unauthorized use of identity information',
    'pretending to be':     'impersonation identity theft offences against dignity of a person',
    'impersonat':           'identity theft unauthorized use of identity information',
    'using my name':        'unauthorized use of identity information',
    'using my photo':       'offences against dignity harm to reputation',
    'using my photos':      'offences against dignity harm to reputation',
    'using my photographs': 'offences against dignity harm to reputation',
}


def preprocess_query(query: str) -> str:
    """
    Normalize and enrich the query for better embedding retrieval.

    Steps:
      1. Strip excess whitespace / control chars
      2. Detect Urdu script → append English legal synonyms
      3. Normalize punctuation and casing for embedding
      4. Return enriched query string
    """
    if not query:
        return query

    query = query.strip()
    query = re.sub(r'[^\S\n]+', ' ', query)        # collapse whitespace
    query = re.sub(r'\n+', ' ', query)              # flatten to single line

    # ── Urdu script detection ─────────────────────────────────────────────────
    urdu_chars = len(re.findall(r'[\u0600-\u06FF]', query))
    total_alpha = len(re.findall(r'[^\s\d\W]', query)) or 1

    if urdu_chars / total_alpha > 0.3:
        # Append English synonyms for detected Urdu legal terms
        additions = []
        for urdu_word, english_equiv in _URDU_LEGAL_EXPANSIONS.items():
            if urdu_word in query:
                additions.append(english_equiv)
        if additions:
            query = query + " " + " ".join(additions)

    # ── English colloquial phrasing → legal terminology ──────────────────────
    q_lower_for_expansion = query.lower()
    legal_additions = [
        expansion
        for phrase, expansion in _ENGLISH_LEGAL_EXPANSIONS.items()
        if phrase in q_lower_for_expansion
    ]
    if legal_additions:
        query = query + " " + " ".join(dict.fromkeys(legal_additions))

    # ── General normalization ─────────────────────────────────────────────────
    # Expand common legal abbreviations only if not already followed by their expansion.
    _abbrevs = [
        ('FIR',  'FIR first information report',  'first information'),
        ('PPC',  'PPC Pakistan Penal Code',        'Pakistan Penal'),
        ('CrPC', 'CrPC Code of Criminal Procedure','Code of Criminal'),
        ('CPC',  'CPC Code of Civil Procedure',    'Code of Civil'),
    ]
    for abbr, expansion, already_marker in _abbrevs:
        # Only expand if the expansion marker doesn't immediately follow the abbreviation
        query = re.sub(
            rf'\b{abbr}\b(?!\s+{re.escape(already_marker.split()[0])})',
            expansion,
            query,
        )

    return query.strip()


# ── Build ──────────────────────────────────────────────────────────────────────

def build_index(chunks: list[dict], force: bool = False) -> None:
    """
    Embed all chunk texts and build a FAISS IndexFlatIP (inner product = cosine
    on normalised vectors).  Saves index + metadata to FAISS_DIR.
    """
    global _index, _metadata

    os.makedirs(FAISS_DIR, exist_ok=True)

    if not force and os.path.exists(_INDEX_PATH) and os.path.exists(_METADATA_PATH):
        logger.info("FAISS index already exists — loading from disk.")
        _load_index()
        return

    if not chunks:
        raise ValueError("No chunks provided to build_index().")

    logger.info(f"Building FAISS index for {len(chunks):,} chunks …")
    texts = [c["text"] for c in chunks]

    logger.info("Encoding chunks (this takes ~1–3 min on first run) …")
    embeddings = encode_texts(texts, batch_size=64, show_progress=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)   # exact inner product (cosine on normed vecs)
    index.add(embeddings)

    faiss.write_index(index, _INDEX_PATH)

    # Metadata: strip full text to save space (text is in chunks.json anyway)
    meta = [{
        "id":         c["id"],
        "law_name":   c["law_name"],
        "category":   c["category"],
        "section":    c["section"],
        "source":     c["source"],
        "page_start": c["page_start"],
        "text":       c["text"],          # keep for retrieval display
    } for c in chunks]

    with open(_METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    _index    = index
    _metadata = meta

    logger.info(f"FAISS index built: {index.ntotal:,} vectors (dim={dim})")
    logger.info(f"Saved to: {FAISS_DIR}")


# ── Schedule / appendix detector (used at index-load time) ────────────────────
# Detects chunks whose body text contains a schedule/appendix/form marker.
# The detector is then propagated to (cont.) continuation chunks that share
# the same section description — because the parser sometimes mislabels
# schedule items with operative section numbers (e.g. IRA Schedule II item 8
# gets labeled "Section 8", and its continuation chunks inherit that label).
_LOCAL_SCHEDULE_RX = re.compile(
    r'\b(SCHEDULE[-\s_]*[IVX0-9]+|FIRST SCHEDULE|SECOND SCHEDULE|THIRD SCHEDULE|'
    r'FOURTH SCHEDULE|FIFTH SCHEDULE|APPENDIX[-\s_]*[IVX]+|APPENDIX[-\s_]+[A-Z]\b|'
    r'FORM\s+(?:NO\.\s*)?[IVX0-9]+|RULES OF PROCEDURE|MODEL FORM)\b',
    re.IGNORECASE,
)

_CONT_RX = re.compile(r'\s*\(cont\.\)\s*$')


def _annotate_schedule_flags(metadata: list[dict]) -> None:
    """
    Walk metadata in document order (per law) and set chunk['is_schedule']=True
    on chunks whose body contains schedule/appendix markers, propagating to
    (cont.) continuation chunks with the same section description.

    Mutates metadata in place. Idempotent.
    """
    from collections import defaultdict

    by_law: dict[str, list[dict]] = defaultdict(list)
    for c in metadata:
        by_law[c.get("law_name", "")].append(c)

    for law, lst in by_law.items():
        # Sort by id (chunks were assigned ids in document order during build)
        lst.sort(key=lambda c: c.get("id", ""))
        last_base = None
        last_was_schedule = False

        for c in lst:
            text = c.get("text", "") or ""
            sec  = c.get("section", "") or ""
            base = _CONT_RX.sub("", sec).strip()

            local_hit = bool(_LOCAL_SCHEDULE_RX.search(text))
            is_cont   = "(cont.)" in sec
            cont_hit  = (base == last_base and last_was_schedule and is_cont)

            c["is_schedule"] = bool(local_hit or cont_hit)

            # Update tracker for next chunk
            if base != last_base:
                last_base = base
                last_was_schedule = local_hit
            else:
                last_was_schedule = last_was_schedule or local_hit


@functools.lru_cache(maxsize=1)
def _cached_load_index():
    index = faiss.read_index(_INDEX_PATH)

    with open(_METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # Precompute per-chunk schedule flag once — cheap, ~50ms for 8k chunks.
    _annotate_schedule_flags(metadata)

    return index, metadata


def _load_index() -> None:
    global _index, _metadata

    if _index is not None:
        return

    _index, _metadata = _cached_load_index()

    logger.info(f"FAISS index loaded: {_index.ntotal:,} vectors")


# ── Retrieve ───────────────────────────────────────────────────────────────────

def retrieve(query: str, top_k: int = TOP_K_RETRIEVAL) -> list[dict]:
    """
    Embed the (preprocessed) query and return the top_k most relevant law chunks.

    Pipeline:
      1. Preprocess query (multilingual expansion)
      2. Encode to vector
      3. FAISS search (over-fetch 5× for better candidate pool)
      4. Score boosting: category affinity + keyword overlap
      5. Filter by tiered similarity threshold
      6. Enforce diversity: max 3 chunks per law (up from 2)
      7. Return top_k results sorted by boosted score

    Threshold strategy:
      - Primary:  0.40  (was 0.30 — tighter to cut unrelated laws)
      - Fallback: 0.28  (only if fewer than 3 results pass primary)
      - Floor:    never drop below 0.20

    Category affinity boost (+0.06):
      When a chunk's category matches the most-likely legal category inferred
      from the query keywords, its score is boosted before ranking. This
      prevents low-scoring relevant chunks from being displaced by
      higher-scoring but categorically wrong chunks.
    """
    global _index, _metadata

    if _index is None:
        if os.path.exists(_INDEX_PATH):
            _load_index()
        else:
            logger.warning("FAISS index not found — run build_index first.")
            return []

    # Step 1: preprocess
    clean_query = preprocess_query(query)
    logger.debug(f"Preprocessed query: {clean_query[:120]}")

    # Step 2: encode
    q_vec = encode_query(clean_query)

    # Step 3: over-fetch (5× for better candidate pool)
    fetch_k = min(top_k * 5, len(_metadata))
    scores, indices = _index.search(q_vec, fetch_k)

    # ── Category affinity: infer likely legal domain from query keywords ──────
    # Maps query keyword → expected metadata category string.
    # Used to boost chunks whose category matches the query domain.
    _KEYWORD_CATEGORY_MAP = {
        # Family law
        "divorce": "Family Law",    "talaq": "Family Law",
        "nikah": "Family Law",      "marriage": "Family Law",
        "custody": "Family Law",    "khula": "Family Law",
        "mehr": "Family Law",       "maintenance": "Family Law",
        "طلاق": "Family Law",       "نکاح": "Family Law",
        "خلع": "Family Law",        "مہر": "Family Law",
        "تحویل": "Family Law",      "حضانت": "Family Law",
        "نان نفقہ": "Family Law",   "گھریلو تشدد": "Family Law",
        # Labour law
        "salary": "Labour Law",     "wages": "Labour Law",
        "employment": "Labour Law", "termination": "Labour Law",
        "fired": "Labour Law",      "worker": "Labour Law",
        "tankhwah": "Labour Law",   "naukri": "Labour Law",
        "تنخواہ": "Labour Law",     "ملازمت": "Labour Law",
        "برخاستگی": "Labour Law",   "مزدور": "Labour Law",
        # Property
        "rent": "Property Law",     "eviction": "Property Law",
        "tenant": "Property Law",   "landlord": "Property Law",
        "land": "Property Law",     "property": "Property Law",
        "kiraya": "Property Law",   "makaan": "Property Law",
        "زمین": "Property Law",     "مکان": "Property Law",
        "جائیداد": "Property Law",  "کرایہ": "Property Law",
        "مالک مکان": "Property Law","کرایہ دار": "Property Law",
        "قبضہ": "Property Law",     "بے دخل": "Property Law",
        # Criminal
        "fir": "Criminal Law",      "arrest": "Criminal Law",
        "police": "Criminal Law",   "bail": "Criminal Law",
        "murder": "Criminal Law",   "assault": "Criminal Law",
        "violence": "Criminal Law", "beating": "Criminal Law",
        "گرفتاری": "Criminal Law",  "پولیس": "Criminal Law",
        "تشدد": "Criminal Law",     "مار پیٹ": "Criminal Law",
        "حملہ": "Criminal Law",     "قتل": "Criminal Law",
        "چوری": "Criminal Law",     "ڈکیتی": "Criminal Law",
        "گرفتار": "Criminal Law",   "ایف آئی آر": "Criminal Law",
        "مقدمہ": "Criminal Law",    "تھانہ": "Criminal Law",
        # Harassment
        "harassment": "Harassment", "stalking": "Harassment",
        "blackmail": "Harassment",  "threat": "Harassment",
        "ہراسانی": "Harassment",    "ہراساں": "Harassment",
        "دھمکی": "Harassment",      "تعاقب": "Harassment",
        "بلیک میل": "Harassment",   "زیادتی": "Harassment",
        # Inheritance
        "inheritance": "Inheritance Law", "wirasat": "Inheritance Law",
        "وراثت": "Inheritance Law", "ورثاء": "Inheritance Law",
        "حصہ": "Inheritance Law",   "وصیت": "Inheritance Law",
        # Cybercrime
        "cybercrime": "Cybercrime", "online fraud": "Cybercrime",
        "hacking": "Cybercrime",    "سائبر": "Cybercrime",
    }

    q_lower = clean_query.lower()
    # Find the most-signalled category (highest keyword hit count)
    cat_hits: dict[str, int] = {}
    for kw, cat in _KEYWORD_CATEGORY_MAP.items():
        if kw in q_lower or kw in query:
            cat_hits[cat] = cat_hits.get(cat, 0) + 1
    preferred_category = max(cat_hits, key=cat_hits.get) if cat_hits else None
    logger.debug(f"Preferred category: {preferred_category} (hits: {cat_hits})")

    # ── Keyword overlap boost ─────────────────────────────────────────────────
    # Extract meaningful query words (>3 chars) for a lightweight keyword
    # overlap bonus. This helps when the embedding similarity is close between
    # two chunks — the one that shares more words with the query wins.
    query_words = set(w for w in re.findall(r'\b\w{4,}\b', q_lower) if w not in {
        "that", "this", "with", "have", "from", "they", "their", "what",
        "when", "where", "which", "will", "been", "were", "does",
    })

    # ── Score each candidate and apply boosts ─────────────────────────────────
    PRIMARY_THRESHOLD  = 0.40
    FALLBACK_THRESHOLD = 0.28
    CATEGORY_BOOST     = 0.06
    KEYWORD_BOOST_MAX  = 0.04    # max bonus from keyword overlap
    SCHEDULE_PENALTY   = 0.12    # demote schedule/appendix/form chunks
    MAX_PER_LAW        = 3       # increased from 2 — avoids premature law cutoff

    candidates = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue

        sim = float(score)
        meta = _metadata[idx].copy()
        text = meta.get("text", "")

        # Skip trivially short or table-of-contents chunks
        if len(text) < 120:
            continue
        sentences = len(re.findall(r'[.!?]\s', text))
        if len(text) > 200 and sentences < 2 and text.count('\n') > 8:
            continue

        # Apply category affinity boost
        boosted = sim
        if preferred_category and meta.get("category") == preferred_category:
            boosted += CATEGORY_BOOST

        # Apply keyword overlap boost (proportional, capped)
        if query_words:
            chunk_words = set(re.findall(r'\b\w{4,}\b', text.lower()))
            overlap = len(query_words & chunk_words)
            kw_boost = min(overlap / max(len(query_words), 1), 1.0) * KEYWORD_BOOST_MAX
            boosted += kw_boost

        # Schedule / appendix / form penalty: these chunks contain non-operative
        # text (procedural forms, model rules, schedules of fees, etc.). When
        # they share a section label with an operative section due to a parser
        # quirk, they pollute citations. Demote them so an operative section
        # with similar similarity wins. The is_schedule flag is precomputed in
        # _annotate_schedule_flags() at index load time — it correctly handles
        # both direct schedule markers and (cont.) continuation chunks.
        if meta.get("is_schedule"):
            boosted -= SCHEDULE_PENALTY

        meta["score"]        = round(sim, 4)
        meta["boosted_score"] = round(boosted, 4)
        candidates.append(meta)

    # ── Two-pass threshold filtering ──────────────────────────────────────────
    # Pass 1: primary threshold (0.40)
    above_primary = [c for c in candidates if c["boosted_score"] >= PRIMARY_THRESHOLD]

    # Pass 2: if too few results, relax to fallback threshold (0.28)
    if len(above_primary) < 3:
        above_fallback = [
            c for c in candidates
            if FALLBACK_THRESHOLD <= c["boosted_score"] < PRIMARY_THRESHOLD
        ]
        pool = above_primary + above_fallback
        logger.debug(
            f"Threshold relaxed: {len(above_primary)} primary → "
            f"{len(pool)} after fallback"
        )
    else:
        pool = above_primary

    # Sort by boosted score descending
    pool.sort(key=lambda x: x["boosted_score"], reverse=True)

    # ── Diversity cap ─────────────────────────────────────────────────────────
    results = []
    seen_per_law: dict[str, int] = {}

    for meta in pool:
        law = meta["law_name"]
        if seen_per_law.get(law, 0) >= MAX_PER_LAW:
            continue
        seen_per_law[law] = seen_per_law.get(law, 0) + 1

        # Use the original (un-boosted) score for display — the boosted score
        # was only used for ranking, not for showing relevance % to the user.
        results.append(meta)
        if len(results) >= top_k:
            break

    logger.debug(
        f"Retrieved {len(results)} chunks from {len(seen_per_law)} laws "
        f"(preferred_cat={preferred_category})"
    )
    return results


# ── Index health check ─────────────────────────────────────────────────────────

def index_ready() -> bool:
    """Return True if the FAISS index exists on disk."""
    return os.path.exists(_INDEX_PATH) and os.path.exists(_METADATA_PATH)


def index_stats() -> dict:
    """Return basic stats about the loaded index."""
    if not index_ready():
        return {"status": "not_built"}
    _load_index()
    from collections import Counter
    cats = Counter(m["category"] for m in _metadata)
    laws = len({m["law_name"] for m in _metadata})
    return {
        "status":   "ready",
        "vectors":  _index.ntotal,
        "laws":     laws,
        "chunks":   len(_metadata),
        "categories": dict(cats),
    }