"""Cross-encoder reranking: precise relevance scoring over a short candidate
list produced by the (cheaper, coarser) bi-encoder vector search.
"""

from __future__ import annotations

from sentence_transformers import CrossEncoder

_model: CrossEncoder | None = None


def get_reranker() -> CrossEncoder:
    """Load the model once per process and reuse it."""
    global _model
    if _model is None:
        _model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _model


def rerank(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """Score each chunk jointly against the query and return the top_k."""
    if not chunks:
        return []
    pairs = [(query, chunk["text"]) for chunk in chunks]
    scores = get_reranker().predict(pairs)
    ranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)
    return [chunk for chunk, _ in ranked[:top_k]]
