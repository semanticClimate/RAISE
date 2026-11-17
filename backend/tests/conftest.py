"""
Pytest global configuration and fixtures for RAISE Backend.
Ensures singleton state isolation and prevents network socket deadlocks during test runs.
"""

import os
import pytest
import socket
import src.infrastructure.providers.router as router_mod


@pytest.fixture(autouse=True)
def isolate_environment():
    """Preserve and restore environment variables across tests to prevent cross-test leakage."""
    orig_env = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(orig_env)


@pytest.fixture(autouse=True)
def reset_router_singleton():
    """Reset the ProviderRouter singleton before and after every test."""
    router_mod._router_instance = None
    yield
    router_mod._router_instance = None


@pytest.fixture(autouse=True)
def guard_socket_probes(monkeypatch):
    """
    Prevent socket probes from hanging on local background ports (e.g. vLLM:8002, Ollama:11434)
    during automated unit test runs on Windows or CI environments, while passing arguments cleanly.
    """
    orig_create_connection = socket.create_connection

    def guarded_create_connection(address, *args, **kwargs):
        host, port = address[0], address[1]
        if os.getenv("ALLOW_LOCAL_SOCKET_PROBES") != "1":
            if host in ("127.0.0.1", "localhost", "0.0.0.0") and port in (8002, 11434):
                raise ConnectionRefusedError(f"[TEST GUARD] Fast-failing connection to {host}:{port}")
        return orig_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
