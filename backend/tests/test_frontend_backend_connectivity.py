"""
Automated Frontend-Backend Connectivity & Schema Compliance Tests
================================================================
Verifies that all HTTP endpoints called by the React frontend
(services/SystemService, platformAdapter, useBackendConnection, useDocumentLibrary)
exist, return valid JSON, and accept the exact payloads sent by the frontend.
"""

import pytest
from fastapi.testclient import TestClient
from app import app
from src.core.config import models


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_and_readiness_endpoints(client):
    """Verify health and readiness endpoints called by useBackendConnection and systemService."""
    res_api_health = client.get("/api/health")
    assert res_api_health.status_code == 200
    assert "status" in res_api_health.json()

    res_health = client.get("/health")
    assert res_health.status_code == 200

    res_api_ready = client.get("/api/ready")
    assert res_api_ready.status_code in (200, 503)
    assert "status" in res_api_ready.json()

    res_ready = client.get("/ready")
    assert res_ready.status_code in (200, 503)


def test_hardware_telemetry_endpoints(client):
    """Verify hardware telemetry endpoints called by platformAdapter and useBackendTelemetry."""
    res_hw = client.get("/api/hardware-telemetry")
    assert res_hw.status_code == 200
    data_hw = res_hw.json()
    assert "vram_used_gb" in data_hw or "ram_total_gb" in data_hw or "hardware" in data_hw or "status" in data_hw

    res_sys_hw = client.get("/api/system/hardware")
    assert res_sys_hw.status_code == 200
    data_sys = res_sys_hw.json()
    assert isinstance(data_sys, dict)


def test_system_config_lifecycle(client, tmp_path, monkeypatch):
    """Verify GET and POST /api/system/config called by platformAdapter and ControlCenter."""
    import src.features.system.config_service as cs
    test_env = tmp_path / ".env"
    test_root_env = tmp_path / "root.env"
    test_env.write_text("# Test env\n", encoding="utf-8")
    test_root_env.write_text("# Test root env\n", encoding="utf-8")

    monkeypatch.setattr(cs, "ENV_FILE_PATH", test_env)
    monkeypatch.setattr(cs, "ROOT_ENV_FILE_PATH", test_root_env)
    monkeypatch.setattr("src.infrastructure.credentials.manager.CredentialManager.set_credential", lambda self, p, s: True)

    # 1. GET /api/system/config
    get_res = client.get("/api/system/config")
    assert get_res.status_code == 200
    cfg_data = get_res.json()
    assert "llm_backend" in cfg_data or "active_models" in cfg_data

    # 2. POST /api/system/config with frontend ControlCenter payload format
    payload = {
        "llm_backend": "groq",
        "llm_mode": "cloud_groq",
        "llm_model": models.GROQ_MODEL_NAME,
        "embedding_model": models.EMBEDDING_MODEL_NAME,
        "reranker_model": models.RERANKER_MODEL_NAME,
        "nli_verifier_model": models.NLI_MODEL_NAME,
        "embedding_device": "cpu",
        "neural_device": "cpu",
        "groq_api_key": "gsk_test_key_placeholder_for_unit_tests",
        "neo4j_mode": "embedded",
        "redis_mode": "in_memory",
        "postgres_mode": "in_memory",
    }
    post_res = client.post("/api/system/config", json=payload)
    assert post_res.status_code == 200
    assert post_res.json().get("status") == "success"


def test_dynamic_routing_orchestrator_endpoints(client):
    """Verify GET and POST /api/system/routing called by LLMRoutingOrchestrator."""
    # 1. GET dynamic-llms
    dyn_res = client.get("/api/system/dynamic-llms")
    assert dyn_res.status_code == 200
    assert isinstance(dyn_res.json(), list)

    # 2. GET routing status
    route_res = client.get("/api/system/routing")
    assert route_res.status_code == 200
    route_data = route_res.json()
    assert "fallback_chain" in route_data or "fallback_order" in route_data

    # 3. POST routing priority update
    update_payload = {
        "fallback_order": ["vllm", "groq", "gemini", "ollama", "local"],
        "disabled_providers": ["mistral"],
        "primary_provider": "vllm",
        "routing_policy": "priority_fallback",
    }
    post_route = client.post("/api/system/routing", json=update_payload)
    assert post_route.status_code == 200
    assert post_route.json().get("status") == "success"


def test_models_catalog_and_preflight_endpoints(client):
    """Verify /api/system/models/catalog and /api/system/preflight-assets called by ControlCenter."""
    cat_res = client.get("/api/system/models/catalog")
    assert cat_res.status_code == 200
    assert isinstance(cat_res.json(), list)

    pre_res = client.get("/api/system/preflight-assets")
    assert pre_res.status_code == 200
    pre_data = pre_res.json()
    assert isinstance(pre_data, dict)
    assert "assets" in pre_data
    assert isinstance(pre_data["assets"], list)


def test_provider_verification_endpoints(client):
    """Verify /api/system/providers/verify and /api/system/test-llm-key called by platformAdapter."""
    # 1. Providers verify endpoint
    ver_payload = {
        "provider": "custom",
        "api_key": "test_dummy_key_12345",
    }
    ver_res = client.post("/api/system/providers/verify", json=ver_payload)
    assert ver_res.status_code == 200
    assert "online" in ver_res.json()

    # 2. Fallback test-llm-key endpoint
    test_key_payload = {
        "llm_mode": "cloud_groq",
        "groq_api_key": "test_dummy_key_12345",
    }
    key_res = client.post("/api/system/test-llm-key", json=test_key_payload)
    assert key_res.status_code == 200
    assert "llm" in key_res.json()


def test_models_load_endpoint(client):
    """Verify POST /api/system/models/load called by platformAdapter."""
    load_payload = {
        "embedding_model": models.EMBEDDING_MODEL_NAME,
        "reranker_model": models.RERANKER_MODEL_NAME,
        "nli_verifier_model": models.NLI_MODEL_NAME,
    }
    load_res = client.post("/api/system/models/load", json=load_payload)
    assert load_res.status_code == 200
    assert load_res.json().get("status") in ("success", "degraded")


def test_auth_handshake_endpoints(client):
    """Verify POST /api/v1/auth/handshake and /session/handshake called by WebSocket connection."""
    res1 = client.post("/api/v1/auth/handshake")
    assert res1.status_code == 200
    assert "token" in res1.json()

    res2 = client.post("/session/handshake")
    assert res2.status_code == 200
    assert "token" in res2.json()


def test_document_library_endpoints(client):
    """Verify /api/documents and /api/documents/manifest called by useDocumentLibrary."""
    res_docs = client.get("/api/documents")
    assert res_docs.status_code == 200
    docs_data = res_docs.json()
    assert isinstance(docs_data, (list, dict))

    res_man = client.get("/api/documents/manifest")
    assert res_man.status_code == 200
    man_data = res_man.json()
    assert isinstance(man_data, (list, dict))
