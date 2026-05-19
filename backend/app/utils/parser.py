"""
parser.py — PDF text extraction with quality-aware cleaning.

Handles two PDF types found in the dataset:
  1. GOOD PDFs  — clean digitally-born text (most files)
  2. SPACED PDFs — character-spaced OCR output (PPC, Constitution)

Output: raw text per page, ready for the chunker.
"""
from __future__ import annotations
import os
import re
import logging
from dataclasses import dataclass, field
from pypdf import PdfReader

logger = logging.getLogger(__name__)


@dataclass
class ParsedPage:
    page_num:  int
    text:      str
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)


@dataclass
class ParsedDocument:
    file_path:  str
    law_name:   str
    category:   str
    pages:      list[ParsedPage] = field(default_factory=list)
    total_chars: int = 0
    is_spaced:  bool = False

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())


# ── Text cleaning ──────────────────────────────────────────────────────────────

def _is_spaced_text(sample: str) -> bool:
    """Detect character-spaced OCR: 'S e c t i o n' pattern."""
    spaced = len(re.findall(r'[A-Za-z] [A-Za-z] [A-Za-z]', sample))
    total_words = len(sample.split())
    return spaced > 10 and total_words > 0 and (spaced / max(total_words, 1)) > 0.05


def _fix_spaced_text(text: str) -> str:
    """Collapse character-spaced OCR back into normal words."""
    text = text.replace('\xa0', ' ')
    # Run multiple passes of: merge single chars separated by spaces
    for _ in range(10):
        prev = text
        # "S e c t i o n" → "Section" (consecutive single-char tokens)
        text = re.sub(r'(?<![A-Za-z])([A-Za-z]) (?=[A-Za-z] [A-Za-z])', r'\1', text)
        text = re.sub(r'(?<![A-Za-z])([A-Za-z]) (?=[A-Za-z](?:\s|[^A-Za-z]|$))', r'\1', text)
        if text == prev:
            break
    text = re.sub(r'  +', ' ', text)
    return text


def _clean_text(text: str, is_spaced: bool = False) -> str:
    """Common text cleanup after extraction."""
    if is_spaced:
        text = _fix_spaced_text(text)
    # Remove page header artifacts like "Page 5 of 307"
    text = re.sub(r'\nPage \d+ of \d+\s*\n', '\n', text)
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Remove excessive blank lines (keep max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove non-printable chars except newlines/tabs
    text = re.sub(r'[^\x09\x0A\x20-\x7E\u0600-\u06FF\u0080-\uFFFF]', '', text)
    return text.strip()


# ── Main extraction ────────────────────────────────────────────────────────────

def extract_pdf(
    file_path: str,
    law_name: str,
    category: str,
) -> ParsedDocument | None:
    """
    Extract all text from a PDF file.
    Returns ParsedDocument or None on failure.
    """
    try:
        reader = PdfReader(file_path)
        total_pages = len(reader.pages)

        # Sample pages to detect spacing issue
        sample_pages = [reader.pages[i].extract_text() or ""
                        for i in range(min(5, total_pages))]
        sample = " ".join(sample_pages)
        is_spaced = _is_spaced_text(sample)

        if is_spaced:
            logger.info(f"  [SPACED] {os.path.basename(file_path)} — applying de-spacing")

        pages = []
        for i, page in enumerate(reader.pages):
            raw = page.extract_text() or ""
            if not raw.strip():
                continue
            cleaned = _clean_text(raw, is_spaced=is_spaced)
            if len(cleaned) > 50:  # skip near-empty pages
                pages.append(ParsedPage(page_num=i + 1, text=cleaned))

        doc = ParsedDocument(
            file_path=file_path,
            law_name=law_name,
            category=category,
            pages=pages,
            is_spaced=is_spaced,
        )
        doc.total_chars = sum(p.char_count for p in pages)
        logger.info(
            f"  Parsed: {os.path.basename(file_path)} "
            f"({total_pages}pp → {len(pages)} usable, {doc.total_chars:,} chars)"
        )
        return doc

    except Exception as e:
        logger.error(f"  Failed to parse {file_path}: {e}")
        return None
