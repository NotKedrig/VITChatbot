"""
app/rag/ingest.py — Document ingestion pipeline (Phase 1).

Loads raw Markdown documents from data/raw_docs/, chunks them using the
configured strategy, embeds and upserts them into a ChromaDB collection,
and records chunk metadata in PostgreSQL.

No AWS S3: raw documents live on local disk only.
No LLM calls: embeddings are local (sentence-transformers).

Public API
----------
ingest_documents(
    raw_docs_dir,
    chroma_persist_dir,
    chunking_strategy,
    chunk_size,
    chunk_overlap,
    embedding_model_name,
    database_url,
    collection_prefix,
    force_reingest,
)

Each (chunking_strategy) produces a separate Chroma collection so that
Experiment 4 can compare them using an otherwise-identical pipeline.
Collection names follow the pattern:
    "<collection_prefix>_<chunking_strategy>"
e.g. "vitian_kb_fixed_size" and "vitian_kb_semantic".
"""

import hashlib
import logging
from pathlib import Path
from typing import NamedTuple

import chromadb
from chromadb.config import Settings as ChromaSettings
from sqlalchemy import delete

from app.rag.chunking import ChunkResult, chunk_text
from app.llm.embeddings import get_embedder
from app.db.state.db import create_tables, get_session
from app.db.state.models import SourceDocument, DocumentChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class IngestResult(NamedTuple):
    """Summary returned by ingest_documents()."""
    docs_ingested: int
    chunks_created: int
    collection_name: str
    chunking_strategy: str


# ---------------------------------------------------------------------------
# Chroma client factory
# ---------------------------------------------------------------------------

def _get_chroma_client(persist_dir: str) -> chromadb.ClientAPI:
    """Return a persistent ChromaDB client (local directory mode)."""
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _collection_name(prefix: str, strategy: str) -> str:
    return f"{prefix}_{strategy}"


# ---------------------------------------------------------------------------
# Core ingestion logic
# ---------------------------------------------------------------------------

def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _doc_id_from_path(path: Path) -> str:
    """Derive a human-readable doc_id from the file name (no extension)."""
    return path.stem.replace(" ", "_").lower()


