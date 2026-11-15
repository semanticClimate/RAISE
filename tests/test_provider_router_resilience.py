"""
Unit and Integration Tests for ProviderRouter Resilience & Fault-Tolerance
==========================================================================
Tests:
1. test_router_no_hardcoded_blacklists_on_init
2. test_rate_limit_429_triggers_cooldown_and_fallback
3. test_billing_or_auth_error_permanently_disables_provider
4. test_local_execution_mode_never_routes_to_cloud
5. test_router_all_providers_exhausted_raises_exception
6. test_round_robin_thread_safety
7. test_async_stream_fallback_non_blocking
"""

import asyncio
import concurrent.futures
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.core.config import models
from src.infrastructure.providers.router import (
    ProviderRouter,
    ProviderExhaustedError,
    InferenceTask,
    ExecutionMode,
)
from src.infrastructure.providers.llm import LocalOllamaProvider


def test_router_no_hardcoded_blacklists_on_init():
    """
    Requirement 1: Verify that router initializes with an empty disabled_providers set,
    has no hardcoded blacklists for deepseek/openrouter, and registers LocalOllamaProvider.
    """
    router = ProviderRouter()

    # Initial disabled set must be clean
    assert isinstance(router.disabled_providers, set)
    assert len(router.disabled_providers) == 0
    assert "deepseek" not in router.disabled_providers
    assert "openrouter" not in router.disabled_providers

    # All supported cloud and local providers must be registered
    expected_providers = ["vllm", "local", "ollama", "gemini", "groq", "mistral", "nvidia", "cohere", "deepseek", "openrouter", "universal"]
    for p in expected_providers:
        assert p in router.providers, f"Provider '{p}' missing from router.providers"

    # Ollama provider must be instance of LocalOllamaProvider
    assert isinstance(router.providers["ollama"], LocalOllamaProvider)

    # Groq default model matches config
    cloud_meta = router._get_cloud_meta()
    assert cloud_meta["groq"]["default_model"] == models.GROQ_MODEL_NAME


def test_rate_limit_429_triggers_cooldown_and_fallback():
    """
    Requirement 2: Verify that HTTP 429 triggers temporary cooldown without permanently
    disabling the provider, and automatically cascades to the next healthy fallback.
    """
    with patch("src.infrastructure.credentials.manager.CredentialManager.get_credential_status") as mock_cred:
        mock_cred.side_effect = lambda prov: "configured" if prov in ("groq", "gemini") else "missing"

        router = ProviderRouter(mode=ExecutionMode.CLOUD)
        router.set_task_provider(InferenceTask.RAG_GENERATION, "groq")

        # Primary groq raises 429
        mock_groq = MagicMock()
        mock_groq.name = "groq"
        mock_groq.complete.side_effect = RuntimeError("429 Too Many Requests: Rate limit exceeded. Try again in 10s.")
        router.providers["groq"] = mock_groq

        # Fallback gemini succeeds
        mock_gemini = MagicMock()
        mock_gemini.name = "gemini"
        mock_gemini.model_name = models.GEMINI_MODEL_NAME
        mock_gemini.complete.return_value = "Grounded scientific answer from Gemini."
        router.providers["gemini"] = mock_gemini

        result = router.complete("Explain telomerase activation", task=InferenceTask.RAG_GENERATION)

        assert result == "Grounded scientific answer from Gemini."
        assert router.last_used_provider == "gemini"

        # Groq must be in cooldown but NOT permanently disabled
        assert "groq" in router.provider_cooldowns
        assert router.provider_cooldowns["groq"] > time.time()
        assert "groq" not in router.disabled_providers

        # Fallback event recorded in history
        assert len(router.fallback_history) >= 1
        assert router.fallback_history[-1].from_provider == "groq"
        assert router.fallback_history[-1].to_provider == "gemini"


def test_billing_or_auth_error_permanently_disables_provider():
    """
    Requirement 3: Verify that HTTP 401/402/403 or BILLING_RESTRICTED dynamically
    and permanently disables the provider from future inference selections.
    """
    with patch("src.infrastructure.credentials.manager.CredentialManager.get_credential_status") as mock_cred:
        mock_cred.side_effect = lambda prov: "configured" if prov in ("groq", "gemini") else "missing"

        router = ProviderRouter(mode=ExecutionMode.CLOUD)
        router.set_task_provider(InferenceTask.RAG_GENERATION, "groq")

        # Groq raises 402 Payment Required
        mock_groq = MagicMock()
        mock_groq.name = "groq"
        mock_groq.complete.side_effect = RuntimeError("402 Payment Required: BILLING_RESTRICTED - Account credits exhausted.")
        router.providers["groq"] = mock_groq

        mock_gemini = MagicMock()
        mock_gemini.name = "gemini"
        mock_gemini.model_name = models.GEMINI_MODEL_NAME
        mock_gemini.complete.return_value = "Gemini fallback result."
        router.providers["gemini"] = mock_gemini

        res = router.complete("Explain CRISPR Cas9", task=InferenceTask.RAG_GENERATION)
        assert res == "Gemini fallback result."

        # Groq is permanently disabled
        assert "groq" in router.disabled_providers

        # Subsequent routing must bypass groq immediately without trying it
        next_provider = router.get_provider_for_task(InferenceTask.RAG_GENERATION)
        assert next_provider.name != "groq"
        assert next_provider.name == "gemini"


