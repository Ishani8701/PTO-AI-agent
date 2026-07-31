"""Shared access to the persistent policy-document vector store."""

from __future__ import annotations

import chromadb

_PERSIST_PATH = "app/.chroma"
_COLLECTION_NAME = "policies"


def get_collection():
    """Return the on-disk policies collection, creating it on first use."""
    client = chromadb.PersistentClient(path=_PERSIST_PATH)
    return client.get_or_create_collection(_COLLECTION_NAME)