def _title_from_content(content: str, doc_id: str) -> str:
    """Extract the first Markdown heading as the document title, fallback to doc_id."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return doc_id.replace("_", " ").title()


def ingest_documents(
    raw_docs_dir: str = "data/raw_docs",
    chroma_persist_dir: str | None = None,
    chunking_strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedding_model_name: str | None = None,
    database_url: str | None = None,
    collection_prefix: str = "vitian_kb",
    force_reingest: bool = False,
) -> IngestResult:
    """
    Ingest all Markdown documents in *raw_docs_dir* into ChromaDB and PostgreSQL.

    Args:
        raw_docs_dir:         Path to the directory containing raw .md documents.
        chroma_persist_dir:   ChromaDB persistence directory (default from settings).
        chunking_strategy:    "fixed_size" or "semantic" (default from settings).
        chunk_size:           Characters per fixed-size chunk (default from settings).
        chunk_overlap:        Overlap characters (default from settings).
        embedding_model_name: sentence-transformers model name (default from settings).
        database_url:         SQLAlchemy DB URL (default from settings; SQLite OK for tests).
        collection_prefix:    Prefix for the ChromaDB collection name.
        force_reingest:       If True, re-chunk and re-embed even if the doc is already
                              in the DB (useful for testing; production should leave False).

    Returns:
        IngestResult summary.
    """
    from app.config import settings as _settings

    chroma_persist_dir = chroma_persist_dir or _settings.chroma_persist_dir
    chunking_strategy = chunking_strategy or _settings.chunking_strategy
    chunk_size = chunk_size if chunk_size is not None else _settings.chunk_size
    chunk_overlap = chunk_overlap if chunk_overlap is not None else _settings.chunk_overlap
    embedding_model_name = embedding_model_name or _settings.embedding_model_name
    database_url = database_url  # None → get_session will read from settings

    logger.info(
        "Ingest started",
        extra={
            "raw_docs_dir": raw_docs_dir,
            "chunking_strategy": chunking_strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "embedding_model_name": embedding_model_name,
            "chroma_persist_dir": chroma_persist_dir,
        },
    )

    # --- Database setup ---
    create_tables(database_url)

    # --- Chroma setup ---
    chroma = _get_chroma_client(chroma_persist_dir)
    coll_name = _collection_name(collection_prefix, chunking_strategy)
    collection = chroma.get_or_create_collection(
        name=coll_name,
        metadata={"hnsw:space": "cosine"},
    )

    # --- Embedder ---
    embedder = get_embedder(embedding_model_name)

    # --- Discover documents ---
    raw_dir = Path(raw_docs_dir)
    if not raw_dir.exists():
        raise FileNotFoundError(f"raw_docs_dir not found: {raw_docs_dir}")

    doc_paths = sorted(raw_dir.glob("*.md"))
    if not doc_paths:
        logger.warning("No .md files found in %s", raw_docs_dir)
        return IngestResult(0, 0, coll_name, chunking_strategy)

    docs_ingested = 0
    total_chunks = 0

    with get_session(database_url) as db:
        for doc_path in doc_paths:
            raw_bytes = doc_path.read_bytes()
            content = raw_bytes.decode("utf-8", errors="replace")
            file_hash = _sha256(raw_bytes)
            doc_id = _doc_id_from_path(doc_path)
            title = _title_from_content(content, doc_id)

            # Check if already ingested with the same hash (skip unless forced)
            existing: SourceDocument | None = (
                db.query(SourceDocument)
                .filter(SourceDocument.doc_id == doc_id)
                .first()
            )

            if existing and existing.file_hash == file_hash and not force_reingest:
                # Check if chunks for this strategy already exist
                existing_chunks = (
                    db.query(DocumentChunk)
                    .filter(
                        DocumentChunk.doc_id == doc_id,
                        DocumentChunk.chunking_strategy == chunking_strategy,
                    )
                    .count()
                )
                if existing_chunks > 0:
                    logger.debug(
                        "Skipping already-ingested doc",
                        extra={"doc_id": doc_id, "strategy": chunking_strategy},
                    )
                    total_chunks += existing_chunks
                    continue

            logger.info("Ingesting document", extra={"doc_id": doc_id, "title": title})

            # --- Upsert SourceDocument row ---
            if existing is None:
                source_doc = SourceDocument(
                    doc_id=doc_id,
                    title=title,
                    file_path=str(doc_path.resolve()),
                    file_hash=file_hash,
                    char_count=len(content),
                )
                db.add(source_doc)
                db.flush()  # populate auto-id without committing
            else:
                existing.title = title
                existing.file_hash = file_hash
                existing.char_count = len(content)
                source_doc = existing

            # --- Chunk ---
            chunk_results: list[ChunkResult] = chunk_text(
                content,
                strategy=chunking_strategy,
                size=chunk_size,
                overlap=chunk_overlap,
            )

            if not chunk_results:
                logger.warning("No chunks produced for %s", doc_id)
                continue

            # --- Embed ---
            texts = [cr.text for cr in chunk_results]
            vectors = embedder.embed(texts)

            # --- Upsert into Chroma ---
            chroma_ids: list[str] = []
            chroma_docs: list[str] = []
            chroma_metas: list[dict] = []
            chroma_embeds: list[list[float]] = []
            db_chunks: list[DocumentChunk] = []

            for idx, (cr, vec) in enumerate(zip(chunk_results, vectors)):
                chunk_id = f"{doc_id}__{chunking_strategy}__{idx:04d}"
                chroma_ids.append(chunk_id)
                chroma_docs.append(cr.text)
                chroma_embeds.append(vec)
                chroma_metas.append({
                    "doc_id": doc_id,
                    "title": title,
                    "chunk_index": idx,
                    "chunking_strategy": chunking_strategy,
                    "char_start": cr.char_start,
                    "char_end": cr.char_end,
                })

                db_chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    chunk_index=idx,
                    chunking_strategy=chunking_strategy,
                    char_start=cr.char_start,
                    char_end=cr.char_end,
                    text_preview=cr.text[:256],
                    chroma_collection=coll_name,
                ))

            # Delete existing chunks for this doc+strategy before re-inserting
            db.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.doc_id == doc_id,
                    DocumentChunk.chunking_strategy == chunking_strategy,
                )
            )

            collection.upsert(
                ids=chroma_ids,
                documents=chroma_docs,
                embeddings=chroma_embeds,
                metadatas=chroma_metas,
            )

            for dbc in db_chunks:
                db.add(dbc)

            docs_ingested += 1
            total_chunks += len(chunk_results)
            logger.info(
                "Document ingested",
                extra={
                    "doc_id": doc_id,
                    "chunks": len(chunk_results),
                    "strategy": chunking_strategy,
                },
            )

    logger.info(
        "Ingest complete",
        extra={
            "docs_ingested": docs_ingested,
            "total_chunks": total_chunks,
            "collection": coll_name,
        },
    )
    return IngestResult(
        docs_ingested=docs_ingested,
        chunks_created=total_chunks,
        collection_name=coll_name,
        chunking_strategy=chunking_strategy,
    )
