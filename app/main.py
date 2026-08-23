"""
app/main.py — FastAPI application entry point (Phase 0).

Phase 0 exposes only the /health endpoint.  Agent logic, RAG pipelines,
and the frontend are added in later phases.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_config import setup_logging

# ---------------------------------------------------------------------------
# Logging — initialise before any other code runs
# ---------------------------------------------------------------------------
setup_logging(log_dir=settings.log_dir, log_level=settings.log_level)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ---- startup ----
    logger.info(
        "Application startup",
        extra={
            "llm_provider": settings.llm_provider,
            "llm_model_name": settings.llm_model_name,
            "llm_temperature": settings.llm_temperature,
            "embedding_model_name": settings.embedding_model_name,
            "database_url": settings.database_url.split("@")[-1],  # hide credentials
            "chroma_persist_dir": settings.chroma_persist_dir,
            "log_dir": settings.log_dir,
        },
    )
    yield
    # ---- shutdown ----
    logger.info("Application shutdown")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="VITian Chatbot Local POC",
    description=(
        "Multi-agent, retrieval-grounded conversational assistant for academic, "
        "placement, and career guidance.  Fully local proof-of-concept — "
        "no AWS services are used or benchmarked here."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    summary="Health check",
    description=(
        "Returns HTTP 200 with a JSON body confirming the service is running.  "
        "Used by Docker Compose health checks and monitoring."
    ),
    tags=["meta"],
)
async def health() -> JSONResponse:
    """Liveness probe — always returns 200 when the process is running."""
    logger.debug("Health check requested")
    return JSONResponse(
        content={
            "status": "ok",
            "service": "vitian-chatbot",
            "version": "0.1.0",
        }
    )
