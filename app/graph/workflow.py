from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import AgentState
from app.agents.supervisor import supervisor_node
from app.agents.notification import notification_node
from app.agents.progress import progress_node
from app.agents.company_research import company_research_node
from app.agents.planner import planner_node
from app.agents.out_of_scope import out_of_scope_node

# Singleton checkpointer to preserve multi-turn state across the app's lifetime
_memory_saver = MemorySaver()

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
    workflow.add_node("out_of_scope", out_of_scope_node)

    # Supervisor is the entry point
    workflow.add_edge(START, "supervisor")

    # Define a conditional edge function
    def route_from_supervisor(state: AgentState) -> str:
        """Reads the routing decision made by the supervisor node."""
        next_agent = state.get("next_agent", "out_of_scope")
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
            "out_of_scope": "out_of_scope",
        }
    )

    # Adaptive routing: Progress -> Planner (if signal detected)
    def route_from_progress(state: AgentState) -> str:
        if state.get("progress_signal") in ["struggle", "mastery"]:
            return "planner"
        return END

    workflow.add_conditional_edges(
        "progress",
        route_from_progress,
        {
            "planner": "planner",
            END: END
        }
    )

    workflow.add_edge("company_research", END)
    workflow.add_edge("planner", END)
    workflow.add_edge("notification", END)
    workflow.add_edge("out_of_scope", END)

    return workflow.compile(checkpointer=_memory_saver)
