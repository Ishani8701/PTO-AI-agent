"""Two chunking strategies for policy documents, so their difference is
visible rather than assumed. See scripts/chunking_experiment.py for a
side-by-side comparison against real queries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


def naive_chunk(text: str, source: str, chunk_size: int = 300) -> list[Chunk]:
    """Fixed-character chunking. Cuts every `chunk_size` characters with no
    regard for headings, paragraphs, or country boundaries. This is the
    baseline every RAG tutorial starts with, and it's a trap: it will happily
    slice a chunk in half across two countries' sections.
    """
    return [
        Chunk(text=text[i : i + chunk_size], metadata={"source": source})
        for i in range(0, len(text), chunk_size)
    ]


_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_HEADER_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def section_chunk(text: str, source: str) -> list[Chunk]:
    """Split on the document's own `##` headers (Global, US, IN, DE, UK).
    Each chunk is exactly one section's content, tagged with which section
    (country, or "Global") it came from. This respects the document's real
    structure instead of an arbitrary character count.

    Each chunk's text is prefixed with the document's own `#` title, so a
    chunk that never restates its topic in its own words (e.g. "US employees
    receive 15 days of PTO...") still carries that context — a chunk isolated
    from its parent document shouldn't lose the context that document gave it.
    """
    title_match = _TITLE_RE.search(text)
    title = title_match.group(1).strip() if title_match else source

    matches = list(_HEADER_RE.finditer(text))
    chunks = []
    for idx, match in enumerate(matches):
        header = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        chunks.append(
            Chunk(
                text=f"{title} — {header}: {body}",
                metadata={"source": source, "section": header},
            )
        )
    return chunks
