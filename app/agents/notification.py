import json
import logging
import time
import re
import dateparser
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from app.graph.state import AgentState
from app.llm.provider import get_provider
from app.db.state.db import get_session
from app.db.state.models import StudentProfile, Notification
from app.config import settings
from app.scheduler.notifier import schedule_reminder
from dateutil.tz import gettz

logger = logging.getLogger(__name__)

class NotificationRequest(BaseModel):
    message: str = Field(description="The reminder content or task to be reminded about.")
    time_expression: str = Field(description="The exact time expression provided by the user (e.g. 'in 5 minutes', 'tomorrow at 7 PM').")

def _get_parse_settings() -> dict:
    current_tz = gettz(settings.app_timezone) or timezone.utc
    current_time_aware = datetime.now(current_tz)
    relative_base = current_time_aware.replace(tzinfo=None)
    
    return {
        "TIMEZONE": settings.app_timezone,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": relative_base
    }

def _deterministic_parse(text: str) -> tuple[datetime | None, str | None]:
    """
    Attempts to deterministically parse basic reminder time formats to save LLM calls.
    Returns (aware_datetime, matched_time_string) or (None, None).
    """
    parse_settings = _get_parse_settings()

    # Pattern 1: "Remind me [time phrase] to [message]" or just "Remind me [time phrase]"
    match1 = re.search(r'(?i)remind me\s+(in\s+\d+\s+[a-z]+|tomorrow.*?|today at.*?|on\s+\w+.*?)(?:\s+to\s+|$)', text)
    if match1:
        time_phrase = match1.group(1).strip()
        dt = dateparser.parse(time_phrase, settings=parse_settings)
        if dt:
            return dt, time_phrase
            
    # Pattern 2: "Remind me to [message] [time phrase]"
    match2 = re.search(r'(?i)remind me to\s+.*?\s+(in\s+\d+\s+[a-z]+|tomorrow.*?|today at.*?|on\s+\w+.*?)$', text)
    if match2:
        time_phrase = match2.group(1).strip()
        dt = dateparser.parse(time_phrase, settings=parse_settings)
        if dt:
            return dt, time_phrase
            
    return None, None

def _extract_message(text: str, time_str: str) -> str:
    # Remove the time_str
    text = text.replace(time_str, "").strip()
    # Strip common prefixes
    text = re.sub(r'(?i)^(remind me\s+to\s+|remind me\s+|set a reminder\s+to\s+|set a reminder\s+)', '', text)
    # Strip trailing spaces/punctuation
    text = text.strip(" .!,")
    return text or "Reminder"

def notification_node(state: AgentState) -> dict:
    """
    LangGraph node for the Notification Agent.
    Parses deadline/reminder, writes to local DB, and schedules it.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"messages": []}
        
    user_text = messages[-1].get("content", "")
    student_id = state.get("student_id", "default_student")
    
    start_time = time.perf_counter()
    metadata = {"node": "notification", "llm_fallback": False}
    
    due_at = None
    message = None
    
    # 1. Deterministic parsing attempt
    dt, time_str = _deterministic_parse(user_text)
    if dt:
        # Convert to UTC for consistency in scheduling/DB
        due_at = dt.astimezone(timezone.utc)
        if due_at > datetime.now(timezone.utc):
            message = _extract_message(user_text, time_str)
        else:
            due_at = None # Let fallback or rejection handle past dates
    
    # 2. LLM Fallback parsing
    if not due_at:
        metadata["llm_fallback"] = True
        provider = get_provider()
        prompt = (
            f"Extract the reminder details from this text: '{user_text}'. "
            "Return the message to be reminded about, and the time_expression exactly as written by the user. Do not guess the current time."
        )
        try:
            llm_response = provider.complete(
                prompt=prompt,
                temperature=0.0,
                use_cache=True,
                response_schema=NotificationRequest
            )
            parsed_data = json.loads(llm_response.text)
            message = parsed_data.get("message", "Reminder")
            time_expr = parsed_data.get("time_expression")
            
            if time_expr:
                dt = dateparser.parse(time_expr, settings=_get_parse_settings())
                if dt:
                    due_at = dt.astimezone(timezone.utc)
                    
            metadata.update({
                "model_name": llm_response.model_name,
                "model_version": llm_response.model_version,
                "cached": llm_response.cached,
            })
        except Exception as e:
            logger.error(f"Notification Agent LLM fallback failed: {e}")
            
    if not due_at:
        return {
            "messages": [{"role": "agent", "content": "I couldn't understand when you want to be reminded. Please specify a clear time."}],
            "last_agent_output": "I couldn't understand when you want to be reminded.",
            "runtime_metadata": [metadata]
        }
        
    # Ensure it's in the future
    if due_at <= datetime.now(timezone.utc):
        return {
            "messages": [{"role": "agent", "content": "The time you specified is in the past. Please specify a future time."}],
            "last_agent_output": "The time you specified is in the past.",
            "runtime_metadata": [metadata]
        }
        
    # 3. Database Persistence and Scheduling
    try:
        with get_session() as db:
            # Ensure profile exists
            profile = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
            if not profile:
                profile = StudentProfile(student_id=student_id, skill_profile={})
                db.add(profile)
                db.flush()
                
            notification = Notification(
                student_id=student_id,
                message=message,
                due_at=due_at,
                status="pending"
            )
            db.add(notification)
            db.flush() # flush to get ID
            
            schedule_reminder(notification.id, due_at)
            
            # Use app_timezone (or fallback to UTC) for a friendly reply
            app_tz = gettz(settings.app_timezone) or timezone.utc
            # Avoid using %I if due_at isn't precise; but strftime is fine
            local_time_str = due_at.astimezone(app_tz).strftime("%A, %b %d at %I:%M %p").replace(" 0", " ")
            reply = f"Reminder scheduled for {local_time_str}."
            
    except Exception as e:
        logger.error(f"Failed to schedule reminder in DB: {e}")
        return {
            "messages": [{"role": "agent", "content": "An error occurred while scheduling your reminder."}],
            "last_agent_output": "An error occurred while scheduling your reminder.",
            "runtime_metadata": [metadata]
        }

    metadata["latency"] = time.perf_counter() - start_time
    return {
        "messages": [{"role": "agent", "content": reply}],
        "last_agent_output": reply,
        "runtime_metadata": [metadata]
    }
