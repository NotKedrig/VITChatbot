import pytest
import tempfile
from pathlib import Path
from app.db.state.models import Base

def test_debug_db(monkeypatch):
    import app.db.state.db as db_module
    from app.config import settings
    
    db_module._engine = None
    db_module._SessionLocal = None
    
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = str(Path(tmp) / "test.db")
        db_url = f"sqlite:///{db_path}"
        
        monkeypatch.setattr(settings, "database_url", db_url)
        print("Patched settings URL:", settings.database_url)
        
        db_module.create_tables()
        engine = db_module.get_engine()
        print("Engine URL:", engine.url)
