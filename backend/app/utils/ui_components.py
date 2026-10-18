"""
ui_components.py — Reusable styled HTML components for Streamlit UI.

Theme system:
    All component styles use CSS custom properties (variables) defined under
    :root. A `prefers-color-scheme: dark` media query overrides the variables
    when the user's browser is in dark mode, which is what Streamlit uses
    when the theme is set to "Dark" or "Auto" + dark OS preference.

    NOTE on Streamlit theme detection:
        Streamlit doesn't expose a reliable runtime theme flag we can read
        from Python (`st.get_option('theme.base')` returns empty when default).
        Instead we use the browser's `prefers-color-scheme` which Streamlit
        already mirrors. This is more reliable than injecting a `data-theme`
        attribute (which Streamlit's sandboxed iframe would block anyway).
"""
from __future__ import annotations
import re
from app.utils.config import RISK_COLORS

# ── Global CSS ─────────────────────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Source+Sans+3:wght@300;400;600&display=swap');

/* ═══════════════════════════════════════════════════════════════════
   THEME VARIABLES — locked to clean light surfaces (old-code look)
   The user explicitly chose this look regardless of light/dark mode.
   Card backgrounds stay cream/white in both modes; only the page
   background follows Streamlit's theme.
   ═══════════════════════════════════════════════════════════════════ */
:root {
    /* Brand */
    --brand-navy:        #1a3a5c;
    --brand-navy-deep:   #0f2942;
    --brand-gold:        #c9a84c;
    --brand-gold-soft:   #e8c96a;

    /* Surfaces — match old-code hardcoded values exactly */
    --surface:           #ffffff;     /* result-card, primary card surface */
    --surface-soft:      #f8fbff;     /* source-card, ngo-card, summary-card */
    --surface-softer:    #f4f7fb;     /* stat-box, placeholder */
    --surface-tint:      #e8f0fb;     /* category pills, source category badges */

    /* Text — solid dark for cream cards */
    --text-primary:      #2d3748;     /* main body text */
    --text-secondary:    #5a7a8a;     /* labels, captions */
    --text-tertiary:     #7a96ad;     /* placeholder, ghost text */

    /* Borders & shadows */
    --border-soft:       #dce8f5;     /* card outlines */
    --border-softer:     #f0f4f8;     /* row dividers */
    --shadow-card:       0 3px 14px rgba(15, 41, 66, 0.07);
    --shadow-card-hover: 0 6px 20px rgba(15, 41, 66, 0.12);
}

/* Dark mode is honoured ONLY for elements outside the card system —
   the cards themselves stay light-cream as per the chosen design. */
@media (prefers-color-scheme: dark) {
    :root {
        /* keep cards bright; only adjust shadow weight for dark backgrounds */
        --shadow-card:       0 3px 14px rgba(0, 0, 0, 0.35);
        --shadow-card-hover: 0 6px 22px rgba(0, 0, 0, 0.5);
    }
}

/* Apply Source Sans 3 to body, Playfair to display headings only */
html, body, [class*="css"] {
    font-family: 'Source Sans 3', sans-serif;
}

/* ═══════════════════════════════════════════════════════════════════
   MAIN PAGE — tighten default top padding so the hero starts higher
   ═══════════════════════════════════════════════════════════════════ */
.main .block-container,
[data-testid="stAppViewContainer"] .main .block-container {
    padding-top: 2.2rem !important;
    padding-bottom: 3rem !important;
}

/* ═══════════════════════════════════════════════════════════════════
   SIDEBAR — fixed dark gradient (intentionally dark in both modes)
   ═══════════════════════════════════════════════════════════════════ */
/* Hide Streamlit's auto-generated multipage nav (the "app/about/..."
   list at the top of the sidebar). The project uses its own custom
   radio-button navigation instead, so the auto-nav is duplicate clutter. */
