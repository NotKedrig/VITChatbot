from typing import Annotated, Sequence, TypedDict
import operator

class AgentState(TypedDict):
    """
    LangGraph state for the VITian Chatbot POC.
    """
    # A list of dictionaries representing the conversation, e.g., {"role": "user", "content": "..."}
    messages: Annotated[Sequence[dict], operator.add]
    
    # The string identifier of the next agent to route to, populated by the Supervisor
    next_agent: str
