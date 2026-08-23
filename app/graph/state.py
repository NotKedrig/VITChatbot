from typing import Annotated, Sequence, TypedDict
import operator

class AgentState(TypedDict, total=False):
    """
    LangGraph state for the VITian Chatbot POC.
    """
    # A list of dictionaries representing the conversation, e.g., {"role": "user", "content": "..."}
    messages: Annotated[Sequence[dict], operator.add]
    
    # The string identifier of the next agent to route to, populated by the Supervisor
    next_agent: str
    
    # Student Context
    student_id: str
    target_companies: list[str]
    skill_profile: dict[str, str]
    available_time: str
    
    # Outputs / artifacts from specialized agents
    current_plan: dict
    citations: list[dict]
    last_agent_output: str
    
    # Progress routing signals
    progress_signal: str # e.g. "struggle", "mastery", "none"
    affected_topic: str
    
    # Metadata for experimental analysis (latency, model, tokens, etc.)
    runtime_metadata: Annotated[Sequence[dict], operator.add]
