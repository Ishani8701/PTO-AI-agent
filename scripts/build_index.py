"""Build (or rebuild) the policy document index.

Run this whenever samples/policies/*.md changes:

    python3 -m scripts.build_index
"""

import glob

from rag.chunking import section_chunk
from rag.embeddings import embed
from rag.store import get_collection

collection = get_collection()

for path in glob.glob("samples/policies/*.md"):
    text = open(path).read()
    source = path.split("/")[-1]
    chunks = section_chunk(text, source=source)
    collection.upsert(
        documents=[c.text for c in chunks],
        embeddings=embed([c.text for c in chunks]),
        metadatas=[c.metadata for c in chunks],
        ids=[f"{source}-{c.metadata['section']}" for c in chunks],
    )

print(f"Indexed {collection.count()} chunks into '{collection.name}'.")
