"""
utils/voice_input.py — DEPRECATED (Phase 2.0 legacy, used sounddevice/PortAudio).

Superseded by utils/audio.py (Phase 2.2+, uses streamlit-audiorecorder/pydub).
Imports are redirected to the current module.
"""
from utils.audio import validate_audio, audio_info, try_record  # noqa: F401

__all__ = ["validate_audio", "audio_info", "try_record"]
