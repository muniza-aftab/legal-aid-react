"""
utils/translations.py — Locale-based UI translation system.

Translations live in:
    locales/en.json   (English — source of truth)
    locales/ur.json   (Urdu)

Adding a new language = create locales/<code>.json, add to LANGUAGE_CODES.

Usage (unchanged — all existing call sites work as-is):
    from utils.translations import T
    t = T("Urdu")
    t("analyze_btn")             # → "🔍  کیس تجزیہ کریں"
    t("char_counter", count=42)  # → "42/2000 حروف"
    t("some_missing_key")        # → "some_missing_key"  (safe fallback)
"""
from __future__ import annotations
import json
import os
import logging

logger = logging.getLogger(__name__)

# ── Language registry ──────────────────────────────────────────────────────────
# Internal key → display name shown in the UI selectbox.
# Internal key is what session_state.language stores.
LANGUAGE_CODES: dict[str, str] = {
    "English": "English",
    "Urdu":    "اردو",
}

# ── Locale file loader ─────────────────────────────────────────────────────────
_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOCALES_DIR = os.path.join(_BASE_DIR, "locales")

_lang_code_map: dict[str, str] = {
    "English": "en",
    "Urdu":    "ur",
}

_cache: dict[str, dict] = {}


def _load(language: str) -> dict:
    """Load and cache the JSON file for a language. Falls back to English."""
    if language in _cache:
        return _cache[language]

    code = _lang_code_map.get(language, "en")
    path = os.path.join(_LOCALES_DIR, f"{code}.json")

    if not os.path.exists(path):
        logger.warning("Locale file not found: %s — falling back to English", path)
        code = "en"
        path = os.path.join(_LOCALES_DIR, "en.json")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache[language] = data
        return data
    except Exception as exc:
        logger.error("Failed to load locale %s: %s", path, exc)
        _cache[language] = {}
        return {}


# ── T: callable translator ─────────────────────────────────────────────────────

class T:
    """
    Callable translator for a given language.

        t = T("Urdu")
        t("analyze_btn")              # simple lookup
        t("char_counter", count=42)   # with format substitution

    Missing keys return the key string itself — never raises.
    Unresolved format placeholders are left as-is.
    """

    __slots__ = ("lang", "_strings", "_fallback")

    def __init__(self, language: str) -> None:
        self.lang      = language
        self._strings  = _load(language)
        # English is always the fallback
        self._fallback = _load("English") if language != "English" else {}

    def __call__(self, key: str, **kwargs) -> str:
        value = (
            self._strings.get(key)
            or self._fallback.get(key)
            or key          # last resort: return the key itself
        )
        if kwargs:
            try:
                value = value.format(**kwargs)
            except (KeyError, ValueError):
                pass        # return partially-formatted string rather than crash
        return value

    # Convenience: allow t.lang to read the language name
    def __repr__(self) -> str:
        return f"T({self.lang!r})"


def reload_cache() -> None:
    """Force reload of all cached locale files. Useful after editing JSON."""
    _cache.clear()