"""
RAISE LiteLLM Unified Multi-Provider LLM Router
===============================================
Unified Multi-Provider LLM Proxy, Dynamic Failover & Routing Engine.
Architecture Layer: LLM Infrastructure / Provider Routing & Resiliency

Why LiteLLM:
------------
  - Standardizes 100+ LLM APIs into a unified OpenAI-compatible request/response envelope.
  - Built-in exponential backoff, rate-limit retries (429), and failover groups.
  - Automatically handles model-specific parameter quirks (temperature ranges, token limits).
  - Built-in latency timing and token usage telemetry.

Providers Supported:
-------------------
  • Local vLLM (OpenAI-compatible)
  • Groq (ultra-low latency Qwen 2.5 / Llama 3.3)
  • Cohere (Command-R+ enterprise grounding)
  • Google Gemini (Gemini 2.5 Flash)
  • NVIDIA NIM (Llama 3.2 11B / DeepSeek)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("raise.infrastructure.llm.litellm")

try:
    import litellm
    litellm.drop_params = True
    litellm.telemetry = False
    HAS_LITELLM = True
except ImportError:
    litellm = None
    HAS_LITELLM = False


class LiteLLMRouter:
    """
    Unified multi-provider LLM proxy engine powered by LiteLLM.
    Handles dynamic provider failover, retry budgets, and token usage accounting.
    """

    DEFAULT_FALLBACK_ORDER = [
        {"model": "groq/qwen/qwen3.8-27b", "api_key": "GROQ_API_KEY"},
        {"model": "cohere/command-r-plus-08-2024", "api_key": "COHERE_API_KEY"},
        {"model": "gemini/gemini-2.5-flash", "api_key": "GEMINI_API_KEY"},
        {"model": "nvidia/meta/llama-3.2-11b-vision-instruct", "api_key": "NVIDIA_API_KEY"},
    ]

    def __init__(self, default_model: Optional[str] = None):
        self.has_litellm = HAS_LITELLM
        self.default_model = default_model or os.getenv("DEFAULT_LLM_MODEL", "groq/qwen/qwen3.8-27b")
        if HAS_LITELLM:
            logger.info(f"LiteLLM router initialized with default target: {self.default_model}")
        else:
            logger.warning("LiteLLM not installed; operating in passthrough mode.")

    def completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: float = 30.0,
        fallbacks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes unified LLM completion with automatic retries and fallback failover.
        """
        if not self.has_litellm:
            return {
                "content": "LiteLLM library not available.",
                "model": "none",
                "usage": {},
                "latency_ms": 0.0,
                "status": "error",
            }

        target_model = model or self.default_model
        t0 = time.time()

        # Build fallback list if not supplied
        active_fallbacks = fallbacks or [
            f["model"] for f in self.DEFAULT_FALLBACK_ORDER if f["model"] != target_model
        ]

        try:
            resp = litellm.completion(
                model=target_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                fallbacks=active_fallbacks,
            )

            latency_ms = round((time.time() - t0) * 1000.0, 2)
            content = resp.choices[0].message.content or ""
            usage = resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else dict(resp.usage or {})

            return {
                "content": content,
                "model": getattr(resp, "model", target_model),
                "usage": usage,
                "latency_ms": latency_ms,
                "status": "success",
            }
        except Exception as e:
            logger.error(f"LiteLLM completion error: {e}")
            return {
                "content": f"LLM Router Error: {e}",
                "model": target_model,
                "usage": {},
                "latency_ms": round((time.time() - t0) * 1000.0, 2),
                "status": "failed",
                "error": str(e),
            }


# Singleton router instance
_litellm_router: Optional[LiteLLMRouter] = None


def get_litellm_router() -> LiteLLMRouter:
    global _litellm_router
    if _litellm_router is None:
        _litellm_router = LiteLLMRouter()
    return _litellm_router
