"""Chunking comparison experiment: naive fixed-character vs section-based.

Run: python3 scripts/chunking_experiment.py
"""

import glob

import chromadb

from rag.chunking import naive_chunk, section_chunk
from rag.embeddings import embed

client = chromadb.Client()  # in-memory, throwaway — not the app's real store
naive_collection = client.create_collection("naive")
section_collection = client.create_collection("section")

for path in glob.glob("samples/policies/*.md"):
    text = open(path).read()
    source = path.split("/")[-1]

    naive_chunks = naive_chunk(text, source=source)
    naive_collection.add(
        documents=[c.text for c in naive_chunks],
        embeddings=embed([c.text for c in naive_chunks]),
        metadatas=[c.metadata for c in naive_chunks],
        ids=[f"{source}-naive-{i}" for i in range(len(naive_chunks))],
    )

    section_chunks = section_chunk(text, source=source)
    section_collection.add(
        documents=[c.text for c in section_chunks],
        embeddings=embed([c.text for c in section_chunks]),
        metadatas=[c.metadata for c in section_chunks],
        ids=[f"{source}-section-{i}" for i in range(len(section_chunks))],
    )


def show(collection, label):
    query = "How many paid sick days do employees get in Germany?"
    result = collection.query(query_embeddings=embed([query]), n_results=2)
    print(f"=== {label} ===")
    for doc, meta in zip(result["documents"][0], result["metadatas"][0]):
        print(meta, "->", doc[:150])
        print()


show(naive_collection, "NAIVE")
show(section_collection, "SECTION-BASED")
