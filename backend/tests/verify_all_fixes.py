import sys
import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app import app, redis_cache, postgres_manager

client = TestClient(app, raise_server_exceptions=False)

def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    print("Health response:", data)
    assert data.get("postgres") is True or data.get("status") in ("healthy", "PASS")
    print("✓ /api/health passed")

def test_dev_checkup():
    resp = client.get("/api/dev/checkup")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("overall_status") in ("ALL_SYSTEMS_OPERATIONAL", "DEGRADED", "PARTIAL_OUTAGE", "SYSTEMS_ATTENTION_REQUIRED")
    print("✓ /api/dev/checkup passed")

def test_chat_history_post_and_get():
    test_session = "test_verify_session_101"
    messages = [
        {"role": "user", "content": "What is IITMRP?"},
        {"role": "assistant", "content": "IITMRP is IIT Madras Research Park.", "citations": []}
    ]
    resp = client.post("/api/chat/history", json={"session_id": test_session, "messages": messages, "title": "Test Session"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("status") == "synchronized"
    print("✓ POST /api/chat/history passed")

    get_resp = client.get(f"/api/chat/history?session_id={test_session}")
    assert get_resp.status_code == 200
    msgs = get_resp.json().get("messages", [])
    assert len(msgs) >= 2
    print("✓ GET /api/chat/history passed")

def test_graph_search_query_param():
    resp_q = client.get("/api/graph/search?q=IIT")
    assert resp_q.status_code == 200, f"Expected 200 for ?q=, got {resp_q.status_code}"
    resp_query = client.get("/api/graph/search?query=IIT")
    assert resp_query.status_code == 200, f"Expected 200 for ?query=, got {resp_query.status_code}"
    print("✓ /api/graph/search (?q= and ?query=) passed")

def test_feedback_optional_session_id():
    resp = client.post("/api/feedback", json={
        "rating": 5,
        "reason": "Accurate response",
        "message_id": "msg_test_123"
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json().get("status") == "recorded"
    print("✓ POST /api/feedback (optional session_id) passed")

def test_query_intake_softened():
    from src.features.query.intake import IntentRouterNode
    node = IntentRouterNode()
    res = node.route("tell me a recipe for chocolate cake")
    if res and res.direct_response:
        assert "This system is specialized for academic institutional analysis. Your query is outside this scope." not in res.direct_response
        print("✓ Intake intent refusal softened:", res.direct_response[:80], "...")

def test_validation_error_envelope():
    resp = client.post("/api/feedback", json="not a json dict")
    assert resp.status_code == 422
    data = resp.json()
    assert data.get("success") is False
    assert "error" in data
    assert data["error"].get("code") == "VALIDATION_ERROR"
    print("✓ Unified validation error envelope passed:", data)

def test_chat_stream_sse_events():
    with client.stream("POST", "/api/chat", json={
        "message": "hello test",
        "mode": "fast",
        "stream": True,
        "session_id": "test_sse_sess"
    }) as stream_resp:
        assert stream_resp.status_code == 200
        content = ""
        for line in stream_resp.iter_lines():
            content += line + "\n"
        assert "data:" in content or "event:" in content
        print("✓ Chat SSE streaming events passed")

def test_system_modular_endpoints():
    r1 = client.get("/api/system/hardware")
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}"
    hw = r1.json()
    assert "cpu_cores" in hw and "total_ram_gb" in hw
    print(f"✓ /api/system/hardware passed ({hw.get('cpu_cores')} cores, {hw.get('total_ram_gb')} GB RAM)")

    r2 = client.post("/api/system/test-connections", json={})
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}"
    conn = r2.json()
    assert "redis" in conn and "neo4j" in conn and "postgres" in conn
    print(f"✓ /api/system/test-connections passed (redis={conn['redis'].get('online')}, neo4j={conn['neo4j'].get('online')})")

    r3 = client.get("/api/system/preflight-assets")
    assert r3.status_code == 200, f"Expected 200, got {r3.status_code}"
    pflight = r3.json()
    assert "assets" in pflight and len(pflight["assets"]) >= 5
    print(f"✓ /api/system/preflight-assets passed ({len(pflight['assets'])} neural assets tracked)")

    r4 = client.get("/api/system/models/catalog")
    assert r4.status_code == 200, f"Expected 200, got {r4.status_code}"
    res_data = r4.json()
    models = res_data if isinstance(res_data, list) else res_data.get("models", [])
    assert len(models) > 0
    print(f"✓ /api/system/models/catalog passed ({len(models)} dynamic open-weights discovered)")

def test_handshake_endpoints():
    r1 = client.post("/api/v1/auth/handshake", json={})
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}"
    data1 = r1.json()
    assert "token" in data1 and data1.get("status") == "active"
    print(f"✓ POST /api/v1/auth/handshake passed (token={data1['token'][:16]}...)")

    r2 = client.post("/session/handshake", json={})
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}"
    data2 = r2.json()
    assert "token" in data2 and data2.get("status") == "active"
    print(f"✓ POST /session/handshake passed (token={data2['token'][:16]}...)")

def test_session_rename():
    sid = "test_verify_session_101"
    r1 = client.post(f"/api/chat/sessions/{sid}/rename", json={"title": "Renamed Research Session"})
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}: {r1.text}"
    assert r1.json().get("title") == "Renamed Research Session"
    print("✓ POST /api/chat/sessions/{id}/rename passed")

    r2 = client.patch(f"/api/chat/sessions/{sid}/rename", json={"new_title": "Patched Research Session"})
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"
    assert r2.json().get("title") == "Patched Research Session"
    print("✓ PATCH /api/chat/sessions/{id}/rename passed")

def test_empty_drawer_blackhole_fixed():
    # Sending active_docs: [] should search across workspace without crashing or invalid enums
    resp = client.post("/api/chat", json={
        "message": "Hello, provide an overview of research findings",
        "active_docs": [],
        "stream": False,
        "session_id": "test_drawer_sess",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    decision = data.get("quality_gate_decision")
    assert decision in ("accept", "retry", "unable_to_verify", "empty_workspace"), f"Invalid decision: {decision}"
    print(f"✓ Empty drawer contract fix passed (decision={decision})")

if __name__ == "__main__":
    test_health()
    test_dev_checkup()
    test_chat_history_post_and_get()
    test_graph_search_query_param()
    test_feedback_optional_session_id()
    test_query_intake_softened()
    test_validation_error_envelope()
    test_chat_stream_sse_events()
    test_system_modular_endpoints()
    test_handshake_endpoints()
    test_session_rename()
    test_empty_drawer_blackhole_fixed()
    print("\nALL 12 VERIFICATION SUITES PASSED SUCCESSFULLY!")


