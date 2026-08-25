"""
app/logging_config.py — Structured logging setup for the VITian Chatbot POC.

Features:
- JSON-structured log records (via `python-json-logger`) written to stdout
  AND a rotating file under logs/ (configurable via LOG_DIR / LOG_LEVEL).
- A helper function `log_llm_call` that attaches model name, version,
  temperature, and a UTC timestamp to every LLM call log entry, enabling
  full reproducibility tracing across experiment runs.
- No AWS-specific logging sinks.  This replaces CloudWatch locally;
  see docs/future_aws_deployment.md for the production mapping.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Fallback formatter (pure stdlib — no pythonjsonlogger dependency in Phase 0)
# ---------------------------------------------------------------------------

class _StructuredFormatter(logging.Formatter):
    """
    A minimal structured-log formatter that emits JSON-like lines without
    requiring an external dependency.  Each line is a flat key=value string
    that is both human-readable and machine-parseable.

    Format:
        timestamp=<ISO-8601> level=<LEVEL> logger=<name> message=<msg> [extra_key=extra_val ...]
    """

    def format(self, record: logging.LogRecord) -> str:
        # Standard fields
        parts = [
            f"timestamp={datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()}",
            f"level={record.levelname}",
            f"logger={record.name}",
            f"message={record.getMessage()}",
        ]

        # Append any extra fields attached to the record (e.g. via log_llm_call)
        standard_keys = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in standard_keys and not key.startswith("_"):
                parts.append(f"{key}={value}")

        if record.exc_info:
            parts.append(f"exc_info={self.formatException(record.exc_info)}")

        return " ".join(parts)


# ---------------------------------------------------------------------------
# Public setup function
# ---------------------------------------------------------------------------

def setup_logging(log_dir: str = "./logs", log_level: str = "INFO") -> logging.Logger:
    """
    Configure the root logger with two handlers:

    1. StreamHandler → stdout  (structured key=value format)
    2. RotatingFileHandler → <log_dir>/app.log  (same format, max 10 MB × 5 files)

    Call this once at application startup (app/main.py).

    Args:
        log_dir:   Directory where rotating log files are written.  Created if
                   it does not exist.
        log_level: Logging level string ("DEBUG", "INFO", "WARNING", "ERROR").

    Returns:
        The configured root logger.
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = _StructuredFormatter()

    # Stdout handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # Rotating file handler (max 10 MB per file, keep 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, "app.log"),
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers if setup_logging is called more than once
    if not root_logger.handlers:
        root_logger.addHandler(stream_handler)
        root_logger.addHandler(file_handler)

    return root_logger


# ---------------------------------------------------------------------------
# LLM call logging helper
# ---------------------------------------------------------------------------

def log_llm_call(
    logger: logging.Logger,
    prompt_hash: str,
    model_name: str,
    temperature: float,
    *,
    cached: bool = False,
    latency_ms: float | None = None,
    token_usage: dict | None = None,
    extra: dict | None = None,
) -> None:
    """
    Emit a structured log entry for every (attempted or cached) LLM call.

    This helper is intentionally called by app/llm/cache.py and (in later
    phases) app/llm/provider.py so that every experiment run has a traceable
    record of: which model/version was used, at what temperature, at what
    UTC timestamp, whether the response came from cache, and optional
    token-usage / latency metrics.

    Args:
        logger:       The module-level logger of the caller.
        prompt_hash:  SHA-256 hex digest of the prompt string (from cache.py).
        model_name:   Fully-qualified model name/version string (e.g.
                      "gpt-4o-2024-05-13").  Recorded verbatim in results CSVs.
        temperature:  Sampling temperature used for the call.
        cached:       True if the response was served from the local cache.
        latency_ms:   Wall-clock latency in milliseconds (None if cached).
        token_usage:  Dict with keys like "prompt_tokens", "completion_tokens",
                      "total_tokens" (None if cached or unavailable).
        extra:        Any additional key-value pairs to include in the log entry.
    """
    record_extra: dict = {
        "prompt_hash": prompt_hash,
        "model_name": model_name,
        "temperature": temperature,
        "cached": cached,
        "utc_timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    if latency_ms is not None:
        record_extra["latency_ms"] = round(latency_ms, 3)
    if token_usage:
        record_extra.update(token_usage)
    if extra:
        record_extra.update(extra)

    logger.info(
        "llm_call",
        extra=record_extra,
    )
