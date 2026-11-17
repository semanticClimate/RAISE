"""
Unit Tests for RAISE Modular Dispatchers & Switch-Case Logic
============================================================
Tests:
1. RAGModeDispatcher (Fast vs. Expert vs. Conversational mode switch cases)
2. StreamFormatDispatcher (SSE vs. Raw vs. JSON format content negotiation)
3. InferenceExecutionDispatcher (Local vs. Cloud vs. Automatic routing)
4. SubstrateLifecycleDispatcher (Live database vs. In-memory fallback)
"""

import pytest
from src.core.dispatchers import (
    RAGMode,
    RAGModeConfig,
    RAGModeDispatcher,
    StreamFormat,
    StreamFormatDispatcher,
    InferenceMode,
    InferenceExecutionDispatcher,
    SubstrateMode,
    SubstrateLifecycleDispatcher,
)


def test_rag_mode_dispatcher_switch_cases():
    # 1. Fast Mode Switch Case
    cfg_fast = RAGModeDispatcher.dispatch("fast")
    assert cfg_fast.mode == RAGMode.FAST
    assert cfg_fast.hops == 1
    assert cfg_fast.top_k == 4
    assert not cfg_fast.enable_graph_traversal
    assert len(cfg_fast.pipeline_stages) == 4

    # 2. Expert Mode Switch Case
    cfg_expert = RAGModeDispatcher.dispatch("expert")
    assert cfg_expert.mode == RAGMode.EXPERT
    assert cfg_expert.hops == 3
    assert cfg_expert.top_k == 8
    assert cfg_expert.enable_graph_traversal
    assert any(s["stage"] == "GRAPH_RETRIEVAL" for s in cfg_expert.pipeline_stages)

    # 3. Conversational Mode Switch Case
    cfg_conv = RAGModeDispatcher.dispatch("conversational")
    assert cfg_conv.mode == RAGMode.CONVERSATIONAL
    assert cfg_conv.hops == 0
    assert not cfg_conv.enable_graph_traversal

    # 4. Unknown / Default fallback to Fast
    cfg_default = RAGModeDispatcher.dispatch(None)
    assert cfg_default.mode == RAGMode.FAST


def test_stream_format_dispatcher_negotiation():
    # 1. Non-streaming defaults to JSON
    assert StreamFormatDispatcher.resolve_from_request(
        stream_requested=False, format_param="sse"
    ) == StreamFormat.JSON

    # 2. Explicit format='raw'
    assert StreamFormatDispatcher.resolve_from_request(
        stream_requested=True, format_param="raw"
    ) == StreamFormat.RAW

    # 3. Explicit format='sse'
    assert StreamFormatDispatcher.resolve_from_request(
        stream_requested=True, format_param="sse"
    ) == StreamFormat.SSE

    # 4. Browser Accept header containing text/event-stream alongside text/plain
    assert StreamFormatDispatcher.resolve_from_request(
        stream_requested=True,
        format_param=None,
        accept_header="text/event-stream, text/plain; q=0.9, */*; q=0.8",
    ) == StreamFormat.SSE

    # 5. CLI / Curl Accept header strictly containing text/plain without text/event-stream
    assert StreamFormatDispatcher.resolve_from_request(
        stream_requested=True,
        format_param=None,
        accept_header="text/plain",
    ) == StreamFormat.RAW


def test_inference_execution_dispatcher_switch_cases():
    # 1. LOCAL mode always selects vLLM
    assert InferenceExecutionDispatcher.select_provider(
        mode=InferenceMode.LOCAL,
        configured_cloud_providers=["groq", "gemini"],
        vllm_alive=True,
    ) == "vllm"

    # 2. CLOUD mode selects primary cloud provider if configured
    assert InferenceExecutionDispatcher.select_provider(
        mode=InferenceMode.CLOUD,
        configured_cloud_providers=["gemini", "groq"],
        vllm_alive=True,
        primary_cloud="gemini",
    ) == "gemini"

    # 3. AUTOMATIC mode selects local vLLM if online to avoid cloud costs
    assert InferenceExecutionDispatcher.select_provider(
        mode=InferenceMode.AUTOMATIC,
        configured_cloud_providers=["groq"],
        vllm_alive=True,
    ) == "vllm"

    # 4. AUTOMATIC mode falls back to cloud if local vLLM is offline
    assert InferenceExecutionDispatcher.select_provider(
        mode=InferenceMode.AUTOMATIC,
        configured_cloud_providers=["groq", "gemini"],
        vllm_alive=False,
        primary_cloud="groq",
    ) == "groq"


def test_substrate_lifecycle_dispatcher():
    # 1. Explicit override 'in_memory_fallback'
    mode1 = SubstrateLifecycleDispatcher.resolve_substrate_mode(
        env_override="in_memory_fallback",
        connection_probe_fn=lambda: True,
    )
    assert mode1 == SubstrateMode.FALLBACK

    # 2. Explicit override 'live_neo4j'
    mode2 = SubstrateLifecycleDispatcher.resolve_substrate_mode(
        env_override="live_neo4j",
        connection_probe_fn=lambda: False,
    )
    assert mode2 == SubstrateMode.LIVE

    # 3. Auto-probe success
    mode3 = SubstrateLifecycleDispatcher.resolve_substrate_mode(
        env_override=None,
        connection_probe_fn=lambda: True,
    )
    assert mode3 == SubstrateMode.LIVE

    # 4. Auto-probe failure -> graceful fallback
    mode4 = SubstrateLifecycleDispatcher.resolve_substrate_mode(
        env_override=None,
        connection_probe_fn=lambda: False,
    )
    assert mode4 == SubstrateMode.FALLBACK
