from typing import Literal
from langgraph.graph import StateGraph, START, END

from app.graph.state import AgentState
from app.agents.supervisor import supervisor_node
from app.agents.stubs import progress_node, notification_node
from app.agents.company_research import company_research_node
from app.agents.planner import planner_node

def build_graph():
    """
    Builds and compiles the LangGraph StateGraph for the VITian Chatbot POC.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("company_research", company_research_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("progress", progress_node)
    workflow.add_node("notification", notification_node)

    # Supervisor is the entry point
    workflow.add_edge(START, "supervisor")

    # Define a conditional edge function
    def route_from_supervisor(state: AgentState) -> str:
        """Reads the routing decision made by the supervisor node."""
        next_agent = state.get("next_agent", "company_research")
        return next_agent

    # Map the outputs to the respective nodes
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "company_research": "company_research",
            "planner": "planner",
            "progress": "progress",
            "notification": "notification",
        }
    )

    # All specialized agents lead to END (for now, simple one-shot turns)
    workflow.add_edge("company_research", END)
    workflow.add_edge("planner", END)
    workflow.add_edge("progress", END)
    workflow.add_edge("notification", END)

    return workflow.compile()