[data-testid="stSidebarNav"] {
    display: none !important;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f2942 0%, #1a3a5c 100%);
    border-right: 2px solid var(--brand-gold);
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] .stCaption {
    color: #e8e8e8 !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(201, 168, 76, 0.4) !important;
}
/* Input internals stay readable on their own white surfaces */
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] select,
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] [data-baseweb="select"] * {
    color: #1a2a3a !important;
}

/* ═══════════════════════════════════════════════════════════════════
   HERO BANNER
   ═══════════════════════════════════════════════════════════════════ */
.hero-banner {
    background: linear-gradient(135deg, #0f2942, #1a3a5c 60%, #0d3b2e);
    border-radius: 18px;
    padding: 2.5rem 2.5rem 2rem;
    margin-bottom: 1.5rem;
    border-bottom: 4px solid var(--brand-gold);
    position: relative;
    overflow: hidden;
}
.hero-banner::before {
    content: "⚖";
    position: absolute;
    right: 2rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 8rem;
    opacity: 0.06;
    color: var(--brand-gold);
}
/* Hero title — the white !important applies ONLY to the title text itself,
   NOT to children. Inline-styled children (like the version pill) keep
   their own colours. */
.hero-title {
    font-family: 'Playfair Display', serif !important;
    color: #ffffff !important;
    font-size: 2.2rem;
    line-height: 1.2;
    font-weight: 700 !important;
    margin: 0 0 0.4rem;
}

.hero-subtitle {
    color: rgba(255,255,255,0.78);
    font-size: 1rem;
    margin: 0;
    font-weight: 500;
}

/* ═══════════════════════════════════════════════════════════════════
   CARDS — theme-aware
   ═══════════════════════════════════════════════════════════════════ */
.stat-box {
    background: var(--surface);
    border-radius: 12px;
    padding: 1.1rem 1rem;
    text-align: center;
    border: 1px solid var(--border-soft);
    border-top: 3px solid var(--brand-navy);
    box-shadow: var(--shadow-card);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.stat-box:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-card-hover);
}
.stat-box-value {
    color: var(--brand-navy);
    font-weight: 700;
    font-size: 1.35rem;
    line-height: 1.2;
    margin-bottom: 0.2rem;
}
.stat-box-label {
    color: var(--text-secondary);
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-transform: uppercase;
}
/* No dark-mode override needed — stat cards are locked to cream surface
   with navy values + grey labels in both light and dark mode. */

.result-card {
    background: var(--surface);
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    border: 1px solid var(--border-soft);
    box-shadow: var(--shadow-card);
    margin-bottom: 1rem;
}
.result-card-header {
    font-weight: 700;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 0.7rem;
    color: var(--brand-navy);
}
.result-list-item {
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border-softer);
    font-size: 0.95rem;
    line-height: 1.55;
    color: var(--text-primary);
    word-wrap: break-word;
    overflow-wrap: break-word;
}
.result-list-item:last-child { border-bottom: none; }

/* Risk badge */
.risk-badge {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    font-size: 0.95rem;
    border-left: 5px solid;
    margin-bottom: 1rem;
}

/* Source card — wraps long law text */
.source-card {
    background: var(--surface-soft);
    border: 1px solid var(--border-soft);
    border-left: 4px solid var(--brand-navy);
    border-radius: 10px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.6rem;
    font-size: 0.85rem;
    color: var(--text-primary);
    word-wrap: break-word;
    overflow-wrap: break-word;
    word-break: break-word;
    white-space: normal;
    max-width: 100%;
    overflow: hidden;
}

/* NGO card */
.ngo-card {
    background: var(--surface-soft);
    border: 1px solid var(--border-soft);
    border-left: 5px solid var(--brand-navy);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    color: var(--text-primary);
    word-wrap: break-word;
    overflow-wrap: break-word;
}

/* Section label */
.section-label {
    font-weight: 600;
    color: var(--brand-navy);
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.6rem;
}

