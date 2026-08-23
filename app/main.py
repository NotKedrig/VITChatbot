"""
app/main.py — FastAPI application entry point (Phase 0).

Phase 0 exposes only the /health endpoint.  Agent logic, RAG pipelines,
and the frontend are added in later phases.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any

from app.config import settings
from app.logging_config import setup_logging
from app.graph.workflow import build_graph
from app.db.state.db import get_session, create_tables
from app.db.state.models import StudentProfile, PerformanceLog, PlanRevisionLog, Notification
from app.scheduler.notifier import start_scheduler

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
    
    # Initialize the database schemas
    create_tables()
    
    # Start the local scheduler
    start_scheduler()
    
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the long-lived singleton LangGraph compiled workflow
# This retains the MemorySaver checkpointer across the application lifetime.
compiled_graph = build_graph()

# ---------------------------------------------------------------------------
# API Models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    thread_id: str
    student_id: str

class ChatResponse(BaseModel):
    messages: list[dict]
    current_plan: dict | None
    next_agent: str | None
    progress_signal: str | None

class ThreadStateResponse(BaseModel):
    messages: list[dict]
    current_plan: dict | None


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

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Invokes the multi-agent graph with the user's message.
    """
    config = {"configurable": {"thread_id": req.thread_id}}
    input_state = {
        "messages": [{"role": "user", "content": req.message}],
        "student_id": req.student_id
    }
    
    try:
        # LangGraph invoke processes the graph to END
        final_state = compiled_graph.invoke(input_state, config=config)
        
        # Build clean response (stripping runtime metadata and internal config)
        messages = final_state.get("messages", [])
        clean_messages = [{"role": msg.get("role"), "content": msg.get("content")} for msg in messages if isinstance(msg, dict)]
        
        return ChatResponse(
            messages=clean_messages,
            current_plan=final_state.get("current_plan"),
            next_agent=final_state.get("next_agent"),
            progress_signal=final_state.get("progress_signal")
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during chat processing")

@app.get("/api/thread/{thread_id}", response_model=ThreadStateResponse)
async def get_thread_state(thread_id: str):
    """
    Restores conversation history and state from the MemorySaver checkpointer.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state_wrapper = compiled_graph.get_state(config)
    
    if not state_wrapper or not state_wrapper.values:
        return ThreadStateResponse(messages=[], current_plan=None)
        
    state_vals = state_wrapper.values
    messages = state_vals.get("messages", [])
    clean_messages = [{"role": msg.get("role"), "content": msg.get("content")} for msg in messages if isinstance(msg, dict)]
    
    return ThreadStateResponse(
        messages=clean_messages,
        current_plan=state_vals.get("current_plan")
    )

@app.get("/api/state/{student_id}")
async def get_student_state(student_id: str):
    """
    Returns the persistent application state for a student from SQLite.
    """
    with get_session() as db:
        profile = db.query(StudentProfile).filter_by(student_id=student_id).first()
        if not profile:
            # Auto-create for the POC demonstration
            profile = StudentProfile(student_id=student_id, target_companies=[], skill_profile={})
            db.add(profile)
            db.commit()
            db.refresh(profile)
            
        recent_logs = db.query(PerformanceLog).filter_by(student_id=student_id).order_by(PerformanceLog.timestamp.desc()).limit(10).all()
        revisions = db.query(PlanRevisionLog).filter_by(student_id=student_id).order_by(PlanRevisionLog.timestamp.desc()).limit(10).all()
        notifications = db.query(Notification).filter_by(student_id=student_id).order_by(Notification.due_at.asc()).limit(20).all()
        
        def to_dict(obj):
            d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
            return d
            
        return {
            "profile": to_dict(profile),
            "performance_logs": [to_dict(l) for l in recent_logs],
            "plan_revisions": [to_dict(r) for r in revisions],
            "notifications": [to_dict(n) for n in notifications]
        }
