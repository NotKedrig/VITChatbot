import json
import logging
from pathlib import Path
import time
from pydantic import BaseModel, Field

from app.graph.state import AgentState
from app.llm.provider import get_provider

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
    """
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
    start_time = time.perf_counter()
    metadata = {"node": "planner"}
    
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
