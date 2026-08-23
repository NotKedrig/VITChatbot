import pytest
from unittest.mock import MagicMock, patch

from app.graph.workflow import build_graph

# Setup a common graph instance so we can reuse the MemorySaver across turns
@pytest.fixture
def multi_turn_graph():
    return build_graph()

def test_multi_turn_session_preservation(multi_turn_graph):
    """
    Test that state (like runtime_metadata and messages) accumulates correctly
    across multiple sequential user turns using the same thread_id.
    """
    config = {"configurable": {"thread_id": "test_thread_1"}}
    
    # Turn 1: Supervisor -> Company Research
    with patch("app.agents.supervisor.get_provider") as mock_sup_prov, \
         patch("app.agents.company_research.answer_with_rag") as mock_rag:
        
        # Mock Supervisor routing to company_research
        sup_mock_resp = MagicMock()
        sup_mock_resp.text = "company_research"
        sup_mock_resp.cached = True
        sup_mock_resp.model_name = "mock-model"
        sup_mock_resp.model_version = "1.0"
        mock_sup_prov.return_value.complete.return_value = sup_mock_resp
        
        # Mock RAG response
        rag_mock_resp = MagicMock()
        rag_mock_resp.answer = "Novatech requires 7.0 CGPA."
        rag_mock_resp.citations = []
        
        rag_llm_mock = MagicMock()
        rag_llm_mock.model_name = "mock-model"
        rag_llm_mock.model_version = "1.0"
        rag_llm_mock.cached = True
        rag_mock_resp.llm_response = rag_llm_mock
        
        mock_rag.return_value = rag_mock_resp
        
        initial_state = {
            "messages": [{"role": "user", "content": "What is the requirement for Novatech?"}],
            "target_companies": ["Novatech"],
            "skill_profile": {"DSA": "weak"}
        }
        
        state1 = multi_turn_graph.invoke(initial_state, config=config)
        
        assert len(state1["messages"]) == 2
        assert state1["messages"][-1]["content"] == "Novatech requires 7.0 CGPA."
        assert len(state1["runtime_metadata"]) == 2 # 1 for supervisor, 1 for company_research
        assert state1["runtime_metadata"][0]["node"] == "supervisor"
        assert state1["runtime_metadata"][1]["node"] == "company_research"
        
    # Turn 2: Supervisor -> Planner
    with patch("app.agents.supervisor.get_provider") as mock_sup_prov, \
         patch("app.agents.planner.get_provider") as mock_plan_prov:
        
        # Mock Supervisor routing to planner
        sup_mock_resp = MagicMock()
        sup_mock_resp.text = "planner"
        sup_mock_resp.cached = True
        sup_mock_resp.model_name = "mock-model"
        sup_mock_resp.model_version = "1.0"
        mock_sup_prov.return_value.complete.return_value = sup_mock_resp
        
        # Mock Planner output
        import json
        plan_mock_resp = MagicMock()
        plan_mock_resp.text = json.dumps({"tasks": [{"topic": "DSA", "task_description": "Arrays", "priority": "High", "rationale": "weak", "estimated_duration": "2h", "status": "pending"}], "summary": "Plan ready"})
        plan_mock_resp.cached = True
        plan_mock_resp.model_name = "mock-model"
        plan_mock_resp.model_version = "1.0"
        mock_plan_prov.return_value.complete.return_value = plan_mock_resp
        
        turn2_input = {
            "messages": [{"role": "user", "content": "Create a study plan for me."}]
        }
        
        state2 = multi_turn_graph.invoke(turn2_input, config=config)
        
        # The state should accumulate: 
        # Turn 1 User, Turn 1 Agent, Turn 2 User, Turn 2 Agent = 4 messages total
        assert len(state2["messages"]) == 4
        assert "Plan ready" in state2["messages"][-1]["content"]
        assert "DSA" in state2["messages"][-1]["content"]
        
        # Runtime metadata should accumulate:
        # Turn 1 (2 nodes) + Turn 2 (2 nodes) = 4 metadata entries
        assert len(state2["runtime_metadata"]) == 4
        assert state2["runtime_metadata"][2]["node"] == "supervisor"
        assert state2["runtime_metadata"][3]["node"] == "planner"
        
        # Context should remain intact
        assert state2["target_companies"] == ["Novatech"]
        assert state2["skill_profile"]["DSA"] == "weak"


def test_agent_error_fallback(multi_turn_graph):
    """
    Test that an exception within an agent (e.g. provider failure) does not crash
    the graph, but rather records the error in metadata and returns a fallback message.
    """
    config = {"configurable": {"thread_id": "test_thread_error"}}
    
    with patch("app.agents.supervisor.get_provider") as mock_sup_prov, \
         patch("app.agents.company_research.answer_with_rag") as mock_rag:
        
        # Mock Supervisor routing to company_research
        sup_mock_resp = MagicMock()
        sup_mock_resp.text = "company_research"
        sup_mock_resp.cached = True
        sup_mock_resp.model_name = "mock-model"
        sup_mock_resp.model_version = "1.0"
        mock_sup_prov.return_value.complete.return_value = sup_mock_resp
        
        # Force RAG to throw an exception
        mock_rag.side_effect = Exception("Simulated DB timeout")
        
        state = multi_turn_graph.invoke(
            {"messages": [{"role": "user", "content": "Hello?"}]},
            config=config
        )
        
        # Should not crash. Should return fallback message.
        assert "couldn't search the knowledge base" in state["messages"][-1]["content"]
        
        # Metadata should capture the error
        assert "error" in state["runtime_metadata"][1]
        assert "Simulated DB timeout" in state["runtime_metadata"][1]["error"]
