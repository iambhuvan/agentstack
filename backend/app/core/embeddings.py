from openai import OpenAI

from app.config import get_settings

settings = get_settings()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def generate_embedding(text: str) -> list[float]:
    """Generate a vector embedding for the given text using OpenAI.
    Falls back to hash-based pseudo-embedding if OpenAI is unavailable."""
    if not settings.openai_api_key:
        return _fallback_embedding(text)

    try:
        client = _get_client()
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=text,
            dimensions=settings.embedding_dimensions,
        )
        return response.data[0].embedding
    except Exception:
        return _fallback_embedding(text)


def _fallback_embedding(text: str) -> list[float]:
    """Deterministic hash-based pseudo-embedding when no API key is configured.
    Not semantically meaningful, but allows the system to function for dev/testing."""
    import hashlib
    import math
    import random

    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    embedding = [rng.gauss(0, 1) for _ in range(settings.embedding_dimensions)]

    norm = math.sqrt(sum(x * x for x in embedding))
    if norm > 0:
        embedding = [x / norm for x in embedding]
    return embedding
