"""
utils/pdf_generator.py — Professional PDF export for Pakistan AI Legal Aid.

Creates a clean, well-structured case summary PDF using reportlab.
Supports both English and Urdu text (via DejaVuSans TTF font which includes
Arabic/Urdu Unicode glyphs).  Falls back to Helvetica on systems where the
font file is unavailable (English-only output remains fully readable).

Public API:
    generate_case_pdf(result, language) -> str
        result:   LegalAnalysis object (summary, laws, rights, next_steps,
                  risk_level, risk_reason, category, confidence)
        language: "English" or "Urdu"
        Returns:  absolute path to the generated temp PDF file.
"""
from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from typing import Optional

import arabic_reshaper
from bidi.algorithm import get_display


from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Colour palette ─────────────────────────────────────────────────────────────
_NAVY       = colors.HexColor("#1a3a5c")
_GOLD       = colors.HexColor("#c9a84c")
_LIGHT_BG   = colors.HexColor("#f5f7fa")
_BORDER     = colors.HexColor("#dde3ea")
_GREEN      = colors.HexColor("#1d6b3a")
_ORANGE     = colors.HexColor("#e65c00")
_RED        = colors.HexColor("#c62828")
_DARK_RED   = colors.HexColor("#7a0000")    # Critical: deeper than _RED
_GREY_TEXT  = colors.HexColor("#444444")
_LIGHT_GREY = colors.HexColor("#888888")

# Risk level → colour (must include all tiers from groq_client.stabilize_risk)
_RISK_COLORS = {
    "Low":      _GREEN,
    "Medium":   _ORANGE,
    "High":     _RED,
    "Critical": _DARK_RED,
}

# ── Font registration ──────────────────────────────────────────────────────────
# Two font families are registered:
#   • DejaVuSans   — Latin + extended Unicode (used for English body text)
#   • NotoUrdu     — Arabic / Urdu glyphs (used for Urdu body text)
#
# Search order for each font (first hit wins):
#   1. Project-local: <project>/assets/fonts/<font>.ttf  (portable, recommended)
#   2. Debian/Ubuntu system path                          (server fallback)
#
# If a font cannot be registered, the global flag remains False and the
# corresponding language gracefully degrades. The default Helvetica is only
# ever used for English when DejaVuSans is unavailable — Urdu without an
# Arabic-capable font would produce squares, so we explicitly detect that
# situation and warn the user via a message in the PDF instead.

# Project root (one level above utils/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOCAL_FONTS  = os.path.join(_PROJECT_ROOT, "assets", "fonts")

_FONT_REGULAR = "Helvetica"          # Latin font alias used by reportlab
_FONT_BOLD    = "Helvetica-Bold"
_FONT_URDU    = None                 # set to a font name only if Urdu font registers
_FONT_URDU_BOLD = None

