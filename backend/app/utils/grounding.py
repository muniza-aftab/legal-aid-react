"""Validate model citations against the sources actually supplied to it."""
from __future__ import annotations
import re
import unicodedata


def text_list(value, limit: int = 30) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip()[:2500] for item in value[:limit] if isinstance(item, str) and item.strip()]


def _name(value: str) -> str:
    words = re.findall(r"[a-z]+", unicodedata.normalize("NFKC", value).lower())
    return "".join(word for word in words if word not in {"the", "of", "and"})


def _sections(value: str) -> set[str]:
    value = value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    numbers = set(re.findall(r"(?:sections?|articles?|دفعہ|دفع(?:ات|ہ)|آرٹیکل)\s*(\d+[a-z]?)", value, re.I))
    heading = re.match(r"\s*(\d+[a-z]?)\s*[.\-—]", value, re.I)
    if heading:
        numbers.add(heading.group(1).lower())
    return {number.lower() for number in numbers}


def validate_citations(items, source_ids, chunks: list[dict], language: str = "English") -> tuple[list[str], bool]:
    citations = text_list(items)
    ids = source_ids if isinstance(source_ids, list) else []
    accepted = []
    for index, citation in enumerate(citations):
        prefix = citation.split(":", 1)[0]
        explicit = ids[index] if index < len(ids) else None
        if isinstance(explicit, int) and not isinstance(explicit, bool) and 1 <= explicit <= len(chunks):
            candidates = [chunks[explicit - 1]]
        else:
            candidates = chunks if language == "English" else []
        for chunk in candidates:
            law = chunk.get("law_name", "")
            # In English, a fabricated law name cannot be rescued by a valid ID.
            if language == "English" and (not _name(law) or _name(law) not in _name(prefix)):
                continue
            available = _sections(chunk.get("section", "")) | _sections(chunk.get("text", ""))
            if not _sections(prefix).issubset(available):
                continue
            accepted.append(citation)
            break
    return accepted, len(accepted) != len(citations)
