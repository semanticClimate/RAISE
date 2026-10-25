"""
Comprehensive System Verification Test Suite
============================================
Exposes the 12 core verification tests to standard pytest automated collection:
1. Health & Subsystem Verification
2. Operator Dev Checkup
3. Chat History CRUD Synchronization
4. Graph Search Query Parameters (?q= and ?query=)
5. Feedback Ingestion (Optional session_id)
6. Out-of-Scope Intent Routing Softening
7. Validation Error Envelope Compliance
8. Chat SSE Streaming Keep-Alive Events
9. Hardware & Preflight Infrastructure Endpoints
10. Handshake Dual Endpoints
11. Session Renaming (POST & PATCH)
12. Empty Drawer Isolation Contract
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import app

client = TestClient(app, raise_server_exceptions=False)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("postgres") is True or data.get("status") in ("healthy", "PASS")


def test_dev_checkup():
    resp = client.get("/api/dev/checkup")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("overall_status") in (
        "ALL_SYSTEMS_OPERATIONAL",
        "DEGRADED",
        "PARTIAL_OUTAGE",
        "SYSTEMS_ATTENTION_REQUIRED",
    )


def test_chat_history_post_and_get():
    test_session = "test_verify_session_101"
    messages = [
        {"role": "user", "content": "What is IITMRP?"},
        {"role": "assistant", "content": "IITMRP is IIT Madras Research Park.", "citations": []},
    ]
    resp = client.post(
        "/api/chat/history",
        json={"session_id": test_session, "messages": messages, "title": "Test Session"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json().get("status") == "synchronized"

    get_resp = client.get(f"/api/chat/history?session_id={test_session}")
    assert get_resp.status_code == 200
    msgs = get_resp.json().get("messages", [])
    assert len(msgs) >= 2


def test_graph_search_query_param():
    resp_q = client.get("/api/graph/search?q=IIT")
    assert resp_q.status_code == 200, f"Expected 200 for ?q=, got {resp_q.status_code}"
    resp_query = client.get("/api/graph/search?query=IIT")
    assert resp_query.status_code == 200, f"Expected 200 for ?query=, got {resp_query.status_code}"


def test_feedback_optional_session_id():
    resp = client.post(
        "/api/feedback",
        json={"rating": 5, "reason": "Accurate response", "message_id": "msg_test_123"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json().get("status") == "recorded"


def test_query_intake_softened():
    from src.features.query.intake import IntentRouterNode
    node = IntentRouterNode()
    res = node.route("tell me a recipe for chocolate cake")
    if res and res.direct_response:
        assert (
            "This system is specialized for academic institutional analysis. Your query is outside this scope."
            not in res.direct_response
        )


def test_validation_error_envelope():
    resp = client.post("/api/feedback", json="not a json dict")
    assert resp.status_code == 422
    data = resp.json()
    assert data.get("success") is False
    assert "error" in data
    assert data["error"].get("code") == "VALIDATION_ERROR"


def test_chat_stream_sse_events():
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "message": "hello test",
            "mode": "fast",
            "stream": True,
            "session_id": "test_sse_sess",
        },
    ) as stream_resp:
        assert stream_resp.status_code == 200
        content = ""
        for line in stream_resp.iter_lines():
            content += line + "\n"
        assert "data:" in content or "event:" in content


def test_system_modular_endpoints():
    r1 = client.get("/api/system/hardware")
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}"
    hw = r1.json()
    assert "cpu_cores" in hw and "total_ram_gb" in hw

    r2 = client.post("/api/system/test-connections", json={})
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}"
    conn = r2.json()
    assert "redis" in conn and "neo4j" in conn and "postgres" in conn

    r3 = client.get("/api/system/preflight-assets")
    assert r3.status_code == 200, f"Expected 200, got {r3.status_code}"
    pflight = r3.json()
    assert "assets" in pflight and len(pflight["assets"]) >= 5

    r4 = client.get("/api/system/models/catalog")
    assert r4.status_code == 200, f"Expected 200, got {r4.status_code}"
    res_data = r4.json()
    models = res_data if isinstance(res_data, list) else res_data.get("models", [])
    assert len(models) > 0


def test_handshake_endpoints():
    r1 = client.post("/api/v1/auth/handshake", json={})
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}"
    data1 = r1.json()
    assert "token" in data1 and data1.get("status") == "active"

    r2 = client.post("/session/handshake", json={})
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}"
    data2 = r2.json()
    assert "token" in data2 and data2.get("status") == "active"


def test_session_rename():
    sid = "test_verify_session_101"
    r1 = client.post(
        f"/api/chat/sessions/{sid}/rename",
        json={"title": "Renamed Research Session"},
    )
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}: {r1.text}"
    assert r1.json().get("title") == "Renamed Research Session"

    r2 = client.patch(
        f"/api/chat/sessions/{sid}/rename",
        json={"new_title": "Patched Research Session"},
    )
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"
    assert r2.json().get("title") == "Patched Research Session"


def test_empty_drawer_blackhole_fixed():
    resp = client.post(
        "/api/chat",
        json={
            "message": "Hello, provide an overview of research findings",
            "active_docs": [],
            "stream": False,
            "session_id": "test_drawer_sess",
        },
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    decision = data.get("quality_gate_decision")
    assert decision in (
        "accept",
        "retry",
        "unable_to_verify",
        "empty_workspace",
    ), f"Invalid decision: {decision}"