/* Placeholder — readable in both modes */
.results-placeholder {
    background: var(--surface);
    border: 2px dashed var(--border-soft);
    border-radius: 14px;
    padding: 2.5rem;
    text-align: center;
    color: var(--text-secondary);
    box-shadow: var(--shadow-card);
}
.results-placeholder strong {
    color: var(--text-primary);
    font-size: 1.05rem;
    display: block;
    margin-bottom: 0.5rem;
}

/* Footer disclaimer — gold tint, theme-aware */
.footer-disclaimer {
    background: #fff8e7;
    border: 1px solid var(--brand-gold-soft);
    border-left: 5px solid var(--brand-gold);
    border-radius: 10px;
    padding: 1rem 1.4rem;
    color: #7a5c00;
    font-size: 0.88rem;
    margin-top: 2rem;
}
/* No dark override — footer keeps its light-gold parchment look in both modes. */

/* ═══════════════════════════════════════════════════════════════════
   CHAT — fixed-height scrollable region + bubble polish
   ═══════════════════════════════════════════════════════════════════ */
/* The chat block lives inside Streamlit's [data-testid="stVerticalBlock"].
   We target the container of stChatMessage children to give it a fixed
   height with internal scroll. Scope to a wrapper class we set in app.py. */
.chat-scroll-region {
    max-height: 460px;
    overflow-y: auto;
    padding: 0.6rem 0.4rem 0.6rem 0.4rem;
    border: 1px solid var(--border-soft);
    border-radius: 14px;
    background: var(--surface-softer);
    margin-bottom: 0.6rem;
    scrollbar-width: thin;
    scrollbar-color: var(--text-tertiary) transparent;
}
.chat-scroll-region::-webkit-scrollbar {
    width: 6px;
}
.chat-scroll-region::-webkit-scrollbar-track {
    background: transparent;
}
.chat-scroll-region::-webkit-scrollbar-thumb {
    background: var(--text-tertiary);
    border-radius: 4px;
}

/* Improve st.chat_message bubble spacing inside the scroll region */
.chat-scroll-region [data-testid="stChatMessage"] {
    background: transparent;
    padding: 0.4rem 0.6rem;
    margin: 0.2rem 0;
}
.chat-scroll-region [data-testid="stChatMessageContent"] {
    background: var(--surface);
    border: 1px solid var(--border-soft);
    border-radius: 14px;
    padding: 0.7rem 1rem;
    box-shadow: var(--shadow-card);
    max-width: 85%;
}
/* Wrap user bubble in primary colour by detecting role via aria-label
   (Streamlit applies aria-label="user" to user chat messages) */
