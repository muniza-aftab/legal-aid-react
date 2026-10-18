"""
ingest.py — Scans data/laws/, extracts text from every PDF,
splits into legal chunks, attaches metadata, returns list of chunk dicts.

Chunk schema:
  {
    "id":         str,          # unique: "law_slug_chunk_001"
    "law_name":   str,
    "category":   str,
    "section":    str,          # detected section heading or ""
    "text":       str,          # chunk content
    "source":     str,          # basename of source PDF
    "page_start": int
  }
"""
from __future__ import annotations
import os
import re
import json
import hashlib
import logging
from pathlib import Path

from app.utils.config import (
    LAWS_DIR, CHUNKS_FILE,
    FOLDER_CATEGORY_MAP, FILENAME_CATEGORY_MAP,
    CHUNK_SIZE, CHUNK_OVERLAP,
)
from app.utils.parser import extract_pdf, ParsedDocument

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────────

# Boundary patterns: lines that START a new legal section
# Order matters: most specific first.
_BOUNDARY_PATTERNS = [
    # "Article 25." or "Article 25A." at line start
    re.compile(r'^\s*(Article\s+\d+[A-Z]?)\s*[\.\-—]', re.MULTILINE | re.IGNORECASE),
    # "Section 54." or "Section 54A."
    re.compile(r'^\s*(Section\s+\d+[A-Z]?)\s*[\.\-—]', re.MULTILINE | re.IGNORECASE),
    # "CHAPTER III" or "CHAPTER 3"
    re.compile(r'^\s*(CHAPTER\s+(?:[IVXLCDM]+|\d+))\s*[\.\-—\s]', re.MULTILINE | re.IGNORECASE),
    # "Part IV" or "PART 4"
    re.compile(r'^\s*(PART\s+(?:[IVXLCDM]+|\d+))\s*[\.\-—\s]', re.MULTILINE | re.IGNORECASE),
    # "54." or "54A." — bare numbered section at line start (most common in Pakistani laws)
    re.compile(r'^\s*(\d{1,3}[A-Z]?)\.\s+[A-Z][a-z]', re.MULTILINE),
]

# Heading extraction: pull number + first line of title only
_HEADING_EXTRACT = re.compile(
    r'^\s*(?:Section\s+|Article\s+)?(\d+[A-Z]?|[IVXLCDM]+)\s*[\.\-—]\s*([^\n]{0,70})',
    re.MULTILINE | re.IGNORECASE,
)
_CHAPTER_EXTRACT = re.compile(
    r'^\s*((?:CHAPTER|PART|SCHEDULE)\s+\S+)\s*[\.\-—\n]\s*([^\n]{0,60})?',
    re.MULTILINE | re.IGNORECASE,
)


def _extract_section_label(text_block: str) -> str:
    """
    Extract a clean section label from the START of a text block.
    Returns e.g. 'Section 54 — Powers of the Court' or 'Chapter III — Powers of Courts'.
    Strips trailing section numbers, newlines, and overflow.
    Applies de-spacing for spaced OCR text.
    """
    # Try chapter/part first (structural headings)
    m = _CHAPTER_EXTRACT.search(text_block[:300])
    if m:
        num   = m.group(1).strip()
        title = (m.group(2) or "").strip()
        title = _clean_label(title)[:55]
        return f"{num} — {title}".rstrip(" —") if title else num

    # Try numbered section
    m = _HEADING_EXTRACT.search(text_block[:300])
    if m:
        num   = m.group(1).strip()
        title = m.group(2).strip()
        title = _clean_label(title)[:60]
        return f"Section {num} — {title}".rstrip(" —") if title else f"Section {num}"

    return ""


