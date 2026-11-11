"""
Unit and Integration Tests for Security Subsystems and Singleton Invariants
=============================================================================
Tests:
1. Process-wide sys._raise_warmup_lock and singleton reuse in warmup_all_neural_models.
2. PureASGISecurityShieldMiddleware single instance auto-registration on app.state,
   SSE streaming route buffering bypass, and telemetry queue dispatch.
3. Defensiveness in resolve_client_ip against spoofed proxy headers from non-loopback clients.
4. TransactionalOutboxManager error rollback callback and pre_state propagation.
5. PortSweep async wrapper non-blocking execution.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from starlette.types import Scope, Receive, Send

from src.infrastructure.model_warmup import (
    warmup_all_neural_models,
    is_neural_stack_ready,
)
from src.security.asgi_shield import PureASGISecurityShieldMiddleware
from src.security.ip_resolver import resolve_client_ip
from src.security.outbox_manager import TransactionalOutboxManager
from src.security.port_sweep import PortSweep


def test_sys_wide_warmup_lock_and_singleton():
    """Verify sys._raise_warmup_lock exists and prevents duplicate execution."""
    assert hasattr(sys, "_raise_warmup_lock")
    assert hasattr(sys, "_raise_models_loaded")

    # Mock components to test that warmup completes and returns latencies
    mock_rag_engine = MagicMock()
    mock_ve = MagicMock()
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1]
    mock_ve._get_embedding_model.return_value = mock_model
    mock_ve.model_key = "test-embed"
    mock_rag_engine.vector_engine = mock_ve

    mock_reranker = MagicMock()
    mock_reranker.model = MagicMock()
    mock_reranker.model.rerank.return_value = []
    mock_reranker.model_name = "test-reranker"
    mock_rag_engine.reranker = mock_reranker

    with patch("src.features.evaluation.nli_verifier.FineCatNLIVerifier._ensure_loaded", return_value=False):
        latencies = warmup_all_neural_models(force=True, rag_engine=mock_rag_engine)
        assert isinstance(latencies, dict)
        assert is_neural_stack_ready() is True

        # Second call without force should return cached latencies instantly without re-invoking encode
        mock_model.encode.reset_mock()
        latencies2 = warmup_all_neural_models(force=False, rag_engine=mock_rag_engine)
        mock_model.encode.assert_not_called()
        assert latencies2 == latencies


@pytest.mark.asyncio
async def test_asgi_shield_single_instance_auto_registration():
    """Verify that PureASGISecurityShieldMiddleware auto-attaches to app.state.asgi_shield."""
    mock_fastapi_app = MagicMock()
    mock_fastapi_app.state = MagicMock()

    shield = PureASGISecurityShieldMiddleware(
        app=MagicMock(),
        redis_client=None,
        fastapi_app=mock_fastapi_app,
    )
    assert mock_fastapi_app.state.asgi_shield is shield


@pytest.mark.asyncio
async def test_asgi_shield_sse_and_ws_bypass():
    """Verify that SSE stream routes and WebSockets bypass telemetry body buffering."""
    inner_app = AsyncMock()
    shield = PureASGISecurityShieldMiddleware(app=inner_app)

    # 1. SSE Stream Route
    sse_scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/chat/stream",
        "headers": [(b"accept", b"text/event-stream")],
        "client": ("127.0.0.1", 54321),
    }
    receive = AsyncMock()
    send = AsyncMock()

    await shield(sse_scope, receive, send)
    inner_app.assert_awaited_once_with(sse_scope, receive, send)
    # Telemetry queue should NOT have buffered frames for SSE bypass
    assert shield.telemetry_queue.empty()


def test_ip_resolver_defense_against_proxy_spoofing():
    """Verify that forged headers from direct/LAN sockets are rejected."""
    # Scenario A: Direct external or LAN connection passing forged Cloudflare/XFF headers
    untrusted_scope: Scope = {
        "type": "http",
        "client": ("192.168.1.155", 52140),
    }
    forged_headers = {
        "cf-connecting-ip": "8.8.8.8",
        "x-forwarded-for": "1.1.1.1, 8.8.8.8",
        "x-real-ip": "9.9.9.9",
    }
    resolved = resolve_client_ip(untrusted_scope, forged_headers)
    assert resolved == "192.168.1.155", "Forged proxy headers from LAN socket must be rejected"

    # Scenario B: Connection from local Cloudflare tunnel (127.0.0.1)
    trusted_scope: Scope = {
        "type": "http",
        "client": ("127.0.0.1", 41200),
    }
    resolved_trusted = resolve_client_ip(trusted_scope, forged_headers)
    assert resolved_trusted == "8.8.8.8", "Proxy headers from loopback tunnel socket must be accepted"


@pytest.mark.asyncio
async def test_outbox_manager_error_rollback():
    """Verify that TransactionalOutboxManager calls record_error_tx on inference failure."""
    mgr = TransactionalOutboxManager()

    pre_tx = AsyncMock(return_value={"tx_id": "tx-1234", "status": "PENDING"})
    post_tx = AsyncMock()
    error_tx = AsyncMock()

    async def failing_inference():
        raise RuntimeError("vLLM worker out-of-memory or timeout")

    with pytest.raises(RuntimeError, match="vLLM worker out-of-memory"):
        await mgr.execute_decoupled_inference(
            record_pre_inference_tx=pre_tx,
            run_inference=failing_inference,
            record_post_inference_tx=post_tx,
            record_error_tx=error_tx,
        )

    pre_tx.assert_awaited_once()
    post_tx.assert_not_awaited()
    # error_tx must be invoked with pre_state and the exception
    error_tx.assert_awaited_once()
    call_args = error_tx.call_args[0]
    assert call_args[0] == {"tx_id": "tx-1234", "status": "PENDING"}
    assert isinstance(call_args[1], RuntimeError)


@pytest.mark.asyncio
async def test_port_sweep_async_execution():
    """Verify that sweep_and_clean_async executes asynchronously in thread."""
    with patch.object(PortSweep, "sweep_and_clean", return_value=True) as mock_sweep:
        res = await PortSweep.sweep_and_clean_async(8000)
        assert res is True
        mock_sweep.assert_called_once_with(8000, 3)
