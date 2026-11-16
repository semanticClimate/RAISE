"""
Unit and Integration Tests for FailoverLLMProvider and Local Discovery
=======================================================================
Tests:
1. test_failover_llm_provider_switches_on_429
2. test_failover_llm_provider_skips_cooling_provider
3. test_failover_llm_provider_all_exhausted_raises_error
4. test_vllm_is_available_probes_candidate_urls
5. test_ollama_is_available_probes_tags_and_v1
6. test_dynamic_fallback_order_routing_modes
7. test_get_llm_provider_wraps_in_failover_chain
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from src.core.config import settings, models
from src.infrastructure.providers.llm import (
    FailoverLLMProvider,
    LocalVLLMProvider,
    LocalOllamaProvider,
    get_llm_provider,
)
from src.infrastructure.llm.model_discovery import ModelDiscoveryEngine


def test_failover_llm_provider_switches_on_429():
    """Verify that FailoverLLMProvider immediately cascades to fallback when primary hits 429."""
    primary = MagicMock()
    primary.name = "primary_cloud"
    primary.cost_mode = "CLOUD"
    primary.complete.side_effect = RuntimeError("429 Too Many Requests: Rate limit exceeded")

    fallback = MagicMock()
    fallback.name = "vllm"
    fallback.cost_mode = "LOCAL"
    fallback.complete.return_value = "Synthesis from local vLLM"

    provider = FailoverLLMProvider(
        primary=primary,
        fallbacks=[fallback],
        cooldown_seconds=30.0,
    )

    res = provider.complete("Summarize research findings")
    assert res == "Synthesis from local vLLM"
    assert primary.complete.call_count == 1
    assert fallback.complete.call_count == 1
    assert provider._is_cooling_down("primary_cloud") is True


def test_failover_llm_provider_skips_cooling_provider():
    """Verify that a cooling provider is skipped immediately without attempting complete()."""
    primary = MagicMock()
    primary.name = "rate_limited_provider"
    primary.complete.side_effect = RuntimeError("ResourceExhausted: 429 Quota Exceeded")

    fallback = MagicMock()
    fallback.name = "local_vllm"
    fallback.complete.return_value = "Fast local answer"

    provider = FailoverLLMProvider(
        primary=primary,
        fallbacks=[fallback],
        cooldown_seconds=60.0,
    )

    # First call trips the circuit breaker
    res1 = provider.complete("First prompt")
    assert res1 == "Fast local answer"
    assert primary.complete.call_count == 1
    assert fallback.complete.call_count == 1

    # Second call must skip primary completely
    res2 = provider.complete("Second prompt")
    assert res2 == "Fast local answer"
    assert primary.complete.call_count == 1  # Not called again
    assert fallback.complete.call_count == 2


def test_failover_llm_provider_all_exhausted_raises_error():
    """Verify that when all providers fail, a clear RuntimeError is raised."""
    primary = MagicMock()
    primary.name = "failing_primary"
    primary.complete.side_effect = RuntimeError("Connection timed out")

    fallback = MagicMock()
    fallback.name = "failing_fallback"
    fallback.complete.side_effect = RuntimeError("10061 Connection Refused")

    provider = FailoverLLMProvider(
        primary=primary,
        fallbacks=[fallback],
        cooldown_seconds=10.0,
    )

    with pytest.raises(RuntimeError) as exc_info:
        provider.complete("Should fail")
    assert "All LLM providers in failover chain exhausted" in str(exc_info.value)


def test_vllm_is_available_probes_candidate_urls():
    """Verify that LocalVLLMProvider probes candidate URLs and captures responsive endpoint."""
    prov = LocalVLLMProvider(base_url="http://localhost:8002/v1")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"data": [{"id": "mock_vllm_model"}]}'
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("socket.create_connection"), patch("urllib.request.urlopen", return_value=mock_resp):
        is_alive = prov.is_available()
        assert is_alive is True
        assert prov.model_name == "mock_vllm_model"


def test_ollama_is_available_probes_tags_and_v1():
    """Verify that LocalOllamaProvider probes tags and assigns active model."""
    prov = LocalOllamaProvider(base_url="http://localhost:11434")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"models": [{"name": "mock_ollama_model"}]}'
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("socket.create_connection"), patch("urllib.request.urlopen", return_value=mock_resp):
        is_alive = prov.is_available()
        assert is_alive is True
        assert prov.model_name == "mock_ollama_model"


def test_dynamic_fallback_order_routing_modes():
    """Verify that build_dynamic_fallback_order orders local first when LOCAL_FIRST is set."""
    engine = ModelDiscoveryEngine()

    with patch.object(engine, "_discover_vllm", return_value=["local_vllm_id"]), \
         patch.object(engine, "_discover_ollama", return_value=[]), \
         patch.object(engine._cm, "get_credential_status", return_value="configured"):

        with patch.dict("os.environ", {"LLM_ROUTING_MODE": "LOCAL_FIRST"}):
            order_local_first = engine.build_dynamic_fallback_order()
            assert len(order_local_first) > 0
            assert order_local_first[0]["model"].endswith("local_vllm_id")
            assert "api_base" in order_local_first[0]

        with patch.dict("os.environ", {"LLM_ROUTING_MODE": "CLOUD_FIRST"}):
            order_cloud_first = engine.build_dynamic_fallback_order()
            assert len(order_cloud_first) > 0
            # Cloud providers come first in CLOUD_FIRST
            assert order_cloud_first[-1]["model"].endswith("local_vllm_id")


def test_get_llm_provider_wraps_in_failover_chain():
    """Verify factory wraps provider in FailoverLLMProvider with local and cloud fallbacks."""
    with patch.dict("os.environ", {"LLM_BACKEND": "gemini", "GROQ_API_KEY": "gsk_test"}):
        provider = get_llm_provider()
        assert isinstance(provider, FailoverLLMProvider)
        assert len(provider.fallbacks) >= 2


def test_router_cascades_cloud_failure_to_local_vllm():
    """Verify ProviderRouter cascades to local vLLM when all cloud providers fail with 404/429/401."""
    from src.infrastructure.providers.router import ProviderRouter, InferenceTask, ExecutionMode

    router = ProviderRouter(mode=ExecutionMode.AUTOMATIC)
    router.fallback_chain = ["gemini", "groq", "vllm"]

    mock_gemini = MagicMock()
    mock_gemini.name = "gemini"
    mock_gemini.complete.side_effect = RuntimeError("HTTP 404 (MODEL_UNAVAILABLE)")

    mock_groq = MagicMock()
    mock_groq.name = "groq"
    mock_groq.complete.side_effect = RuntimeError("HTTP 401 (AUTH_FAILED)")

    mock_vllm = MagicMock()
    mock_vllm.name = "vllm"
    mock_vllm.is_available.return_value = True
    mock_vllm.complete.return_value = "Verified local GPU synthesis from Qwen 2.5 14B."

    router.providers["gemini"] = mock_gemini
    router.providers["groq"] = mock_groq
    router.providers["vllm"] = mock_vllm

    result = router.complete("Query test", task=InferenceTask.RAG_GENERATION)
    assert result == "Verified local GPU synthesis from Qwen 2.5 14B."
    assert router.last_used_provider == "vllm"