def _clean_label(label: str) -> str:
    """
    Clean a section label: fix fully-spaced OCR chars, remove trailing refs, normalize whitespace.
    Conservative: only fixes "X Y Z" single-char-spaced patterns, not partial words.
    """
    # Fix fully spaced chars only: "T i t l e" → "Title"
    # Matches runs of: single-letter SPACE single-letter (at least 3 in a row)
    for _ in range(10):
        prev = label
        label = re.sub(r'\b([A-Za-z]) ([A-Za-z]) ([A-Za-z])\b', r'\1\2\3', label)
        label = re.sub(r'(?<![A-Za-z])([A-Za-z]) (?=[A-Za-z] )', r'\1', label)
        if label == prev:
            break

    # Remove soft hyphens and non-breaking spaces
    label = label.replace('\xad', '-').replace('\xa0', ' ')

    # Remove trailing bare section numbers like "55" or "56A"
    label = re.sub(r'\s+\d+[A-Z]?\s*$', '', label)

    # Normalize whitespace
    label = re.sub(r'\s+', ' ', label).strip()

    # Truncate at structural break characters
    for sep in [' — ', ' – ', '.[', '  ']:
        if sep in label:
            label = label.split(sep)[0].strip()

    # Remove trailing punctuation
    label = label.rstrip('.,;:- ')

    # Quality gate: detect partial-word spaced OCR like "Titl e an d exten t"
    # Heuristic: high ratio of short (1-4 char) tokens suggests broken OCR
    words = label.split()
    if len(words) >= 4:
        short_words = sum(1 for w in words if 1 <= len(re.sub(r'[^A-Za-z]','',w)) <= 3)
        if short_words / len(words) > 0.5:
            return ""  # caller will use law name as fallback

    return label


def _find_section_boundaries(text: str) -> list[int]:
    """
    Find character positions where new sections begin.
    Returns sorted list of start positions (always includes 0).
    """
    positions = {0}
    for pat in _BOUNDARY_PATTERNS:
        for m in pat.finditer(text):
            positions.add(m.start())
    return sorted(positions)


