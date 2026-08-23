"""
app/llm/embeddings.py — Local embedding wrapper (Phase 1).

Wraps a sentence-transformers model behind a provider-style interface so that
a hosted embedding API (e.g. OpenAI text-embedding-3-small) can be swapped in
later without touching any caller.

Design
------
- Default model: all-MiniLM-L6-v2 (22 M params, fast, 384-dim vectors).
  Configurable via app/config.settings.embedding_model_name.
- The model is downloaded from HuggingFace on first use and cached locally
  in the default sentence-transformers cache directory (~/.cache/huggingface).
- No LLM cache (app/llm/cache.py) is used here: embeddings are deterministic
  for a given model, so re-computation is idempotent.  Caching would only help
  with throughput; a later phase can add it if needed.
- Thread-safe: SentenceTransformer.encode() releases the GIL; the model object
  is safe to share across threads.

Interface contract (for future provider swap)
----------------------------------------------
Any replacement class must implement:

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_one(self, text: str) -> list[float]:
        ...

    @property
    def dimension(self) -> int:
        ...

    @property
    def model_name(self) -> str:
        ...
"""

import logging
from functools import cached_property
from typing import Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol (interface contract)
# ---------------------------------------------------------------------------

class EmbeddingProvider(Protocol):
    """Interface that all embedding providers must satisfy."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns a list of float vectors."""
        ...

    def embed_one(self, text: str) -> list[float]:
        """Embed a single text string. Returns a float vector."""
        ...

    @property
    def dimension(self) -> int:
        """Output vector dimensionality."""
        ...

    @property
    def model_name(self) -> str:
        """Fully-qualified model name/identifier."""
        ...


# ---------------------------------------------------------------------------
# Local sentence-transformers implementation
# ---------------------------------------------------------------------------

class LocalEmbedder:
    """
    Local embedding provider backed by a sentence-transformers model.

    The model is loaded lazily on first use to avoid import-time delays
    and to make unit tests that don't need embeddings fast.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        logger.info(
            "LocalEmbedder initialised",
            extra={"model_name": model_name},
        )

    @cached_property
    def _model(self):  # type: ignore[return]
        """Lazy-load the sentence-transformers model."""
        from sentence_transformers import SentenceTransformer  # type: ignore
        logger.info(
            "Loading sentence-transformers model",
            extra={"model_name": self._model_name},
        )
        return SentenceTransformer(self._model_name)

    @cached_property
    def dimension(self) -> int:
        """Return the output vector dimensionality."""
        return self._model.get_sentence_embedding_dimension()  # type: ignore[return-value]

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """
        Embed a list of texts.

        Args:
            texts:      List of strings to embed.
            batch_size: Internal batch size for the transformer.

        Returns:
            List of float vectors, one per input text.
        """
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [v.tolist() for v in vectors]

    def embed_one(self, text: str) -> list[float]:
        """Embed a single string. Convenience wrapper around embed()."""
        return self.embed([text])[0]


# ---------------------------------------------------------------------------
# Module-level singleton factory
# ---------------------------------------------------------------------------

_default_embedder: LocalEmbedder | None = None


def get_embedder(model_name: str | None = None) -> LocalEmbedder:
    """
    Return the default LocalEmbedder singleton, creating it if necessary.

    Args:
        model_name: Override the model name from settings.  If None, uses
                    app/config.settings.embedding_model_name.

    Returns:
        A LocalEmbedder instance.
    """
    global _default_embedder

    if model_name is None:
        from app.config import settings
        model_name = settings.embedding_model_name

    # Recreate if the requested model differs from the cached one
    if _default_embedder is None or _default_embedder.model_name != model_name:
        _default_embedder = LocalEmbedder(model_name=model_name)

    return _default_embedder
