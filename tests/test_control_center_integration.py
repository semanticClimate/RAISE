"""
Control Center & Pipeline Integration Test Suite
================================================
Validates that the FastAPI backend properly connects with all settings changed
from the frontend Control Center modal:
  1. LLM selection (cloud providers & local Ollama/vLLM)
  2. Neural Engine selection (embedding_model, reranker_model, nli_verifier_model, device)
  3. Memory (PostgreSQL vs In-Memory Python SQLite fallback)
  4. Knowledge Graph (Neo4j vs In-Memory Python Graph)
  5. Cache & Bus (Redis vs In-Memory Python Bus)
  6. Conversational typos and Q&A pipeline responsiveness
"""

import pytest
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "src"))

from app import app
from src.features.system.schemas import SystemConfigRequest
from src.features.system.config_service import save_configuration, get_current_configuration
from src.features.system.connection_service import test_all_connections as probe_all_connections


@pytest.fixture
def client():
    return TestClient(app)


def test_control_center_config_persistence_and_neural_models(tmp_path, monkeypatch):
    """Verify that saving configuration from Control Center updates .env and os.environ without polluting host files."""
    import src.features.system.config_service as cs
    test_env = tmp_path / ".env"
    test_root_env = tmp_path / "root.env"
    test_env.write_text("# Test env\n", encoding="utf-8")
    test_root_env.write_text("# Test root env\n", encoding="utf-8")

    monkeypatch.setattr(cs, "ENV_FILE_PATH", test_env)
    monkeypatch.setattr(cs, "ROOT_ENV_FILE_PATH", test_root_env)
    monkeypatch.setattr("src.infrastructure.credentials.manager.CredentialManager.set_credential", lambda self, p, s: True)

    req = SystemConfigRequest(
        llm_backend="groq",
        llm_mode="cloud_groq",
        groq_api_key="gsk_testdummyapikey1234567890",
        embedding_model="google/embeddinggemma-2",
        reranker_model="jinaai/jina-reranker-v3.5",
        nli_verifier_model="dleemiller/finecat-nli-ultra-l",
        neural_device="auto",
        huggingface_token="hf_testtoken1234567890",
        neo4j_mode="in_memory_fallback",
        postgres_mode="in_memory_fallback",
        redis_mode="in_memory_fallback",
    )

    res = save_configuration(req)
    assert res["status"] == "success"

    # Verify os.environ synchronization
    assert os.environ.get("EMBEDDING_MODEL") == "google/embeddinggemma-2"
    assert os.environ.get("RERANKER_MODEL") == "jinaai/jina-reranker-v3.5"
    assert os.environ.get("NLI_VERIFIER_MODEL") == "dleemiller/finecat-nli-ultra-l"
    assert os.environ.get("NEURAL_DEVICE") == "auto"
    assert os.environ.get("GROQ_API_KEY") == "gsk_testdummyapikey1234567890"

    # Verify that test_env was written to
    assert test_env.exists()
    assert "GROQ_API_KEY=gsk_testdummyapikey1234567890" in test_env.read_text(encoding="utf-8")

    # Verify masked output in get_current_configuration
    curr = get_current_configuration()
    assert curr["embedding_model"] == "google/embeddinggemma-2"
    assert curr["reranker_model"] == "jinaai/jina-reranker-v3.5"
    assert curr["groq_configured"] is True
    assert "..." in curr["groq_masked"] or "********" in curr["groq_masked"]


def test_in_memory_substrates_connection_probes():
    """Verify that in-memory fallback for Neo4j, Redis, and PostgreSQL returns online=True."""
    req = SystemConfigRequest(
        neo4j_mode="in_memory_fallback",
        postgres_mode="in_memory_fallback",
        redis_mode="in_memory_fallback",
        llm_backend="groq",
        groq_api_key="gsk_validkeyformat1234567",
    )

    results = probe_all_connections(req)

    assert results["neo4j"]["online"] is True
    assert results["neo4j"]["mode"] == "in_memory_fallback"

    assert results["redis"]["online"] is True
    assert results["redis"]["mode"] == "in_memory_fallback"

    assert results["postgres"]["online"] is True
    assert results["postgres"]["mode"] == "in_memory_fallback"

    assert results["chroma"]["online"] is True
    assert results["llm"]["online"] is True


def test_hardware_telemetry_endpoint(client):
    """Verify /api/system/hardware and /api/hardware-telemetry return required fields."""
    res = client.get("/api/system/hardware")
    assert res.status_code == 200
    data = res.json()
    assert "total_ram_gb" in data
    assert "ram_total_gb" in data
    assert "cpu_cores" in data
    assert "has_metal_or_cuda" in data

    res2 = client.get("/api/hardware-telemetry")
    assert res2.status_code == 200
    data2 = res2.json()
    assert "total_ram_gb" in data2
    assert "has_metal_or_cuda" in data2


def test_conversational_typo_handling(client):
    """Verify that greeting typos (hekko, sup, heyy) return fast persona reply and do not trigger empty workspace error."""
    res = client.post("/api/chat", json={"message": "hekko", "mode": "fast", "session_id": "test-session-1"})
    assert res.status_code == 200
    data = res.json()
    reply = data.get("reply", "") or data.get("answer", "")
    assert len(reply) > 0
    assert "No documents have been uploaded" not in reply


def test_empty_workspace_message_phrasing(client):
    """Verify empty workspace fallback phrasing does not contain 'from the frontend'."""
    res = client.post("/api/chat", json={"message": "What is the capital of France in these papers?", "mode": "fast", "active_docs": []})
    assert res.status_code == 200
    data = res.json()
    reply = data.get("reply", "") or data.get("answer", "")
    assert "from the frontend" not in reply
    assert "to RAISE" in reply or "No active documents" in reply or "No documents have been uploaded" in reply
