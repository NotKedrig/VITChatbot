import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app

client = TestClient(app)

@patch("app.main.compiled_graph.invoke")
def test_chat_endpoint_success(mock_invoke):
    mock_invoke.return_value = {
        "messages": [{"role": "user", "content": "Hello"}, {"role": "agent", "content": "Hi"}],
        "current_plan": {"tasks": []},
        "next_agent": "planner",
        "progress_signal": None
    }
    
    response = client.post("/api/chat", json={
        "message": "Hello",
        "thread_id": "thread123",
        "student_id": "test_student"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 2
    assert data["next_agent"] == "planner"

@patch("app.main.compiled_graph.get_state")
def test_get_thread_state_empty(mock_get_state):
    mock_get_state.return_value = None
    
    response = client.get("/api/thread/nonexistent")
    assert response.status_code == 200
    data = response.json()
    assert data["messages"] == []
    assert data["current_plan"] is None

@patch("app.main.get_session")
def test_get_student_state_not_found(mock_get_session):
    mock_db = MagicMock()
    mock_db.query().filter_by().first.return_value = None
    mock_get_session.return_value.__enter__.return_value = mock_db
    
    response = client.get("/api/state/nonexistent")
    assert response.status_code == 404
