"""
Unit Tests for Multi-Backend Providers & ProviderRouter
Verifies error classification, task routing, bounded fallback, and diagnostic reporting.
All tests run 100% offline using deterministic mocks (zero cloud calls).
"""

import pytest
from unittest.mock import MagicMock, patch

from src.infrastructure.providers.base import ProviderHealth, LLMProvider
from src.infrastructure.providers.http_client import (
    classify_http_status,
    ProviderHTTPError,
    safe_http_request,
)
from src.infrastructure.providers.llm import LocalVLLMProvider, get_llm_provider
from src.infrastructure.providers.gemini import GeminiProvider
from src.infrastructure.providers.groq import GroqProvider
from src.infrastructure.providers.deepseek import DeepSeekProvider
from src.infrastructure.providers.nvidia import NvidiaNIMProvider
from src.infrastructure.providers.cohere import CohereProvider
from src.infrastructure.providers.router import (
    ProviderRouter,
    InferenceTask,
    ExecutionMode,
    FallbackEvent,
)
from src.infrastructure.providers.diagnostics import ProviderDiagnostics


def test_classify_http_status():
    """Verify standard HTTP code classification according to Section 8."""
    assert classify_http_status(401) == "AUTH_FAILED"
    assert classify_http_status(403) == "AUTH_FAILED"
    assert classify_http_status(404) == "MODEL_UNAVAILABLE"
    assert classify_http_status(429) == "RATE_LIMITED"
    assert classify_http_status(402) == "BILLING_RESTRICTED"
    assert classify_http_status(500) == "ENDPOINT_UNREACHABLE"
    assert classify_http_status(503) == "ENDPOINT_UNREACHABLE"


def test_provider_cost_modes():
    """Verify distinct labeling of local vs cloud cost modes according to Section 9."""
    vllm = LocalVLLMProvider()
    assert "LOCAL / NO EXTERNAL API BILLING" in vllm.cost_mode

    for prov in [GeminiProvider(), GroqProvider(), DeepSeekProvider(), NvidiaNIMProvider(), CohereProvider()]:
        assert "CLOUD / USER ACCOUNT" in prov.cost_mode
        # Ensure cloud is NEVER labeled as free
        assert "FREE" not in prov.cost_mode.upper()
        assert "ZERO-COST" not in prov.cost_mode.upper()


def test_unconfigured_provider_health():
    """Verify that unconfigured providers report NOT_CONFIGURED without errors."""
    prov = GroqProvider(api_key=None)
    with patch.object(prov, "_resolve_api_key", return_value=None):
        health = prov.health_check()
        assert health.status == "NOT_CONFIGURED"
        assert health.configured is False
        assert health.credential_valid is False
        assert health.functional_test is False


@patch("src.infrastructure.providers.groq.safe_http_request")
def test_groq_completion_mocked(mock_http):
    """Verify Groq provider completion formatting and response handling."""
    mock_http.return_value = (
        {"choices": [{"message": {"content": "Groq verified answer."}}]},
        45.2,
    )
    prov = GroqProvider(api_key="mock_test_groq_token")
    reply = prov.complete(prompt="Hello", system_prompt="Be concise")
    assert reply == "Groq verified answer."
    mock_http.assert_called_once()


@patch("src.infrastructure.providers.deepseek.safe_http_request")
def test_deepseek_reasoning_preservation(mock_http):
    """Verify DeepSeek reasoner token extraction when requested."""
    mock_http.return_value = (
        {"choices": [{"message": {
            "content": "Final deepseek answer",
            "reasoning_content": "Chain of thought steps here"
        }}]},
        120.5,
    )
    prov = DeepSeekProvider(api_key="mock_test_deepseek_token")

    
    # Without reasoning inclusion
    resp_standard = prov.complete(prompt="Math question")
    assert resp_standard == "Final deepseek answer"
    assert "<think>" not in resp_standard

    # With reasoning inclusion
    resp_with_reasoning = prov.complete(prompt="Math question", include_reasoning=True)
    assert "<think>" in resp_with_reasoning
    assert "Chain of thought steps here" in resp_with_reasoning
    assert "Final deepseek answer" in resp_with_reasoning


