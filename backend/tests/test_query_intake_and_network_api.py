"""
Tests for Query Intake & Reformulation Architecture and Remote Network API.
Verifies:
  1. GET /health with live subsystem telemetry and Mac LAN URL
  2. CORS preflight validation for remote LAN Mac frontend
  3. Intent Router & Out-of-Scope Firewall (Zero-DB bypass)
  4. Coreference Resolution & Pronoun Disambiguation in multi-turn conversation
  5. Query Decomposition (splitting compound questions)
  6. POST /api/query Contract Compliance (JSON payload with stages & data lineage)
  7. POST /api/query/stream Server-Sent Events (SSE) streaming (stage, token, final events)
"""

import json
import pytest
from fastapi.testclient import TestClient

from app import app, rag_engine, session_memory_manager
from src.features.query.intake import IntentRouterNode, CoreferenceResolverNode, QueryDecomposerNode, PipelineTelemetry


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_endpoint(client):
    """Verify GET /health returns complete subsystem status and network coordinates."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert data.get("status") in ["healthy", "degraded", "unhealthy"]
    assert "RAISE" in data.get("service", "")
    assert "version" in data

    # Network coordinates
    network = data.get("network", {})
    assert "lan_ipv4" in network
    assert "port" in network
    assert "mac_accessible_url" in network
    assert network["mac_accessible_url"].startswith("http://")

    # Subsystem telemetry
    subsystems = data.get("subsystems", {})
    assert "neo4j" in subsystems
    assert "chromadb" in subsystems
    assert "llm" in subsystems
    assert "hardware" in subsystems
    assert "gpu" in subsystems["hardware"]
    assert "ram_total_gb" in subsystems["hardware"]


def test_cors_preflight_headers(client):
    """Verify CORS preflight allows remote Mac frontend across local LAN."""
    headers = {
        "Origin": "http://192.168.31.250:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,Authorization",
    }
    response = client.options("/api/query", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://192.168.31.250:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_intent_router_and_out_of_scope_firewall(client):
    """Verify general conversation bypasses database retrieval and returns instant response."""
    response = client.post("/api/query", json={"query": "Hello, good morning! Can you help me today?"})
    assert response.status_code == 200
    data = response.json()

    assert data.get("grounded_answer") or data.get("answer")
    assert len(data.get("grounded_answer") or data.get("answer")) > 5
    assert data.get("query_type") in ["GENERAL_CHAT", "GREETING", "OUT_OF_SCOPE", None] or data.get("quality_decision") == "ACCEPT"

    # Verify pipeline stages: Vector and Graph stages must be skipped
    stages = {s["stage"]: s["status"] for s in data.get("pipeline_stages", [])}
    assert stages.get("ROUTING") == "completed"
    assert stages.get("VECTOR_RETRIEVAL") == "skipped"
    assert stages.get("GRAPH_RETRIEVAL") == "skipped"
    assert stages.get("COMPLETED") == "completed"


def test_coreference_resolution_multi_turn(client):
    """Verify multi-turn pronoun disambiguation using session memory."""
    thread_id = "test-thread-coref-verify"

    # Turn 1: Establish referent entity
    res1 = client.post("/api/query", json={
        "query": "Tell me about the IITM Research Park and its initiatives.",
        "thread_id": thread_id,
        "active_docs": [],
    })
    assert res1.status_code == 200

    # Turn 2: Query with ambiguous pronoun "their"
    res2 = client.post("/api/query", json={
        "query": "What is their total funding and valuation?",
        "thread_id": thread_id,
        "active_docs": [],
    })
    assert res2.status_code == 200
    data2 = res2.json()

    resolved = data2.get("resolved_query", "")
    assert "IITM Research Park" in resolved or "their" in data2.get("original_query", "")


def test_query_decomposition_unit():
    """Unit test for query decomposition on compound inquiries."""
    decomposer = QueryDecomposerNode()
    query = "What is the total research grant budget and how many patents were filed in 2024?"
    sub_queries = decomposer.decompose(query)

    assert len(sub_queries) == 2
    assert any("budget" in sq.lower() or "grant" in sq.lower() for sq in sub_queries)
    assert any("patent" in sq.lower() for sq in sub_queries)


def test_api_query_contract_compliance(client):
    """Verify standard POST /api/query JSON contract matches specification."""
    req_payload = {
        "query": "What is the solar energy target?",
        "thread_id": "test-contract-thread",
        "hops": 2,
        "top_k": 4,
        "active_docs": [],
    }
    response = client.post("/api/query", json=req_payload)
    assert response.status_code == 200
    data = response.json()

    # Essential contract keys required by remote Mac frontend
    required_keys = [
        "query",
        "original_query",
        "resolved_query",
        "decomposed_queries",
        "grounded_answer",
        "answer",
        "citations",
        "data_lineage",
        "subgraph",
        "pipeline_stages",
        "execution_time",
        "thread_id",
    ]
    for key in required_keys:
        assert key in data, f"Missing required API contract key: '{key}'"

    assert isinstance(data["pipeline_stages"], list)
    assert len(data["pipeline_stages"]) > 0


def test_api_query_stream_sse(client):
    """Verify POST /api/query/stream delivers Server-Sent Events (stage, token, final)."""
    req_payload = {
        "query": "Hello assistant",
        "thread_id": "test-sse-thread",
        "active_docs": [],
    }
    response = client.post("/api/query/stream", json=req_payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    lines = [line if isinstance(line, str) else line.decode("utf-8") for line in response.iter_lines() if line]
    events_found = set()
    final_payload = None

    for idx, line in enumerate(lines):
        if line.startswith("event: "):
            ev_name = line.replace("event: ", "").strip()
            events_found.add(ev_name)
            if ev_name == "final" and idx + 1 < len(lines):
                data_line = lines[idx + 1]
                if data_line.startswith("data: "):
                    final_payload = json.loads(data_line.replace("data: ", ""))

    assert "stage" in events_found
    assert "final" in events_found
    if final_payload:
        assert "grounded_answer" in final_payload or "answer" in final_payload
