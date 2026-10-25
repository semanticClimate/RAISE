"""
Authentication & Ephemeral Handshake Router
===========================================
Provides two-step security handshake endpoints for frontend clients.
"""

import logging
import secrets
from typing import Any, Dict
from fastapi import APIRouter, Request

logger = logging.getLogger("raise.api.routers.auth")

router = APIRouter(tags=["Authentication & Security Handshake"])


@router.post("/api/v1/auth/handshake", operation_id="auth_handshake_api_v1")
@router.post("/session/handshake", operation_id="auth_handshake_session")
async def create_auth_handshake(request: Request) -> Dict[str, Any]:
    """Establishes ephemeral security token for browser client workstation."""
    mgr = (
        getattr(request.app.state, "handshake_mgr", None)
        if hasattr(request, "app") and hasattr(request.app, "state")
        else None
    )
    client_ip = "127.0.0.1"
    try:
        from src.security import resolve_client_ip
        client_ip = resolve_client_ip(dict(request.scope))
    except Exception:
        pass

    if not mgr or not getattr(mgr, "redis", None):
        mock_token = f"standalone_{secrets.token_urlsafe(24)}"
        return {
            "token": mock_token,
            "expires_in": 300,
            "status": "active",
            "mode": "standalone",
            "client_ip": client_ip,
        }

    token = await mgr.create_handshake_token(metadata={"client_ip": client_ip})
    return {
        "token": token,
        "expires_in": 300,
        "status": "active",
        "client_ip": client_ip,
    }
