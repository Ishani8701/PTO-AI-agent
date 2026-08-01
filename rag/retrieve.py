"""Query the policy index, scoped to a specific country plus Global rules."""

from __future__ import annotations

from rag.embeddings import embed
from rag.rerank import rerank
from rag.store import get_collection
from tracing import traced

_CANDIDATE_POOL = 15


@traced("search_policy")
def retrieve_policy(query: str, country: str, k: int = 3) -> list[dict]:
    """Return the top-k policy chunks relevant to `query`, restricted to
    `country`'s sections and the shared "Global" section. Country is a hard
    filter, applied before ranking — never a chunk from another country.

    Two-stage retrieval: a bi-encoder vector search casts a wide net
    (`_CANDIDATE_POOL` candidates) for recall, then a cross-encoder reranks
    those candidates against the query for precision before truncating to k.

    The reranking query has the employee's country folded in explicitly.
    A cross-encoder scores text pairs on literal relevance and has no idea
    "country" is a meaningful axis unless it's spelled out — the employee's
    own country is known context we have and the raw user question usually
    won't restate ("how much leave do I get" rarely says "...in Germany").
    """
    collection = get_collection()
    result = collection.query(
        query_embeddings=embed([query]),
        n_results=_CANDIDATE_POOL,
        where={"section": {"$in": [country, "Global"]}},
    )
    candidates = [
        {"text": doc, "metadata": meta}
        for doc, meta in zip(result["documents"][0], result["metadatas"][0])
    ]
    rerank_query = f"{query} (employee location: {country})"
    return rerank(rerank_query, candidates, top_k=k)
