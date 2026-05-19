"""
validator.py — Input sanitisation and prompt injection guard.
"""
from __future__ import annotations
import re
from utils.config import MAX_QUERY_LENGTH, MIN_QUERY_LENGTH, INJECTION_PATTERNS


class ValidationError(ValueError):
    pass


def sanitize(text: str) -> str:
    """
    Clean and validate user input. Returns cleaned text or raises ValidationError.
    Steps: strip → remove control chars → collapse blank lines →
           length check → injection check.
    """
    if not isinstance(text, str):
        raise ValidationError("Input must be text.")

    text = text.strip()
    # Remove non-printable chars (keep newlines, tabs, Arabic/Urdu Unicode)
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u0600-\u06FF\u0080-\uFFFF]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    if len(text) < MIN_QUERY_LENGTH:
        raise ValidationError(
            f"Please describe your issue in at least {MIN_QUERY_LENGTH} characters "
            f"so we can help accurately. (You wrote {len(text)} chars)"
        )
    if len(text) > MAX_QUERY_LENGTH:
        raise ValidationError(
            f"Input too long ({len(text)} chars). "
            f"Please keep it under {MAX_QUERY_LENGTH} characters."
        )

    lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lower:
            raise ValidationError(
                "⚠️ Your input contains restricted phrases. "
                "Please describe your legal issue in plain language."
            )

    return text
