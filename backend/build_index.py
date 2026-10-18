#!/usr/bin/env python3
"""
build_index.py — Index builder with separable phases.

Usage
-----
    python build_index.py             # default: smart auto-rebuild
    python build_index.py auto        # same as default
    python build_index.py chunks      # only re-parse PDFs → chunks.json
    python build_index.py embed       # only encode chunks → embeddings cache
    python build_index.py faiss       # only build FAISS index from cache
    python build_index.py status      # print what's on disk and what's stale
    python build_index.py purge       # delete cache + FAISS index

Why split the phases?
---------------------
Encoding 10k chunks with `multilingual-e5-base` takes ~1 hour. Most rebuilds
(category-mapping tweaks, chunk-size changes that only re-shape, etc.)
shouldn't have to redo encoding for chunks whose TEXT didn't actually change.

This script uses a content-addressed embedding cache (utils/embedding_cache.py)
keyed by SHA-1 of the chunk text + the embedding model name, so unchanged
chunks are reused across rebuilds.

What each phase does
--------------------
chunks  — Scan data/laws/, parse PDFs, write data/chunks.json.
          Re-runs every time you invoke it (cheap, ~30 sec).

embed   — Read data/chunks.json, look up each chunk's text in the cache,
          encode only the misses, save cache to data/embeddings_cache.{npz,json}.
          First run: ~1 hour. Subsequent runs after small edits: seconds.

faiss   — Read chunks.json + embedding cache, build the FAISS IndexFlatIP,
          write data/faiss_index/{index.bin, metadata.json}. ~5 sec.

auto    — Run whichever phases look stale based on file mtimes:
          * chunks.json missing            → run chunks
          * EMBED_MODEL changed or
            chunks.json newer than cache    → run embed
          * any input newer than FAISS file → run faiss
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

# Make sure utils/ is importable regardless of where the script is run from.
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "app"))

from app.utils.config import CHUNKS_FILE, FAISS_DIR, EMBED_MODEL, LAWS_DIR
from app.utils.embedding_cache import (
    cache_stats,
    encode_with_cache,
    _VECTORS_PATH,
    _SIDECAR_PATH,
)


# ─── UI helpers ───────────────────────────────────────────────────────────────
def _hr():
    print("=" * 64)


def _h1(title: str):
    _hr()
    print(title)
    _hr()


def _h2(title: str):
    print(f"\n[{title}]")


# ─── Phase 1: chunks ──────────────────────────────────────────────────────────
def phase_chunks() -> list[dict]:
    """Parse PDFs → chunks list, save chunks.json."""
    from app.utils.ingest import _scan_pdf_files, _chunk_document, _infer_law_name, _infer_category
    from app.utils.parser import extract_pdf

    _h2("PHASE 1/3: Parse PDFs and chunk")

    files = _scan_pdf_files()
    print(f"  Found {len(files)} PDFs in {LAWS_DIR}")

    all_chunks: list[dict] = []
    for i, (fp, folder, fname) in enumerate(files, 1):
        ln = _infer_law_name(fname)
        cat = _infer_category(fname, folder)
        doc = extract_pdf(fp, ln, cat)
        if not doc:
            print(f"  [{i:02d}] SKIP  {fname[:50]}")
            continue
        chs = _chunk_document(doc)
        all_chunks.extend(chs)
        print(f"  [{i:02d}] OK    {ln[:42]:42s} | {len(chs):4d} chunks | {cat}")

    print(f"\n  Total: {len(all_chunks):,} chunks from {len(files)} PDFs")

    cats = Counter(c["category"] for c in all_chunks)
    print("\n  Category breakdown:")
    for cat, n in cats.most_common():
        print(f"    {cat}: {n:,}")

    os.makedirs(os.path.dirname(CHUNKS_FILE), exist_ok=True)
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False)
    print(f"\n  Saved chunks → {CHUNKS_FILE}")

    return all_chunks


def _load_chunks() -> list[dict]:
    if not os.path.exists(CHUNKS_FILE):
        print(f"  ✗ {CHUNKS_FILE} not found. Run `build_index.py chunks` first.")
        sys.exit(1)
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── Phase 2: embed ───────────────────────────────────────────────────────────
def phase_embed(chunks: list[dict] | None = None):
    """Encode chunks (cache-aware) and persist the embedding cache."""
    from app.utils.embeddings import encode_texts

    _h2("PHASE 2/3: Encode chunks (cache-aware)")
    print(f"  Model: {EMBED_MODEL}")

    if chunks is None:
        chunks = _load_chunks()

    print(f"  Chunks to embed: {len(chunks):,}")

    t0 = time.time()
    embeddings = encode_with_cache(
        chunks,
        encode_fn=lambda texts: encode_texts(texts, batch_size=64, show_progress=True),
    )
    elapsed = time.time() - t0
    print(f"  Embedding phase complete in {elapsed:.1f}s")

    return embeddings


# ─── Phase 3: faiss ───────────────────────────────────────────────────────────
def phase_faiss(chunks: list[dict] | None = None, embeddings=None):
    """Build the FAISS index + write metadata sidecar from cached embeddings."""
    import faiss
    import numpy as np

    _h2("PHASE 3/3: Build FAISS index")

    if chunks is None:
        chunks = _load_chunks()

    if embeddings is None:
        # Reuse cache without re-encoding.
        from app.utils.embeddings import encode_texts

        embeddings = encode_with_cache(
            chunks,
            encode_fn=lambda texts: encode_texts(texts, batch_size=64, show_progress=True),
        )

    os.makedirs(FAISS_DIR, exist_ok=True)
    index_path = os.path.join(FAISS_DIR, "index.bin")
    metadata_path = os.path.join(FAISS_DIR, "metadata.json")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))
    faiss.write_index(index, index_path)

    metadata = [
        {
            "id": c["id"],
            "law_name": c["law_name"],
            "category": c["category"],
            "section": c["section"],
            "source": c["source"],
            "page_start": c["page_start"],
            "text": c["text"],
        }
        for c in chunks
    ]
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False)

    print(f"  FAISS index : {index.ntotal:,} vectors (dim={dim})")
    print(f"  Saved index : {index_path}")
    print(f"  Saved meta  : {metadata_path}")


# ─── Phase: status ────────────────────────────────────────────────────────────
def phase_status():
    _h1("Index status")

    print(f"\nEmbedding model (current config): {EMBED_MODEL}")

    # chunks.json
    if os.path.exists(CHUNKS_FILE):
        try:
            with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            mtime = time.ctime(os.path.getmtime(CHUNKS_FILE))
            print(f"\nchunks.json    ✔  {len(chunks):,} chunks  (mtime: {mtime})")
        except Exception as e:
            print(f"\nchunks.json    ⚠  unreadable: {e}")
            chunks = None
    else:
        print("\nchunks.json    ✗  missing")
        chunks = None

    # Embedding cache
    stats = cache_stats()
    if stats.get("exists"):
        match = "✔" if stats["model_name"] == EMBED_MODEL else "⚠ MODEL MISMATCH"
        print(
            f"\nembed cache    {match}  {stats['vectors']:,} vectors  "
            f"dim={stats['dim']}  {stats['size_mb']:.1f} MB  "
            f"model={stats['model_name']}"
        )
    else:
        print("\nembed cache    ✗  missing  (next embed phase will be the slow one)")

    # FAISS index
    index_path = os.path.join(FAISS_DIR, "index.bin")
    metadata_path = os.path.join(FAISS_DIR, "metadata.json")
    if os.path.exists(index_path) and os.path.exists(metadata_path):
        size_mb = os.path.getsize(index_path) / 1024 / 1024
        mtime = time.ctime(os.path.getmtime(index_path))
        print(f"\nFAISS index    ✔  {size_mb:.1f} MB  (mtime: {mtime})")
    else:
        print("\nFAISS index    ✗  missing")

    # Staleness analysis
    print("\nStaleness check:")

    def _stale(target: str, source: str) -> bool:
        if not (os.path.exists(target) and os.path.exists(source)):
            return True
        return os.path.getmtime(source) > os.path.getmtime(target)

    if not os.path.exists(CHUNKS_FILE):
        print("  • chunks.json missing       → run `build_index.py chunks`")
    else:
        # Embed cache stale if model changed OR chunks newer than cache.
        cache_stale = (
            not stats.get("exists")
            or stats.get("model_name") != EMBED_MODEL
            or _stale(_VECTORS_PATH, CHUNKS_FILE)
        )
        if cache_stale:
            print("  • embed cache stale         → run `build_index.py embed`")
        else:
            print("  • embed cache fresh")

        if _stale(index_path, CHUNKS_FILE) or _stale(index_path, _VECTORS_PATH):
            print("  • FAISS index stale         → run `build_index.py faiss`")
        else:
            print("  • FAISS index fresh")

    _hr()


# ─── Phase: purge ─────────────────────────────────────────────────────────────
def phase_purge():
    _h1("Purging derived artifacts")
    targets = [
        CHUNKS_FILE,
        _VECTORS_PATH,
        _SIDECAR_PATH,
        os.path.join(FAISS_DIR, "index.bin"),
        os.path.join(FAISS_DIR, "metadata.json"),
    ]
    for p in targets:
        if os.path.exists(p):
            os.remove(p)
            print(f"  removed  {p}")
        else:
            print(f"  skip     {p}  (not present)")
    _hr()


# ─── Phase: auto (smart rebuild) ──────────────────────────────────────────────
def phase_auto():
    _h1("AUTO REBUILD — running stale phases only")

    # 1) chunks: always run (cheap, side-effect-free if PDFs unchanged).
    chunks = phase_chunks()

    # 2) embed: skipped automatically by the cache when chunk hashes are present.
    embeddings = phase_embed(chunks=chunks)

    # 3) faiss: rebuilt to keep metadata + vectors in lockstep.
    phase_faiss(chunks=chunks, embeddings=embeddings)


# ─── Smoke tests (only after auto/full builds) ────────────────────────────────
def _smoke_tests():
    print("\n[VERIFY] Retrieval smoke-tests")
    from app.utils.rag_engine import retrieve, index_stats

    stats = index_stats()
    print(f"  Vectors: {stats['vectors']:,}  Laws: {stats['laws']}  Chunks: {stats['chunks']:,}")

    test_queries = [
        ("unpaid salary", "Labour Law"),
        ("divorce wife rights", "Family Law"),
        ("FIR police arrest", "Criminal Law"),
        ("tenant landlord deposit", "Property Law"),
    ]
    for query, expected in test_queries:
        results = retrieve(query, top_k=3)
        cats = [r["category"] for r in results]
        hit = expected in cats
        top = results[0]["law_name"][:35] if results else "—"
        marker = "✔" if hit else "?"
        print(f"  {marker} '{query}' → {top}  ({cats[0] if cats else '—'})")


# ─── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Pakistan AI Legal Aid — Index Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "phase",
        nargs="?",
        default="auto",
        choices=["auto", "chunks", "embed", "faiss", "status", "purge"],
        help="Which phase to run (default: auto)",
    )
    args = parser.parse_args()

    _h1(f"PAKISTAN AI LEGAL AID — Index Builder  ({args.phase})")

    if args.phase == "status":
        phase_status()
        return

    if args.phase == "purge":
        phase_purge()
        return

    t_start = time.time()

    if args.phase == "chunks":
        phase_chunks()
    elif args.phase == "embed":
        phase_embed()
    elif args.phase == "faiss":
        phase_faiss()
    else:  # auto
        phase_auto()
        _smoke_tests()

    print(f"\nTotal time: {time.time() - t_start:.1f}s")
    _hr()
    print("DONE ✔")
    if args.phase in ("auto", "faiss"):
        print("Run the app with:  python main.py  # start backend")
    _hr()


if __name__ == "__main__":
    main()
