"""Local embedding model wrapper.

Uses Sentence Transformers instead of a hosted embeddings API: free, no
network calls, no extra vendor dependency, and policy text never leaves the
machine. Quality is more than sufficient at the scale of a handful of policy
documents.
"""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    """Load the model once per process and reuse it."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """Turn a list of strings into a list of embedding vectors."""
    return get_embedder().encode(texts).tolist()