def _infer_law_name(filename: str) -> str:
    """Clean filename → readable law name."""
    name = Path(filename).stem
    # Remove trailing date / revision markers
    name = re.sub(r',?\s*\d{4}\s*(\(Under Review\))?$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'#U2019', "'", name)
    name = name.strip(" .-_")
    return name.title()


def _infer_category(filename: str, folder: str) -> str:
    """Map filename + folder to canonical legal category."""
    upper = filename.upper()
    for keyword, cat in FILENAME_CATEGORY_MAP.items():
        if keyword in upper:
            return cat
    return FOLDER_CATEGORY_MAP.get(folder, "General / Other")


def _make_id(law_name: str, idx: int) -> str:
    slug = re.sub(r'[^a-z0-9]+', '_', law_name.lower())[:30]
    return f"{slug}_chunk_{idx:04d}"


# ── Chunker ────────────────────────────────────────────────────────────────────

def _chunk_document(doc: ParsedDocument) -> list[dict]:
    """
    Split a ParsedDocument into legal chunks, one section per chunk.

    Strategy:
      1. Find all section boundaries in the full text using _find_section_boundaries().
      2. Slice text at each boundary → one raw section block.
      3. If a block is ≤ CHUNK_SIZE: emit as single chunk.
      4. If a block is > CHUNK_SIZE: split at sentence boundaries with CHUNK_OVERLAP carry.
      5. Skip blocks that are too short (boilerplate, page headers).
      6. Label each chunk with a clean section heading extracted from its own text.
    """
    chunks: list[dict] = []
    full_text = doc.full_text
    if not full_text.strip():
        return chunks

    boundaries = _find_section_boundaries(full_text)

    # Build raw section slices
    raw_sections: list[str] = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(full_text)
        block = full_text[start:end].strip()
        if block:
            raw_sections.append(block)

    # Fallback: if no boundaries found (e.g. free-form text), use paragraphs
    if len(raw_sections) <= 1:
        raw_sections = [p.strip() for p in re.split(r'\n{3,}', full_text) if p.strip()]

    idx = 0

    def emit(text: str, section_label: str) -> None:
        nonlocal idx
        text = text.strip()
        # Skip: too short, or pure boilerplate (page refs, amendment notes)
        if len(text) < 120:
            return
        boilerplate_ratio = len(re.findall(
            r'(?:Subs?\.|Omitted|Repealed|Amended|ibid|Punjab|Balochistan)\s',
            text[:200]
        )) / max(len(text.split()[:30]), 1)
        if boilerplate_ratio > 0.4:
            return

        chunks.append({
            "id":         _make_id(doc.law_name, idx),
            "law_name":   doc.law_name,
            "category":   doc.category,
            "section":    section_label,
            "text":       text,
            "source":     os.path.basename(doc.file_path),
            "page_start": 1,
        })
        idx += 1

    for block in raw_sections:
        # Extract a clean label from this block's own content
        section_label = _extract_section_label(block)

        if len(block) <= CHUNK_SIZE:
            emit(block, section_label)
        else:
            # Hard-split large sections at sentence boundaries with overlap
            remaining = block
            first = True
            while len(remaining) > CHUNK_SIZE:
                # Find best split point: last ". " before CHUNK_SIZE
                split_at = remaining.rfind('. ', 0, CHUNK_SIZE)
                if split_at < CHUNK_SIZE // 3:
                    # No good sentence boundary — split at paragraph
                    split_at = remaining.rfind('\n\n', 0, CHUNK_SIZE)
                if split_at < CHUNK_SIZE // 3:
                    split_at = CHUNK_SIZE

                piece = remaining[:split_at + 1].strip()
                # First piece gets the real section label; continuations note it
                label = section_label if first else (
                    f"{section_label} (cont.)" if section_label else "")
                emit(piece, label)

                # Carry overlap from end of this piece into next
                overlap_start = max(0, split_at - CHUNK_OVERLAP)
                remaining = remaining[overlap_start:].strip()
                first = False

            if remaining.strip():
                label = section_label if first else (
                    f"{section_label} (cont.)" if section_label else "")
                emit(remaining, label)

    return chunks


# ── PDF scanner ────────────────────────────────────────────────────────────────

def _scan_pdf_files() -> list[tuple[str, str, str]]:
    """
    Walk LAWS_DIR and return list of (file_path, folder_name, filename).
    Skips Urdu-only PDFs (Urdu Constitution) — not processable with current embeddings.
    """
    skip_keywords = ["urdu", "constitution-2015-urdu"]
    results = []

    laws_path = Path(LAWS_DIR)
    # Root-level PDFs (CrPC, Constitution)
    for pdf in laws_path.glob("*.pdf"):
        fname = pdf.name.lower()
        if any(k in fname for k in skip_keywords):
            logger.info(f"  Skipping Urdu-only: {pdf.name}")
            continue
        results.append((str(pdf), "Core", pdf.name))

    # Sub-folder PDFs
    for folder in laws_path.iterdir():
        if folder.is_dir():
            for pdf in folder.glob("*.pdf"):
                results.append((str(pdf), folder.name, pdf.name))

    return sorted(results, key=lambda x: x[2])


# ── Public API ─────────────────────────────────────────────────────────────────

def ingest_all(force: bool = False) -> list[dict]:
    """
    Main ingestion entry point.
    - If CHUNKS_FILE exists and force=False: load from cache.
    - Otherwise: re-parse all PDFs and save to cache.
    Returns list of chunk dicts.
    """
    os.makedirs(os.path.dirname(CHUNKS_FILE), exist_ok=True)

    if not force and os.path.exists(CHUNKS_FILE):
        logger.info(f"Loading existing chunks from {CHUNKS_FILE}")
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        logger.info(f"Loaded {len(chunks):,} chunks from cache")
        return chunks

    logger.info(f"Scanning PDFs in: {LAWS_DIR}")
    pdf_files = _scan_pdf_files()
    logger.info(f"Found {len(pdf_files)} PDFs to process\n")

    all_chunks: list[dict] = []
    for file_path, folder, filename in pdf_files:
        law_name = _infer_law_name(filename)
        category = _infer_category(filename, folder)
        logger.info(f"→ {law_name} [{category}]")

        doc = extract_pdf(file_path, law_name, category)
        if doc is None:
            logger.warning(f"  SKIP (extraction failed)")
            continue

        chunks = _chunk_document(doc)
        all_chunks.extend(chunks)
        logger.info(f"  → {len(chunks)} chunks\n")

    # Save cache
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'='*50}")
    logger.info(f"INGESTION COMPLETE: {len(all_chunks):,} total chunks")
    logger.info(f"Saved to: {CHUNKS_FILE}")

    # Print category breakdown
    from collections import Counter
    cats = Counter(c["category"] for c in all_chunks)
    for cat, count in cats.most_common():
        logger.info(f"  {cat}: {count} chunks")

    return all_chunks