def test_router_local_first_default():
    """Verify router defaults to Local vLLM when mode is LOCAL."""
    router = ProviderRouter(mode=ExecutionMode.LOCAL)
    target = router.get_provider_for_task(InferenceTask.CHAT)
    assert target.name == "vllm"

    target_rag = router.get_provider_for_task(InferenceTask.RAG_GENERATION)
    assert target_rag.name == "vllm"


def test_router_task_policy_routing():
    """Verify router assigns tasks to configured providers in CLOUD mode."""
    router = ProviderRouter(mode=ExecutionMode.CLOUD, cloud_allowed=True)
    chat_prov = router.get_provider_for_task(InferenceTask.CHAT)
    assert chat_prov.name == "groq"

    reason_prov = router.get_provider_for_task(InferenceTask.REASONING)
    assert reason_prov.name in ("deepseek", "groq")


def test_router_automatic_fallback_logging():
    """Verify automated failover from failing cloud provider to local vLLM with non-secret logging."""
    router = ProviderRouter(mode=ExecutionMode.CLOUD, cloud_allowed=True)
    router.fallback_chain = ["groq", "vllm"]

    # Mock groq failure
    mock_failing_groq = MagicMock()
    mock_failing_groq.name = "groq"
    mock_failing_groq.complete.side_effect = ProviderHTTPError("HTTP 429 (RATE_LIMITED)", 429, "RATE_LIMITED")
    router.providers["groq"] = mock_failing_groq

    # Mock local vLLM success
    mock_vllm = MagicMock()
    mock_vllm.name = "vllm"
    mock_vllm.complete.return_value = "Recovered answer from local vLLM"
    router.providers["vllm"] = mock_vllm

    result = router.complete("What is the revenue?", task=InferenceTask.CHAT)
    assert result == "Recovered answer from local vLLM"

    # Verify non-secret fallback event was logged
    assert len(router.fallback_history) == 1
    event = router.fallback_history[0]
    assert event.from_provider == "groq"
    assert event.to_provider == "vllm"
    assert "429" in event.reason


def test_diagnostics_table_formatting():
    """Verify diagnostic table outputs clean format without raw keys."""
    diag = ProviderDiagnostics()
    fake_results = {
        "Local vLLM": ProviderHealth(
            provider="vllm",
            configured=True,
            credential_valid=True,
            endpoint_reachable=True,
            model_available=True,
            functional_test=True,
            status="READY",
            latency_ms=85.0,
            cost_mode="LOCAL / NO EXTERNAL API BILLING",
        ),
        "Groq": ProviderHealth(
            provider="groq",
            configured=False,
            credential_valid=False,
            endpoint_reachable=False,
            model_available=False,
            functional_test=False,
            status="NOT_CONFIGURED",
            cost_mode="CLOUD / USER ACCOUNT",
        ),
    }

    table = diag.format_table(fake_results)
    assert "Local vLLM" in table
    assert "Groq" in table
    assert "READY" in table
    assert "NOT_CONFIGURED" in table
    assert "LOCAL / NO EXTERNAL API BILLING" in table
    assert "CLOUD / USER ACCOUNT" in table


def test_openrouter_provider_mocked(monkeypatch):
    """Verify OpenRouter provider serialization and response parsing."""
    from src.infrastructure.providers.openrouter import OpenRouterProvider

    fake_response = {
        "choices": [{"message": {"content": "OpenRouter test answer"}}]
    }

    monkeypatch.setattr(
        "src.infrastructure.providers.openrouter.safe_http_request",
        lambda url, payload, headers, timeout, **kwargs: (fake_response, 45.0),
    )

    prov = OpenRouterProvider(api_key="sk-or-test-mock-key")
    ans = prov.complete("Hello world")
    assert ans == "OpenRouter test answer"
    assert prov.name == "openrouter"
    assert prov.cost_mode == "CLOUD / USER ACCOUNT"
