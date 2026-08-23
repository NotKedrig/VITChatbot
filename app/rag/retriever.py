"""
app/rag/retriever.py — ChromaDB retriever (Phase 1).

Given a natural-language query, embeds it using the local embedder and
queries the appropriate ChromaDB collection, returning top-k passages with
source metadata attached.

No LLM calls: query embedding uses the same local sentence-transformers
model as the ingestion pipeline (identical embedding space required for
meaningful similarity search).

Public API
----------
retrieve(query, collection_name, top_k, chroma_persist_dir, embedding_model_name)
    → list[RetrievedChunk]
"""

import logging
from typing import NamedTuple

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.llm.embeddings import get_embedder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class RetrievedChunk(NamedTuple):
    """A single chunk returned by the retriever."""
    chunk_id: str
    doc_id: str
    title: str
    text: str
    similarity_score: float   # cosine similarity ∈ [0, 1] (higher = more similar)
    chunk_index: int
    chunking_strategy: str
    char_start: int
    char_end: int


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

def _get_chroma_client(persist_dir: str) -> chromadb.ClientAPI:
    from pathlib import Path
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def retrieve(
    query: str,
    collection_name: str,
    top_k: int = 5,
    chroma_persist_dir: str | None = None,
    embedding_model_name: str | None = None,
) -> list[RetrievedChunk]:
    """
    Retrieve the top-k most similar chunks to *query* from *collection_name*.

    Args:
        query:                Natural-language query string.
        collection_name:      Name of the ChromaDB collection to search.
        top_k:                Number of results to return.
        chroma_persist_dir:   ChromaDB directory (default from settings).
        embedding_model_name: Embedding model (default from settings).

    Returns:
        List of RetrievedChunk, sorted by descending similarity_score.

    Raises:
        ValueError: if the collection does not exist.
    """
    from app.config import settings as _settings

    chroma_persist_dir = chroma_persist_dir or _settings.chroma_persist_dir
    embedding_model_name = embedding_model_name or _settings.embedding_model_name

    embedder = get_embedder(embedding_model_name)
    query_vector = embedder.embed_one(query)

    chroma = _get_chroma_client(chroma_persist_dir)

    try:
        collection = chroma.get_collection(name=collection_name)
    except Exception as exc:
        raise ValueError(
            f"ChromaDB collection '{collection_name}' not found. "
            "Run ingest_documents() first."
        ) from exc

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[RetrievedChunk] = []
    if not results["ids"] or not results["ids"][0]:
        return chunks

    for chunk_id, text, meta, distance in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # Chroma returns cosine distance ∈ [0, 2] when space="cosine"
        # Convert to similarity: similarity = 1 - distance/2
        similarity = max(0.0, 1.0 - distance / 2.0)

        chunks.append(RetrievedChunk(
            chunk_id=chunk_id,
            doc_id=meta.get("doc_id", ""),
            title=meta.get("title", ""),
            text=text,
            similarity_score=round(similarity, 4),
            chunk_index=int(meta.get("chunk_index", -1)),
            chunking_strategy=meta.get("chunking_strategy", ""),
            char_start=int(meta.get("char_start", 0)),
            char_end=int(meta.get("char_end", 0)),
        ))

    # Sort by descending similarity (Chroma returns by ascending distance already,
    # but we re-sort to be explicit after the similarity conversion)
    chunks.sort(key=lambda c: c.similarity_score, reverse=True)

    logger.debug(
        "Retrieval complete",
        extra={
            "query": query[:100],
            "collection": collection_name,
            "top_k": top_k,
            "returned": len(chunks),
        },
    )
    return chunks
