"""
Tests for Patch 13: Provider Router Resilience & Fallback under 403/AUTH_FAILED.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.infrastructure.providers.router import ProviderRouter, InferenceTask, ProviderExhaustedError
from src.infrastructure.providers.base import LLMProvider


class DummyMockProvider(LLMProvider):
    def __init__(self, name: str, fails_with: Exception = None, returns: str = "ok"):
        self.name = name
        self.fails_with = fails_with
        self.returns = returns
        self.model_name = "dummy-model"

    def complete(self, prompt: str, **kwargs) -> str:
        if self.fails_with:
            raise self.fails_with
        return self.returns

    async def complete_stream(self, prompt: str, **kwargs):
        yield self.complete(prompt, **kwargs)

    def is_available(self) -> bool:
        return self.fails_with is None


def test_router_disables_403_and_fails_over():
    router = ProviderRouter()
    p1 = DummyMockProvider("dummy_cloud", fails_with=RuntimeError("HTTP 403 (AUTH_FAILED)"))
    p2 = DummyMockProvider("dummy_fallback", returns="Fallback success response")

    router.providers = {
        "dummy_cloud": p1,
        "dummy_fallback": p2,
    }
    router.fallback_chain = ["dummy_cloud", "dummy_fallback"]
    router.disabled_providers = set()
    router.task_policy = {InferenceTask.RAG_GENERATION: "dummy_cloud"}

    with patch("src.infrastructure.providers.router.get_credential_manager") as mock_cm_fn:
        mock_cm = MagicMock()
        mock_cm.get_credential_status.return_value = "configured"
        mock_cm_fn.return_value = mock_cm

        res = router.complete("Test query", task=InferenceTask.RAG_GENERATION)

    assert res == "Fallback success response"
    assert "dummy_cloud" in router.disabled_providers


def test_router_raises_no_llm_available_when_exhausted():
    router = ProviderRouter()
    p1 = DummyMockProvider("dummy_cloud", fails_with=RuntimeError("HTTP 403 (AUTH_FAILED)"))

    router.providers = {
        "dummy_cloud": p1,
    }
    router.fallback_chain = ["dummy_cloud"]
    router.disabled_providers = set()
    router.task_policy = {InferenceTask.RAG_GENERATION: "dummy_cloud"}
    router.local_allowed = False

    with patch("src.infrastructure.providers.router.get_credential_manager") as mock_cm_fn:
        mock_cm = MagicMock()
        mock_cm.get_credential_status.return_value = "configured"
        mock_cm_fn.return_value = mock_cm

        with pytest.raises(ProviderExhaustedError) as exc_info:
            router.complete("Test query", task=InferenceTask.RAG_GENERATION)

    assert "NO_LLM_AVAILABLE" in str(exc_info.value)
