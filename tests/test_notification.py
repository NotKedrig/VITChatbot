import pytest
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from dateutil.tz import gettz

from app.agents.notification import notification_node, _deterministic_parse
from app.db.state.models import Base, StudentProfile, Notification
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import contextlib
from app.config import settings

@pytest.fixture(autouse=True)
def setup_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    
    with patch("app.agents.notification.get_session") as mock_notif_session, \
         patch("app.scheduler.notifier.get_session") as mock_sched_session:
         
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
                
        mock_notif_session.side_effect = mock_session
        mock_sched_session.side_effect = mock_session
        
        # Stop scheduler between tests
        from app.scheduler.notifier import scheduler, _is_started
        if _is_started:
            scheduler.shutdown(wait=False)
            import app.scheduler.notifier as notifier
            notifier._is_started = False
            notifier.scheduler = type(scheduler)() # Re-init fresh
            
        yield TestingSessionLocal

@pytest.fixture
def mock_provider():
    with patch("app.agents.notification.get_provider") as mock_prov:
        provider_instance = MagicMock()
        mock_prov.return_value = provider_instance
        yield provider_instance

def _set_mock_response(mock_provider, message, due_iso):
    mock_resp = MagicMock()
    if due_iso:
        mock_resp.text = f'{{"message": "{message}", "due_date_iso": "{due_iso}"}}'
    else:
        mock_resp.text = f'{{"message": "{message}", "due_date_iso": null}}'
    mock_resp.model_name = "mock"
    mock_resp.model_version = "1"
    mock_resp.cached = True
    mock_provider.complete.return_value = mock_resp

def test_deterministic_parse_relative():
    dt, time_str = _deterministic_parse("Remind me in 5 minutes to read")
    assert time_str == "in 5 minutes"
    assert dt is not None
    assert dt.tzinfo is not None

def test_notification_node_deterministic(setup_db):
    state = {
        "messages": [{"role": "user", "content": "Remind me in 1 minute to test notification"}],
        "student_id": "test_student"
    }
    result = notification_node(state)
    
    # Verify response
    assert "Reminder scheduled" in result["messages"][0]["content"]
    assert not result["runtime_metadata"][0]["llm_fallback"]
    
    # Verify DB
    with setup_db() as db:
        notif = db.query(Notification).first()
        assert notif is not None
        assert notif.student_id == "test_student"
        assert notif.message == "test notification"
        assert notif.status == "pending"

def test_notification_node_llm_fallback(mock_provider, setup_db):
    # E.g. next Friday evening (harder for simple regex)
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    iso_time = future_time.isoformat()
    _set_mock_response(mock_provider, "Complex task", iso_time)
    
    state = {
        "messages": [{"role": "user", "content": "Remind me next Friday evening to do Complex task"}],
        "student_id": "test_student_2"
    }
    result = notification_node(state)
    
    assert "Reminder scheduled" in result["messages"][0]["content"]
    assert result["runtime_metadata"][0]["llm_fallback"]
    
    with setup_db() as db:
        notif = db.query(Notification).first()
        assert notif.message == "Complex task"
        
        # SQLite returns naive datetime, convert for assert
        db_due_at = notif.due_at.replace(tzinfo=timezone.utc) if notif.due_at.tzinfo is None else notif.due_at
        assert db_due_at == future_time

def test_scheduler_execution_and_duplicate_protection(setup_db):
    from app.scheduler.notifier import start_scheduler, dispatch_notification, scheduler
    
    # Seed DB with a due job
    with setup_db() as db:
        profile = StudentProfile(student_id="sched_student")
        db.add(profile)
        # Due in the past (so it runs immediately on start)
        notif = Notification(student_id="sched_student", message="Fire immediately", due_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        db.add(notif)
        db.commit()
        notif_id = notif.id
        
    start_scheduler()
    
    # Instead of waiting for APScheduler's background thread (which fails with sqlite :memory: threading issues), 
    # we manually call the dispatch function to test its duplicate protection logic directly.
    dispatch_notification(notif_id)
    
    with setup_db() as db:
        n = db.query(Notification).filter_by(id=notif_id).first()
        assert n.status == "dispatched"
        assert n.dispatched_at is not None
        
    # Test duplicate protection
    dispatch_notification(notif_id) # Should return safely without error
    
def test_invalid_past_time(setup_db):
    state = {
        "messages": [{"role": "user", "content": "Remind me 5 minutes ago to do something"}],
        "student_id": "test_student_3"
    }
    # Deterministic parses it, but rejects because it's past, so falls back to LLM.
    # We'll mock the LLM to also give a past date.
    with patch("app.agents.notification.get_provider") as mock_prov:
        prov = MagicMock()
        resp = MagicMock()
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        resp.text = f'{{"message": "do something", "due_date_iso": "{past_iso}"}}'
        prov.complete.return_value = resp
        mock_prov.return_value = prov
        
        result = notification_node(state)
        
    assert "in the past" in result["messages"][0]["content"]