_DEJAVU_REGULAR_CANDIDATES = [
    os.path.join(_LOCAL_FONTS, "DejaVuSans.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_DEJAVU_BOLD_CANDIDATES = [
    os.path.join(_LOCAL_FONTS, "DejaVuSans-Bold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# NotoNastaliqUrdu is purpose-built for Urdu (Nastaliq script style).
# NotoNaskhArabic / NotoSansArabic are acceptable substitutes if Nastaliq is missing.
_URDU_REGULAR_CANDIDATES = [
    os.path.join(_LOCAL_FONTS, "NotoNastaliqUrdu-Regular.ttf"),
    os.path.join(_LOCAL_FONTS, "NotoNaskhArabic-Regular.ttf"),
    "/usr/share/fonts/truetype/noto/NotoNastaliqUrdu-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
]
_URDU_BOLD_CANDIDATES = [
    os.path.join(_LOCAL_FONTS, "NotoNastaliqUrdu-Bold.ttf"),
    os.path.join(_LOCAL_FONTS, "NotoNaskhArabic-Bold.ttf"),
    "/usr/share/fonts/truetype/noto/NotoNastaliqUrdu-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
]


def _first_existing(paths: list[str]) -> Optional[str]:
    """Return the first path in `paths` that exists on disk, else None."""
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def _try_register_fonts() -> None:
    """
    Register Latin (DejaVuSans) and Urdu (Noto) fonts at module load.
    Updates module-level font name globals on success.
    Failures are silent; downstream code degrades gracefully.
    """
    global _FONT_REGULAR, _FONT_BOLD, _FONT_URDU, _FONT_URDU_BOLD

    # ── Latin: DejaVuSans (Unicode-capable replacement for Helvetica) ─────────
    dv_reg  = _first_existing(_DEJAVU_REGULAR_CANDIDATES)
    dv_bold = _first_existing(_DEJAVU_BOLD_CANDIDATES)
    if dv_reg and dv_bold:
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans",      dv_reg))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", dv_bold))
            _FONT_REGULAR = "DejaVuSans"
            _FONT_BOLD    = "DejaVuSans-Bold"
        except Exception:
            pass   # keep Helvetica fallback

    # ── Urdu: NotoNastaliqUrdu / NotoNaskhArabic / NotoSansArabic ─────────────
    ur_reg  = _first_existing(_URDU_REGULAR_CANDIDATES)
    ur_bold = _first_existing(_URDU_BOLD_CANDIDATES)
    if ur_reg:
        try:
            pdfmetrics.registerFont(TTFont("NotoUrdu", ur_reg))
            _FONT_URDU = "NotoUrdu"
            if ur_bold:
                pdfmetrics.registerFont(TTFont("NotoUrdu-Bold", ur_bold))
                _FONT_URDU_BOLD = "NotoUrdu-Bold"
            else:
                _FONT_URDU_BOLD = "NotoUrdu"   # fall back to regular weight
        except Exception:
            _FONT_URDU      = None
            _FONT_URDU_BOLD = None


_try_register_fonts()
_URDU_FONT_AVAILABLE = _FONT_URDU is not None


# ── Urdu shaping & bidi ────────────────────────────────────────────────────────
#
# CRITICAL: arabic_reshaper + python-bidi must be applied PER LINE / PER SENTENCE,
# not on a whole multi-sentence block. python-bidi's get_display reverses the
# visual run for the entire RTL paragraph it receives. If we hand ReportLab a
# pre-reversed multi-sentence string, ReportLab's word-wrap will then place the
# original first sentence on the LAST visual line and vice versa — sentences
# come out in reverse order on the page.
#
# Fix:
#   • _urdu_line(text)        → reshape + bidi a SINGLE line/sentence.
#   • _urdu(text)             → kept for short labels (single phrase, no wrap).
#   • _split_urdu_sentences() → break a paragraph at Urdu/English sentence
#                               enders (۔ . ! ? \n) so each piece can be flipped
#                               independently and emitted as its own Paragraph.

# Sentence terminators: Urdu full-stop (۔), Latin . ! ?, hard newlines.
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[۔\.\!\?])\s+|\n+')


def _urdu_line(text: str) -> str:
    """Reshape and bidi-flip a SINGLE Urdu line/sentence (no internal wrapping)."""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def _urdu(text: str) -> str:
    """
    Reshape Urdu/Arabic text for ReportLab.

    Safe for short labels (titles, badges, single phrases). For multi-sentence
    body text, use _urdu_paragraphs() instead — it splits sentences first so
    line ordering is preserved when ReportLab wraps the text.
    """
    return _urdu_line(text)


def _split_urdu_sentences(text: str) -> list[str]:
    """Split Urdu/mixed text into sentences for independent bidi processing."""
    if not text:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(str(text)) if p and p.strip()]
    return parts or [str(text).strip()]


# ── Proper RTL line wrapping ───────────────────────────────────────────────
#
# The right way to render long Urdu paragraphs:
#   1. Reshape the logical-order text once (Arabic letter joining).
#   2. Word-wrap in LOGICAL order using actual font metrics so we know exactly
#      which words fit on which visual line.
#   3. Bidi-flip each wrap-line independently. Now the FIRST word of the
#      logical sentence is on the FIRST visual line, etc.
#   4. Emit each wrap-line as its own right-aligned Paragraph (or join with
#      <br/> in a single Paragraph — either works because each line is
#      flipped on its own).
#
# This replaces the previous approach of splitting only on sentence enders,
# which broke when a single sentence was longer than one wrap-line.


