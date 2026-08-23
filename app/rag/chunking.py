"""
app/rag/chunking.py — Two chunking strategies behind one interface (Phase 1).

Strategies
----------
fixed_size_chunk(text, size, overlap)
    Splits text into overlapping windows of `size` characters with `overlap`
    characters of context carried over from the previous chunk.
    Respects word boundaries: never splits mid-word.

semantic_chunk(text)
    Paragraph/section-boundary-aware splitter that keeps semantically coherent
    units together.  A new chunk is started at:
      1. Markdown headings (lines starting with #).
      2. Blank-line-separated paragraphs when the accumulated chunk exceeds a
         minimum threshold.
    Chunks that exceed MAX_SEMANTIC_CHUNK_CHARS are split further at sentence
    boundaries to avoid very long passages.

Both functions return a list of ChunkResult named-tuples containing the chunk
text and the character offsets (char_start, char_end) into the original text,
enabling citation traceability (master plan Section 5, Experiment 4).

Config integration
------------------
The ingest pipeline selects a strategy via app/config.settings.chunking_strategy
("fixed_size" or "semantic").  Both strategies are kept in this module so
Experiment 4 can compare them on an otherwise-identical pipeline.
"""

import re
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class ChunkResult(NamedTuple):
    """A single chunk produced by either chunking strategy."""
    text: str
    char_start: int   # inclusive byte offset in the original document
    char_end: int     # exclusive byte offset in the original document


# ---------------------------------------------------------------------------
# Strategy 1: Fixed-size chunking
# ---------------------------------------------------------------------------

def fixed_size_chunk(
    text: str,
    size: int = 512,
    overlap: int = 64,
) -> list[ChunkResult]:
    """
    Split *text* into overlapping windows of *size* characters.

    Word-boundary-safe: after computing the nominal end position, we walk
    backwards to the nearest whitespace so that we never cut a word in half.
    The overlap region is taken from the end of the previous chunk.

    Args:
        text:    The full document text.
        size:    Target chunk size in characters (default 512).
        overlap: Number of characters of overlap with the previous chunk (default 64).

    Returns:
        List of ChunkResult with text, char_start, char_end.
    """
    if not text or size <= 0:
        return []
    if overlap >= size:
        raise ValueError(f"overlap ({overlap}) must be less than size ({size})")

    chunks: list[ChunkResult] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + size, text_len)

        # Snap to word boundary (unless we're at the very end of the text)
        if end < text_len:
            # Walk back to nearest whitespace
            snap = end
            while snap > start and not text[snap].isspace():
                snap -= 1
            if snap > start:
                end = snap

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(ChunkResult(text=chunk_text, char_start=start, char_end=end))

        # Next chunk starts (size - overlap) characters after the current start,
        # clamped so we never make negative progress.
        step = max(size - overlap, 1)
        start += step

    return chunks


# ---------------------------------------------------------------------------
# Strategy 2: Semantic chunking
# ---------------------------------------------------------------------------

# Thresholds (in characters) that drive splitting decisions
_MIN_SEMANTIC_CHUNK_CHARS = 200    # minimum before splitting at a paragraph boundary
_MAX_SEMANTIC_CHUNK_CHARS = 1200   # hard cap; split at sentence boundary above this
_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def semantic_chunk(text: str) -> list[ChunkResult]:
    """
    Split *text* at paragraph and section boundaries.

    Algorithm:
    1. Split at Markdown headings (# … ######) — always start a new chunk.
    2. Within a heading section, accumulate paragraphs (blank-line separated).
       When the accumulated text exceeds _MIN_SEMANTIC_CHUNK_CHARS and a
       paragraph boundary is found, emit the chunk.
    3. If a chunk would exceed _MAX_SEMANTIC_CHUNK_CHARS, split further at the
       nearest sentence boundary (period/exclamation/question followed by space).

    Args:
        text: The full document text (Markdown or plain text).

    Returns:
        List of ChunkResult with text, char_start, char_end.
    """
    if not text:
        return []

    chunks: list[ChunkResult] = []
    _flush_buffer(chunks, text)
    return chunks


def _flush_buffer(chunks: list[ChunkResult], text: str) -> None:
    """Worker that performs the actual semantic splitting."""
    # Step 1: split on heading boundaries first
    sections = _split_on_headings(text)

    for section_text, section_start in sections:
        # Step 2: split each section into paragraphs
        paragraphs = _split_paragraphs(section_text, section_start)
        _accumulate_paragraphs(chunks, paragraphs)


