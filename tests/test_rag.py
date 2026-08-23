"""
tests/test_rag.py — Phase 1: RAG pipeline tests.

Tests:
  1. Ingest with fixed_size strategy → Chroma collection created, chunks in DB.
  2. Ingest with semantic strategy → separate Chroma collection, chunks in DB.
  3. Retrieval: 5 hand-written queries verified against expected source documents.
  4. Citation metadata: correct attachment and traceability (doc_id, char offsets,
     strategy, chunk_index).

All tests use:
  - A temporary directory for ChromaDB (isolated per test session).
  - An in-memory SQLite database (no Postgres required).
  - The actual sample documents under data/raw_docs/ (real content, real embeddings).
  - The real all-MiniLM-L6-v2 sentence-transformers model (downloads once, cached).

Queries are intentionally paraphrased — NOT copied verbatim from the documents —
to test genuine retrieval rather than exact string matching.
"""

import os
import pytest
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RAW_DOCS_DIR = str(Path(__file__).parent.parent / "data" / "raw_docs")
COLLECTION_PREFIX = "test_kb"


@pytest.fixture(scope="session")
def tmp_dirs():
    """Create a single temporary directory used for all RAG tests in this session."""
    with tempfile.TemporaryDirectory(prefix="vitian_rag_test_", ignore_cleanup_errors=True) as tmp:
        chroma_dir = str(Path(tmp) / "chroma")
        db_path = str(Path(tmp) / "test.db")
        yield {
            "chroma_dir": chroma_dir,
            "db_url": f"sqlite:///{db_path}",
        }


@pytest.fixture(scope="session")
def ingest_fixed(tmp_dirs):
    """Ingest all sample docs with fixed_size strategy (once per session)."""
    from app.rag.ingest import ingest_documents
    result = ingest_documents(
        raw_docs_dir=RAW_DOCS_DIR,
        chroma_persist_dir=tmp_dirs["chroma_dir"],
        chunking_strategy="fixed_size",
        chunk_size=512,
        chunk_overlap=64,
        embedding_model_name="all-MiniLM-L6-v2",
        database_url=tmp_dirs["db_url"],
        collection_prefix=COLLECTION_PREFIX,
        force_reingest=False,
    )
    return result


@pytest.fixture(scope="session")
def ingest_semantic(tmp_dirs):
    """Ingest all sample docs with semantic strategy (once per session)."""
    from app.rag.ingest import ingest_documents
    result = ingest_documents(
        raw_docs_dir=RAW_DOCS_DIR,
        chroma_persist_dir=tmp_dirs["chroma_dir"],
        chunking_strategy="semantic",
        embedding_model_name="all-MiniLM-L6-v2",
        database_url=tmp_dirs["db_url"],
        collection_prefix=COLLECTION_PREFIX,
        force_reingest=False,
    )
    return result


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _retrieve(query: str, strategy: str, tmp_dirs: dict, top_k: int = 5):
    from app.rag.retriever import retrieve
    collection_name = f"{COLLECTION_PREFIX}_{strategy}"
    return retrieve(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        chroma_persist_dir=tmp_dirs["chroma_dir"],
        embedding_model_name="all-MiniLM-L6-v2",
    )


# ---------------------------------------------------------------------------
# Section 1: Ingest tests
# ---------------------------------------------------------------------------

class TestIngestFixedSize:
    def test_docs_ingested(self, ingest_fixed):
        """At least 8 documents must be ingested."""
        assert ingest_fixed.docs_ingested >= 8, (
            f"Expected ≥8 docs, got {ingest_fixed.docs_ingested}"
        )

    def test_chunks_created(self, ingest_fixed):
        """At least one chunk must be produced per document."""
        assert ingest_fixed.chunks_created >= ingest_fixed.docs_ingested

    def test_collection_name(self, ingest_fixed):
        """Collection name must include the strategy."""
        assert "fixed_size" in ingest_fixed.collection_name

    def test_strategy_recorded(self, ingest_fixed):
        assert ingest_fixed.chunking_strategy == "fixed_size"


class TestIngestSemantic:
    def test_docs_ingested(self, ingest_semantic):
        """At least 8 documents must be ingested with semantic strategy."""
        assert ingest_semantic.docs_ingested >= 8

    def test_chunks_created(self, ingest_semantic):
        assert ingest_semantic.chunks_created >= ingest_semantic.docs_ingested

    def test_collection_name(self, ingest_semantic):
        assert "semantic" in ingest_semantic.collection_name

    def test_separate_collection_from_fixed(self, ingest_fixed, ingest_semantic):
        """The two strategies must produce distinct Chroma collections."""
        assert ingest_fixed.collection_name != ingest_semantic.collection_name


