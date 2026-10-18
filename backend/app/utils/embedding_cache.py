"""
embedding_cache.py — Content-addressed cache for chunk embeddings.

Why this exists
---------------
Re-running `build_index.py` after a small change (e.g. tweaking a category
mapping in config.py) used to force a full re-encode of every chunk through
the sentence-transformer — ~1 hour for 10k chunks on `multilingual-e5-base`.

This cache keeps an on-disk map of:

    sha1(chunk_text)  ─┐
    EMBED_MODEL name  ─┴──► float32 vector (dim,)

so unchanged chunks are reused across rebuilds.  Only chunks whose text
actually differs (or whose model changed) get re-encoded.

The cache is stored as two files in `data/`:
    embeddings_cache.npz   — vectors stacked as a (N, dim) float32 array
    embeddings_cache.json  — sidecar with model_name, dim, and a
                             list of sha1 hashes parallel to the vectors

Invalidation rules
------------------
- If `EMBED_MODEL` in the cache sidecar differs from the current
  `EMBED_MODEL`, the cache is treated as empty (full re-encode).
- If a chunk's sha1 is missing from the cache, that chunk is re-encoded.
- Stale entries (chunks no longer present) are pruned at save time.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Iterable

import numpy as np

from app.utils.config import BASE_DIR, EMBED_MODEL

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_CACHE_DIR = os.path.join(BASE_DIR, "data")
_VECTORS_PATH = os.path.join(_CACHE_DIR, "embeddings_cache.npz")
_SIDECAR_PATH = os.path.join(_CACHE_DIR, "embeddings_cache.json")


# ── Hashing ───────────────────────────────────────────────────────────────────
def chunk_hash(text: str) -> str:
    """Stable per-chunk identity. SHA-1 is fine here — we only need uniqueness,
    not cryptographic strength."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


# ── Load / save ───────────────────────────────────────────────────────────────
def load_cache() -> dict[str, np.ndarray]:
    """
    Load the embedding cache as a {sha1: vector} dict.

    Returns an empty dict if:
      * the cache files don't exist
      * the cached `model_name` differs from the current EMBED_MODEL
      * the sidecar/vector files are out of sync
    """
    if not (os.path.exists(_VECTORS_PATH) and os.path.exists(_SIDECAR_PATH)):
        return {}

    try:
        with open(_SIDECAR_PATH, "r", encoding="utf-8") as f:
            sidecar = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Could not read embedding cache sidecar: {e}")
        return {}

    if sidecar.get("model_name") != EMBED_MODEL:
        logger.info(
            f"Embedding cache was built with model "
            f"{sidecar.get('model_name')!r}, current is {EMBED_MODEL!r}. "
            f"Ignoring cache (will re-encode)."
        )
        return {}

    hashes = sidecar.get("hashes") or []
    try:
        with np.load(_VECTORS_PATH) as npz:
            vectors = npz["vectors"]
    except (OSError, KeyError) as e:
        logger.warning(f"Could not read embedding cache vectors: {e}")
        return {}

    if vectors.shape[0] != len(hashes):
        logger.warning(
            f"Embedding cache is corrupt "
            f"(vectors={vectors.shape[0]}, hashes={len(hashes)}). "
            f"Ignoring cache."
        )
        return {}

    return {h: vectors[i] for i, h in enumerate(hashes)}


def save_cache(cache: dict[str, np.ndarray], dim: int) -> None:
    """Persist the cache to disk in the canonical format."""
    os.makedirs(_CACHE_DIR, exist_ok=True)

    if not cache:
        # Wipe to keep state consistent.
        for p in (_VECTORS_PATH, _SIDECAR_PATH):
            if os.path.exists(p):
                os.remove(p)
        return

    hashes = list(cache.keys())
    vectors = np.stack([cache[h] for h in hashes], axis=0).astype(np.float32)

    np.savez_compressed(_VECTORS_PATH, vectors=vectors)
    with open(_SIDECAR_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"model_name": EMBED_MODEL, "dim": dim, "hashes": hashes},
            f,
            ensure_ascii=False,
        )

    size_mb = os.path.getsize(_VECTORS_PATH) / 1024 / 1024
    logger.info(
        f"Embedding cache saved: {len(cache):,} vectors, "
        f"dim={dim}, {size_mb:.1f} MB"
    )


# ── High-level API used by build_index.py ─────────────────────────────────────
def encode_with_cache(
    chunks: list[dict],
    *,
    encode_fn,
    batch_size: int = 64,
) -> np.ndarray:
    """
    Encode chunk texts, reusing cached vectors where possible.

    Args:
        chunks:    list of chunk dicts (must contain 'text')
        encode_fn: callable(texts: list[str]) -> np.ndarray of shape (N, dim).
                   Pass utils.embeddings.encode_texts here.
        batch_size: forwarded to encode_fn (informational; the encoder
                    already batches internally).

    Returns:
        Embeddings array of shape (len(chunks), dim) aligned with `chunks`.

    Side effects:
        Updates the on-disk cache so subsequent calls are even faster.
    """
    cache = load_cache()

    hashes = [chunk_hash(c["text"]) for c in chunks]

    missing_idx: list[int] = [i for i, h in enumerate(hashes) if h not in cache]
    hits = len(chunks) - len(missing_idx)

    logger.info(
        f"Embedding cache: {hits:,}/{len(chunks):,} hits "
        f"({100 * hits / max(len(chunks), 1):.1f}%) "
        f"— need to encode {len(missing_idx):,} new chunks"
    )

    # Encode only the missing ones.
    if missing_idx:
        missing_texts = [chunks[i]["text"] for i in missing_idx]
        new_vecs = encode_fn(missing_texts)
        for i, vec in zip(missing_idx, new_vecs):
            cache[hashes[i]] = vec.astype(np.float32)

    # Determine dim (from any cached vector).
    sample_vec = next(iter(cache.values()))
    dim = sample_vec.shape[0]

    # Prune entries no longer referenced — keeps cache size bounded.
    referenced = set(hashes)
    if len(cache) > len(referenced):
        before = len(cache)
        cache = {h: v for h, v in cache.items() if h in referenced}
        logger.info(f"Pruned {before - len(cache):,} stale cache entries")

    # Persist.
    save_cache(cache, dim=dim)

    # Assemble output in the SAME order as the input chunks.
    out = np.empty((len(chunks), dim), dtype=np.float32)
    for i, h in enumerate(hashes):
        out[i] = cache[h]
    return out


def cache_stats() -> dict:
    """Return a small dict for CLI display."""
    if not os.path.exists(_SIDECAR_PATH):
        return {"exists": False}

    try:
        with open(_SIDECAR_PATH, "r", encoding="utf-8") as f:
            sidecar = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"exists": False}

    size_mb = (
        os.path.getsize(_VECTORS_PATH) / 1024 / 1024
        if os.path.exists(_VECTORS_PATH)
        else 0.0
    )
    return {
        "exists": True,
        "model_name": sidecar.get("model_name"),
        "dim": sidecar.get("dim"),
        "vectors": len(sidecar.get("hashes") or []),
        "size_mb": size_mb,
    }
