"""
text_extractor.py — Text extraction from PDF, DOCX, and image files.

Extraction pipeline per type:
  PDF   → pypdf (primary) → pdfplumber fallback for sparse/complex pages
  DOCX  → python-docx (paragraph-level; Urdu RTL preserved as Unicode)
  Image → image_preprocessor (OpenCV) → pytesseract (eng+urd)

Structured output per extraction:
  extracted_text         — cleaned plain UTF-8 text
  detected_language      — "English" | "Urdu" | "Mixed" | "Unknown"
  extraction_confidence  — 0.0 – 1.0 heuristic quality score
  method                 — which extractor was used
  warning                — non-fatal advisory string (scanned PDF, missing tessdata…)

Isolation guarantee: no Groq, no RAG, no DB access in this module.
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Tesseract language string for primary OCR attempt (English + Urdu)
_TESS_LANGS = "eng+urd"

# pypdf pages yielding fewer chars than this per page trigger a pdfplumber retry
_SPARSE_CPP_THRESHOLD = 80   # chars per page

# pdfplumber result still sparse → declare document as scanned
_SCANNED_CPP_THRESHOLD = 30

# Hard cap on returned text to prevent OOM and LLM token blowout
_TEXT_CAP_CHARS = 100_000


# ═══════════════════════════════════════════════════════════════════════════════
# Result dataclass
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExtractionResult:
    """
    Unified result from any extraction path.

    method values:
        "pdf_text"        — pypdf direct text extraction
        "pdf_pdfplumber"  — pdfplumber fallback (pypdf was too sparse)
        "docx_text"       — python-docx paragraph extraction
        "ocr"             — pytesseract (may be eng+urd or eng-only)
        "ocr_unavailable" — Tesseract binary / pytesseract not installed

    detected_language values:
        "English" | "Urdu" | "Mixed" | "Unknown"
    """
    text:                   str
    method:                 str
    pages:                  int   = 0
    char_count:             int   = 0
    word_count:             int   = 0
    warning:                str   = ""
    detected_language:      str   = "Unknown"
    extraction_confidence:  float = 0.0
    preprocessing_steps:    list  = field(default_factory=list)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)
        self.word_count = len(self.text.split()) if self.text else 0
        # Populate language and confidence if not already set by the extractor
        if self.detected_language == "Unknown" and self.text:
            self.detected_language = _detect_language(self.text)
        if self.extraction_confidence == 0.0 and self.method != "ocr_unavailable":
            self.extraction_confidence = _estimate_confidence(
                self.text, self.method, self.pages
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Shared text utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _clean(text: str, fix_spaced: bool = False) -> str:
    """
    Normalise whitespace, strip control characters, and optionally fix
    character-spaced OCR artefacts (e.g. 'S e c t i o n' → 'Section').

    Preserves:
      - Printable ASCII (U+0020–U+007E)
      - Horizontal tab (U+0009) and newline (U+000A)
      - Arabic / Urdu block (U+0600–U+06FF)
      - Extended Latin and all other Unicode planes (U+0080–U+FFFF)
    """
    # NFC normalization: decomposed Arabic/Urdu characters (hamza, diacritics)
    # become their canonical composed forms, preventing rendering duplicates.
    try:
        text = unicodedata.normalize('NFC', text)
    except Exception:
        pass

    # Strip null bytes — rare in documents but can appear in corrupt PDFs.
    text = text.replace('\x00', '')

    if fix_spaced:
        text = _fix_spaced_text(text)

    # Remove page header artefacts common in legal PDFs
    text = re.sub(r"\nPage \d+ of \d+\s*\n", "\n", text)

    # Strip disallowed control characters while keeping Unicode
    text = re.sub(r"[^\x09\x0A\x20-\x7E؀-ۿ-￿]", "", text)

    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse runs of 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ── Spaced-text detection and repair (ported from parser.py) ──────────────────

def _is_spaced_text(sample: str) -> bool:
    """
    Detect character-spaced OCR output: 'S e c t i o n' pattern.
    Used to identify PDFs that were already OCR-processed with spacing artefacts.
    """
    spaced      = len(re.findall(r"[A-Za-z] [A-Za-z] [A-Za-z]", sample))
    total_words = len(sample.split())
    return spaced > 10 and total_words > 0 and (spaced / max(total_words, 1)) > 0.05


def _fix_spaced_text(text: str) -> str:
    """
    Collapse character-spaced OCR artefacts back into normal words.
    Runs up to 10 passes; stops early when the text stabilises.
    E.g. 'S e c t i o n   5' → 'Section 5'
    """
    text = text.replace("\xa0", " ")
    for _ in range(10):
        prev = text
        text = re.sub(
            r"(?<![A-Za-z])([A-Za-z]) (?=[A-Za-z] [A-Za-z])", r"\1", text
        )
        text = re.sub(
            r"(?<![A-Za-z])([A-Za-z]) (?=[A-Za-z](?:\s|[^A-Za-z]|$))", r"\1", text
        )
        if text == prev:
            break
    return re.sub(r"  +", " ", text)


# ── Language detection ────────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    """
    Heuristic language detection based on Unicode block ratios.

    Counts Arabic/Urdu block characters (U+0600–U+06FF) against ASCII
    alphabetic characters to classify the document language.

    Returns: "Urdu" | "English" | "Mixed" | "Unknown"
    """
    if not text:
        return "Unknown"

    urdu_chars  = len(re.findall(r"[؀-ۿ]", text))
    ascii_chars = len(re.findall(r"[A-Za-z]", text))
    total       = urdu_chars + ascii_chars

    if total == 0:
        return "Unknown"

    urdu_ratio = urdu_chars / total

    if urdu_ratio >= 0.65:
        return "Urdu"
    if urdu_ratio <= 0.10:
        return "English"
    return "Mixed"


# ── Confidence estimation ─────────────────────────────────────────────────────

def _estimate_confidence(text: str, method: str, pages: int) -> float:
    """
    Heuristic extraction quality score (0.0 – 1.0).

    PDF / pdfplumber: scored on average chars-per-page (density).
    DOCX:             scored on paragraph count.
    OCR:              scored on ratio of dictionary-like words.
    ocr_unavailable:  always 0.0.
    """
    if not text or method == "ocr_unavailable":
        return 0.0

    char_count  = len(text)
    words       = text.split()
    total_words = len(words)

    if method == "docx_text":
        if total_words < 5:
            return 0.60
        return min(0.95, 0.85 + min(total_words, 500) / 10_000)

    if method in ("pdf_text", "pdf_pdfplumber"):
        cpp = char_count / max(pages, 1)   # chars per page
        if cpp >= 800:
            return 0.90
        if cpp >= 400:
            return 0.80
        if cpp >= _SPARSE_CPP_THRESHOLD:
            return 0.65
        if cpp >= _SCANNED_CPP_THRESHOLD:
            return 0.40
        return 0.15   # almost certainly scanned

    if method == "ocr":
        # Ratio of plausible words (length ≥ 3, all alpha / Urdu)
        def _is_plausible(w: str) -> bool:
            return len(w) >= 3 and all(
                c.isalpha() or "؀" <= c <= "ۿ" for c in w
            )
        valid      = sum(1 for w in words if _is_plausible(w))
        word_ratio = valid / max(total_words, 1)
        return min(0.85, 0.25 + word_ratio * 0.60)

    return 0.50


# ═══════════════════════════════════════════════════════════════════════════════
# PDF extraction
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_pdf_pypdf(path: str) -> tuple[str, int, bool]:
    """
    Primary PDF extraction using pypdf.
    Returns (full_text, num_pages, was_spaced).
    Raises RuntimeError on hard failure.
    """
    from pypdf import PdfReader

    reader     = PdfReader(path)
    num_pages  = len(reader.pages)

    # Sample up to 5 pages to detect character-spaced artefacts
    sample = " ".join(
        reader.pages[i].extract_text() or ""
        for i in range(min(5, num_pages))
    )
    is_spaced = _is_spaced_text(sample)
    if is_spaced:
        logger.info("PDF character-spacing artefact detected — applying fix")

    page_texts: list[str] = []
    for page in reader.pages:
        raw     = page.extract_text() or ""
        cleaned = _clean(raw, fix_spaced=is_spaced)
        if len(cleaned) > 50:
            page_texts.append(cleaned)

    return "\n\n".join(page_texts), num_pages, is_spaced


def _extract_pdf_pdfplumber(path: str) -> str:
    """
    Fallback PDF extraction using pdfplumber (pdfminer.six under the hood).
    Better at non-standard encodings and complex layouts.
    Already in requirements.txt.
    """
    import pdfplumber  # type: ignore

    page_texts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            raw = page.extract_text() or ""
            cleaned = _clean(raw)
            if cleaned:
                page_texts.append(cleaned)
    return "\n\n".join(page_texts)


def extract_pdf(path: str) -> ExtractionResult:
    """
    Extract text from a PDF file.

    Strategy:
      1. pypdf (fast, consistent with existing parser.py).
      2. pdfplumber fallback when pypdf yields < _SPARSE_CPP_THRESHOLD chars/page.
      3. If still sparse after pdfplumber: warn that document appears scanned.

    Raises RuntimeError on unrecoverable failure.
    """
    try:
        pypdf_text, num_pages, was_spaced = _extract_pdf_pypdf(path)
    except Exception as exc:
        logger.error("pypdf failed for %s: %s", path, exc)
        raise RuntimeError(f"Could not read PDF: {exc}") from exc

    cpp = len(pypdf_text) / max(num_pages, 1)
    method  = "pdf_text"
    text    = pypdf_text
    warning = ""

    # ── pdfplumber fallback ───────────────────────────────────────────────────
    if cpp < _SPARSE_CPP_THRESHOLD:
        logger.info(
            "pypdf sparse (%d cpp) — retrying with pdfplumber: %s",
            int(cpp), os.path.basename(path),
        )
        try:
            plumber_text = _extract_pdf_pdfplumber(path)
            plumber_cpp  = len(plumber_text) / max(num_pages, 1)
            # Accept pdfplumber result if it meaningfully improves things
            if plumber_cpp > cpp:
                text   = plumber_text
                method = "pdf_pdfplumber"
                cpp    = plumber_cpp
        except Exception as plumber_exc:
            logger.warning("pdfplumber also failed: %s", plumber_exc)

    # ── Scanned PDF detection ─────────────────────────────────────────────────
    if cpp < _SCANNED_CPP_THRESHOLD:
        warning = (
            "This PDF appears to be scanned (image-based) and contains very little "
            "extractable text. For best results, upload individual pages as PNG or "
            "JPG images to enable full OCR processing."
        )
        logger.warning("Likely scanned PDF: %s (%d cpp)", os.path.basename(path), int(cpp))

    language   = _detect_language(text)
    confidence = _estimate_confidence(text, method, num_pages)

    logger.info(
        "PDF extracted: method=%s  pages=%d  chars=%d  lang=%s  conf=%.2f",
        method, num_pages, len(text), language, confidence,
    )
    return ExtractionResult(
        text=text,
        method=method,
        pages=num_pages,
        warning=warning,
        detected_language=language,
        extraction_confidence=confidence,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DOCX extraction
# ═══════════════════════════════════════════════════════════════════════════════

def extract_docx(path: str) -> ExtractionResult:
    """
    Extract text from a DOCX file using python-docx.
    Iterates paragraphs; Urdu RTL text is stored as plain Unicode in DOCX XML
    and round-trips correctly without arabic-reshaper or bidi processing.
    Raises RuntimeError on parse failure.
    """
    from docx import Document  # python-docx, already in requirements.txt

    try:
        doc        = Document(path)
        paragraphs = [_clean(p.text) for p in doc.paragraphs if p.text.strip()]
        full_text  = "\n".join(paragraphs)
    except Exception as exc:
        logger.error("DOCX extraction failed for %s: %s", path, exc)
        raise RuntimeError(f"Could not read DOCX: {exc}") from exc

    language   = _detect_language(full_text)
    confidence = _estimate_confidence(full_text, "docx_text", 0)

    logger.info(
        "DOCX extracted: paragraphs=%d  chars=%d  lang=%s  conf=%.2f",
        len(paragraphs), len(full_text), language, confidence,
    )
    return ExtractionResult(
        text=full_text,
        method="docx_text",
        pages=0,
        detected_language=language,
        extraction_confidence=confidence,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Image / OCR extraction
# ═══════════════════════════════════════════════════════════════════════════════

def extract_image(path: str) -> ExtractionResult:
    """
    Extract text from an image using OpenCV preprocessing + pytesseract.

    Steps:
      1. Preprocess with image_preprocessor (grayscale, deskew, denoise, binarize).
      2. Run Tesseract with eng+urd; fall back to eng-only if urd tessdata absent.
      3. Detect language and estimate confidence from the output.

    Returns method="ocr_unavailable" (not an error) when Tesseract is not installed.
    Raises RuntimeError on image open failure or unexpected OCR errors.
    """
    from utils.image_preprocessor import preprocess_image

    # ── Check OCR dependencies ────────────────────────────────────────────────
    try:
        from PIL import Image as _PILImage    # type: ignore
        import pytesseract                    # type: ignore
    except ImportError as exc:
        logger.warning("pytesseract/Pillow not importable — OCR unavailable: %s", exc)
        return ExtractionResult(
            text="",
            method="ocr_unavailable",
            warning=(
                "OCR libraries are not installed. "
                "Run: pip install pytesseract Pillow  "
                "then install the Tesseract binary: "
                "https://github.com/UB-Mannheim/tesseract/wiki"
            ),
            detected_language="Unknown",
            extraction_confidence=0.0,
        )

    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract binary not found in PATH")
        return ExtractionResult(
            text="",
            method="ocr_unavailable",
            warning=(
                "Tesseract OCR binary is not installed or not on PATH. "
                "Download from https://github.com/UB-Mannheim/tesseract/wiki "
                "and add to your system PATH."
            ),
            detected_language="Unknown",
            extraction_confidence=0.0,
        )

    # ── Preprocess image ──────────────────────────────────────────────────────
    preprocessed_path, prep_steps = preprocess_image(path)
    new_temp = preprocessed_path != path   # True → we must delete it after OCR

    try:
        img = _PILImage.open(preprocessed_path)

        # ── OCR: try eng+urd, fall back to eng ───────────────────────────────
        lang_used = _TESS_LANGS
        warning   = ""
        try:
            raw = pytesseract.image_to_string(img, lang=_TESS_LANGS)
        except (pytesseract.TesseractError, OSError, MemoryError) as _ocr_err:
            logger.warning(
                "Primary OCR failed (%s) — falling back to English-only OCR: %s",
                type(_ocr_err).__name__, _ocr_err,
            )
            raw       = pytesseract.image_to_string(img, lang="eng")
            lang_used = "eng"
            warning   = (
                "Urdu tessdata was not found or OCR encountered an error; "
                "analysis ran in English-only mode. "
                "Urdu text may not be recognised correctly. "
                "Install urd.traineddata for Tesseract."
            )

        text       = _clean(raw)
        language   = _detect_language(text)
        confidence = _estimate_confidence(text, "ocr", 1)

        logger.info(
            "OCR complete: lang_used=%s  preprocessing=%s  chars=%d  "
            "detected_lang=%s  conf=%.2f",
            lang_used, prep_steps, len(text), language, confidence,
        )
        return ExtractionResult(
            text=text,
            method="ocr",
            pages=1,
            warning=warning,
            detected_language=language,
            extraction_confidence=confidence,
            preprocessing_steps=prep_steps,
        )

    except Exception as exc:
        logger.error("OCR failed for %s: %s", path, exc)
        raise RuntimeError(f"Image OCR failed: {exc}") from exc

    finally:
        # Clean up the preprocessed temp file (not the caller's original)
        if new_temp:
            try:
                os.unlink(preprocessed_path)
            except OSError as rm_err:
                logger.warning("Could not delete preprocessed temp: %s", rm_err)


# ═══════════════════════════════════════════════════════════════════════════════
# Public dispatch
# ═══════════════════════════════════════════════════════════════════════════════

def extract_text(tmp_path: str, file_type: str) -> ExtractionResult:
    """
    Route extraction to the correct handler.

    Args:
        tmp_path:  Absolute path to the validated temp file.
        file_type: "pdf" | "docx" | "image"

    Raises:
        ValueError   — unknown file_type
        RuntimeError — extraction failure (caller should map to HTTP 422)
    """
    if file_type == "pdf":
        result = extract_pdf(tmp_path)
    elif file_type == "docx":
        result = extract_docx(tmp_path)
    elif file_type == "image":
        result = extract_image(tmp_path)
    else:
        raise ValueError(f"Unknown file_type: {file_type!r}")

    # Hard cap: very large documents (scanned books, bulk PDFs) can exceed
    # LLM token budgets and cause OOM in downstream processing.
    if len(result.text) > _TEXT_CAP_CHARS:
        logger.warning(
            "Extracted text capped from %d to %d chars: %s",
            len(result.text), _TEXT_CAP_CHARS, os.path.basename(tmp_path),
        )
        result.text       = result.text[:_TEXT_CAP_CHARS]
        result.char_count = len(result.text)
        result.word_count = len(result.text.split())

    return result
