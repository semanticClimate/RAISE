"""
RAISE Core Architecture: Modular Strategy & Switch-Case Dispatchers
===================================================================
Provides type-safe, modular switch-case dispatchers for:
1. RAGModeDispatcher: Fast vs. Expert vs. Conversational mode configuration
2. StreamFormatDispatcher: SSE vs. Raw text vs. JSON format negotiation
3. InferenceExecutionDispatcher: Local vs. Cloud vs. Automatic hybrid inference routing
4. SubstrateLifecycleDispatcher: Live Docker databases vs. In-memory fallback adapters
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("RAISE.Dispatchers")


# ==============================================================================
# 1. RAG Mode Dispatcher (Fast vs. Expert vs. Conversational)
# ==============================================================================

class RAGMode(str, Enum):
    FAST = "fast"
    EXPERT = "expert"
    CONVERSATIONAL = "conversational"
    AUTO = "auto"

    @classmethod
    def from_str(cls, val: Optional[str]) -> RAGMode:
        if not val:
            return cls.FAST
        normalized = str(val).lower().strip()
        if normalized in ("expert", "deep", "full", "multihop"):
            return cls.EXPERT
        if normalized in ("conversational", "memory", "chat", "persona"):
            return cls.CONVERSATIONAL
        return cls.FAST


@dataclass(frozen=True)
class RAGModeConfig:
    mode: RAGMode
    hops: int
    top_k: int
    enable_graph_traversal: bool
    enable_table_engine: bool
    pipeline_stages: List[Dict[str, str]]
    timeout_sec: float


class RAGModeDispatcher:
    """Modular switch-case dispatcher for RAG query execution parameters."""

    _CONFIG_REGISTRY: Dict[RAGMode, RAGModeConfig] = {
        RAGMode.FAST: RAGModeConfig(
            mode=RAGMode.FAST,
            hops=1,
            top_k=4,
            enable_graph_traversal=False,
            enable_table_engine=False,
            pipeline_stages=[
                {"stage": "QUERY_INTAKE", "node": "query_intake", "status": "active", "detail": "Analyzing research query intent & resolving entities"},
                {"stage": "VECTOR_RETRIEVAL", "node": "vector_retrieval", "status": "active", "detail": "Dense vector & BM25 indexing search"},
                {"stage": "RERANKING", "node": "reranking", "status": "active", "detail": "Cross-encoder neural reranking & scoring"},
                {"stage": "SYNTHESIS", "node": "synthesis", "status": "active", "detail": "Synthesizing grounded citations"},
            ],
            timeout_sec=30.0,
        ),
        RAGMode.EXPERT: RAGModeConfig(
            mode=RAGMode.EXPERT,
            hops=3,
            top_k=8,
            enable_graph_traversal=True,
            enable_table_engine=True,
            pipeline_stages=[
                {"stage": "QUERY_INTAKE", "node": "query_intake", "status": "active", "detail": "Analyzing research query intent & resolving entities"},
                {"stage": "VECTOR_RETRIEVAL", "node": "vector_retrieval", "status": "active", "detail": "Dense vector & BM25 indexing search"},
                {"stage": "GRAPH_RETRIEVAL", "node": "graph_retrieval", "status": "active", "detail": "Traversing multi-hop knowledge graph via openCypher"},
                {"stage": "RERANKING", "node": "reranking", "status": "active", "detail": "Cross-encoder neural reranking & scoring"},
                {"stage": "SYNTHESIS", "node": "synthesis", "status": "active", "detail": "Synthesizing grounded citations"},
            ],
            timeout_sec=90.0,
        ),
        RAGMode.CONVERSATIONAL: RAGModeConfig(
            mode=RAGMode.CONVERSATIONAL,
            hops=0,
            top_k=0,
            enable_graph_traversal=False,
            enable_table_engine=False,
            pipeline_stages=[
                {"stage": "QUERY_INTAKE", "node": "query_intake", "status": "active", "detail": "Processing conversational dialogue context"},
                {"stage": "SYNTHESIS", "node": "synthesis", "status": "active", "detail": "Direct persona memory synthesis"},
            ],
            timeout_sec=15.0,
        ),
    }

    @classmethod
    def dispatch(cls, mode_val: Optional[Union[RAGMode, str]]) -> RAGModeConfig:
        """Switch-case resolution for RAG execution strategy."""
        mode = RAGMode.from_str(str(mode_val)) if isinstance(mode_val, str) else (mode_val or RAGMode.FAST)
        return cls._CONFIG_REGISTRY.get(mode, cls._CONFIG_REGISTRY[RAGMode.FAST])


# ==============================================================================
# 2. Stream Format Dispatcher (SSE vs. Raw vs. JSON)
# ==============================================================================

class StreamFormat(str, Enum):
    SSE = "sse"
    RAW = "raw"
    JSON = "json"

    @classmethod
    def resolve_from_request(
        cls,
        format_param: Optional[str] = None,
        accept_header: Optional[str] = None,
        stream_requested: bool = False,
    ) -> StreamFormat:
        """
        Content negotiation switch-case:
        - Non-streaming requests default to JSON
        - Explicit format='raw' or Accept header with text/plain (and no text/event-stream) -> RAW
        - Everything else requesting stream -> SSE
        """
        if not stream_requested:
            return cls.JSON

        accept = (accept_header or "").lower()
        param = (format_param or "").lower().strip()

        # Switch-case logic
        if param == "raw":
            return cls.RAW
        if param == "sse":
            return cls.SSE

        if "text/plain" in accept and "text/event-stream" not in accept:
            return cls.RAW

        return cls.SSE


class StreamFormatDispatcher:
    """Modular switch-case dispatcher for API stream format negotiation."""

    @staticmethod
    def resolve_from_request(
        format_param: Optional[str] = None,
        accept_header: Optional[str] = None,
        stream_requested: bool = False,
    ) -> StreamFormat:
        return StreamFormat.resolve_from_request(
            format_param=format_param,
            accept_header=accept_header,
            stream_requested=stream_requested,
        )


# ==============================================================================
# 3. Inference Execution Mode Dispatcher (Local vs. Cloud vs. Automatic)
# ==============================================================================

class InferenceMode(str, Enum):
    LOCAL = "LOCAL"
    CLOUD = "CLOUD"
    AUTOMATIC = "AUTOMATIC"

    @classmethod
    def from_str(cls, val: Optional[str]) -> InferenceMode:
        if not val:
            return cls.AUTOMATIC
        norm = str(val).upper().strip()
        if norm in ("LOCAL", "OFFLINE", "VLLM", "AIR_GAPPED"):
            return cls.LOCAL
        if norm in ("CLOUD", "REMOTE", "API"):
            return cls.CLOUD
        return cls.AUTOMATIC


class InferenceExecutionDispatcher:
    """Modular switch-case dispatcher for resolving target LLM provider."""

    @staticmethod
    def select_provider(
        mode: InferenceMode,
        configured_cloud_providers: List[str],
        vllm_alive: bool,
        primary_cloud: str = "groq",
    ) -> str:
        """
        Switch-case strategy:
        - LOCAL: strictly vllm (or local in-process fallback)
        - CLOUD: primary cloud if configured, else first available cloud candidate
        - AUTOMATIC: vLLM if online; otherwise best available cloud; otherwise in-process
        """
        match mode:
            case InferenceMode.LOCAL:
                return "vllm"

            case InferenceMode.CLOUD:
                if primary_cloud in configured_cloud_providers:
                    return primary_cloud
                return configured_cloud_providers[0] if configured_cloud_providers else "groq"

            case InferenceMode.AUTOMATIC:
                # Prioritize local vLLM if healthy to save cloud API tokens & latency
                if vllm_alive:
                    return "vllm"
                if primary_cloud in configured_cloud_providers:
                    return primary_cloud
                if configured_cloud_providers:
                    return configured_cloud_providers[0]
                return "vllm"

            case _:
                return "vllm"


# ==============================================================================
# 4. Substrate Lifecycle Dispatcher (Live Docker vs. In-Memory Fallback)
# ==============================================================================

class SubstrateMode(str, Enum):
    LIVE = "live"
    FALLBACK = "fallback"


@dataclass
class SubstrateStatus:
    neo4j_mode: SubstrateMode
    postgres_mode: SubstrateMode
    redis_mode: SubstrateMode
    llm_mode: str
    details: Dict[str, Any] = field(default_factory=dict)


class SubstrateLifecycleDispatcher:
    """Dispatches database, cache, and vector store operations to live vs. fallback drivers."""

    @staticmethod
    def resolve_substrate_mode(
        env_override: Optional[str],
        connection_probe_fn: Callable[[], bool],
    ) -> SubstrateMode:
        """Determines whether to engage live connection or graceful fallback."""
        if env_override:
            norm = env_override.lower().strip()
            if norm.startswith("fallback") or norm.startswith("in_memory") or norm in ("mock", "offline"):
                return SubstrateMode.FALLBACK
            if norm.startswith("live") or norm in ("production", "online", "docker", "real"):
                return SubstrateMode.LIVE

        # Run connection probe
        try:
            is_alive = connection_probe_fn()
            return SubstrateMode.LIVE if is_alive else SubstrateMode.FALLBACK
        except Exception:
            return SubstrateMode.FALLBACK
