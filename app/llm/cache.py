"""
app/llm/cache.py — LLM response cache (Phase 0).

Stores and retrieves LLM responses keyed by (prompt_hash, model, temperature)
using a local SQLite database.  This allows experiment re-runs to avoid
repeated API cost and keeps outputs deterministic for the same inputs.

The cache is bypass-able via an explicit flag (`use_cache=False` or the
`--no-cache` CLI flag added in later phases) so that forced fresh calls
are always possible without deleting the cache database.

Design notes:
- SQLite is used (via stdlib `sqlite3`) to keep this dependency-free from
  the project's perspective — no extra pip package needed.
- The cache lives at `<CHROMA_PERSIST_DIR>/../llm_cache.db` by default, i.e.
  alongside the Chroma data directory.  Override with the `LLM_CACHE_DB_PATH`
  env var.
- Thread-safe: each call opens its own connection (check_same_thread=False
  is set; SQLite's WAL mode handles concurrent reads).
- Records are never automatically expired; purge the DB manually if needed.
"""

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.logging_config import log_llm_call

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default cache database path
# ---------------------------------------------------------------------------
_DEFAULT_CACHE_DB = os.environ.get(
    "LLM_CACHE_DB_PATH",
    str(Path("./llm_cache.db").resolve()),
)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS llm_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key       TEXT    NOT NULL UNIQUE,
    prompt_hash     TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    temperature     REAL    NOT NULL,
    prompt_text     TEXT,           -- stored for auditability (may be large)
    response_json   TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_llm_cache_key ON llm_cache (cache_key);
"""


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def make_cache_key(prompt: str, model: str, temperature: float) -> tuple[str, str]:
    """
    Derive a deterministic cache key and prompt hash from the call parameters.

    Returns:
        (cache_key, prompt_hash) where:
        - cache_key  : hex string identifying this (prompt, model, temperature) triple
        - prompt_hash: SHA-256 hex digest of the prompt string alone
                       (used in log_llm_call for reproducibility tracing)
    """
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    # Include model and temperature in the key so the same prompt at a different
    # temperature or model is stored separately.
    combined = f"{prompt_hash}::{model}::{temperature}"
    cache_key = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    return cache_key, prompt_hash


def _get_connection(db_path: str) -> sqlite3.Connection:
    """Open (and initialise) the SQLite cache database."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# LLMCache class
# ---------------------------------------------------------------------------

class LLMCache:
    """
    Simple (prompt_hash, model, temperature) → response cache backed by SQLite.

    Usage (Phase 2+)::

        cache = LLMCache()

        cached = cache.get(prompt, model="gpt-4o-2024-05-13", temperature=0.0)
        if cached is not None:
            return cached  # dict previously returned by the LLM provider

        response = llm_provider.complete(prompt, temperature=0.0)
        cache.set(prompt, model="gpt-4o-2024-05-13", temperature=0.0,
                  response=response)
        return response
    """

    def __init__(self, db_path: str = _DEFAULT_CACHE_DB) -> None:
        self._db_path = db_path
        logger.debug("LLMCache initialised", extra={"db_path": db_path})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        prompt: str,
        model: str,
        temperature: float,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any] | None:
        """
        Look up a cached response.

        Args:
            prompt:      The full prompt string sent to the LLM.
            model:       Fully-qualified model name/version string.
            temperature: Sampling temperature.
            use_cache:   If False, always return None (cache miss) without
                         querying the database.  Useful for forced fresh calls.

        Returns:
            The cached response dict, or None on a miss.
        """
        if not use_cache:
            return None

        cache_key, prompt_hash = make_cache_key(prompt, model, temperature)

        try:
            conn = _get_connection(self._db_path)
            with conn:
                row = conn.execute(
                    "SELECT response_json FROM llm_cache WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
        except sqlite3.Error as exc:
            logger.warning("LLMCache read error", extra={"error": str(exc)})
            return None

        if row is None:
            return None

        log_llm_call(
            logger,
            prompt_hash=prompt_hash,
            model_name=model,
            temperature=temperature,
            cached=True,
        )
        return json.loads(row[0])

    def set(
        self,
        prompt: str,
        model: str,
        temperature: float,
        response: dict[str, Any],
    ) -> None:
        """
        Store a response in the cache.

        Args:
            prompt:      The full prompt string sent to the LLM.
            model:       Fully-qualified model name/version string.
            temperature: Sampling temperature.
            response:    The response dict returned by the LLM provider.
                         Must be JSON-serialisable.
        """
        cache_key, prompt_hash = make_cache_key(prompt, model, temperature)
        response_json = json.dumps(response, ensure_ascii=False)
        created_at = datetime.now(tz=timezone.utc).isoformat()

        try:
            conn = _get_connection(self._db_path)
            with conn:
                conn.execute(
                    """
                    INSERT INTO llm_cache
                        (cache_key, prompt_hash, model, temperature,
                         prompt_text, response_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO NOTHING
                    """,
                    (cache_key, prompt_hash, model, temperature,
                     prompt, response_json, created_at),
                )
        except sqlite3.Error as exc:
            logger.warning("LLMCache write error", extra={"error": str(exc)})
            return

        logger.debug(
            "LLMCache stored",
            extra={
                "cache_key": cache_key,
                "prompt_hash": prompt_hash,
                "model": model,
                "temperature": temperature,
            },
        )

    def clear(self) -> int:
        """
        Delete all entries from the cache.

        Returns:
            Number of rows deleted.
        """
        try:
            conn = _get_connection(self._db_path)
            with conn:
                cursor = conn.execute("DELETE FROM llm_cache")
                deleted = cursor.rowcount
        except sqlite3.Error as exc:
            logger.warning("LLMCache clear error", extra={"error": str(exc)})
            return 0

        logger.info("LLMCache cleared", extra={"rows_deleted": deleted})
        return deleted

    def stats(self) -> dict[str, Any]:
        """
        Return basic statistics about the cache for observability.

        Returns:
            Dict with keys: total_entries, db_path, size_bytes.
        """
        try:
            conn = _get_connection(self._db_path)
            with conn:
                (total,) = conn.execute(
                    "SELECT COUNT(*) FROM llm_cache"
                ).fetchone()
            size_bytes = Path(self._db_path).stat().st_size if Path(self._db_path).exists() else 0
        except (sqlite3.Error, OSError) as exc:
            logger.warning("LLMCache stats error", extra={"error": str(exc)})
            return {"error": str(exc)}

        return {
            "total_entries": total,
            "db_path": self._db_path,
            "size_bytes": size_bytes,
        }
