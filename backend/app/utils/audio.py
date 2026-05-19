"""
utils/audio.py — Audio capture, validation, and normalisation.

Public API:
  extract_wav_bytes(uploaded_file)  → bytes
  resample_to_16k(wav_bytes)        → bytes
  validate_audio(wav_bytes)         → (bool, str)
  audio_info(wav_bytes)             → dict
  try_record(duration)              → (bytes, str|None)
"""
from __future__ import annotations
import io
import struct
import logging
from typing import Optional

logger = logging.getLogger(__name__)

WHISPER_SAMPLE_RATE = 16_000
MIN_AUDIO_BYTES     = 8_000
MIN_DURATION_S      = 0.3
MAX_DURATION_S      = 300.0


# Plain string — translated versions are served via t("voice_empty_hint") in translations.py
RECORDING_HINT = "🎤 Press 'Start Recording', speak clearly, then press 'Stop Recording'."


# ── WAV header ────────────────────────────────────────────────────────────────

def _read_wav_header(wav_bytes: bytes) -> dict | None:
    try:
        if len(wav_bytes) < 44:
            return None
        if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
            return None

        channels        = struct.unpack_from("<H", wav_bytes, 22)[0]
        sample_rate     = struct.unpack_from("<I", wav_bytes, 24)[0]
        bits_per_sample = struct.unpack_from("<H", wav_bytes, 34)[0]

        offset    = 12
        data_size = 0
        while offset + 8 <= len(wav_bytes):
            chunk_id   = wav_bytes[offset:offset + 4]
            chunk_size = struct.unpack_from("<I", wav_bytes, offset + 4)[0]
            if chunk_id == b"data":
                data_size = chunk_size
                break
            offset += 8 + chunk_size

        bpf = (bits_per_sample // 8) * channels
        return {
            "sample_rate":     sample_rate,
            "channels":        channels,
            "bits_per_sample": bits_per_sample,
            "num_frames":      data_size // bpf if bpf else 0,
        }
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def extract_wav_bytes(uploaded_file) -> bytes:
    """Pull raw bytes from an st.audio_input UploadedFile."""
    if uploaded_file is None:
        return b""
    try:
        uploaded_file.seek(0)
        return uploaded_file.read()
    except Exception as exc:
        logger.warning("extract_wav_bytes: %s", exc)
        return b""


def resample_to_16k(wav_bytes: bytes) -> bytes:
    """
    Convert WAV audio to 16 kHz mono PCM.
    Uses scipy + soundfile if available.
    """
    if not wav_bytes:
        return wav_bytes

    try:
        import soundfile as sf
        import numpy as np
        from scipy.signal import resample_poly
        from math import gcd

        audio, sr_in = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
        audio = audio.mean(axis=1)  # stereo → mono

        if sr_in != WHISPER_SAMPLE_RATE:
            g = gcd(WHISPER_SAMPLE_RATE, sr_in)
            audio = resample_poly(
                audio,
                WHISPER_SAMPLE_RATE // g,
                sr_in // g
            ).astype(np.float32)

        buf = io.BytesIO()
        sf.write(buf, audio, WHISPER_SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return buf.getvalue()

    except ImportError:
        return wav_bytes
    except Exception as exc:
        logger.warning("resample_to_16k failed (%s), using original", exc)
        return wav_bytes


def validate_audio(wav_bytes: bytes) -> tuple[bool, str]:
    """
    Validate WAV audio before sending to Whisper.
    """
    if not wav_bytes:
        return False, "No audio data received. Please try recording again."

    if len(wav_bytes) < MIN_AUDIO_BYTES:
        return False, (
            f"Recording too short ({len(wav_bytes):,} bytes). "
            "Please speak for at least one second."
        )

    header = _read_wav_header(wav_bytes)
    if header is None:
        return False, "Invalid audio format. Please try again."

    sr       = header["sample_rate"] or WHISPER_SAMPLE_RATE
    duration = header["num_frames"] / sr if sr else 0.0

    if duration < MIN_DURATION_S:
        return False, (
            f"Recording too short ({duration:.1f}s). "
            f"Please speak for at least {MIN_DURATION_S:.1f} seconds."
        )

    if duration > MAX_DURATION_S:
        return False, (
            f"Recording too long ({duration:.0f}s). "
            "Please keep it under 5 minutes."
        )

    # ✅ Improved silence detection (less strict)
    try:
        import soundfile as sf
        import numpy as np
        audio, _ = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=False)

        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 1e-5:
            return False, "No speech detected. Please speak clearly."

    except Exception:
        pass

    return True, ""


def audio_info(wav_bytes: bytes) -> dict:
    """Return basic audio stats."""
    header = _read_wav_header(wav_bytes)
    if not header:
        return {}

    sr = header["sample_rate"] or 1

    return {
        "duration_s":      round(header["num_frames"] / sr, 2),
        "sample_rate":     header["sample_rate"],
        "channels":        header["channels"],
        "bits_per_sample": header["bits_per_sample"],
        "file_size_kb":    round(len(wav_bytes) / 1024, 1),
    }


def try_record(duration: int = 10) -> tuple[bytes, Optional[str]]:
    """Fallback recording (not used in main app)."""
    try:
        import sounddevice as sd
        import soundfile as sf

        audio = sd.rec(
            int(duration * WHISPER_SAMPLE_RATE),
            samplerate=WHISPER_SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )
        sd.wait()

        buf = io.BytesIO()
        sf.write(buf, audio, WHISPER_SAMPLE_RATE, format="WAV", subtype="PCM_16")
        wav = buf.read()

        ok, err = validate_audio(wav)
        return (wav, None) if ok else (b"", err)

    except ImportError:
        return b"", "PortAudio not installed. Use browser recording."
    except Exception as exc:
        return b"", f"Recording failed: {exc}"