"""Embedding generation using a local sentence-transformers model.

Defaults to all-MiniLM-L6-v2 (384 dims, ~80MB, fast on CPU).
Falls back to OpenAI if AGENTSTACK_EMBEDDING_PROVIDER=openai is set.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

settings = get_settings()
logger = logging.getLogger(__name__)

LOCAL_MODEL_NAME = "all-MiniLM-L6-v2"
LOCAL_MODEL_DIMS = 384

_local_model: SentenceTransformer | None = None


def _get_local_model() -> SentenceTransformer:
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading local embedding model: %s", LOCAL_MODEL_NAME)
        _local_model = SentenceTransformer(LOCAL_MODEL_NAME)
        logger.info("Model loaded.")
    return _local_model


def _use_openai() -> bool:
    return (
        getattr(settings, "embedding_provider", "local") == "openai"
        and bool(settings.openai_api_key)
    )


def generate_embedding(text: str) -> list[float]:
    if _use_openai():
        return _openai_embedding(text)
    model = _get_local_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    if _use_openai():
        return _openai_embeddings_batch(texts)
    model = _get_local_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=len(texts) > 500)
    return [v.tolist() for v in vecs]


# --- OpenAI fallback (used only when embedding_provider=openai) ---

_openai_client = None
OPENAI_BATCH_SIZE = 256


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def _openai_embedding(text: str) -> list[float]:
    try:
        client = _get_openai_client()
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=text,
            dimensions=settings.embedding_dimensions,
        )
        return response.data[0].embedding
    except Exception:
        return _fallback_embedding(text)


def _openai_embeddings_batch(texts: list[str]) -> list[list[float]]:
    import time

    client = _get_openai_client()
    all_embeddings: list[list[float]] = [[] for _ in texts]

    for i in range(0, len(texts), OPENAI_BATCH_SIZE):
        batch = texts[i : i + OPENAI_BATCH_SIZE]
        try:
            response = client.embeddings.create(
                model=settings.embedding_model,
                input=batch,
                dimensions=settings.embedding_dimensions,
            )
            for item in response.data:
                all_embeddings[i + item.index] = item.embedding
        except Exception as e:
            logger.warning("OpenAI batch embedding failed at offset %d: %s, using fallback", i, e)
            for j, text in enumerate(batch):
                all_embeddings[i + j] = _fallback_embedding(text)

        if i + OPENAI_BATCH_SIZE < len(texts):
            time.sleep(0.2)

    return all_embeddings


def _fallback_embedding(text: str) -> list[float]:
    """Deterministic hash-based pseudo-embedding for when nothing else works."""
    import hashlib
    import math
    import random

    dims = settings.embedding_dimensions
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    embedding = [rng.gauss(0, 1) for _ in range(dims)]
    norm = math.sqrt(sum(x * x for x in embedding))
    if norm > 0:
        embedding = [x / norm for x in embedding]
    return embedding
