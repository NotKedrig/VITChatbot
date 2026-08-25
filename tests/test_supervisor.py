import pytest
from unittest.mock import MagicMock, patch
from app.agents.rule_router import rule_route
from app.graph.state import AgentState
from app.graph.workflow import build_graph

# ---------------------------------------------------------------------------
# Test Rule Router (Deterministic Baseline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("utterance, expected", [
    ("What is the CTC for Novatech?", "company_research"),
    ("Tell me about the eligibility criteria for Aether Robotics.", "company_research"),
    ("Create a timetable for my DSA prep.", "planner"),
    ("I need a syllabus for the aptitude test.", "planner"),
    ("I completely failed my mock interview yesterday.", "progress"),
    ("I just finished the arrays chapter.", "progress"),
    ("Remind me to submit my resume tomorrow.", "notification"),
    ("Set an alert for the deadline.", "notification"),
    ("Just saying hello", "out_of_scope"), # Default fallback
    ("how to make dosa", "out_of_scope"),
    ("what is the capital of France?", "out_of_scope"),
    ("tell me a joke", "out_of_scope"),
])
def test_rule_router_accuracy(utterance: str, expected: str):
    """Verify the rule router baseline correctly classifies standard phrases."""
    assert rule_route(utterance) == expected


# ---------------------------------------------------------------------------
# Test LangGraph Wiring (Mocked LLM)
# ---------------------------------------------------------------------------

@patch("app.graph.workflow.planner_node")
@patch("app.agents.supervisor.get_provider")
def test_langgraph_routing_with_mock(mock_get_provider, mock_planner_node):
    """
    Verify that the deterministic graph wiring works without burning API quota.
    We mock the provider to return 'planner' and ensure the graph routes there.
    """
    # Setup mock provider response for supervisor
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "planner"
    mock_response.cached = True
    mock_response.model_name = "mock-model"
    mock_response.model_version = "1.0"
    mock_provider.complete.return_value = mock_response
    mock_get_provider.return_value = mock_provider

    # Setup mock planner node to simulate successful routing
    def dummy_planner(state):
        return {"messages": [{"role": "agent", "content": "[STUB] Planner Agent received the request."}], "next_agent": "planner"}
    mock_planner_node.side_effect = dummy_planner

    graph = build_graph()
    
    initial_state = {
        "messages": [{"role": "user", "content": "Can you build me a study schedule?"}]
    }

    # Execute graph
    final_state = graph.invoke(
        initial_state, 
        config={"configurable": {"thread_id": "test_routing_mock"}}
    )

    # Verify provider was called
    mock_provider.complete.assert_called_once()
    
    # Verify the supervisor correctly updated the next_agent state
    assert final_state["next_agent"] == "planner"
    
    # Verify the downstream mock (planner_node) was executed
    messages = final_state.get("messages", [])
    assert len(messages) == 2
    assert "[STUB] Planner Agent" in messages[-1]["content"]

@patch("app.agents.supervisor.get_provider")
def test_langgraph_routing_out_of_scope(mock_get_provider):
    """
    Verify that an out of scope request correctly routes to the deterministic out_of_scope node
    and does not trigger any LLM calls beyond the supervisor.
    """
    # Setup mock provider response for supervisor
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "out_of_scope"
    mock_response.cached = True
    mock_response.model_name = "mock-model"
    mock_response.model_version = "1.0"
    mock_provider.complete.return_value = mock_response
    mock_get_provider.return_value = mock_provider

    graph = build_graph()
    
    initial_state = {
        "messages": [{"role": "user", "content": "how to make dosa"}]
    }

    # Execute graph
    final_state = graph.invoke(
        initial_state, 
        config={"configurable": {"thread_id": "test_routing_out_of_scope"}}
    )

    # Verify provider was called
    mock_provider.complete.assert_called_once()
    
    # Verify the supervisor correctly updated the next_agent state
    assert final_state["next_agent"] == "out_of_scope"
    
    # Verify the output message matches the deterministic rejection
    messages = final_state.get("messages", [])
    assert len(messages) == 2
    assert "I'm designed to help with placement preparation" in messages[-1]["content"]


# ---------------------------------------------------------------------------
# Test LLM Smoke Test (Uses Cache)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Daily Gemini Free Tier quota exhausted.")
@pytest.mark.smoke
def test_supervisor_live_cached():
    """
    A single live/cached smoke test to verify the actual Supervisor prompt and API integration.
    Relies on app/llm/cache.py to prevent burning quota on subsequent runs.
    """
    graph = build_graph()
    
    initial_state = {
        "messages": [{"role": "user", "content": "What is the interview process for Novatech?"}]
    }
    
    # Execute graph - will hit Gemini API the first time, then cache it.
    final_state = graph.invoke(initial_state)
    
    assert final_state["next_agent"] == "company_research"
    messages = final_state.get("messages", [])
    assert "[STUB] Company Research Agent" in messages[-1]["content"]