def _wrap_urdu_lines(
    text: str,
    font_name: str,
    font_size: float,
    max_width_pts: float,
) -> list[str]:
    """
    Word-wrap an Urdu/mixed string in logical order using real font metrics,
    then bidi-flip each resulting wrap-line independently. Returns the
    wrap-lines in correct top-to-bottom visual order.
    """
    if not text:
        return [""]

    # Reshape once — this performs Arabic letter joining without changing
    # logical order. Word boundaries (spaces) survive intact.
    reshaped = arabic_reshaper.reshape(str(text))

    # Tokenise on whitespace while keeping the words in logical order.
    words = reshaped.split(" ")
    if not words:
        return [""]

    space_w = pdfmetrics.stringWidth(" ", font_name, font_size)

    lines: list[list[str]] = [[]]
    current_w = 0.0

    for w in words:
        if not w:
            continue
        w_width = pdfmetrics.stringWidth(w, font_name, font_size)

        if not lines[-1]:
            # First word on a new line — always accept it (even if it
            # exceeds max_width — that case is unavoidable for a very long
            # token; ReportLab will just overflow visually but the order
            # remains correct).
            lines[-1].append(w)
            current_w = w_width
        else:
            # Need a leading space before this word.
            projected = current_w + space_w + w_width
            if projected <= max_width_pts:
                lines[-1].append(w)
                current_w = projected
            else:
                # Overflow — start a new line.
                lines.append([w])
                current_w = w_width

    # Bidi-flip each line independently — first logical word stays first.
    visual_lines: list[str] = []
    for line_words in lines:
        if not line_words:
            continue
        logical_line = " ".join(line_words)
        visual_lines.append(get_display(logical_line))

    return visual_lines or [""]


# ── Urdu translation tables for meta values ───────────────────────────────────
# When the report language is Urdu, English values like "Medium" or category
# names should be displayed in Urdu so the whole meta line reads naturally.
_RISK_UR = {
    "Low":      "کم",
    "Medium":   "درمیانہ",
    "High":     "زیادہ",
    "Critical": "انتہائی سنگین",
}

_CONFIDENCE_UR = {
    "low":    "کم",
    "medium": "درمیانہ",
    "high":   "زیادہ",
    "Low":    "کم",
    "Medium": "درمیانہ",
    "High":   "زیادہ",
}

_CATEGORY_UR = {
    "Constitutional Law":     "آئینی قانون",
    "Criminal Law":           "فوجداری قانون",
    "Civil Law / Procedure":  "دیوانی قانون / طریقہ کار",
    "Contract Law":           "قانونِ معاہدہ",
    "Family Law":             "خاندانی قانون",
    "Labour Law":             "محنت کا قانون",
    "Property Law":           "جائیداد کا قانون",
    "Inheritance Law":        "وراثت کا قانون",
    "Cybercrime":             "سائبر کرائم",
    "Consumer Rights":        "صارفین کے حقوق",
    "Harassment":             "ہراسانی",
    "General / Other":        "عام / دیگر",
}


def _ur_value(value: str, table: dict) -> str:
    """Map an English value to its Urdu equivalent, falling back to the original."""
    if not value:
        return ""
    return table.get(str(value).strip(), str(value))


