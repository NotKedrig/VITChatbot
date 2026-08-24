"""
app/db/state/models.py — SQLAlchemy ORM models (Phase 1).

Tables:
  - source_documents: one row per ingested raw document.
  - document_chunks:  one row per chunk produced during ingestion,
                      linked back to source_documents.

Student state, plan, progress, and replanning-log tables are added in Phase 7.
No AWS storage: all data lives in local PostgreSQL.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    ForeignKey,
    Index,
    JSON,
    Boolean,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Source documents
# ---------------------------------------------------------------------------

class SourceDocument(Base):
    """
    Represents one raw document that has been ingested into the knowledge base.

    doc_id is a human-readable slug derived from the filename (without extension),
    e.g. "novatech_recruitment_guide".
    """

    __tablename__ = "source_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(255), nullable=False, unique=True, index=True)
    title = Column(String(512), nullable=False)
    file_path = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=True)   # SHA-256 of raw file content
    char_count = Column(Integer, nullable=True)
    ingested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    chunks = relationship(
        "DocumentChunk",
        back_populates="source_document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<SourceDocument doc_id={self.doc_id!r}>"


# ---------------------------------------------------------------------------
# Document chunks
# ---------------------------------------------------------------------------

class DocumentChunk(Base):
    """
    Represents one chunk produced by the ingestion pipeline.

    chunk_id is globally unique across all collections:
        "<doc_id>__<strategy>__<index>"
    e.g. "novatech_recruitment_guide__fixed_size__000"

    char_start and char_end are byte offsets into the *original* document text,
    enabling citation lookup to trace a chunk back to its exact position in the
    source file.
    """

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(String(512), nullable=False, unique=True, index=True)
    doc_id = Column(
        String(255),
        ForeignKey("source_documents.doc_id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index = Column(Integer, nullable=False)  # 0-based position within the doc
    chunking_strategy = Column(String(64), nullable=False)  # "fixed_size" | "semantic"
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    text_preview = Column(String(256), nullable=True)  # first 256 chars for debugging
    chroma_collection = Column(String(255), nullable=True)  # which Chroma collection
    ingested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    source_document = relationship("SourceDocument", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("doc_id", "chunk_index", "chunking_strategy",
                         name="uq_chunk_doc_index_strategy"),
        Index("idx_chunks_doc_strategy", "doc_id", "chunking_strategy"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk chunk_id={self.chunk_id!r} "
            f"strategy={self.chunking_strategy!r}>"
        )


# ---------------------------------------------------------------------------
# Student State & Progress
# ---------------------------------------------------------------------------

class StudentProfile(Base):
    """
    Tracks the student's context and persistent skill profile across the application.
    """
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(255), nullable=False, unique=True, index=True)
    target_companies = Column(JSON, nullable=True) # List of strings
    skill_profile = Column(JSON, nullable=True)    # Dict of topic -> "weak", "mastered", etc.
    available_time = Column(String(255), nullable=True)
    
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PerformanceLog(Base):
    """
    Tracks individual test/mock scores reported by the student.
    """
    __tablename__ = "performance_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(
        String(255),
        ForeignKey("student_profiles.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic = Column(String(255), nullable=False)
    score = Column(Integer, nullable=False) # 0-100 percentage
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    is_struggle = Column(Boolean, nullable=False, default=False)
    is_mastery = Column(Boolean, nullable=False, default=False)
    
    student = relationship("StudentProfile", backref="performance_logs")


class PlanRevisionLog(Base):
    """
    Audit log of adaptive plan revisions.
    """
    __tablename__ = "plan_revision_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(
        String(255),
        ForeignKey("student_profiles.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    triggering_signal = Column(String(255), nullable=False) # e.g. "struggle", "mastery"
    affected_topic = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    
    student = relationship("StudentProfile", backref="plan_revisions")

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class Notification(Base):
    """
    Tracks scheduled and dispatched local notifications.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(
        String(255),
        ForeignKey("student_profiles.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message = Column(Text, nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(64), nullable=False, default="pending") # pending, dispatched
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    
    student = relationship("StudentProfile", backref="notifications")

# ---------------------------------------------------------------------------
# Study Plans
# ---------------------------------------------------------------------------

class StudyPlan(Base):
    """
    Tracks the active study plan for a student.
    """
    __tablename__ = "study_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(
        String(255),
        ForeignKey("student_profiles.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    is_active = Column(Boolean, nullable=False, default=True)
    
    student = relationship("StudentProfile", backref="study_plans")
