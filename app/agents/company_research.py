"""
app/agents/company_research.py — RAG-grounded company research agent (Phase 2).

Takes a natural-language question, retrieves relevant passages from ChromaDB
using app/rag/retriever.py, constructs a context-augmented prompt, generates
an answer via app/llm/provider.py, and returns the answer + formatted citations.

This agent is used directly by Experiment 1 as the "RAG system" being evaluated.
It is NOT a LangGraph node yet — that integration happens in Phase 4.

No AWS services.  No LLM calls for retrieval — embeddings are local.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.rag.retriever import RetrievedChunk, retrieve
from app.rag.citations import Citation, format_citations, format_inline
from app.llm.provider import LLMResponse, get_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load prompt template once at import time
# ---------------------------------------------------------------------------

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "company_research.txt"
_VANILLA_PATH = Path(__file__).parent.parent.parent / "prompts" / "vanilla_baseline.txt"


def _load_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Public response types
# ---------------------------------------------------------------------------

@dataclass
class RAGAnswer:
    """Answer produced by the RAG-grounded agent."""
    question: str
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
    llm_response: LLMResponse
    collection_name: str

    @property
    def cited_doc_ids(self) -> list[str]:
        """Unique source doc IDs cited in this answer."""
        return list(dict.fromkeys(c.doc_id for c in self.citations))


@dataclass
class VanillaAnswer:
    """Answer produced by the vanilla (no-retrieval) baseline."""
    question: str
    answer: str
    llm_response: LLMResponse


# ---------------------------------------------------------------------------
# RAG-grounded agent
# ---------------------------------------------------------------------------

def answer_with_rag(
    question: str,
    collection_name: str,
    top_k: int | None = None,
    chroma_persist_dir: str | None = None,
    embedding_model_name: str | None = None,
    temperature: float = 0.0,
    use_cache: bool = True,
) -> RAGAnswer:
    """
    Retrieve relevant passages and generate a grounded answer.

    Args:
        question:             Natural-language question.
        collection_name:      ChromaDB collection to search (e.g. "vitian_kb_fixed_size").
        top_k:                Number of passages to retrieve (default from settings).
        chroma_persist_dir:   ChromaDB directory (default from settings).
        embedding_model_name: Embedding model (default from settings).
        temperature:          LLM sampling temperature (0.0 for determinism).
        use_cache:            Use LLM response cache.

    Returns:
        RAGAnswer with answer text, citations, and provenance metadata.
    """
    from app.config import settings
    top_k = top_k if top_k is not None else settings.top_k_retrieval

    # --- Retrieve ---
    chunks: list[RetrievedChunk] = retrieve(
        query=question,
        collection_name=collection_name,
        top_k=top_k,
        chroma_persist_dir=chroma_persist_dir,
        embedding_model_name=embedding_model_name,
    )

    # --- Build context block ---
    if chunks:
        context_lines = []
        for i, chunk in enumerate(chunks, start=1):
            context_lines.append(
                f"[Source {i}: {chunk.title}]\n{chunk.text}"
            )
        context = "\n\n---\n\n".join(context_lines)
    else:
        context = "(No relevant passages retrieved.)"

    # --- Build prompt ---
    template = _load_prompt(_PROMPT_PATH)
    prompt = template.format(context=context, question=question)

    # --- Generate ---
    provider = get_provider()
    llm_response = provider.complete(
        prompt=prompt,
        temperature=temperature,
        use_cache=use_cache,
    )

    # --- Format citations ---
    citations = format_citations(chunks)

    logger.info(
        "RAG answer generated",
        extra={
            "question": question[:80],
            "chunks_retrieved": len(chunks),
            "model": llm_response.model_name,
            "cached": llm_response.cached,
        },
    )

    return RAGAnswer(
        question=question,
        answer=llm_response.text,
        citations=citations,
        retrieved_chunks=chunks,
        llm_response=llm_response,
        collection_name=collection_name,
    )


# ---------------------------------------------------------------------------
# Vanilla baseline
# ---------------------------------------------------------------------------

def answer_vanilla(
    question: str,
    temperature: float = 0.0,
    use_cache: bool = True,
) -> VanillaAnswer:
    """
    Generate an answer WITHOUT retrieved context (vanilla baseline).

    Same LLM, same question, no RAG.  Used as the Experiment 1 comparator.

    Args:
        question:    Natural-language question.
        temperature: LLM sampling temperature.
        use_cache:   Use LLM response cache.

    Returns:
        VanillaAnswer with answer text and provenance metadata.
    """
    template = _load_prompt(_VANILLA_PATH)
    prompt = template.format(question=question)

    provider = get_provider()
    llm_response = provider.complete(
        prompt=prompt,
        temperature=temperature,
        use_cache=use_cache,
    )

    logger.info(
        "Vanilla answer generated",
        extra={
            "question": question[:80],
            "model": llm_response.model_name,
            "cached": llm_response.cached,
        },
    )

    return VanillaAnswer(
        question=question,
        answer=llm_response.text,
        llm_response=llm_response,
    )
