import json
import logging
import time
from pydantic import BaseModel, Field

from app.graph.state import AgentState
from app.llm.provider import get_provider
from app.db.state.db import get_session
from app.db.state.models import StudentProfile, PerformanceLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration & Thresholds
# ---------------------------------------------------------------------------
# POC thresholds. These are heuristics for demonstration purposes,
# explicitly not tuned against experimental outcomes.
STRUGGLE_THRESHOLD = 50
MASTERY_THRESHOLD = 85

# Number of repeated signals required to change the persistent topic status
# (e.g. 2 consecutive poor scores -> persistent 'weak' status).
PERSISTENT_STATUS_WINDOW = 2

# ---------------------------------------------------------------------------
# Structured Output Model
# ---------------------------------------------------------------------------

class PerformanceReport(BaseModel):
    topic: str = Field(description="The topic the user is reporting a score for (e.g., 'DSA', 'Aptitude')")
    score: int = Field(description="The percentage score (0-100) the user reported")


# ---------------------------------------------------------------------------
# Progress Agent Node
# ---------------------------------------------------------------------------

def _evaluate_persistent_status(db, student_id: str, topic: str) -> str | None:
    """
    Evaluates the persistent status based on the last N performance logs for this topic.
    Returns "weak", "mastered", or None if no persistent change is justified.
    """
    recent_logs = (
        db.query(PerformanceLog)
        .filter(PerformanceLog.student_id == student_id, PerformanceLog.topic == topic)
        .order_by(PerformanceLog.timestamp.desc())
        .limit(PERSISTENT_STATUS_WINDOW)
        .all()
    )
    
    if len(recent_logs) < PERSISTENT_STATUS_WINDOW:
        return None
        
    # Check if ALL of the recent logs agree
    if all(log.is_struggle for log in recent_logs):
        return "weak"
    elif all(log.is_mastery for log in recent_logs):
        return "mastered"
        
    return None

def progress_node(state: AgentState) -> dict:
    """
    LangGraph node for the Progress Agent.
    Parses user performance, writes to DB, calculates deterministic struggle/mastery,
    and sets the progress_signal for adaptive routing.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"progress_signal": "none"}
        
    user_text = messages[-1].get("content", "")
    student_id = state.get("student_id", "default_student")
    
    start_time = time.perf_counter()
    metadata = {"node": "progress"}
    
    provider = get_provider()
    
    try:
        # 1. Parse score and topic from the user message
        prompt = f"Extract the topic and percentage score from this student report: '{user_text}'"
        llm_response = provider.complete(
            prompt=prompt,
            temperature=0.0,
            use_cache=True,
            response_schema=PerformanceReport
        )
        
        parsed_data = json.loads(llm_response.text)
        topic = parsed_data.get("topic")
        score = parsed_data.get("score")
        
        if topic is None or score is None:
            raise ValueError("LLM failed to extract topic or score")
            
        # 2. Deterministic Immediate Signal Calculation
        is_struggle = score < STRUGGLE_THRESHOLD
        is_mastery = score >= MASTERY_THRESHOLD
        
        if is_struggle:
            immediate_signal = "struggle"
            reply = f"I've recorded {score}% for {topic}. It looks like you're struggling with this. Let me see if I can revise your study plan to help."
        elif is_mastery:
            immediate_signal = "mastery"
            reply = f"Great job! I've recorded {score}% for {topic}. You've mastered this topic. I'll adjust your plan to focus on other areas."
        else:
            immediate_signal = "none"
            reply = f"I've recorded {score}% for {topic}. Keep up the good work!"
            
        # 3. Database Persistence & Persistent Status Calculation
        with get_session() as db:
            # Ensure profile exists
            profile = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
            if not profile:
                profile = StudentProfile(student_id=student_id, skill_profile={})
                db.add(profile)
                db.flush()
                
            # Log performance
            new_log = PerformanceLog(
                student_id=student_id,
                topic=topic,
                score=score,
                is_struggle=is_struggle,
                is_mastery=is_mastery
            )
            db.add(new_log)
            db.flush() # flush so it's queryable immediately
            
            # Evaluate Persistent Status
            persistent_status = _evaluate_persistent_status(db, student_id, topic)
            if persistent_status:
                skill_profile = profile.skill_profile or {}
                # Create a new dict for SQLAlchemy to detect JSON mutation
                new_skill_profile = dict(skill_profile)
                new_skill_profile[topic] = persistent_status
                profile.skill_profile = new_skill_profile
                
                logger.info(f"Persistent status for {topic} updated to {persistent_status} for {student_id}")
                
        metadata.update({
            "latency": time.perf_counter() - start_time,
            "model_name": llm_response.model_name,
            "model_version": llm_response.model_version,
            "cached": llm_response.cached,
        })
        
        return {
            "messages": [{"role": "agent", "content": reply}],
            "progress_signal": immediate_signal,
            "affected_topic": topic,
            "last_agent_output": reply,
            "runtime_metadata": [metadata]
        }

    except Exception as e:
        logger.error(f"Progress Agent failed: {e}")
        metadata.update({
            "latency": time.perf_counter() - start_time,
            "error": str(e)
        })
        return {
            "messages": [{"role": "agent", "content": "I couldn't properly record your score at this time."}],
            "progress_signal": "none",
            "last_agent_output": "I couldn't properly record your score at this time.",
            "runtime_metadata": [metadata]
        }
