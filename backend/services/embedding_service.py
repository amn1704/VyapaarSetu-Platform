"""
UBID Platform — AI Embedding Service (Production)

Embedding feature generation using nomic-embed-text via local Ollama.
Embeddings support candidate discovery, semantic matching, and clustering.
Threshold decisions remain auditable and reviewer-reversible.

All inference runs locally — zero cloud dependencies.
"""

import logging
import asyncio
from urllib.parse import urlparse
from typing import Optional

from ollama import AsyncClient
from ..config import settings

logger = logging.getLogger("ubid.embedding")

# ── Model Configuration ──────────────────────────────────────────────────────

EMBEDDING_MODEL = settings.EMBEDDING_MODEL
EMBEDDING_DIM = 768
OLLAMA_HOST = settings.OLLAMA_HOST

_client: Optional[AsyncClient] = None


def _get_client() -> AsyncClient:
    """Singleton Ollama client using configured host."""
    global _client
    if _client is None:
        parsed = urlparse(OLLAMA_HOST)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal", "ollama"}:
            raise RuntimeError("OLLAMA_HOST must point to a local Ollama instance")
        _client = AsyncClient(host=OLLAMA_HOST)
    return _client


# ── Single Embedding ─────────────────────────────────────────────────────────

async def generate_embedding(text: str) -> list[float]:
    """
    Generate a 768-dim embedding vector for the given text
    using local Ollama nomic-embed-text.

    Returns empty list on failure (caller must handle gracefully).
    """
    if not text or not text.strip():
        return []

    try:
        client = _get_client()
        response = None
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = await client.embeddings(
                    model=EMBEDDING_MODEL,
                    prompt=text.strip(),
                )
                break
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(0.25 * (attempt + 1))
        if response is None:
            raise RuntimeError(f"Ollama embedding failed after retries: {last_error}")
        embedding = response.get("embedding", [])
        if len(embedding) != EMBEDDING_DIM:
            logger.warning(
                f"Unexpected embedding dimension: got {len(embedding)}, expected {EMBEDDING_DIM}"
            )
        return embedding
    except Exception as e:
        logger.error(f"Embedding generation failed for '{text[:50]}...': {e}")
        return []


# ── Batch Embedding ──────────────────────────────────────────────────────────

async def batch_generate_embeddings(
    texts: list[str],
    concurrency: int = 4,
) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts with controlled concurrency.

    Args:
        texts: List of text strings to embed.
        concurrency: Maximum parallel Ollama requests (avoid overloading GPU).

    Returns:
        List of embedding vectors (same order as input).
    """
    semaphore = asyncio.Semaphore(concurrency)
    results: list[list[float]] = [[] for _ in texts]

    async def _embed_one(idx: int, text: str):
        async with semaphore:
            results[idx] = await generate_embedding(text)

    tasks = [_embed_one(i, t) for i, t in enumerate(texts)]
    await asyncio.gather(*tasks, return_exceptions=True)
    return results


# ── Combined Identity String Builder ─────────────────────────────────────────

def build_identity_text(
    normalized_name: Optional[str] = None,
    address_raw: Optional[str] = None,
    sector: Optional[str] = None,
    pan: Optional[str] = None,
    gstin: Optional[str] = None,
) -> str:
    """
    Build a combined identity string for embedding generation.

    Example output:
        "abc textiles rajajinagar bangalore textile manufacturing"

    This concatenation captures the full semantic identity of a business
    so that the embedding model can reason over name + location + sector
    in a single vector.
    """
    parts = []
    if normalized_name:
        parts.append(normalized_name)
    if address_raw:
        # Strip punctuation, lowercase
        clean_addr = address_raw.lower().replace(",", " ").replace(".", " ")
        parts.append(clean_addr)
    if sector:
        parts.append(sector.lower())
    # Do NOT embed PAN/GSTIN — they are exact-match identifiers, not semantic
    return " ".join(parts).strip()
