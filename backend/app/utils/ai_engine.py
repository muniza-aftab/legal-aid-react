"""
utils/ai_engine.py — DEPRECATED (Phase 2.0 legacy, used Gemini API).

Superseded by utils/groq_client.py (Phase 2.1+, uses Groq).
Imports are redirected to the current module.
"""
from utils.groq_client import analyze_with_rag, LegalAnalysis  # noqa: F401

__all__ = ["analyze_with_rag", "LegalAnalysis"]
