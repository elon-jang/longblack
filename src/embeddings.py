"""Embedding generation with provider selection (OpenAI or Local)."""

import os
from typing import Literal, Optional

CHUNK_SIZE = 2000  # Characters per chunk
CHUNK_OVERLAP = 150  # Overlap between chunks
MAX_CHUNKS = 100  # Maximum chunks per article

# Provider type
EmbeddingProvider = Literal["openai", "local"]

# Cached local model
_local_model = None


def get_provider() -> EmbeddingProvider:
    """Get embedding provider from environment variable."""
    provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    if provider not in ("openai", "local"):
        provider = "local"
    return provider


def get_embedding_dimension(provider: Optional[EmbeddingProvider] = None) -> int:
    """Get embedding dimension for the provider."""
    provider = provider or get_provider()
    if provider == "openai":
        return 1536  # text-embedding-3-small
    else:
        return 384  # all-MiniLM-L6-v2


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    max_chunks: int = MAX_CHUNKS,
) -> list[str]:
    """Split text into overlapping chunks.

    Args:
        text: Text to split
        chunk_size: Characters per chunk
        overlap: Overlap between chunks
        max_chunks: Maximum number of chunks (0 for unlimited)

    Returns:
        List of text chunks (limited to max_chunks)
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break at sentence or word boundary
        if end < len(text):
            # Look for sentence end
            for sep in [". ", ".\n", "? ", "!\n", "\n\n"]:
                last_sep = text[start:end].rfind(sep)
                if last_sep > chunk_size // 2:
                    end = start + last_sep + len(sep)
                    break

        chunks.append(text[start:end].strip())
        start = end - overlap

        # Limit chunk count
        if max_chunks > 0 and len(chunks) >= max_chunks:
            break

    return [c for c in chunks if c]


# --- OpenAI Provider ---

def _get_openai_client():
    """Get OpenAI client."""
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI embeddings")
    return OpenAI(api_key=api_key)


def _create_openai_embeddings(texts: list[str]) -> list[list[float]]:
    """Create embeddings using OpenAI API."""
    client = _get_openai_client()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


# --- Local Provider (sentence-transformers) ---

def _get_local_model():
    """Get or create local sentence-transformers model."""
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _local_model


def _create_local_embeddings(texts: list[str]) -> list[list[float]]:
    """Create embeddings using local sentence-transformers model."""
    model = _get_local_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


# --- Public API ---

def create_embeddings(texts: list[str], provider: Optional[EmbeddingProvider] = None) -> list[list[float]]:
    """Create embeddings for a list of texts.

    Args:
        texts: List of texts to embed
        provider: 'openai' or 'local' (default: from EMBEDDING_PROVIDER env var)

    Returns:
        List of embedding vectors
    """
    provider = provider or get_provider()

    if provider == "openai":
        return _create_openai_embeddings(texts)
    else:
        return _create_local_embeddings(texts)


def create_embedding(text: str, provider: Optional[EmbeddingProvider] = None) -> list[float]:
    """Create embedding for a single text."""
    return create_embeddings([text], provider)[0]
