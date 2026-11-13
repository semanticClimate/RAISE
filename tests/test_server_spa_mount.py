import pytest
from starlette.testclient import TestClient
from pathlib import Path


def test_spa_mount_and_endpoints():
    import server

    client = TestClient(server.app)

    # 1. Test /api/info
    res_info = client.get("/api/info")
    assert res_info.status_code == 200
    data = res_info.json()
    assert data["status"] == "operational"
    assert "RAISE" in data["name"]

    # 2. Test SPA index route
    frontend_dist_candidates = [
        Path(__file__).resolve().parent.parent / "frontend" / "dist",
        Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
    ]
    frontend_dist = next((p for p in frontend_dist_candidates if (p / "index.html").is_file()), frontend_dist_candidates[0])
    if (frontend_dist / "index.html").is_file():
        res_root = client.get("/")
        assert res_root.status_code == 200
        assert "html" in res_root.headers.get("content-type", "").lower()
        assert "<!doctype html" in res_root.text.lower() or "<html" in res_root.text.lower()

        # Test client-side route fallback to index.html
        res_spa = client.get("/chat-session/test-123")
        assert res_spa.status_code == 200
        assert "<!doctype html" in res_spa.text.lower() or "<html" in res_spa.text.lower()

        # Test non-existent API route does NOT return HTML, returns 404 JSON
        res_api_404 = client.get("/api/nonexistent_test_route_123")
        assert res_api_404.status_code == 404
        assert res_api_404.headers.get("content-type", "").startswith("application/json")

        # Test missing /assets/* file returns 404 JSON (prevents SyntaxError: Unexpected token '<')
        res_asset_404 = client.get("/assets/index-OLD_NONEXISTENT_HASH.js")
        assert res_asset_404.status_code == 404
        assert res_asset_404.headers.get("content-type", "").startswith("application/json")
