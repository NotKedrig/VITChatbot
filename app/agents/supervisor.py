import logging
from pathlib import Path
import time
from app.graph.state import AgentState
from app.llm.provider import get_provider

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "supervisor.txt"

def _load_prompt() -> str:
    if not _PROMPT_PATH.exists():
        raise FileNotFoundError(f"Supervisor prompt not found at {_PROMPT_PATH}")
    return _PROMPT_PATH.read_text(encoding="utf-8")

def supervisor_node(state: AgentState) -> dict:
    """
    LangGraph node for the Supervisor.
    Classifies the user's latest message and sets `next_agent`.
    """
    messages = state.get("messages", [])
    if not messages:
        logger.warning("No messages in state, defaulting to company_research")
        return {"next_agent": "company_research"}

    # Get the last user message
    # In a real app, this might be more complex, but for now we'll just grab the last message content.
    last_message = messages[-1]
    user_text = last_message.get("content", "")

    template = _load_prompt()
    prompt = template.format(user_message=user_text)

    provider = get_provider()
    start_time = time.perf_counter()
    try:
        llm_response = provider.complete(
            prompt=prompt,
            temperature=0.0,
            use_cache=True,
        )
        decision = llm_response.text.strip().lower()
        decision = decision.strip("`'\" \n")
        
        valid_agents = {"company_research", "planner", "progress", "notification", "out_of_scope"}
        if decision not in valid_agents:
            logger.error(f"Supervisor produced invalid routing decision: {decision}. Defaulting to out_of_scope.")
            decision = "out_of_scope"
            
        metadata = {
            "node": "supervisor",
            "latency": time.perf_counter() - start_time,
            "model_name": llm_response.model_name,
            "model_version": llm_response.model_version,
            "cached": llm_response.cached,
        }
            
    except Exception as e:
        logger.error(f"Supervisor provider call failed: {e}")
        decision = "out_of_scope"  # Safe fallback
        metadata = {
            "node": "supervisor",
            "latency": time.perf_counter() - start_time,
            "error": str(e)
        }

    logger.info(
        "Supervisor routing decision",
        extra={
            "user_text": user_text[:50],
            "decision": decision,
        }
    )

    return {
        "next_agent": decision,
        "runtime_metadata": [metadata]
    }
