import pytest
from app.agents.planner import planner_node
from app.db.state.models import Base, PlanRevisionLog, StudentProfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch
import contextlib

@pytest.fixture(autouse=True)
def setup_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    
    with patch("app.agents.planner.get_session") as mock_get_session:
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
        
        # Insert test student profile
        with TestingSessionLocal() as session:
            session.add(StudentProfile(student_id="test_adaptive_1"))
            session.add(StudentProfile(student_id="test_adaptive_2"))
            session.commit()
            
        yield TestingSessionLocal

@pytest.fixture
def base_plan():
    return {
        "tasks": [
            {
                "topic": "DSA",
                "task_description": "Do arrays",
                "estimated_duration": "2 hours",
                "priority": "Medium",
                "rationale": "Base plan",
                "status": "pending"
            },
            {
                "topic": "DBMS",
                "task_description": "SQL joins",
                "estimated_duration": "1 hour",
                "priority": "Low",
                "rationale": "Base plan",
                "status": "pending"
            }
        ],
        "summary": "Initial plan"
    }

def test_planner_adaptive_struggle(base_plan, setup_db):
    state = {
        "student_id": "test_adaptive_1",
        "progress_signal": "struggle",
        "affected_topic": "DSA",
        "current_plan": base_plan
    }
    
    result = planner_node(state)
    
    new_plan = result["current_plan"]
    tasks = new_plan["tasks"]
    
    assert result["progress_signal"] == "none"
    assert tasks[0]["topic"] == "DSA"
    assert tasks[0]["priority"] == "High"
    
    with setup_db() as db:
        logs = db.query(PlanRevisionLog).filter_by(student_id="test_adaptive_1").all()
        assert len(logs) == 1
        assert logs[0].triggering_signal == "struggle"

def test_planner_adaptive_mastery(base_plan, setup_db):
    state = {
        "student_id": "test_adaptive_2",
        "progress_signal": "mastery",
        "affected_topic": "DSA",
        "current_plan": base_plan
    }
    
    result = planner_node(state)
    new_plan = result["current_plan"]
    tasks = new_plan["tasks"]
    
    dsa_tasks = [t for t in tasks if t["topic"] == "DSA"]
    assert dsa_tasks[0]["priority"] == "Low"
    
    with setup_db() as db:
        logs = db.query(PlanRevisionLog).filter_by(student_id="test_adaptive_2").all()
        assert len(logs) == 1
        assert logs[0].triggering_signal == "mastery"