def _esc(text: str) -> str:
    """Escape XML special characters so Paragraph() doesn't choke."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ── Style factory ──────────────────────────────────────────────────────────────

def _make_styles(is_urdu: bool) -> dict:
    """
    Build a dict of named ParagraphStyles for this document.
    """

    if is_urdu and _FONT_URDU:
        font = _FONT_URDU
        bold = _FONT_URDU_BOLD or _FONT_URDU
    else:
        font = _FONT_REGULAR
        bold = _FONT_BOLD

    align = TA_RIGHT if is_urdu else TA_LEFT

    return {

        # ─────────────────────────────────────────────────────────────
        # DOCUMENT TITLE
        # ─────────────────────────────────────────────────────────────
        "doc_title": ParagraphStyle(
            "doc_title",
            fontName=bold,
            fontSize=22,
            leading=28,
            textColor=_NAVY,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),

        # ─────────────────────────────────────────────────────────────
        # DOCUMENT SUBTITLE
        # ─────────────────────────────────────────────────────────────
        "doc_subtitle": ParagraphStyle(
            "doc_subtitle",
            fontName=font,
            fontSize=9,
            leading=14,
            textColor=_LIGHT_GREY,
            alignment=TA_CENTER,
            spaceAfter=5 * mm,
        ),

        # ─────────────────────────────────────────────────────────────
        # SECTION HEADINGS
        # ─────────────────────────────────────────────────────────────
        "section_head": ParagraphStyle(
            "section_head",
            fontName=bold,
            fontSize=13,
            leading=18,
            textColor=_NAVY,
            spaceBefore=7 * mm,
            spaceAfter=3 * mm,
            alignment=align,
        ),

        # ─────────────────────────────────────────────────────────────
        # BODY TEXT
        # ─────────────────────────────────────────────────────────────
        "body": ParagraphStyle(
            "body",
            fontName=font,
            fontSize=10,
            leading=16,
            textColor=_GREY_TEXT,
            alignment=align,
            spaceAfter=3 * mm,
            wordWrap="RTL" if is_urdu else "LTR",
        ),

        # ─────────────────────────────────────────────────────────────
        # BULLET TEXT
        # ─────────────────────────────────────────────────────────────
        "bullet": ParagraphStyle(
            "bullet",
            fontName=font,
            fontSize=10,
            leading=16,
            textColor=_GREY_TEXT,
            leftIndent=6 * mm if not is_urdu else 0,
            rightIndent=6 * mm if is_urdu else 0,
            spaceAfter=2 * mm,
            alignment=align,
            wordWrap="RTL" if is_urdu else "LTR",
        ),

        # ─────────────────────────────────────────────────────────────
        # RISK BADGE
        # ─────────────────────────────────────────────────────────────
        "risk_badge": ParagraphStyle(
            "risk_badge",
            fontName=bold,
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
        ),

        # ─────────────────────────────────────────────────────────────
        # FOOTER / DISCLAIMER
        # ─────────────────────────────────────────────────────────────
        "footer": ParagraphStyle(
            "footer",
            fontName=font,
            fontSize=7.5,
            leading=11,
            textColor=_LIGHT_GREY,
            alignment=TA_CENTER,
        ),

        # ─────────────────────────────────────────────────────────────
        # META INFO
        # ─────────────────────────────────────────────────────────────
        "meta": ParagraphStyle(
            "meta",
            fontName=font,
            fontSize=9,
            leading=14,
            textColor=_LIGHT_GREY,
            alignment=align,
            spaceAfter=3 * mm,
            wordWrap="RTL" if is_urdu else "LTR",
        ),
    }

# ── Section builder helpers ────────────────────────────────────────────────────

def _divider() -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=1.5 * mm)

# Usable text width on A4 with 20mm side margins (matches SimpleDocTemplate).
# 595.276 pt page − 2 × (20 mm → 56.6929 pt) ≈ 481.89 pt.
_A4_USABLE_WIDTH_PT = A4[0] - 2 * (20 * mm)

# We pre-wrap conservatively so ReportLab itself never needs to wrap further.
# pdfmetrics.stringWidth and ReportLab's actual rendering can disagree slightly
# for shaped Arabic glyphs (different advance widths post-shaping). A safety
# margin avoids the case where our wrap thinks text fits but ReportLab wraps
# it again — which would put the original first words on the BOTTOM visual
# line because the second-pass wrap operates on already-bidi-flipped text.
_URDU_WRAP_SAFETY_FACTOR = 0.92
_URDU_BODY_WRAP_WIDTH_PT = _A4_USABLE_WIDTH_PT * _URDU_WRAP_SAFETY_FACTOR

# Slightly narrower for indented bullets / table-cell content to be safe.
_BULLET_USABLE_WIDTH_PT = _A4_USABLE_WIDTH_PT - (10 * mm)


def _urdu_body_paragraphs(
    text: str,
    style,
    *,
    available_width_pt: float = _URDU_BODY_WRAP_WIDTH_PT,
) -> list:
    """
    Convert an Urdu body string into a list of Paragraphs, one per VISUAL
    wrap-line, each independently reshaped + bidi-flipped.

    Inter-line spacing is suppressed between wrap-lines of the SAME logical
    paragraph by emitting all but the last line with a zero-spaceAfter clone
    of the style — so the block looks like one paragraph rather than many.

    This guarantees correct word and sentence ORDER on the page even when
    a single sentence is longer than one line.
    """
    if not text:
        return []

    font_name = getattr(style, "fontName", _FONT_REGULAR)
    font_size = getattr(style, "fontSize", 10)

    visual_lines = _wrap_urdu_lines(
        str(text),
        font_name=font_name,
        font_size=font_size,
        max_width_pts=available_width_pt,
    )
    visual_lines = [v for v in visual_lines if v]
    if not visual_lines:
        return []

    # Clone style with no inter-line spacing for all lines except the last.
    tight_style = ParagraphStyle(
        f"{getattr(style, 'name', 'body')}_tight",
        parent=style,
        spaceAfter=0,
        spaceBefore=0,
    )

    paragraphs = []
    for i, line in enumerate(visual_lines):
        s = style if i == len(visual_lines) - 1 else tight_style
        paragraphs.append(Paragraph(line, s))
    return paragraphs


def _section(title: str, items: list[str], style_map: dict, is_urdu: bool) -> list:
    """
    Build a section with proper Urdu RTL rendering support.

    Each Urdu bullet item is split into sentences so multi-sentence bullets
    render in the correct visual order.
    """

    display_title = _urdu_line(title) if is_urdu else _esc(title)

    elems: list = [
        Paragraph(display_title, style_map["section_head"]),
        _divider(),
    ]

    if items:

        bullet_char = "•"

        for item in items:

            text = item.strip()

            if is_urdu:
                # Properly word-wrap the bullet text in LOGICAL order using
                # real font metrics, then bidi-flip each visual wrap-line
                # independently. This preserves correct word order even for
                # very long bullets that span multiple lines.
                bullet_style = style_map["bullet"]
                font_name = getattr(bullet_style, "fontName", _FONT_REGULAR)
                font_size = getattr(bullet_style, "fontSize", 10)

                # The bullet glyph + a space takes some width on the first
                # visual line — reserve it so wrapping accounts for it.
                bullet_prefix = f" {bullet_char}"
                bullet_w = pdfmetrics.stringWidth(
                    bullet_prefix, font_name, font_size
                )

                # Conservative width — see _URDU_WRAP_SAFETY_FACTOR comment.
                first_line_width = _URDU_BODY_WRAP_WIDTH_PT - bullet_w
                visual_lines = _wrap_urdu_lines(
                    text,
                    font_name=font_name,
                    font_size=font_size,
                    max_width_pts=first_line_width,
                )

                # Append the bullet character to the FIRST visual line (which
                # is right-aligned in RTL — so the bullet sits at the right
                # edge as expected). bullet_char is bidi-neutral, so adding
                # it after the already-flipped line places it at the visual
                # right end of that line.
                visual_lines = [v for v in visual_lines if v]
                if visual_lines:
                    visual_lines[0] = f"{visual_lines[0]}{bullet_prefix}"

                # Suppress inter-line spacing inside one bullet so multi-line
                # bullets visually read as a single item, not a stack.
                bullet_tight = ParagraphStyle(
                    f"{getattr(bullet_style, 'name', 'bullet')}_tight",
                    parent=bullet_style,
                    spaceAfter=0,
                    spaceBefore=0,
                )
                for i, vline in enumerate(visual_lines):
                    s = bullet_style if i == len(visual_lines) - 1 else bullet_tight
                    elems.append(Paragraph(vline, s))

            else:

                text = _esc(text)

                elems.append(
                    Paragraph(
                        f"{bullet_char}  {text}",
                        style_map["bullet"]
                    )
                )

    else:

        placeholder = (
            "کوئی معلومات دستیاب نہیں۔"
            if is_urdu else
            "No information available."
        )

        if is_urdu:
            placeholder = _urdu_line(placeholder)

        elems.append(
            Paragraph(
                placeholder,
                style_map["body"]
            )
        )

    return elems

def _risk_table(
    risk_level: str,
    risk_reason: str,
    style_map: dict,
    is_urdu: bool
) -> list:

    risk_color = _RISK_COLORS.get(risk_level, _ORANGE)

    risk_labels = {
        "Low":      ("Low Risk", "کم خطرہ"),
        "Medium":   ("Medium Risk", "درمیانہ خطرہ"),
        "High":     ("High Risk", "زیادہ خطرہ"),
        "Critical": ("Critical Risk", "انتہائی سنگین خطرہ"),
    }

    en_label, ur_label = risk_labels.get(
        risk_level,
        ("Medium Risk", "درمیانہ خطرہ")
    )

    label = ur_label if is_urdu else en_label

    if is_urdu:
        label = _urdu(label)

    badge = Paragraph(
        label,
        style_map["risk_badge"]
    )

    if is_urdu:
        # Sentence-split so multi-sentence reasons render in correct order.
        reason_cells = _urdu_body_paragraphs(risk_reason or "", style_map["body"])
        if not reason_cells:
            reason_cells = [Paragraph("", style_map["body"])]
        reason_text = reason_cells if len(reason_cells) > 1 else reason_cells[0]
    else:
        reason_text = Paragraph(
            _esc(risk_reason or ""),
            style_map["body"]
        )

    tbl = Table(
        [[badge], [reason_text]],
        colWidths=["100%"],
    )

    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), risk_color),
        ("TEXTCOLOR",  (0, 0), (0, 0), colors.white),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#fff8f8")),
        ("BOX", (0, 0), (-1, -1), 1, risk_color),
    ]))

    return [tbl, Spacer(1, 2 * mm)]


# ── Main public function ───────────────────────────────────────────────────────

def generate_case_pdf(result, language: str = "English") -> str:
    """
    Generate a professional case summary PDF and return its file path.

    Args:
        result:   LegalAnalysis object with .summary, .laws, .rights,
                  .next_steps, .risk_level, .risk_reason, .category,
                  .confidence fields.
        language: "English" or "Urdu"

    Returns:
        Absolute path to the temporary PDF file.
        The caller is responsible for streaming it; it will be cleaned up
        on system reboot (lives in /tmp/).
    """
    is_urdu   = language == "Urdu"
    style_map = _make_styles(is_urdu)

    # ── Build output path ──────────────────────────────────────────────────────
    tmp_file = tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False, prefix="legal_aid_"
    )
    tmp_path = tmp_file.name
    tmp_file.close()

    # ── Document setup ─────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        tmp_path,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="Pakistan AI Legal Aid Report",
        author="Pakistan AI Legal Aid Assistant",
    )

    story: list = []

    # ─────────────────────────────────────────────────────────────────────
    # HEADER
    # ─────────────────────────────────────────────────────────────────────

    if is_urdu:
        doc_title_text = _urdu_line("پاکستان اے آئی قانونی امداد رپورٹ")
    else:
        doc_title_text = "Pakistan AI Legal Aid Report"

    story.append(
        Paragraph(
            doc_title_text,
            style_map["doc_title"]
        )
    )

    date_str = datetime.now().strftime('%d %B %Y, %H:%M')
    if is_urdu:
        subtitle_text = _urdu_line(f"تاریخ: {date_str}")
    else:
        subtitle_text = f"Generated: {date_str}"

    story.append(
        Paragraph(
            subtitle_text,
            style_map["doc_subtitle"]
        )
    )

    story.append(Spacer(1, 2 * mm))

    story.append(
        HRFlowable(
            width="100%",
            thickness=1.2,
            color=_GOLD,
            spaceBefore=1 * mm,
            spaceAfter=6 * mm
        )
    )

    # ─────────────────────────────────────────────────────────────────────
    # META INFORMATION
    # ─────────────────────────────────────────────────────────────────────

    category = getattr(result, "category", "General / Other")
    confidence = getattr(result, "confidence", "")

    if is_urdu:
        # ── Urdu meta line ────────────────────────────────────────────────
        # Render as a 2-cell Table, each cell containing a SINGLE
        # `<b>label:</b> value` pair that is reshaped + bidi-flipped together
        # as one logical RTL segment. This prevents the previous bug where
        # the values ("Medium", "General / Other") visually appeared BEFORE
        # their Urdu labels because labels and values were flipped separately
        # and concatenated in LTR order.
        #
        # Values are also translated to Urdu so the line reads naturally.
        cat_val_ur  = _ur_value(category, _CATEGORY_UR)
        conf_val_ur = _ur_value(confidence, _CONFIDENCE_UR)

        # Reshape each "label value" pair as a single unit. The label is on
        # the right (logical-first) and the value on the left visually — the
        # natural Urdu reading order.
        cat_pair  = _urdu_line(f"زمرہ: {cat_val_ur}")
        conf_pair = _urdu_line(f"اعتماد: {conf_val_ur}")

        meta_table = Table(
            [[Paragraph(conf_pair, style_map["meta"]),
              Paragraph(cat_pair,  style_map["meta"])]],
            colWidths=["50%", "50%"],
        )
        meta_table.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",        (0, 0), (0, 0),  "RIGHT"),   # right cell-content right-aligned
            ("ALIGN",        (1, 0), (1, 0),  "RIGHT"),   # left cell-content right-aligned
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))
        story.append(meta_table)
    else:
        meta_line = (
            f"<b>Category:</b> {_esc(category)}"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b>Confidence:</b> {_esc(confidence)}"
        )
        story.append(
            Paragraph(
                meta_line,
                style_map["meta"]
            )
        )

    story.append(Spacer(1, 2 * mm))

    # ─────────────────────────────────────────────────────────────────────
    # CASE SUMMARY
    # ─────────────────────────────────────────────────────────────────────

    summary_title = _urdu_line("خلاصہ") if is_urdu else "CASE SUMMARY"

    story.append(
        Paragraph(
            summary_title,
            style_map["section_head"]
        )
    )

    story.append(_divider())

    summary_text = getattr(result, "summary", "") or ""

    if is_urdu:
        # Split the summary into sentences so each is bidi-flipped
        # independently — fixes "sentences appear in reverse order" bug.
        story.extend(_urdu_body_paragraphs(summary_text, style_map["body"]))
    else:
        story.append(
            Paragraph(
                _esc(summary_text),
                style_map["body"]
            )
        )

    story.append(Spacer(1, 2 * mm))

    # ─────────────────────────────────────────────────────────────────────
    # RISK LEVEL
    # ─────────────────────────────────────────────────────────────────────

    risk_title = _urdu("خطرے کی سطح") if is_urdu else "RISK LEVEL"

    risk_level = getattr(result, "risk_level", "Medium")
    risk_reason = getattr(result, "risk_reason", "")

    story.append(
        Paragraph(
            risk_title,
            style_map["section_head"]
        )
    )

    story.append(_divider())

    story.extend(
        _risk_table(
            risk_level,
            risk_reason,
            style_map,
            is_urdu
        )
    )

    story.append(Spacer(1, 2 * mm))

    # ─────────────────────────────────────────────────────────────────────
    # RELEVANT LAWS
    # ─────────────────────────────────────────────────────────────────────

    laws_title = "متعلقہ قوانین" if is_urdu else "RELEVANT LAWS"

    laws = getattr(result, "laws", []) or []

    story.extend(
        _section(
            laws_title,
            laws,
            style_map,
            is_urdu
        )
    )

    story.append(Spacer(1, 2 * mm))

    # ─────────────────────────────────────────────────────────────────────
    # YOUR RIGHTS
    # ─────────────────────────────────────────────────────────────────────

    rights_title = "آپ کے حقوق" if is_urdu else "YOUR RIGHTS"

    rights = getattr(result, "rights", []) or []

    story.extend(
        _section(
            rights_title,
            rights,
            style_map,
            is_urdu
        )
    )

    story.append(Spacer(1, 2 * mm))

    # ─────────────────────────────────────────────────────────────────────
    # RECOMMENDED NEXT STEPS
    # ─────────────────────────────────────────────────────────────────────

    steps_title = (
        "تجویز کردہ اقدامات"
        if is_urdu else
        "RECOMMENDED NEXT STEPS"
    )

    next_steps = getattr(result, "next_steps", []) or []

    story.extend(
        _section(
            steps_title,
            next_steps,
            style_map,
            is_urdu
        )
    )

    story.append(Spacer(1, 5 * mm))

    # ─────────────────────────────────────────────────────────────────────
    # DISCLAIMER
    # ─────────────────────────────────────────────────────────────────────

    story.append(
        HRFlowable(
            width="100%",
            thickness=0.6,
            color=_BORDER,
            spaceAfter=3 * mm
        )
    )

    disclaimer = (
        "یہ ٹول صرف قانونی معلومات فراہم کرتا ہے اور کسی لائسنس یافتہ وکیل کا متبادل نہیں ہے۔"
        if is_urdu else
        "This tool provides legal information only and does not replace a licensed lawyer. "
        "Always consult a qualified legal professional for advice specific to your situation."
    )

    if is_urdu:
        # Disclaimer can be multi-sentence — emit one Paragraph per sentence.
        story.extend(_urdu_body_paragraphs(disclaimer, style_map["footer"]))
    else:
        story.append(
            Paragraph(
                _esc(disclaimer),
                style_map["footer"]
            )
        )

    # ── Build ──────────────────────────────────────────────────────────────────
    doc.build(story)
    return tmp_path