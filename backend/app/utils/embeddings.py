"""
embeddings.py — Sentence-transformers wrapper.
Provides encode() for both queries and document chunks.
Model is loaded once and cached in module state.
"""
from __future__ import annotations
import logging
import numpy as np
from typing import TYPE_CHECKING
import threading
if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
from app.utils.config import EMBED_MODEL
import functools  # streamlit removed

logger = logging.getLogger(__name__)
_model = None
_model_lock = threading.Lock()

@functools.lru_cache(maxsize=1)
def _load_embedding_model() -> SentenceTransformer:
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", EMBED_MODEL)
            _model = SentenceTransformer(EMBED_MODEL)
            logger.info("Embedding model loaded.")
    return _model


def get_model() -> SentenceTransformer:
    return _load_embedding_model()


def encode_texts(texts: list[str], batch_size: int = 64, show_progress: bool = True) -> np.ndarray:
    """
    Encode a list of texts → float32 numpy array (N, dim).
    Normalises vectors for cosine similarity via dot product.
    """
    model = get_model()
    embeddings = model.encode(
        # ["passage: " + t for t in texts], for e5
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        normalize_embeddings=True,   # L2-normalize → cosine = dot product
        convert_to_numpy=True,
    )
    return embeddings.astype(np.float32)


def encode_query(query: str) -> np.ndarray:
    """Encode a single query string → shape (1, dim) float32 array."""
    model = get_model()

    embedding = model.encode(
        # ["query: " + query], for e5
        [query],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return embedding.astype(np.float32)
