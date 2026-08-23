import json
import pytest
from unittest.mock import MagicMock, patch

from app.agents.planner import planner_node, StudyPlan, StudyTask
from app.graph.state import AgentState

@pytest.fixture
def mock_planner_provider():
    with patch("app.agents.planner.get_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_response = MagicMock()
        
        # Valid JSON matching StudyPlan schema
        mock_response.text = json.dumps({
            "tasks": [
                {
                    "topic": "DSA",
                    "task_description": "Solve 5 array problems",
                    "estimated_duration": "2 hours",
                    "priority": "High",
                    "rationale": "Weak topic",
                    "status": "pending"
                }
            ],
            "summary": "You've got this!"
        })
        mock_response.cached = True
        mock_provider.complete.return_value = mock_response
        mock_get_provider.return_value = mock_provider
        
        yield mock_provider

def test_planner_normal_generation(mock_planner_provider):
    state: AgentState = {
        "messages": [{"role": "user", "content": "I need a study plan."}],
        "target_companies": ["Novatech"],
        "skill_profile": {"DSA": "weak", "DBMS": "strong"},
        "available_time": "10 hours a week"
    }

    result = planner_node(state)
    
    # Assert provider was called with the correct schema
    mock_planner_provider.complete.assert_called_once()
    call_kwargs = mock_planner_provider.complete.call_args.kwargs
    assert call_kwargs["response_schema"] == StudyPlan
    
    # Assert the returned state changes
    assert "messages" in result
    agent_message = result["messages"][0]["content"]
    assert "You've got this!" in agent_message
    assert "DSA" in agent_message
    assert "Solve 5 array problems" in agent_message
    
    assert "current_plan" in result
    assert result["current_plan"]["tasks"][0]["topic"] == "DSA"
    assert result["last_agent_output"] == agent_message.strip()


@patch("app.agents.planner.get_provider")
def test_planner_failure_handling(mock_get_provider):
    mock_provider = MagicMock()
    mock_provider.complete.side_effect = Exception("API Error")
    mock_get_provider.return_value = mock_provider
    
    state: AgentState = {
        "messages": [{"role": "user", "content": "plan plz"}]
    }
    
    result = planner_node(state)
    
    assert "Failed to generate plan." in result["current_plan"]["summary"]
    assert "I encountered an error" in result["messages"][0]["content"]

