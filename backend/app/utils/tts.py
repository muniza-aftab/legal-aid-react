"""
utils/tts.py — Text-to-Speech for Pakistan AI Legal Aid Assistant.

Backend strategy (tried in order):
    1. ElevenLabs API (high-quality) — used when ELEVENLABS_API_KEY is set
       AND the API endpoint is reachable.
    2. espeak-ng (offline, zero-dependency, zero-cost) — always available as
       a system fallback; produces clear WAV audio with no network calls.
    3. gTTS (Google Text-to-Speech) — final network fallback when espeak-ng
       is unavailable; requires internet access to translate.google.com.

Public API (unchanged from previous version):
    generate_tts(text, language) → str | None
        Returns: absolute path to generated audio file, or None on failure.

    tts_available() → bool
        Returns True when at least one backend is functional.

Language support:
    English → espeak-ng "en" / ElevenLabs Adam / gTTS "en"
    Urdu    → espeak-ng "ur" / ElevenLabs Adam multilingual / gTTS "ur"

Caching:
    Files cached by MD5(language:text) to avoid regenerating identical audio.
    Cache dir: /tmp/legal_aid_tts/

Text limit: 2000 characters (truncated before synthesis).
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from typing import Optional

try:
    from gtts import gTTS as _gTTS
    _GTTS_AVAILABLE = True
except ImportError:
    _gTTS = None          # type: ignore[assignment]
    _GTTS_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Cache directory ────────────────────────────────────────────────────────────
_CACHE_DIR     = os.path.join(tempfile.gettempdir(), "legal_aid_tts")
_MAX_TTS_CHARS = 2000

# ── Language → voice code mapping ─────────────────────────────────────────────
_ESPEAK_LANG: dict[str, str] = {
    "English": "en",
    "Urdu":    "ur",
}

_ELEVENLABS_BASE = "https://api.elevenlabs.io/v1/text-to-speech"
_ELEVENLABS_VOICE_MAP: dict[str, str] = {
    "English": "pNInz6obpgDQGcFmaJgB",
    "Urdu":    "pNInz6obpgDQGcFmaJgB",
}
_MODEL_ID = "eleven_multilingual_v2"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cache_path(text: str, language: str, ext: str = "wav") -> str:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    key = hashlib.md5(f"{language}:{text}".encode("utf-8")).hexdigest()
    return os.path.join(_CACHE_DIR, f"{key}.{ext}")


def _get_elevenlabs_key() -> str:
    try:
        from utils.config import ELEVENLABS_API_KEY
        return ELEVENLABS_API_KEY or ""
    except ImportError:
        return os.getenv("ELEVENLABS_API_KEY", "")


from functools import lru_cache


@lru_cache(maxsize=1)
def _espeak_available() -> bool:
    try:
        result = subprocess.run(
            ["espeak-ng", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── Backend 1: ElevenLabs ──────────────────────────────────────────────────────

def _generate_elevenlabs(text: str, language: str, out_path: str) -> bool:
    api_key = _get_elevenlabs_key()
    if not api_key:
        return False
    try:
        import requests
    except ImportError:
        return False

    voice_id = _ELEVENLABS_VOICE_MAP.get(language, _ELEVENLABS_VOICE_MAP["English"])
    url      = f"{_ELEVENLABS_BASE}/{voice_id}"
    headers  = {
        "xi-api-key":   api_key,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }
    payload = {
        "text":     text,
        "model_id": _MODEL_ID,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(resp.content)
        if os.path.getsize(out_path) == 0:
            os.unlink(out_path)
            return False
        logger.info("ElevenLabs TTS: %d chars → %s", len(text), out_path)
        return True
    except Exception as exc:
        logger.warning("ElevenLabs TTS failed: %s", exc)
        try:
            if os.path.exists(out_path):
                os.unlink(out_path)
        except OSError:
            pass
        return False


# ── Backend 2: espeak-ng (offline) ────────────────────────────────────────────

def _generate_espeak(text: str, language: str, out_path: str) -> bool:
    """
    Synthesise text to WAV using espeak-ng (fully offline).

    Flags:
        -v <lang>  voice/language code
        -s 140     speaking rate (words per minute)
        -a 180     amplitude 0–200
        -w <path>  write to WAV file (no sound card needed)
    """
    lang_code = _ESPEAK_LANG.get(language, "en")
    safe_text = text.replace("\x00", " ").strip()
    if not safe_text:
        return False
    try:
        result = subprocess.run(
            ["espeak-ng", "-v", lang_code, "-s", "140", "-a", "180",
             "-w", out_path, safe_text],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.warning("espeak-ng rc=%d: %s", result.returncode, result.stderr[:200])
            return False
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            logger.warning("espeak-ng: empty/missing file at %s", out_path)
            return False
        logger.info("espeak-ng TTS (%s): %d chars → %s", lang_code, len(text), out_path)
        return True
    except subprocess.TimeoutExpired:
        logger.warning("espeak-ng timed out for %d chars", len(text))
        try:
            if os.path.exists(out_path): os.unlink(out_path)
        except OSError:
            pass
        return False
    except FileNotFoundError:
        logger.warning("espeak-ng not found. Install: apt-get install espeak-ng")
        return False
    except Exception as exc:
        logger.warning("espeak-ng unexpected error: %s", exc)
        return False



# ── Backend 3: gTTS (Google Text-to-Speech, network fallback) ─────────────────

# Language mapping: gTTS uses ISO 639-1 codes
_GTTS_LANG: dict[str, str] = {
    "English": "en",
    "Urdu":    "ur",
}


def _generate_gtts(text: str, language: str, out_path: str) -> bool:
    """
    Synthesise text to MP3 using gTTS (Google Text-to-Speech).

    This is Backend 3 — a network fallback for environments where espeak-ng
    is not installed. Requires internet access to translate.google.com.

    Returns True on success, False on any failure (import error, network
    error, 403, timeout, etc.). Never raises.
    """
    if not _GTTS_AVAILABLE:
        logger.debug("gTTS not installed; skipping (pip install gtts to enable).")
        return False

    if not text or not text.strip():
        return False

    lang_code = _GTTS_LANG.get(language, "en")

    try:
        tts = _gTTS(text=text.strip(), lang=lang_code, slow=False)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        tts.save(out_path)

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            logger.info("gTTS TTS (%s): %d chars → %s", lang_code, len(text), out_path)
            return True

        # File missing or empty
        logger.warning("gTTS produced empty/missing file at %s", out_path)
        return False

    except Exception as exc:
        logger.warning("gTTS failed: %s", exc)
        # Clean up any partial file
        try:
            if os.path.exists(out_path):
                os.unlink(out_path)
        except OSError:
            pass
        return False


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_tts(text: str, language: str = "English") -> Optional[str]:
    """
    Convert text to speech and return the path to the generated audio file.

    Backend order:
        1. ElevenLabs API (MP3)    — if ELEVENLABS_API_KEY is set and reachable
        2. espeak-ng offline (WAV) — if binary is installed (apt install espeak-ng)
        3. gTTS / Google TTS (MP3) — final network fallback if gTTS is installed

    Args:
        text:     Text to synthesise. Truncated to 2000 chars.
        language: "English" (default) or "Urdu"

    Returns:
        str  — absolute path to audio file (MP3 or WAV)
        None — if all backends fail
    """
    if not text or not text.strip():
        return None

    text = text.strip()[:_MAX_TTS_CHARS]

    # ── Backend 1: ElevenLabs (MP3) ───────────────────────────────────────────
    api_key = _get_elevenlabs_key()
    if api_key:
        el_path = _cache_path(text, language, ext="mp3")
        if os.path.exists(el_path) and os.path.getsize(el_path) > 0:
            return el_path
        if _generate_elevenlabs(text, language, el_path):
            return el_path

    # ── Backend 2: espeak-ng (WAV, fully offline) ──────────────────────────────
    esp_path = _cache_path(text, language, ext="wav")
    if os.path.exists(esp_path) and os.path.getsize(esp_path) > 0:
        return esp_path
    if _generate_espeak(text, language, esp_path):
        return esp_path

    # ── Backend 3: gTTS (MP3, Google network fallback) ────────────────────────
    # Uses a distinct cache key suffix ("_gtts") to avoid colliding with the
    # ElevenLabs MP3 cache even though both use .mp3 extension.
    gtts_path = _cache_path(text + "_gtts", language, ext="mp3")
    if os.path.exists(gtts_path) and os.path.getsize(gtts_path) > 0:
        logger.info("gTTS cache hit: %s", gtts_path)
        return gtts_path
    if _generate_gtts(text, language, gtts_path):
        return gtts_path

    logger.error("TTS: all backends failed. language=%s len=%d", language, len(text))
    return None


def tts_available() -> bool:
    """
    Return True if at least one TTS backend is usable.
    Used by app.py to decide whether to show 🔊 buttons.

    Checks (in order — stops at first positive):
        1. ElevenLabs API key is configured
        2. espeak-ng binary is installed
        3. gTTS library is installed (network availability is not pre-checked
           as Google endpoint may be intermittent)
    """
    if _get_elevenlabs_key():
        return True
    if _espeak_available():
        return True
    if _GTTS_AVAILABLE:
        return True
    return False