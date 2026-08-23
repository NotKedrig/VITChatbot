from app.graph.state import AgentState



def progress_node(state: AgentState) -> dict:
    """Stub node for progress agent."""
    return {"messages": [{"role": "agent", "content": "[STUB] Progress Agent received the request."}]}

def notification_node(state: AgentState) -> dict:
    """Stub node for notification agent."""
    return {"messages": [{"role": "agent", "content": "[STUB] Notification Agent received the request."}]}