def _split_on_headings(text: str) -> list[tuple[str, int]]:
    """
    Return a list of (section_text, char_start_in_original) tuples,
    where each section starts at a heading (or at position 0 for pre-heading text).
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [(text, 0)]

    sections: list[tuple[str, int]] = []
    prev_end = 0

    # Text before the first heading
    if matches[0].start() > 0:
        sections.append((text[0:matches[0].start()], 0))
        prev_end = matches[0].start()

    for i, m in enumerate(matches):
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((text[m.start():next_start], m.start()))
        prev_end = next_start

    return sections


def _split_paragraphs(text: str, offset: int) -> list[tuple[str, int]]:
    """
    Split *text* on blank lines, returning (paragraph_text, char_start_in_original).
    """
    parts = re.split(r"\n\s*\n", text)
    paragraphs: list[tuple[str, int]] = []
    pos = 0
    for part in parts:
        idx = text.find(part, pos)
        if idx == -1:
            idx = pos
        stripped = part.strip()
        if stripped:
            paragraphs.append((stripped, offset + idx))
        pos = idx + len(part)
    return paragraphs


def _accumulate_paragraphs(
    chunks: list[ChunkResult],
    paragraphs: list[tuple[str, int]],
) -> None:
    """
    Greedily accumulate paragraphs into chunks, splitting when limits are hit.
    """
    buffer_parts: list[str] = []
    buffer_start: int = 0
    buffer_len: int = 0
    first = True

    def emit() -> None:
        nonlocal buffer_parts, buffer_start, buffer_len, first
        if not buffer_parts:
            return
        joined = "\n\n".join(buffer_parts)
        _emit_with_sentence_split(chunks, joined, buffer_start)
        buffer_parts = []
        buffer_len = 0
        first = True

    for para_text, para_start in paragraphs:
        para_len = len(para_text)

        if first:
            buffer_start = para_start
            first = False

        # If adding this paragraph would exceed the hard cap, emit first
        if buffer_len > 0 and buffer_len + para_len + 2 > _MAX_SEMANTIC_CHUNK_CHARS:
            emit()
            buffer_start = para_start

        buffer_parts.append(para_text)
        buffer_len += para_len + (2 if len(buffer_parts) > 1 else 0)

        # Soft split: if we've passed the minimum and this is a paragraph boundary
        if buffer_len >= _MIN_SEMANTIC_CHUNK_CHARS:
            emit()
            buffer_start = para_start  # reset (will be overwritten on next para)

    emit()  # flush remaining


def _emit_with_sentence_split(
    chunks: list[ChunkResult],
    text: str,
    char_start: int,
) -> None:
    """
    Emit *text* as one or more ChunkResults, splitting at sentence boundaries
    if len(text) > _MAX_SEMANTIC_CHUNK_CHARS.
    """
    if len(text) <= _MAX_SEMANTIC_CHUNK_CHARS:
        stripped = text.strip()
        if stripped:
            chunks.append(ChunkResult(
                text=stripped,
                char_start=char_start,
                char_end=char_start + len(text),
            ))
        return

    # Split at sentence boundaries
    sentences = _SENTENCE_END_RE.split(text)
    buffer = ""
    buf_start = char_start
    pos = 0

    for sentence in sentences:
        if len(buffer) + len(sentence) > _MAX_SEMANTIC_CHUNK_CHARS and buffer:
            stripped = buffer.strip()
            if stripped:
                chunks.append(ChunkResult(
                    text=stripped,
                    char_start=buf_start,
                    char_end=buf_start + len(buffer),
                ))
            buf_start = char_start + pos
            buffer = sentence
        else:
            buffer += (" " if buffer else "") + sentence
        pos += len(sentence) + 1  # +1 for the split whitespace

    if buffer.strip():
        chunks.append(ChunkResult(
            text=buffer.strip(),
            char_start=buf_start,
            char_end=buf_start + len(buffer),
        ))


# ---------------------------------------------------------------------------
# Dispatcher — select strategy by name
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    strategy: str,
    size: int = 512,
    overlap: int = 64,
) -> list[ChunkResult]:
    """
    Dispatch to the appropriate chunking strategy.

    Args:
        text:     The full document text.
        strategy: "fixed_size" or "semantic".
        size:     Used only for "fixed_size" strategy.
        overlap:  Used only for "fixed_size" strategy.

    Returns:
        List of ChunkResult.

    Raises:
        ValueError: if strategy is not recognised.
    """
    if strategy == "fixed_size":
        return fixed_size_chunk(text, size=size, overlap=overlap)
    elif strategy == "semantic":
        return semantic_chunk(text)
    else:
        raise ValueError(
            f"Unknown chunking strategy: {strategy!r}. "
            "Expected 'fixed_size' or 'semantic'."
        )
