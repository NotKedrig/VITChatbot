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
    
    with get_session() as db:
        active_plan = db.query(StudyPlan).filter_by(student_id=req.student_id, is_active=True).order_by(StudyPlan.id.desc()).first()
        if active_plan:
            current_plan = active_plan.plan_json
        else:
            current_plan = None

    input_state = {
        "messages": [{"role": "user", "content": req.message}],
        "student_id": req.student_id
    }
    if current_plan:
        input_state["current_plan"] = current_plan
        
    try:
        # LangGraph invoke processes the graph to END
        final_state = compiled_graph.invoke(input_state, config=config)
        
        # Build clean response (stripping runtime metadata and internal config)
        messages = final_state.get("messages", [])
        clean_messages = [{"role": msg.get("role"), "content": msg.get("content")} for msg in messages if isinstance(msg, dict)]
        
        # If the planner modified the plan during this turn, save it back to the DB
        if final_state.get("progress_signal") in ["struggle", "mastery"]:
            plan_json = final_state.get("current_plan")
            if plan_json:
                with get_session() as db:
                    db.query(StudyPlan).filter_by(student_id=req.student_id).update({"is_active": False})
                    new_plan = StudyPlan(student_id=req.student_id, plan_json=plan_json, is_active=True)
                    db.add(new_plan)
                    db.commit()
        
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

# ---------------------------------------------------------------------------
# New REST Endpoints (Frontend Overhaul)
# ---------------------------------------------------------------------------

from app.agents.company_research import answer_with_rag, retrieve_only
from app.llm.provider import QuotaExhaustedError
from app.agents.planner import planner_node
from app.db.state.models import StudyPlan

class ResearchRequest(BaseModel):
    query: str
    collection_name: str | None = None

@app.post("/api/research")
async def api_research(req: ResearchRequest):
    collection = req.collection_name or f"vitian_kb_{settings.chunking_strategy}"
    try:
        ans = answer_with_rag(question=req.query, collection_name=collection)
        return {
            "question": ans.question,
            "answer": ans.answer,
            "citations": [c.to_dict() for c in ans.citations],
            "chunks": [{"text": c.text, "title": c.title, "doc_id": c.doc_id, "similarity_score": c.similarity_score, "chunk_index": c.chunk_index} for c in ans.retrieved_chunks],
            "is_offline": False
        }
    except (QuotaExhaustedError, RuntimeError):
        return retrieve_only(question=req.query, collection_name=collection)


class PlanGenerateRequest(BaseModel):
    student_id: str
    target_companies: list[str]
    available_time: str
    skills: str
    message: str | None = None

@app.post("/api/plan/generate")
async def api_plan_generate(req: PlanGenerateRequest):
    state = {
        "student_id": req.student_id,
        "messages": [{"role": "user", "content": req.message or f"Generate a study plan for {', '.join(req.target_companies)} with {req.available_time} focusing on {req.skills}."}]
    }
    with get_session() as db:
        profile = db.query(StudentProfile).filter_by(student_id=req.student_id).first()
        if profile:
            profile.target_companies = req.target_companies
            profile.available_time = req.available_time
            db.commit()
    
    result = planner_node(state)
    plan_json = result.get("current_plan")
    
    with get_session() as db:
        db.query(StudyPlan).filter_by(student_id=req.student_id).update({"is_active": False})
        if plan_json:
            plan = StudyPlan(student_id=req.student_id, plan_json=plan_json, is_active=True)
            db.add(plan)
        db.commit()
        
    return {"plan": plan_json}

@app.get("/api/plan/{student_id}")
async def get_plan(student_id: str):
    with get_session() as db:
        plan = db.query(StudyPlan).filter_by(student_id=student_id, is_active=True).order_by(StudyPlan.id.desc()).first()
        revisions = db.query(PlanRevisionLog).filter_by(student_id=student_id).order_by(PlanRevisionLog.timestamp.desc()).limit(10).all()
        
        rev_list = [{"triggering_signal": r.triggering_signal, "affected_topic": r.affected_topic, "reason": r.reason, "timestamp": r.timestamp.isoformat()} for r in revisions]
        
        if plan:
            return {"plan": plan.plan_json, "revisions": rev_list}
        return {"plan": None, "revisions": rev_list}


class ProgressSubmitRequest(BaseModel):
    student_id: str
    topic: str
    score: int