class TestDatabaseChunks:
    def test_fixed_chunks_in_db(self, ingest_fixed, tmp_dirs):
        """PostgreSQL/SQLite must contain chunk rows for fixed_size strategy."""
        from app.db.state.db import get_session
        from app.db.state.models import DocumentChunk
        with get_session(tmp_dirs["db_url"]) as db:
            count = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.chunking_strategy == "fixed_size")
                .count()
            )
        assert count >= ingest_fixed.docs_ingested

    def test_semantic_chunks_in_db(self, ingest_semantic, tmp_dirs):
        """SQLite must contain chunk rows for semantic strategy."""
        from app.db.state.db import get_session
        from app.db.state.models import DocumentChunk
        with get_session(tmp_dirs["db_url"]) as db:
            count = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.chunking_strategy == "semantic")
                .count()
            )
        assert count >= ingest_semantic.docs_ingested

    def test_source_documents_in_db(self, ingest_fixed, tmp_dirs):
        """SourceDocument rows must exist for all ingested files."""
        from app.db.state.db import get_session
        from app.db.state.models import SourceDocument
        with get_session(tmp_dirs["db_url"]) as db:
            count = db.query(SourceDocument).count()
        assert count >= 8

    def test_chunk_metadata_completeness(self, ingest_fixed, tmp_dirs):
        """Every chunk must have a non-empty text_preview and valid char offsets."""
        from app.db.state.db import get_session
        from app.db.state.models import DocumentChunk
        with get_session(tmp_dirs["db_url"]) as db:
            chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.chunking_strategy == "fixed_size")
                .limit(20)
                .all()
            )
            # Read all attributes inside the session to avoid DetachedInstanceError
            # (SQLAlchemy expires attributes on commit; accessing them after session
            # close triggers a lazy load which fails on a detached instance).
            chunk_data = [
                (c.chunk_id, c.text_preview, c.char_start, c.char_end)
                for c in chunks
            ]
        for chunk_id, text_preview, char_start, char_end in chunk_data:
            assert text_preview, f"Empty text_preview for {chunk_id}"
            assert char_start >= 0
            assert char_end > char_start


# ---------------------------------------------------------------------------
# Section 2: Retrieval tests — 5 hand-written queries per strategy
# Queries are paraphrased from the documents (not verbatim copies).
# ---------------------------------------------------------------------------

# Each entry: (query, expected_doc_id_fragment, description)
RETRIEVAL_TEST_CASES = [
    (
        "What is the minimum GPA required to apply at NovaTech?",
        "novatech",
        "NovaTech CGPA eligibility requirement",
    ),
    (
        "How many interview rounds does Meridian FinTech conduct for software engineers?",
        "meridian",
        "Meridian FinTech interview round count",
    ),
    (
        "Which programming language is used for embedded firmware at the robotics company?",
        "aether",
        "Aether Robotics embedded C/C++ language",
    ),
    (
        "How should I format my resume projects section for a tech job application?",
        "resume",
        "Resume project bullet format guidance",
    ),
    (
        "What topics are covered in the aptitude test for campus placements?",
        "aptitude",
        "General aptitude exam topics",
    ),
]


class TestRetrievalFixedSize:
    @pytest.mark.parametrize("query,expected_doc_fragment,description",
                             RETRIEVAL_TEST_CASES)
    def test_retrieval_returns_expected_doc(
        self, query, expected_doc_fragment, description,
        ingest_fixed, tmp_dirs
    ):
        """
        Top-5 results must include at least one chunk from the expected source document.
        Query is a paraphrase — not copied verbatim from the document.
        """
        results = _retrieve(query, "fixed_size", tmp_dirs, top_k=5)
        assert results, f"No results returned for: {query!r}"
        doc_ids = [r.doc_id for r in results]
        assert any(expected_doc_fragment in d for d in doc_ids), (
            f"[fixed_size] Query: {description!r}\n"
            f"  Expected doc containing '{expected_doc_fragment}' in top-5\n"
            f"  Got: {doc_ids}"
        )

    def test_results_have_similarity_scores(self, ingest_fixed, tmp_dirs):
        """Every returned chunk must have a non-negative similarity score."""
        results = _retrieve(
            "What salary does NovaTech offer for entry-level engineers?",
            "fixed_size", tmp_dirs, top_k=5,
        )
        for r in results:
            assert r.similarity_score >= 0.0
            assert r.similarity_score <= 1.0

    def test_results_sorted_by_similarity(self, ingest_fixed, tmp_dirs):
        """Results must be sorted highest similarity first."""
        results = _retrieve(
            "Tell me about the NovaTech online assessment format",
            "fixed_size", tmp_dirs, top_k=5,
        )
        for i in range(len(results) - 1):
            assert results[i].similarity_score >= results[i + 1].similarity_score


