"""
Unit tests for vLLM routing integrity, pinned primary preservation,
and zero-secret-hijack failover policies.
"""

from unittest.mock import MagicMock, patch
import pytest
from src.infrastructure.providers.router import ProviderRouter, InferenceTask, ExecutionMode
from src.features.system.schemas import SystemConfigRequest
from src.features.system.config_service import save_configuration
from src.retrieval.hyde import HyDEGenerator


def test_pinned_primary_provider_preservation():
    """Verify that pinning vLLM as primary prevents generic refreshes from shifting it down."""
    router = ProviderRouter()
    # Mock vllm as available
    if "vllm" in router.providers:
        router.providers["vllm"].is_available = MagicMock(return_value=True)

    # Pin vllm as primary
    res = router.set_routing(
        fallback_order=["vllm", "gemini", "groq", "ollama", "local"],
        primary_provider="vllm",
    )
    assert res["primary_provider"] == "vllm"
    assert router.pinned_primary_provider == "vllm"
    assert router.fallback_chain[0] == "vllm"

    # Now simulate a generic background refresh passing primary_cloud="groq"
    router._refresh_fallback_chain(primary_cloud="groq")

    # Pinned primary must remain locked as #1
    assert router.fallback_chain[0] == "vllm"
    assert router.pinned_primary_provider == "vllm"


def test_config_service_preserves_pinned_primary():
    """Verify that saving unrelated configuration (e.g. neural models) does not reset LLM backend to groq."""
    router = ProviderRouter()
    if "vllm" in router.providers:
        router.providers["vllm"].is_available = MagicMock(return_value=True)

    router.set_routing(
        fallback_order=["vllm", "gemini", "groq"],
        primary_provider="vllm",
    )

    with patch("src.infrastructure.providers.router.get_provider_router", return_value=router):
        # Save only an embedding model (no llm_backend provided)
        save_configuration(SystemConfigRequest(
            embedding_model="google/embeddinggemma-2",
        ))

        # The router fallback chain must still have vllm as primary
        assert router.fallback_chain[0] == "vllm"


def test_hyde_uses_router_complete():
    """Verify that HyDE query expansion calls router.complete with InferenceTask.QUERY_REWRITE instead of hardcoding Gemini."""
    generator = HyDEGenerator()
    mock_router = MagicMock()
    mock_router.complete.return_value = "Hypothetical expansion about scientific institutions"
    mock_router.fallback_chain = ["vllm", "groq", "gemini"]

    with patch.object(generator, "_get_router", return_value=mock_router):
        expanded = generator.generate_hypothetical_document("What is the primary mission of NIPGR?")

        assert mock_router.complete.called
        call_kwargs = mock_router.complete.call_args[1]
        assert call_kwargs["task"] == InferenceTask.QUERY_REWRITE
        assert expanded == "Hypothetical expansion about scientific institutions"


def test_vllm_error_propagates_without_gemini_hijack():
    """Verify that LocalVLLMProvider complete() raises cleanly rather than secretly calling GeminiProvider."""
    from src.infrastructure.providers.llm import LocalVLLMProvider

    vllm_prov = LocalVLLMProvider(base_url="http://127.0.0.1:8002/v1")

    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("Connection refused: 10061")):
        with pytest.raises(RuntimeError) as exc_info:
            vllm_prov.complete(prompt="Test prompt")

        assert "Local vLLM inference failed" in str(exc_info.value)
