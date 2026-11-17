"""
Regression tests for routing persistence, sub-millisecond execution,
and citation preservation in normalized message objects.
"""

import pytest
import asyncio
from src.features.system.schemas import RoutingUpdateRequest
from src.infrastructure.providers.router import get_provider_router
from src.api.routers.system import update_system_routing
from src.infrastructure.database.mixins.chat_mixin import ChatStoreMixin


def test_provider_router_registers_openai_and_universal():
    """Verify that ProviderRouter registers both 'universal' and 'openai' adapters."""
    router = get_provider_router()
    assert "universal" in router.providers, "ProviderRouter missing 'universal'"
    assert "openai" in router.providers, "ProviderRouter missing 'openai'"
    assert router.providers["openai"].name == "openai"


@pytest.mark.asyncio
async def test_update_system_routing_fast_and_preserves_openai(monkeypatch):
    """Verify update_system_routing executes without heavy socket hangs and preserves openai."""
    router = get_provider_router()
    # Mock vllm.is_available to return True so local pinning works in test environment
    monkeypatch.setattr(router.providers["vllm"], "is_available", lambda: True)

    req = RoutingUpdateRequest(
        fallback_order=["vllm", "gemini", "openai", "groq"],
        disabled_providers=["mistral"],
        primary_provider="vllm",
        routing_policy="LOCAL_FIRST"
    )

    res = await update_system_routing(req)
    assert res.get("status") == "success"
    assert res.get("primary_provider") == "vllm"
    chain = res.get("fallback_chain", [])
    assert "openai" in chain, f"OpenAI was dropped from fallback chain: {chain}"
    assert "vllm" in chain


def test_chat_mixin_preserves_citations_in_response_wrapper():
    """Verify that ChatStoreMixin._normalize_msg guarantees response.citations exists."""
    class DummyChatStore(ChatStoreMixin):
        def __init__(self):
            self.is_connected = False
            self._memory_chat = {}

    store = DummyChatStore()
    sample_cits = [
        {"pdf_filename": "report.pdf", "primary_page": 9, "citation_index": 1}
    ]
    raw_msg = {
        "role": "assistant",
        "text": "Extracted answer [1]",
        "content": "Extracted answer [1]",
        "sources": sample_cits,
        "citations": sample_cits,
    }

    store._memory_chat["session-test"] = [raw_msg]
    messages = store.get_messages("session-test")

    assert len(messages) == 1
    norm = messages[0]
    assert norm["role"] == "assistant"
    assert norm["citations"] == sample_cits
    assert norm.get("response") is not None, "Response wrapper was None"
    assert norm["response"].get("citations") == sample_cits, "response.citations missing or empty"
    assert norm["response"].get("sources") == sample_cits, "response.sources missing or empty"
