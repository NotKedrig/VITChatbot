"""
app/rag/citations.py — Citation formatter (Phase 1).

Formats RetrievedChunk objects into structured citation records that are
traceable back to source documents, chunk positions, and the chunking
strategy used — satisfying the master plan's requirement for citations
traceable to source documents (Section 5, Experiments 1 and 4).

Public API
----------
format_citations(chunks) → list[Citation]
format_inline(chunks)    → str   (human-readable inline citation block)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rag.retriever import RetrievedChunk


# ---------------------------------------------------------------------------
# Citation dataclass
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    """
    A structured citation traceable to a specific chunk in a source document.

    Fields
    ------
    citation_number : 1-based index for display (e.g. [1], [2]).
    chunk_id        : Unique chunk identifier (e.g. "novatech_recruitment_guide__fixed_size__0004").
    doc_id          : Source document identifier (slug).
    title           : Human-readable document title.
    text_snippet    : First 200 characters of the retrieved chunk (for display).
    full_text       : Complete chunk text.
    similarity_score: Cosine similarity of the chunk to the query.
    chunk_index     : 0-based position of this chunk within the document.
    chunking_strategy: "fixed_size" or "semantic".
    char_start      : Byte offset of the chunk start in the original document.
    char_end        : Byte offset of the chunk end in the original document.
    source_ref      : Human-readable reference string (e.g. "NovaTech Recruitment Guide, chunk 4").
    """

    citation_number: int
    chunk_id: str
    doc_id: str
    title: str
    text_snippet: str
    full_text: str
    similarity_score: float
    chunk_index: int
    chunking_strategy: str
    char_start: int
    char_end: int
    source_ref: str = field(init=False)

    def __post_init__(self) -> None:
        self.source_ref = (
            f"{self.title}, chunk {self.chunk_index} "
            f"(chars {self.char_start}–{self.char_end}, "
            f"strategy: {self.chunking_strategy})"
        )

    def to_dict(self) -> dict:
        """Serialise to a plain dict (for JSON output in results CSVs)."""
        return {
            "citation_number": self.citation_number,
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "text_snippet": self.text_snippet,
            "similarity_score": self.similarity_score,
            "chunk_index": self.chunk_index,
            "chunking_strategy": self.chunking_strategy,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "source_ref": self.source_ref,
        }


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def format_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    """
    Convert a list of RetrievedChunk objects into Citation records.

    Args:
        chunks: List returned by app.rag.retriever.retrieve().

    Returns:
        List of Citation objects (1-based citation numbers, same order as input).
    """
    citations: list[Citation] = []
    for i, chunk in enumerate(chunks, start=1):
        snippet = chunk.text[:200].replace("\n", " ").strip()
        if len(chunk.text) > 200:
            snippet += "…"
        citations.append(Citation(
            citation_number=i,
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            title=chunk.title,
            text_snippet=snippet,
            full_text=chunk.text,
            similarity_score=chunk.similarity_score,
            chunk_index=chunk.chunk_index,
            chunking_strategy=chunk.chunking_strategy,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        ))
    return citations


def format_inline(chunks: list[RetrievedChunk]) -> str:
    """
    Produce a human-readable citation block for display in agent responses.

    Example output::

        Sources:
        [1] NovaTech Recruitment Guide (chunk 4, fixed_size) — similarity: 0.8732
            "Candidates from MCA programmes are also eligible for Software Engineer
            roles if they meet the CGPA threshold…"

        [2] NovaTech Interview Prep Guide (chunk 12, fixed_size) — similarity: 0.8105
            "NovaTech interviewers probe depth: if you mention a concept, expect a
            follow-up question one level deeper…"

    Args:
        chunks: List returned by app.rag.retriever.retrieve().

    Returns:
        Formatted multi-line string.
    """
    if not chunks:
        return "Sources: (none)"

    citations = format_citations(chunks)
    lines = ["Sources:"]
    for c in citations:
        lines.append(
            f"[{c.citation_number}] {c.title} "
            f"(chunk {c.chunk_index}, {c.chunking_strategy}) "
            f"— similarity: {c.similarity_score:.4f}"
        )
        lines.append(f'    "{c.text_snippet}"')
        lines.append("")
    return "\n".join(lines).rstrip()
