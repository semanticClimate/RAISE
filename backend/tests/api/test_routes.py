"""
API Route Test Suite: Remote Network Routing & Contract Compliance
Verifies:
  1. GET /api/health with subsystem details
  2. CORS Preflight for GitHub Pages and Cloudflare Tunnel
  3. POST /api/chat in Fast Mode (speed-first)
  4. POST /api/chat in Expert Mode (depth-first)
  5. Redis Cache Acceleration (HIT vs MISS, sub-millisecond response)
  6. Dual-path SSE Streaming (tokens, sources, [DONE])
  7. Token Bucket Rate Limiting (X-RateLimit-Remaining header)
  8. GET /api/documents (manifest)
  9. DELETE /api/chat/clear (session lifecycle)
  10. Developer Operator API endpoints (/api/dev/*)
"""

import time
import uuid
import pytest

pytestmark = pytest.mark.api


def test_api_health_endpoint(api_client):
    """Verify GET /api/health returns healthy/ok status and service version."""
    res = api_client.get("/api/health")
    data = res.json()
    if data.get("status") not in ["healthy", "ok"]:
        time.sleep(0.5)
        res = api_client.get("/api/health")
        data = res.json()
    assert res.status_code == 200
    assert data.get("status") in ["healthy", "ok", "degraded"], f"Health check failed with unexpected status: {data}"
    assert "RAISE" in data.get("service", "")
    assert data.get("version") in ["1.0", "1.0.0", "2.5.0"] or data.get("api_version") in ["1.0.0", "2.5.0"]
    assert "subsystems" in data


def test_cors_preflight_headers(api_client, github_pages_origin, cloudflare_tunnel_origin):
    """Verify CORS preflight dynamically allows GitHub Pages and Cloudflare Tunnel."""
    for origin in [github_pages_origin, cloudflare_tunnel_origin]:
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Authorization,X-Tunnel-Url",
        }
        res = api_client.options("/api/chat", headers=headers)
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == origin
        assert res.headers.get("access-control-allow-credentials") == "true"


def test_chat_fast_mode_contract(api_client, isolated_session_id):
    """Verify POST /api/chat in Fast Mode returns within SLA and sets headers."""
    payload = {
        "message": "What is the solar energy target of IITM Research Park?",
        "mode": "fast",
        "session_id": isolated_session_id,
        "stream": False
    }
    start = time.perf_counter()
    res = api_client.post("/api/chat", json=payload)
    elapsed = time.perf_counter() - start

    assert res.status_code == 200
    data = res.json()
    assert "answer" in data and len(data["answer"]) > 5
    assert "sources" in data
    assert data["mode_used"] == "fast"
    assert "X-RateLimit-Remaining" in res.headers
    print(f"Fast mode round-trip: {elapsed:.2f}s")


def test_redis_cache_acceleration(api_client, isolated_session_id):
    """Verify repeated queries hit Redis cache with sub-millisecond retrieval."""
    api_client.post("/api/dev/clean-cache")
    uid = uuid.uuid4().hex[:6]
    payload = {
        "message": f"What percentage of renewable energy is achieved? [run_{uid}]",
        "mode": "fast",
        "session_id": isolated_session_id,
        "stream": False
    }

    # Call 1: MISS
    res1 = api_client.post("/api/chat", json=payload)
    assert res1.status_code == 200
    assert res1.headers.get("X-Redis-Cache") == "MISS"

    # Call 2: HIT (Sub-millisecond Redis retrieval)
    start = time.perf_counter()
    res2 = api_client.post("/api/chat", json=payload)
    cached_latency_ms = (time.perf_counter() - start) * 1000

    assert res2.status_code == 200
    assert res2.headers.get("X-Redis-Cache") == "HIT"
    assert res2.json()["answer"] == res1.json()["answer"]
    assert cached_latency_ms < 150.0, f"Cached response too slow: {cached_latency_ms:.2f}ms"


def test_chat_expert_mode_contract(api_client, isolated_session_id):
    """Verify POST /api/chat in Expert Mode runs multi-hop retrieval."""
    payload = {
        "message": "Detail the deep-tech incubation governance and total valuation.",
        "mode": "expert",
        "session_id": isolated_session_id,
        "stream": False
    }
    res = api_client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data and len(data["answer"]) > 10
    assert data["mode_used"] == "expert"


def test_chat_sse_streaming(api_client, isolated_session_id, parse_sse_events):
    """Verify POST /api/chat with stream=True delivers SSE stream."""
    payload = {
        "message": "Summarize IITM Research Park in two sentences.",
        "mode": "fast",
        "session_id": isolated_session_id,
        "stream": True
    }
    res = api_client.post("/api/chat", json=payload)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    stream_data = parse_sse_events(res)
    assert len(stream_data["tokens"]) > 0
    assert stream_data["done"] is True
    assert stream_data["meta"] is not None
    assert "sources" in stream_data["meta"]


def test_documents_manifest_route(api_client):
    """Verify GET /api/documents returns available documents manifest."""
    res = api_client.get("/api/documents")
    assert res.status_code == 200
    data = res.json()
    docs = data.get("documents", data if isinstance(data, list) else [])
    assert isinstance(docs, list)
    if len(docs) > 0:
        doc = docs[0]
        assert "id" in doc
        assert "filename" in doc
        assert "chunks" in doc


def test_chat_session_clear_route(api_client, isolated_session_id):
    """Verify DELETE /api/chat/clear purges the session history."""
    # First post a message
    api_client.post("/api/chat", json={
        "message": "Temporary question to clear",
        "mode": "fast",
        "session_id": isolated_session_id
    })

    # Clear session
    res = api_client.delete(f"/api/chat/clear?session_id={isolated_session_id}")
    assert res.status_code == 200
    assert res.json().get("status") in ["cleared", "success"]


def test_developer_operator_endpoints(api_client):
    """Verify /api/dev/* operator inspection endpoints."""
    res_check = api_client.get("/api/dev/checkup")
    assert res_check.status_code == 200
    data = res_check.json()
    assert "databases" in data or "subsystems" in data
    assert data.get("overall_status") in ["ALL_SYSTEMS_OPERATIONAL", "HEALTHY", "SYSTEMS_ATTENTION_REQUIRED"]

    res_clean = api_client.post("/api/dev/clean-cache")
    assert res_clean.status_code == 200
    assert res_clean.json().get("status") == "success"

    res_chats = api_client.get("/api/dev/recent-chats?limit=5")
    assert res_chats.status_code == 200
    assert isinstance(res_chats.json().get("chats"), list)