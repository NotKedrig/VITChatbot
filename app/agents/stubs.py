from app.graph.state import AgentState

def company_research_node(state: AgentState) -> dict:
    """Stub node for company research agent."""
    return {"messages": [{"role": "agent", "content": "[STUB] Company Research Agent received the request."}]}

def planner_node(state: AgentState) -> dict:
    """Stub node for planner agent."""
    return {"messages": [{"role": "agent", "content": "[STUB] Planner Agent received the request."}]}

def progress_node(state: AgentState) -> dict:
    """Stub node for progress agent."""
    return {"messages": [{"role": "agent", "content": "[STUB] Progress Agent received the request."}]}

def notification_node(state: AgentState) -> dict:
    """Stub node for notification agent."""
    return {"messages": [{"role": "agent", "content": "[STUB] Notification Agent received the request."}]}