def test_local_execution_mode_never_routes_to_cloud():
    """
    Requirement 4: Verify that ExecutionMode.LOCAL strictly air-gaps inference from
    external cloud APIs, routing extraction, reranking, and generation strictly to local/vLLM.
    """
    with patch("src.infrastructure.credentials.manager.CredentialManager.get_credential_status") as mock_cred:
        # Even if cloud keys exist in environment
        mock_cred.return_value = "configured"

        router = ProviderRouter(mode=ExecutionMode.LOCAL)
        assert router.mode == ExecutionMode.LOCAL
        assert router.cloud_allowed is False

        # Task policies must target local substrates
        assert router.task_policy[InferenceTask.DOCUMENT_EXTRACTION] in ("vllm", "local")
        assert router.task_policy[InferenceTask.RERANKING] in ("vllm", "local")

        # Mock local vLLM provider
        mock_vllm = MagicMock()
        mock_vllm.name = "vllm"
        mock_vllm.is_available.return_value = True
        mock_vllm.complete.return_value = "Strictly local offline synthesis."
        router.providers["vllm"] = mock_vllm

        # Cloud provider must never be called
        mock_gemini = MagicMock()
        mock_gemini.complete.side_effect = AssertionError("Cloud API invoked under LOCAL execution mode!")
        router.providers["gemini"] = mock_gemini

        ans = router.complete("Extract biomedical tables", task=InferenceTask.DOCUMENT_EXTRACTION)
        assert ans == "Strictly local offline synthesis."
        assert router.last_used_provider == "vllm"
        mock_gemini.complete.assert_not_called()


def test_router_all_providers_exhausted_raises_exception():
    """
    Requirement 5: Verify that complete() raises ProviderExhaustedError instead of
    returning error strings when all fallback candidates fail.
    """
    with patch("src.infrastructure.credentials.manager.CredentialManager.get_credential_status") as mock_cred:
        mock_cred.return_value = "configured"

        router = ProviderRouter(mode=ExecutionMode.CLOUD)

        # Mock all candidates in fallback chain to raise exceptions
        for name, prov in router.providers.items():
            mock_p = MagicMock()
            mock_p.name = name
            mock_p.complete.side_effect = RuntimeError(f"Connection refused on {name}")
            mock_p.is_available.return_value = False
            router.providers[name] = mock_p

        with pytest.raises(ProviderExhaustedError) as exc_info:
            router.complete("Failing query", task=InferenceTask.RAG_GENERATION)

        err = exc_info.value
        assert isinstance(err, ProviderExhaustedError)
        assert hasattr(err, "errors")
        assert len(err.errors) > 0
        assert "All inference providers in fallback chain failed" in str(err)


def test_round_robin_thread_safety():
    """
    Requirement 6: Verify that round-robin load distribution is thread-safe across
    concurrent multi-threaded requests and evenly rotates across available models.
    """
    with patch("src.infrastructure.credentials.manager.CredentialManager.get_credential_status") as mock_cred:
        mock_cred.side_effect = lambda prov: "configured" if prov in ("groq", "gemini") else "missing"

        router = ProviderRouter(mode=ExecutionMode.CLOUD)
        router.round_robin_enabled = True
        router.fallback_chain = ["groq", "gemini"]

        mock_groq = MagicMock()
        mock_groq.name = "groq"
        mock_gemini = MagicMock()
        mock_gemini.name = "gemini"
        router.providers["groq"] = mock_groq
        router.providers["gemini"] = mock_gemini

        num_calls = 40
        selected = []

        def worker():
            prov = router.get_provider_for_task(InferenceTask.CHAT)
            return prov.name

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker) for _ in range(num_calls)]
            for f in concurrent.futures.as_completed(futures):
                selected.append(f.result())

        # Assert no exceptions and equal distribution
        assert len(selected) == num_calls
        groq_count = selected.count("groq")
        gemini_count = selected.count("gemini")
        assert groq_count == 20
        assert gemini_count == 20


@pytest.mark.asyncio
async def test_async_stream_fallback_non_blocking():
    """
    Requirement 7: Verify that complete_stream() catches streaming failures and
    falls back cleanly to synchronous completion via asyncio.to_thread without blocking.
    """
    router = ProviderRouter()

    # Primary provider streaming generator fails mid-stream
    async def failing_stream(*args, **kwargs):
        yield "Initial broken token"
        raise RuntimeError("Streaming connection terminated by remote server")

    mock_primary = MagicMock()
    mock_primary.name = "groq"
    mock_primary.complete_stream = MagicMock(side_effect=failing_stream)
    router.providers["groq"] = mock_primary

    # Router's complete() fallback returns recovered full text
    with patch.object(router, "complete", return_value="Full recovered response via sync fallback"):
        with patch.object(router, "get_provider_for_task", return_value=mock_primary):
            tokens = []
            async for chunk in router.complete_stream("Stream this text"):
                tokens.append(chunk)

            assert "Full recovered response via sync fallback" in tokens
