import logging
import time

from app.graph.state import AgentState

logger = logging.getLogger(__name__)

def out_of_scope_node(state: AgentState) -> dict:
    """
    LangGraph node for handling out-of-scope requests.
    Returns a deterministic friendly rejection message without calling an LLM.
    """
    start_time = time.perf_counter()
    
    reply = "I'm designed to help with placement preparation, company research, study planning, progress tracking, and reminders. I can't help with that request."
    
    metadata = {
        "node": "out_of_scope",
        "latency": time.perf_counter() - start_time,
        "llm_fallback": False,
        "cached": True # Not technically a cache, but deterministic
    }
    
    logger.info("Out of scope request rejected deterministically.")
    
    return {
        "messages": [{"role": "agent", "content": reply}],
        "last_agent_output": reply,
        "runtime_metadata": [metadata]
    }
