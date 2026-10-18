"""Opt-in synthetic provider smoke test: python tests/live_smoke.py.

Uses configured API keys and provider quotas, but never opens the case database.
"""
import json
import logging
import os
import pathlib
import re
import sys
import time

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
logging.disable(logging.CRITICAL)
from app.utils.rag_engine import retrieve
from app.utils.groq_client import analyze_with_rag, analyze_document_with_rag, transcribe_audio
from app.utils.chat_service import chat, clear_session
from app.utils.tts import generate_tts

results = []
output = root.parent / ".local" / "live-results.json"
output.parent.mkdir(exist_ok=True)

def record(feature, passed, **details):
    row = {"feature": feature, "passed": bool(passed), **details}
    results.append(row)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(row, ensure_ascii=True), flush=True)

print("Loading the cached retrieval model; live requests use synthetic information only.", flush=True)
queries = {
    "English": "My employer has not paid my salary for three months. What are my rights?",
    "Urdu": "میرے آجر نے تین ماہ سے تنخواہ نہیں دی۔ میرے کیا حقوق ہیں؟",
}
for language, query in queries.items():
    try:
        started = time.monotonic()
        chunks = retrieve(query)
        result = analyze_with_rag(query, chunks, language)
        record(f"analysis_{language}", not result.error and bool(result.summary),
               category=result.category, laws=len(result.laws), confidence=result.confidence,
               correct_script=bool(re.search(r"[\u0600-\u06ff]", result.summary)) if language == "Urdu" else True,
               error=result.error, seconds=round(time.monotonic()-started, 1))
        sid = "synthetic-live-" + language
        followup = "What documents should I collect for my unpaid salary case?" if language == "English" else "تنخواہ کے معاملے میں مجھے کون سے کاغذات جمع کرنے چاہئیں؟"
        reply = chat(sid, followup, language, {"category": result.category, "summary": result.summary, "last_query": query})
        record(f"chat_{language}", not reply.error and bool(reply.reply), sources=len(reply.sources), confidence=reply.confidence, error=reply.error)
        clear_session(sid)
    except Exception as exc:
        record(f"analysis_chat_{language}", False, error=f"{type(exc).__name__}: {str(exc)[:300]}")

for language, text in {"English": "This is a synthetic test. My salary has not been paid for three months.",
                       "Urdu": "یہ صرف جانچ کے لیے ہے۔ میری تین ماہ کی تنخواہ ادا نہیں ہوئی۔"}.items():
    try:
        path = generate_tts(text, language)
        record(f"tts_{language}", bool(path and os.path.getsize(path)), bytes=os.path.getsize(path) if path else 0)
        if path:
            with open(path, "rb") as audio:
                transcript, error = transcribe_audio(audio.read(), language)
            record(f"transcription_{language}", bool(transcript) and not error, characters=len(transcript), error=error)
    except Exception as exc:
        record(f"speech_{language}", False, error=f"{type(exc).__name__}: {str(exc)[:300]}")

document = "LEGAL NOTICE. Synthetic test only. The employer is requested to pay the employee's outstanding wages for three months. Please respond to this notice within 14 days of receipt. This is not a real case."
for language in ("English", "Urdu"):
    try:
        result = analyze_document_with_rag(document, "Legal Notice", "English", language)
        record(f"document_{language}", bool(result.summary) and not result.error,
               deadlines=len(result.deadlines), coverage=result.analyzed_characters,
               total=result.total_characters, truncated=result.truncated, error=result.error)
    except Exception as exc:
        record(f"document_{language}", False, error=f"{type(exc).__name__}: {str(exc)[:300]}")

print("Provider smoke results saved to .local/live-results.json", flush=True)
sys.exit(0 if all(row["passed"] for row in results) else 1)