@app.post("/api/progress/submit")
async def api_progress_submit(req: ProgressSubmitRequest):
    from app.agents.progress import STRUGGLE_THRESHOLD, MASTERY_THRESHOLD, _evaluate_persistent_status
    is_struggle = req.score < STRUGGLE_THRESHOLD
    is_mastery = req.score >= MASTERY_THRESHOLD
    with get_session() as db:
        log = PerformanceLog(
            student_id=req.student_id,
            topic=req.topic,
            score=req.score,
            is_struggle=is_struggle,
            is_mastery=is_mastery
        )
        db.add(log)
        db.commit()
        
        signal = "struggle" if is_struggle else "mastery" if is_mastery else "neutral"
        
        persistent_status = _evaluate_persistent_status(db, req.student_id, req.topic)
        profile = db.query(StudentProfile).filter_by(student_id=req.student_id).first()
        if persistent_status and profile:
            sp = profile.skill_profile or {}
            sp = dict(sp)
            sp[req.topic] = persistent_status
            profile.skill_profile = sp
            db.commit()
        
        return {"signal": signal, "skill_profile": profile.skill_profile if profile else {}}


@app.get("/api/progress/{student_id}")
async def get_progress(student_id: str):
    with get_session() as db:
        recent_logs = db.query(PerformanceLog).filter_by(student_id=student_id).order_by(PerformanceLog.timestamp.desc()).all()
        return {"logs": [{"topic": l.topic, "score": l.score, "timestamp": l.timestamp.isoformat(), "is_struggle": l.is_struggle, "is_mastery": l.is_mastery} for l in recent_logs]}


from datetime import datetime

class ReminderRequest(BaseModel):
    student_id: str
    message: str
    due_at_iso: str

@app.post("/api/reminders")
async def create_reminder(req: ReminderRequest):
    from app.scheduler.notifier import schedule_reminder
    due_at = datetime.fromisoformat(req.due_at_iso.replace('Z', '+00:00'))
    with get_session() as db:
        n = Notification(student_id=req.student_id, message=req.message, due_at=due_at)
        db.add(n)
        db.commit()
        db.refresh(n)
        schedule_reminder(n.id, n.due_at)
        return {"id": n.id, "status": "scheduled"}


@app.get("/api/reminders/{student_id}")
async def get_reminders(student_id: str):
    from datetime import timezone
    with get_session() as db:
        notifications = db.query(Notification).filter_by(student_id=student_id).order_by(Notification.due_at.asc()).all()
        return {"reminders": [{"id": n.id, "message": n.message, "due_at": n.due_at.replace(tzinfo=timezone.utc).isoformat() if not n.due_at.tzinfo else n.due_at.isoformat(), "status": n.status} for n in notifications]}


@app.delete("/api/reminders/{id}")
async def delete_reminder(id: int):
    with get_session() as db:
        n = db.query(Notification).filter_by(id=id).first()
        if n:
            n.status = "cancelled"
            db.commit()
            from app.scheduler.notifier import scheduler
            job_id = f"notification_{id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
            return {"status": "cancelled"}
        raise HTTPException(404, "Reminder not found")


class ProfileRequest(BaseModel):
    target_companies: list[str]
    available_time: str

@app.put("/api/profile/{student_id}")
async def update_profile(student_id: str, req: ProfileRequest):
    with get_session() as db:
        profile = db.query(StudentProfile).filter_by(student_id=student_id).first()
        if profile:
            profile.target_companies = req.target_companies
            profile.available_time = req.available_time
            db.commit()
            return {"status": "updated"}
        raise HTTPException(404, "Profile not found")


@app.get("/api/health/status")
async def health_status():
    db_ok = True
    try:
        from sqlalchemy import text
        with get_session() as db:
            db.execute(text("SELECT 1"))
    except:
        db_ok = False
        
    kb_ok = True
    try:
        from app.rag.retriever import _get_chroma_client
        chroma = _get_chroma_client(settings.chroma_persist_dir)
        kb_ok = len(chroma.list_collections()) > 0
    except:
        kb_ok = False
        
    scheduler_ok = True
    try:
        from app.scheduler.notifier import scheduler
        scheduler_ok = scheduler.running
    except:
        scheduler_ok = False
        
    gemini_ok = True
    try:
        from app.llm.provider import get_provider
        provider = get_provider()
        if not provider:
            gemini_ok = False
    except:
        gemini_ok = False
        
    return {
        "database": db_ok,
        "knowledge_base": kb_ok,
        "scheduler": scheduler_ok,
        "gemini": gemini_ok
    }