.chat-scroll-region [data-testid="stChatMessage"][aria-label="user"]
[data-testid="stChatMessageContent"] {
    background: var(--brand-navy);
    color: #ffffff;
    border-color: var(--brand-navy);
    margin-left: auto;
}
.chat-scroll-region [data-testid="stChatMessage"][aria-label="user"]
[data-testid="stChatMessageContent"] * { color: #ffffff !important; }

/* Chat input subtle border */
[data-testid="stChatInput"] {
    border-radius: 12px !important;
    border: 1px solid var(--border-soft) !important;
}
[data-testid="stChatInput"] textarea {
    font-size: 0.95rem !important;
}

/* ═══════════════════════════════════════════════════════════════════
   CHAT HEADER BAR — navy gradient, flush above the chat container
   ═══════════════════════════════════════════════════════════════════ */
.chat-header-bar {
    background: linear-gradient(135deg, #1a3a5c 0%, #2c5282 100%);
    border-radius: 12px 12px 0 0;
    padding: 14px 22px 12px;
    margin: 0.5rem 0 0;
    border-bottom: 0;
}
.chat-header-title {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    color: #ffffff;
    font-size: 1.05rem;
    font-weight: 700;
    line-height: 1.2;
}
.chat-header-icon {
    font-size: 1.25rem;
}
.chat-header-subtitle {
    color: rgba(255, 255, 255, 0.78);
    font-size: 0.83rem;
    margin: 4px 0 0 1.85rem;     /* aligns under the title text, past icon */
    line-height: 1.3;
}

/* ═══════════════════════════════════════════════════════════════════
   BUTTONS — consistent radius, hover effect
   ═══════════════════════════════════════════════════════════════════ */
.stButton > button {
    transition: transform 0.15s ease, box-shadow 0.15s ease,
                background 0.15s ease, color 0.15s ease !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--brand-gold), #a87d2a) !important;
    color: var(--brand-navy-deep) !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 2rem !important;
    box-shadow: 0 4px 14px rgba(201, 168, 76, 0.35) !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(201, 168, 76, 0.45) !important;
}
.stButton > button:not([kind="primary"]) {
    border: 2px solid var(--brand-navy) !important;
    color: var(--brand-navy) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    background: transparent !important;
}
.stButton > button:not([kind="primary"]):hover {
    background: var(--brand-navy) !important;
    color: #ffffff !important;
    transform: translateY(-1px) !important;
}
@media (prefers-color-scheme: dark) {
    .stButton > button:not([kind="primary"]) {
        border-color: #5a8fc2 !important;
        color: #5a8fc2 !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        background: #5a8fc2 !important;
        color: var(--brand-navy-deep) !important;
    }
}

/* RAG badge */
.rag-badge{display:inline-block;background:#e8f4e8;color:#1d6b3a;
    border:1px solid #1d6b3a;border-radius:20px;
    padding:2px 12px;font-size:0.75rem;font-weight:600;}

/* ══════════════════════════════════════════════════════════════════
   QUICK-ISSUE CATEGORY CHIPS — even grid, graceful wrap, zoom-proof
   Buttons whose key starts with "chip_" (set in app.py) get a fixed
   min-height so all 8 cells line up in two clean rows even when one label
   wraps. word-break + hyphens stop ugly mid-word splits like "Harassmen / t".
   ═════════════════════════════════════════════════════════════════ */
/* All non-primary buttons inside any horizontal column block (chips +
   audio row trash/download): uniform min-height, sane wrap, no mid-word
   fragmentation like "Harassmen / t". */
div[data-testid="stHorizontalBlock"] .stButton > button:not([kind="primary"]) {
    min-height: 64px !important;
    white-space: normal !important;
    overflow-wrap: break-word !important;
    word-break: normal !important;
    line-height: 1.3 !important;
    padding: 10px 8px !important;
    font-size: 0.88rem !important;
}
/* Audio button row: uniform height across mic / trash / download / analyze
   so they don't stagger when "Start Recording" wraps. */
div[data-testid="stHorizontalBlock"] .stButton > button,
div[data-testid="stHorizontalBlock"] .stDownloadButton > button {
    min-height: 48px !important;
}
/* Primary "Analyze" stays taller and a touch bolder — reaffirm after the
   generic rule above so it wins. */
div[data-testid="stHorizontalBlock"] .stButton > button[kind="primary"] {
    min-height: 48px !important;
    white-space: nowrap !important;
}
</style>
"""

# ── Components ─────────────────────────────────────────────────────────────────

def hero_banner(title: str, subtitle: str, version: str = "") -> str:
    ver = (f'<span style="background:rgba(201,168,76,0.12);color:#f4c542;border:1px solid #c9a84c;'
           f'border-radius:20px;padding:2px 12px;font-size:0.72rem;margin-left:10px;">'
           f'{version}</span>') if version else ""
    return f"""<div class="hero-banner">
        <h1 class="hero-title">{title}{ver}</h1>
        <p class="hero-subtitle">{subtitle}</p>
        <span class="rag-badge" style="margin-top:0.5rem;display:inline-block;">
            🟢 RAG + Groq Active
        </span>
    </div>"""


def stat_box(icon: str, value: str, label: str) -> str:
    return (f'<div class="stat-box">'
            f'<div style="font-size:1.5rem;margin-bottom:0.25rem;">{icon}</div>'
            f'<div class="stat-box-value">{value}</div>'
            f'<div class="stat-box-label">{label}</div></div>')


def section_label(text: str) -> str:
    return f'<div class="section-label">{text}</div>'


def risk_card(level: str, reason: str, confidence: str = "",
              language: str = "English") -> str:
    from app.utils.translations import T
    t = T(language)
    cfg = RISK_COLORS.get(level, RISK_COLORS["Medium"])
    conf_html = (f'<span style="font-size:0.8rem;opacity:0.75;margin-left:8px;">'
                 f'{t("confidence_label")}: {confidence}</span>') if confidence else ""
    return (f'<div class="risk-badge" style="background:{cfg["bg"]};'
            f'border-color:{cfg["border"]};color:{cfg["text"]};">'
            f'<span style="font-size:1.4rem;">{cfg["icon"]}</span>'
            f'<div><strong>{t("risk_label")}: {level}</strong>{conf_html}'
            f'<div style="font-size:0.88rem;font-weight:400;margin-top:2px;">{reason}</div>'
            f'</div></div>')


def summary_card(text: str, category: str, language: str = "English") -> str:
    from app.utils.translations import T
    t = T(language)
    return (f'<div class="result-card" style="border-top:4px solid var(--brand-navy);'
            f'background:var(--surface-soft);">'
            f'<div class="result-card-header">{t("case_summary_label")}</div>'
            f'<p style="font-size:1rem;line-height:1.7;margin:0 0 0.8rem;'
            f'color:var(--text-primary);'
            f'word-wrap:break-word;overflow-wrap:break-word;">{text}</p>'
            f'<span style="background:var(--surface-tint);color:var(--brand-navy);'
            f'border-radius:20px;padding:3px 14px;font-size:0.8rem;font-weight:600;">'
            f'🏷️ {category}</span>'
            f'</div>')


# Citation regex: matches "Law Name <sep> Section X:" or "Law Name:"
# Accepts hyphen (-), en-dash (–), em-dash (—), or colon as separator before "Section".
# Length bounds prevent matching long sentences that happen to contain a colon.
_CITATION_RE = re.compile(
    r'^([^:—–\n]{5,80}?(?:\s*[\-—–]\s*[^:\n]{3,60})?:)\s*(.*)',
    re.DOTALL,
)

# Detect if a string contains Urdu / Arabic-script characters
_URDU_RE = re.compile(r'[\u0600-\u06FF]')

# Strip a leading emoji (and trailing space) from a header string. Used to
# avoid rendering the same icon twice when the localized header already
# embeds an emoji and the caller also passes an icon.
_LEADING_EMOJI_RE = re.compile(
    r'^[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F600-\U0001F64F'
    r'\U0001F900-\U0001F9FF\U0001F680-\U0001F6FF]+\s*'
)


def _strip_leading_emoji(text: str) -> str:
    """Remove a leading emoji and following whitespace if present."""
    return _LEADING_EMOJI_RE.sub("", text or "").strip()


def result_card(header: str, icon: str, items: list[str], accent: str = "#1a3a5c") -> str:
    """Render a result card.

    Citation handling: when an item starts with 'Law Name - Section X:' (any
    dash variant) or 'Law Name:', the citation portion is bolded and shown on
    its own line for Urdu (so RTL/LTR mixing of digits + colons cannot scramble
    the visual order). For English, the citation is inlined with a leading
    bullet for visual consistency across all items.
    """
    # Avoid duplicate emoji if the localized header already embeds one
    clean_header = _strip_leading_emoji(header)
    is_urdu_header = bool(_URDU_RE.search(clean_header))

    rows = []
    for item in items:
        item_str = (item or "").strip()
        if not item_str:
            continue

        is_urdu_item = bool(_URDU_RE.search(item_str))
        citation_match = _CITATION_RE.match(item_str)

        if citation_match:
            citation = citation_match.group(1).strip()
            rest     = citation_match.group(2).strip()
        else:
            citation = ""
            rest     = item_str

        if is_urdu_item:
            # RTL row: bullet sits inline at the right edge of the FIRST line
            # of text. Use a flex container with direction:rtl so the bullet
            # column lands on the right; align-items:baseline keeps the bullet
            # aligned with the first line of wrapped text (not centered
            # vertically across the whole block).
            if citation:
                inner_html = (
                    f'<div style="unicode-bidi:isolate;">'
                    f'<bdi style="color:{accent};font-weight:700;'
                    f'font-size:0.92rem;">{citation}</bdi>'
                    f'<div style="margin-top:3px;line-height:1.85;">'
                    f'<bdi>{rest}</bdi></div>'
                    f'</div>'
                )
            else:
                inner_html = (
                    f'<div style="unicode-bidi:isolate;line-height:1.85;">'
                    f'<bdi>{rest}</bdi></div>'
                )
            row_html = (
                f'<div class="result-list-item rtl" '
                f'style="display:flex;direction:rtl;text-align:right;'
                f'align-items:baseline;gap:8px;">'
                f'<span style="color:{accent};font-weight:700;'
                f'flex-shrink:0;line-height:1.85;">•</span>'
                f'<div style="flex:1;min-width:0;">{inner_html}</div>'
                f'</div>'
            )
        else:
            # English: bullet always; bold the citation prefix when present
            if citation:
                row_html = (
                    f'<div class="result-list-item">'
                    f'<span style="color:{accent};font-weight:700;">• {citation}</span> '
                    f'{rest}</div>'
                )
            else:
                row_html = (
                    f'<div class="result-list-item">• {rest}</div>'
                )
        rows.append(row_html)

    # Header: merge style attributes; align right for Urdu cards
    header_attrs = (
        f' dir="rtl" style="color:{accent};text-align:right;"'
        if is_urdu_header
        else f' style="color:{accent};"'
    )
    return (
        f'<div class="result-card" style="border-top:4px solid {accent};">'
        f'<div class="result-card-header"{header_attrs}>'
        f'{icon} {clean_header}</div>'
        f'{"".join(rows)}</div>'
    )


def grounding_warning(confidence: str, language: str = "English") -> str:
    """Show a low-confidence warning when RAG context is weak."""
    if confidence != "Low":
        return ""
    from app.utils.translations import T
    t = T(language)
    return (
        '<div style="background:#fff3cd;border:1px solid #ffc107;border-left:4px solid #ffc107;'
        'border-radius:8px;padding:0.7rem 1rem;margin-bottom:0.8rem;font-size:0.88rem;color:#856404;">'
        + t("grounding_warning_text")
        + '</div>'
    )


def sources_card(chunks: list[dict], language: str = "English") -> str:
    """
    Render retrieved law sources with clear attribution:
    law name, section, category, relevance bar, and a 2-line text snippet.
    """
    if not chunks:
        return ""

    from app.utils.translations import T
    t = T(language)

    rows = []
    seen: set[str] = set()

    for i, c in enumerate(chunks, 1):
        key = f"{c['law_name']}|{c.get('section', '')}"
        if key in seen:
            continue
        seen.add(key)

        section_html = ""
        if c.get("section"):
            section_html = (
                f'<div style="color:var(--brand-navy);font-size:0.82rem;margin-top:3px;">'
                f'📌 {c["section"]}</div>'
            )

        score = c.get("score", 0)
        bar_width = int(score * 100)
        bar_color = "#1d6b3a" if score >= 0.60 else "#f9a825" if score >= 0.40 else "#999"
        score_bar = (
            f'<div style="margin-top:5px;">'
            f'<div style="display:inline-block;width:{bar_width}%;height:4px;'
            f'background:{bar_color};border-radius:2px;"></div>'
            f'<span style="font-size:0.72rem;color:var(--text-tertiary);margin-left:6px;">'
            f'{score:.0%} match</span></div>'
        )

        # Snippet: clean up run-together words from PDF parsing artifacts
        snippet = c.get("text", "")
        snippet_lines = [ln.strip() for ln in snippet.split('\n') if len(ln.strip()) > 30]
        snippet_preview = " ".join(snippet_lines[:2])[:200]
        snippet_html = (
            f'<div style="color:var(--text-secondary);font-size:0.82rem;margin-top:5px;'
            f'font-style:italic;line-height:1.5;'
            f'word-break:break-word;overflow-wrap:anywhere;white-space:normal;">'
            f'"{snippet_preview}…"</div>'
            if snippet_preview else ""
        )

        rows.append(
            f'<div class="source-card" style="margin-bottom:0.8rem;'
            f'word-break:break-word;overflow-wrap:anywhere;">'
            f'<div style="display:flex;align-items:flex-start;gap:8px;">'
            f'<span style="background:var(--brand-navy);color:#fff;border-radius:50%;'
            f'width:20px;height:20px;display:flex;align-items:center;'
            f'justify-content:center;font-size:0.7rem;font-weight:700;'
            f'flex-shrink:0;margin-top:1px;">{i}</span>'
            f'<div style="flex:1;min-width:0;">'
            f'<strong style="color:var(--brand-navy);font-size:0.9rem;'
            f'word-break:break-word;">📖 {c["law_name"]}</strong>'
            f'<span style="background:var(--surface-tint);color:var(--brand-navy);border-radius:20px;'
            f'padding:1px 8px;font-size:0.7rem;margin-left:6px;">{c["category"]}</span>'
            f'{section_html}'
            f'{score_bar}'
            f'{snippet_html}'
            f'</div></div></div>'
        )

    html = "".join(rows)
    sources_label = t("sources_label")
    return (
        f'<div class="result-card" style="border-top:4px solid #4a6fa5;">'
        f'<div class="result-card-header" style="color:#4a6fa5;">'
        f'{sources_label} ({len(rows)} sections used)</div>'
        f'{html}</div>'
    )


def ngo_card(ngo: dict) -> str:
    ws = (f'<a href="{ngo["website"]}" target="_blank" '
          f'style="color:#1a73e8;font-size:0.82rem;white-space:nowrap;">🔗 Website</a>'
          if ngo.get("website") else "")
    svc = (f'<div style="color:#555;font-size:0.83rem;margin-top:0.3rem;">'
           f'🛎️ {ngo["services"]}</div>'
           if ngo.get("services") else "")
    return (f'<div class="ngo-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
            f'<div><strong style="color:#1a3a5c;">{ngo["name"]}</strong>'
            f'<span style="background:#1a3a5c;color:#fff;border-radius:20px;'
            f'padding:1px 10px;font-size:0.72rem;margin-left:8px;">{ngo.get("type","")}</span>'
            f'<div style="color:#555;margin-top:0.3rem;font-size:0.9rem;">'
            f'📍 {ngo.get("city","")} &nbsp;|&nbsp; 📞 <strong>{ngo.get("phone","")}</strong>'
            f'</div>{svc}</div>'
            f'<div style="padding-top:2px;">{ws}</div></div></div>')


def placeholder_box() -> str:
    return ('<div class="results-placeholder">'
            '<div style="font-size:3rem;margin-bottom:0.8rem;">⚖️</div>'
            '<strong>AI analysis will appear here.</strong>'
            '<p style="margin-top:0.5rem;font-size:0.88rem;">'
            'Describe your legal issue and click <em>Analyze Case</em>.</p></div>')


def footer(disclaimer: str) -> str:
    return f'<div class="footer-disclaimer">{disclaimer}</div>'