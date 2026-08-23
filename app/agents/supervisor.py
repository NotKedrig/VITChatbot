import logging
from pathlib import Path
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
    
    # We use temperature 0 for deterministic routing
    # use_cache=True is critical for minimizing API calls during development
    llm_response = provider.complete(
        prompt=prompt,
        temperature=0.0,
        use_cache=True,
    )

    decision = llm_response.text.strip().lower()
    
    # Clean up markdown if the LLM hallucinated formatting (e.g. `company_research`)
    decision = decision.strip("`'\" \n")
    
    valid_agents = {"company_research", "planner", "progress", "notification"}
    if decision not in valid_agents:
        logger.error(f"Supervisor produced invalid routing decision: {decision}. Defaulting to company_research.")
        decision = "company_research"

    logger.info(
        "Supervisor routing decision",
        extra={
            "user_text": user_text[:50],
            "decision": decision,
            "cached": llm_response.cached,
        }
    )

    return {"next_agent": decision}
