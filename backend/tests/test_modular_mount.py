"""
Quick verification of server.py and app.py integration after modularization.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app as core_app
import server

def test_server_and_core_app_mount():
    """Verify that core OpenAPI paths and gateway singletons mount properly."""
    assert len(core_app.openapi()["paths"]) > 0
    assert len(server.app.openapi()["paths"]) > 0

    # Check that core singletons are present on server.app.state
    for key in ["rag_engine", "postgres_manager", "redis_cache", "session_memory_manager", "dev_operator"]:
        val = getattr(server.app.state, key, None)
        assert val is not None, f"Expected {key} on server.app.state!"

