"""
utils/ngo_engine.py — DEPRECATED (Phase 2.0 legacy).

This module has been superseded by utils/ngo_matcher.py which adds
risk-level-aware scoring and urgent helpline support.

All imports from this file are redirected to ngo_matcher to prevent
the "unexpected keyword argument 'risk_level'" TypeError that occurs
when callers use the new signature against the old function.
"""
from utils.ngo_matcher import recommend_ngos, get_urgent_helplines  # noqa: F401

__all__ = ["recommend_ngos", "get_urgent_helplines"]
