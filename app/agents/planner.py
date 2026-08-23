import json
import logging
from pathlib import Path
import time
from pydantic import BaseModel, Field

from app.graph.state import AgentState
from app.llm.provider import get_provider
from app.db.state.db import get_session
from app.db.state.models import PlanRevisionLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured Output Models
# ---------------------------------------------------------------------------

class StudyTask(BaseModel):
    topic: str = Field(description="The broad topic, e.g., 'DSA', 'DBMS', 'Aptitude'")
    task_description: str = Field(description="Specific actionable task")
    estimated_duration: str = Field(description="Estimated time, e.g., '2 hours'")
    priority: str = Field(description="'High', 'Medium', or 'Low'")
    rationale: str = Field(description="Why this task is recommended right now")
    status: str = Field(description="Task status, e.g., 'pending'")

class StudyPlan(BaseModel):
    tasks: list[StudyTask] = Field(description="List of study tasks")
    summary: str = Field(description="A short encouragement or overview of the plan")


# ---------------------------------------------------------------------------
# Planner Node
# ---------------------------------------------------------------------------

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "planner.txt"

def _load_prompt() -> str:
    if not _PROMPT_PATH.exists():
        raise FileNotFoundError(f"Planner prompt not found at {_PROMPT_PATH}")
    return _PROMPT_PATH.read_text(encoding="utf-8")

def planner_node(state: AgentState) -> dict:
    """
    LangGraph node for the Planner Agent.
    Generates a structured study plan based on student state and the user's request.
    If a progress_signal is present, it dynamically revises the existing plan deterministically.
    """
    progress_signal = state.get("progress_signal", "none")
    affected_topic = state.get("affected_topic", "")
    current_plan = state.get("current_plan", {"tasks": [], "summary": ""})
    student_id = state.get("student_id", "default_student")
    
    start_time = time.perf_counter()
    metadata = {"node": "planner"}
    
    # -----------------------------------------------------------------------
    # ADAPTIVE REPLANNING (Deterministic)
    # -----------------------------------------------------------------------
    if progress_signal in ["struggle", "mastery"] and current_plan.get("tasks"):
        logger.info(f"Adaptive replanning triggered by {progress_signal} on {affected_topic}")
        new_tasks = list(current_plan.get("tasks", []))
        
        if progress_signal == "struggle":
            # 1. Promote existing tasks for this topic to High
            for t in new_tasks:
                if t.get("topic", "").lower() == affected_topic.lower():
                    t["priority"] = "High"
                    t["rationale"] = "Priority increased due to recent struggle."
            
            # 2. Insert a remedial task
            remedial_task = {
                "topic": affected_topic,
                "task_description": "Targeted Remedial Review",
                "estimated_duration": "1 hour",
                "priority": "High",
                "rationale": "Inserted to address recent performance struggle.",
                "status": "pending"
            }
            new_tasks.insert(0, remedial_task)
            
            # 3. Preserve study time by demoting/dropping a low priority task if list is getting long
            if len(new_tasks) > 5:
                # Remove the last non-High task
                for i in range(len(new_tasks)-1, -1, -1):
                    if new_tasks[i].get("priority") != "High":
                        new_tasks.pop(i)
                        break
            
            summary = f"I've revised your plan to focus more on {affected_topic} following your recent mock score."
            reason = "Struggle detected, inserted remedial task."
            
        elif progress_signal == "mastery":
            # Demote tasks for this topic
            for t in new_tasks:
                if t.get("topic", "").lower() == affected_topic.lower():
                    t["priority"] = "Low"
                    t["rationale"] = "Priority reduced due to recent mastery. Light maintenance only."
            
            summary = f"I've adjusted your plan to reduce emphasis on {affected_topic} since you've mastered it!"
            reason = "Mastery detected, demoted task priority."
            
        # Write to DB
        with get_session() as db:
            rev_log = PlanRevisionLog(
                student_id=student_id,
                triggering_signal=progress_signal,
                affected_topic=affected_topic,
                reason=reason
            )
            db.add(rev_log)
            # flush/commit happens automatically via context manager
            
        plan_data = {"tasks": new_tasks, "summary": summary}
        
        # Format the reply
        agent_reply = f"Here is your customized study plan:\n\n{summary}\n\n"
        for i, task in enumerate(new_tasks, start=1):
            agent_reply += f"**{i}. {task.get('topic')}** ({task.get('priority')} Priority) - {task.get('estimated_duration')}\n"
            agent_reply += f"   *Task*: {task.get('task_description')}\n"
            agent_reply += f"   *Why*: {task.get('rationale')}\n\n"
            
        metadata.update({
            "latency": time.perf_counter() - start_time,
            "replanned": True,
            "signal": progress_signal
        })
        
        # Clear the signal so it doesn't loop
        return {
            "messages": [{"role": "agent", "content": agent_reply.strip()}],
            "current_plan": plan_data,
            "last_agent_output": agent_reply.strip(),
            "progress_signal": "none",
            "affected_topic": "",
            "runtime_metadata": [metadata]
        }
        
    # -----------------------------------------------------------------------
    # STATIC / INITIAL PLANNING (LLM)
    # -----------------------------------------------------------------------
    messages = state.get("messages", [])
    if not messages:
        user_text = ""
    else:
        user_text = messages[-1].get("content", "")

    template = _load_prompt()
    
    # Extract context from state (with safe defaults)
    target_companies = ", ".join(state.get("target_companies", [])) or "None specified"
    skill_profile_dict = state.get("skill_profile", {})
    skill_profile = ", ".join(f"{k}: {v}" for k, v in skill_profile_dict.items()) or "None specified"
    available_time = state.get("available_time", "Not specified")

    prompt = template.format(
        target_companies=target_companies,
        skill_profile=skill_profile,
        available_time=available_time,
        user_message=user_text,
    )

    provider = get_provider()
    
    try:
        llm_response = provider.complete(
            prompt=prompt,
            temperature=0.2, # Slight creativity for planning
            use_cache=True,
            response_schema=StudyPlan,
        )
        
        # Parse the JSON output
        plan_data = json.loads(llm_response.text)
        
        # Format a readable message for the chat history
        agent_reply = f"Here is your customized study plan:\n\n{plan_data.get('summary', '')}\n\n"
        for i, task in enumerate(plan_data.get("tasks", []), start=1):
            agent_reply += f"**{i}. {task.get('topic')}** ({task.get('priority')} Priority) - {task.get('estimated_duration')}\n"
            agent_reply += f"   *Task*: {task.get('task_description')}\n"
            agent_reply += f"   *Why*: {task.get('rationale')}\n\n"
            
        logger.info("Planner generated a study plan successfully.", extra={"cached": llm_response.cached})
        
        metadata.update({
            "latency": time.perf_counter() - start_time,
            "model_name": llm_response.model_name,
            "model_version": llm_response.model_version,
            "cached": llm_response.cached,
        })

    except Exception as e:
        logger.error(f"Planner failed to generate plan: {e}")
        plan_data = {"tasks": [], "summary": "Failed to generate plan."}
        agent_reply = "I'm sorry, I encountered an error while trying to build your study plan."
        
        metadata.update({
            "latency": time.perf_counter() - start_time,
            "error": str(e)
        })

    # Return new state variables
    return {
        "messages": [{"role": "agent", "content": agent_reply.strip()}],
        "current_plan": plan_data,
        "last_agent_output": agent_reply.strip(),
        "runtime_metadata": [metadata]
    }
