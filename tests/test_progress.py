import pytest
from unittest.mock import MagicMock, patch
from app.agents.progress import progress_node, STRUGGLE_THRESHOLD, MASTERY_THRESHOLD
from app.db.state.models import Base, StudentProfile, PerformanceLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import contextlib

@pytest.fixture(autouse=True)
def setup_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    
    with patch("app.agents.progress.get_session") as mock_get_session:
        @contextlib.contextmanager
        def mock_session(*args, **kwargs):
            session = TestingSessionLocal()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
                
        mock_get_session.side_effect = mock_session
        yield TestingSessionLocal

@pytest.fixture
def mock_provider():
    with patch("app.agents.progress.get_provider") as mock_prov:
        provider_instance = MagicMock()
        mock_prov.return_value = provider_instance
        yield provider_instance

def _set_mock_response(mock_provider, topic, score):
    mock_resp = MagicMock()
    mock_resp.text = f'{{"topic": "{topic}", "score": {score}}}'
    mock_resp.model_name = "mock"
    mock_resp.model_version = "1"
    mock_resp.cached = True
    mock_provider.complete.return_value = mock_resp

def test_progress_struggle(mock_provider, setup_db):
    _set_mock_response(mock_provider, "DSA", STRUGGLE_THRESHOLD - 10)
    
    state = {
        "messages": [{"role": "user", "content": "I got 40 in DSA"}],
        "student_id": "test_student"
    }
    
    result = progress_node(state)
    
    assert result["progress_signal"] == "struggle"
    assert result["affected_topic"] == "DSA"
    assert "struggling" in result["messages"][0]["content"].lower()

def test_progress_mastery(mock_provider, setup_db):
    _set_mock_response(mock_provider, "DBMS", MASTERY_THRESHOLD + 5)
    
    state = {
        "messages": [{"role": "user", "content": "I got 90 in DBMS"}],
        "student_id": "test_student_2"
    }
    
    result = progress_node(state)
    
    assert result["progress_signal"] == "mastery"
    assert result["affected_topic"] == "DBMS"
    assert "mastered" in result["messages"][0]["content"].lower()

def test_persistent_status_weak(mock_provider, setup_db):
    # First report
    _set_mock_response(mock_provider, "Aptitude", 30)
    state = {"messages": [{"role": "user", "content": "30 in Aptitude"}], "student_id": "test_student_3"}
    progress_node(state)
    
    # Second report
    _set_mock_response(mock_provider, "Aptitude", 40)
    progress_node(state)
    
    # Check DB
    with setup_db() as db:
        profile = db.query(StudentProfile).filter_by(student_id="test_student_3").first()
        assert profile is not None
        assert profile.skill_profile.get("Aptitude") == "weak"

def test_persistent_status_mastered(mock_provider, setup_db):
    _set_mock_response(mock_provider, "System Design", 90)
    state = {"messages": [{"role": "user", "content": "90 in SD"}], "student_id": "test_student_4"}
    progress_node(state)
    _set_mock_response(mock_provider, "System Design", 95)
    progress_node(state)
    
    with setup_db() as db:
        profile = db.query(StudentProfile).filter_by(student_id="test_student_4").first()
        assert profile.skill_profile.get("System Design") == "mastered"

def test_invalid_input(mock_provider, setup_db):
    mock_resp = MagicMock()
    mock_resp.text = '{"topic": null, "score": null}'
    mock_provider.complete.return_value = mock_resp
    
    state = {"messages": [{"role": "user", "content": "I failed"}], "student_id": "test_student_5"}
    result = progress_node(state)
    
    assert result["progress_signal"] == "none"
    assert "couldn't properly record" in result["messages"][0]["content"]