class TestRetrievalSemantic:
    @pytest.mark.parametrize("query,expected_doc_fragment,description",
                             RETRIEVAL_TEST_CASES)
    def test_retrieval_returns_expected_doc(
        self, query, expected_doc_fragment, description,
        ingest_semantic, tmp_dirs
    ):
        """Same 5 queries must retrieve the correct source with semantic chunking."""
        results = _retrieve(query, "semantic", tmp_dirs, top_k=5)
        assert results, f"No results returned for: {query!r}"
        doc_ids = [r.doc_id for r in results]
        assert any(expected_doc_fragment in d for d in doc_ids), (
            f"[semantic] Query: {description!r}\n"
            f"  Expected doc containing '{expected_doc_fragment}' in top-5\n"
            f"  Got: {doc_ids}"
        )


# ---------------------------------------------------------------------------
# Section 3: Citation metadata tests
# ---------------------------------------------------------------------------

class TestCitations:
    def test_citation_format(self, ingest_fixed, tmp_dirs):
        """format_citations() must return one Citation per chunk with correct fields."""
        from app.rag.citations import format_citations
        results = _retrieve(
            "What are the CGPA requirements for NovaTech?",
            "fixed_size", tmp_dirs, top_k=3,
        )
        citations = format_citations(results)

        assert len(citations) == len(results)
        for i, citation in enumerate(citations):
            assert citation.citation_number == i + 1
            assert citation.chunk_id, "chunk_id must not be empty"
            assert citation.doc_id, "doc_id must not be empty"
            assert citation.title, "title must not be empty"
            assert citation.text_snippet, "text_snippet must not be empty"
            assert len(citation.text_snippet) <= 210  # 200 chars + "…"
            assert citation.char_start >= 0
            assert citation.char_end > citation.char_start
            assert citation.chunking_strategy in ("fixed_size", "semantic")
            assert "fixed_size" in citation.source_ref or "semantic" in citation.source_ref

    def test_citation_doc_id_traceable_to_db(self, ingest_fixed, tmp_dirs):
        """Every citation's doc_id must resolve to a SourceDocument row in the DB."""
        from app.rag.citations import format_citations
        from app.db.state.db import get_session
        from app.db.state.models import SourceDocument

        results = _retrieve(
            "NovaTech interview rounds technical assessment",
            "fixed_size", tmp_dirs, top_k=5,
        )
        citations = format_citations(results)

        with get_session(tmp_dirs["db_url"]) as db:
            for citation in citations:
                doc = (
                    db.query(SourceDocument)
                    .filter(SourceDocument.doc_id == citation.doc_id)
                    .first()
                )
                assert doc is not None, (
                    f"Citation doc_id '{citation.doc_id}' has no matching "
                    f"SourceDocument row in the database."
                )

    def test_chunk_id_traceable_to_db(self, ingest_fixed, tmp_dirs):
        """Every citation's chunk_id must resolve to a DocumentChunk row."""
        from app.rag.citations import format_citations
        from app.db.state.db import get_session
        from app.db.state.models import DocumentChunk

        results = _retrieve(
            "eligibility criteria for placement at NovaTech",
            "fixed_size", tmp_dirs, top_k=5,
        )
        citations = format_citations(results)

        with get_session(tmp_dirs["db_url"]) as db:
            for citation in citations:
                chunk = (
                    db.query(DocumentChunk)
                    .filter(DocumentChunk.chunk_id == citation.chunk_id)
                    .first()
                )
                assert chunk is not None, (
                    f"Citation chunk_id '{citation.chunk_id}' has no matching "
                    f"DocumentChunk row in the database."
                )

    def test_inline_citation_format(self, ingest_fixed, tmp_dirs):
        """format_inline() must produce a non-empty string with numbered citations."""
        from app.rag.citations import format_inline
        results = _retrieve("NovaTech HR round details", "fixed_size", tmp_dirs, top_k=3)
        inline = format_inline(results)
        assert inline.startswith("Sources:")
        assert "[1]" in inline
        if len(results) > 1:
            assert "[2]" in inline

    def test_to_dict_serialisable(self, ingest_fixed, tmp_dirs):
        """Citation.to_dict() must be JSON-serialisable."""
        import json
        from app.rag.citations import format_citations
        results = _retrieve("Aether Robotics interview process", "fixed_size", tmp_dirs, top_k=2)
        citations = format_citations(results)
        for c in citations:
            d = c.to_dict()
            json.dumps(d)  # must not raise
