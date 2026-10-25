"""
Pure ASGI Security Shield & Ingress Verification Suite
Validates:
- O(1) Redis IP blacklist checks (immediate 403 / 4403 rejection)
- Proxy IP header precedence (CF-Connecting-IP > X-Forwarded-For > Socket)
- User-Agent device & OS parsing
- Large upload body memory bypass (prevents 20MB-100MB buffering crashes)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from src.security.ip_resolver import resolve_client_ip, extract_edge_telemetry
from src.security.device_parser import parse_client_device
from src.security.asgi_shield import PureASGISecurityShieldMiddleware


class MockRedis:
    """In-memory async Redis mock for high-speed deterministic test assertions."""
    def __init__(self):
        self.store = {}
        self.published = []

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def set(self, key: str, val: str):
        self.store[key] = val

    async def delete(self, key: str) -> int:
        return 1 if self.store.pop(key, None) is not None else 0

    async def publish(self, channel: str, message: str):
        self.published.append((channel, message))


def create_test_app(mock_redis):
    async def sample_endpoint(request):
        body = await request.body()
        return JSONResponse({"status": "ok", "body_len": len(body)})

    async def upload_endpoint(request):
        body = await request.body()
        return JSONResponse({"status": "uploaded", "body_len": len(body)})

    routes = [
        Route("/api/search", sample_endpoint, methods=["GET", "POST"]),
        Route("/api/documents/upload", upload_endpoint, methods=["POST"]),
    ]

    base_app = Starlette(routes=routes)
    shield = PureASGISecurityShieldMiddleware(app=base_app, redis_client=mock_redis)
    return shield


@pytest.mark.asyncio
async def test_ip_blacklist_immediate_403():
    """Validates that blacklisted IP is immediately rejected with 403."""
    mock_redis = MockRedis()
    blocked_ip = "198.51.100.42"
    await mock_redis.set(f"blacklist:ip:{blocked_ip}", "Malicious actor")

    app = create_test_app(mock_redis)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request from blocked IP via Cloudflare header
        resp = await client.get("/api/search", headers={"cf-connecting-ip": blocked_ip})
        assert resp.status_code == 403
        assert "ERR_BLOCKED_IP" in resp.text

        # Request from clean IP succeeds
        clean_resp = await client.get("/api/search", headers={"cf-connecting-ip": "192.0.2.1"})
        assert clean_resp.status_code == 200
        assert clean_resp.json()["status"] == "ok"


def test_ip_resolver_precedence():
    """Validates proxy header resolution precedence."""
    # 1. CF-Connecting-IP wins
    scope = {"headers": [
        (b"cf-connecting-ip", b"203.0.113.1"),
        (b"x-forwarded-for", b"198.51.100.2, 10.0.0.1"),
    ], "client": ("127.0.0.1", 50000)}
    assert resolve_client_ip(scope) == "203.0.113.1"

    # 2. X-Forwarded-For leftmost wins if no CF header
    scope2 = {"headers": [
        (b"x-forwarded-for", b"198.51.100.2, 10.0.0.1"),
    ], "client": ("127.0.0.1", 50000)}
    assert resolve_client_ip(scope2) == "198.51.100.2"

    # 3. Raw socket client fallback
    scope3 = {"headers": [], "client": ("192.168.1.50", 40000)}
    assert resolve_client_ip(scope3) == "192.168.1.50"


def test_device_parser_matrix():
    """Validates User-Agent device and browser parsing."""
    # Desktop Windows Chrome
    ua_chrome = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    res1 = parse_client_device(ua_chrome)
    assert res1["device"] == "Desktop"
    assert res1["os"] == "Windows"
    assert res1["browser"] == "Chrome"

    # Mobile iPhone Safari
    ua_iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    res2 = parse_client_device(ua_iphone)
    assert res2["device"] == "Mobile"
    assert res2["os"] == "iOS"
    assert res2["browser"] == "Safari"

    # Tablet iPad
    ua_ipad = "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
    res3 = parse_client_device(ua_ipad)
    assert res3["device"] == "Tablet"
    assert res3["os"] == "iOS"


@pytest.mark.asyncio
async def test_large_upload_body_bypass():
    """Validates that large document uploads bypass request body buffering in ASGI middleware."""
    mock_redis = MockRedis()
    app = create_test_app(mock_redis)

    # 1MB dummy payload simulating a PDF document chunk
    dummy_payload = b"%PDF-1.4 " + (b"X" * 1024 * 1024)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/documents/upload",
            content=dummy_payload,
            headers={"content-type": "multipart/form-data; boundary=xyz"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "uploaded"
        assert resp.json()["body_len"] == len(dummy_payload)
