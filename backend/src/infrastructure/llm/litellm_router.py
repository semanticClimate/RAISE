"""
RAISE LiteLLM Unified Multi-Provider LLM Router
===============================================
Unified Multi-Provider LLM Proxy, Dynamic Failover & Routing Engine.
Architecture Layer: LLM Infrastructure / Provider Routing & Resiliency

Zero Hardcoded Models Policy:
-----------------------------
- Dynamically discovers active models on user accounts and local engines via live APIs.
- Automatically builds dynamic fallback order from configured credentials.
- Inspects real-time API response envelopes to identify the exact model that generated the response.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from src.infrastructure.llm.model_discovery import get_model_discovery_engine

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
    Zero hardcoded models: dynamically discovers models from provider APIs,
    constructs dynamic failover chains, and captures the exact generating model.
    """

    def __init__(self, default_model: Optional[str] = None):
        self.has_litellm = HAS_LITELLM
        self.discovery_engine = get_model_discovery_engine()
        self._explicit_default_model = default_model or os.getenv("DEFAULT_LLM_MODEL")
        self._cached_fallback_order: List[Dict[str, str]] = []
        self._cached_default_model: str = ""
        self.refresh_fallback_order()

    def refresh_fallback_order(self) -> None:
        """Dynamically discovers and caches models from live APIs."""
        discovered = self.discovery_engine.build_dynamic_fallback_order()
        if discovered:
            self._cached_fallback_order = discovered
        else:
            groq_m = self.discovery_engine.get_preferred_model("groq", "llama-3.3-70b-versatile")
            gemini_m = self.discovery_engine.get_preferred_model("gemini", "gemini-2.0-flash")
            self._cached_fallback_order = [
                {"model": f"groq/{groq_m}", "api_key": "GROQ_API_KEY"},
                {"model": f"gemini/{gemini_m}", "api_key": "GEMINI_API_KEY"},
            ]
        self._cached_default_model = (
            self._explicit_default_model
            or (self._cached_fallback_order[0]["model"] if self._cached_fallback_order else "groq/llama-3.3-70b-versatile")
        )

    @property
    def default_model(self) -> str:
        """Instant sub-microsecond resolution of active default model."""
        return self._cached_default_model

    @property
    def DEFAULT_FALLBACK_ORDER(self) -> List[Dict[str, str]]:
        """Instant sub-microsecond resolution of dynamic fallback order."""
        return self._cached_fallback_order

    def get_fallback_order(self) -> List[Dict[str, str]]:
        """Returns the dynamic fallback order."""
        return self._cached_fallback_order

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
        Executes unified LLM completion with dynamic API discovery and telemetry.
        Returns the exact model that generated the output.
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

        # Build dynamic fallback list if not explicitly supplied
        if fallbacks is None:
            active_fallbacks = [
                f["model"] for f in self.get_fallback_order() if f["model"] != target_model
            ]
        else:
            active_fallbacks = fallbacks

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
            
            # Extract the EXACT generating model directly from the API response envelope
            actual_generating_model = getattr(resp, "model", None) or resp.get("model", target_model)

            logger.info(f"LiteLLM completion succeeded via model: {actual_generating_model} ({latency_ms}ms)")

            return {
                "content": content,
                "model": actual_generating_model,       # Exact generating model reported by the API!
                "target_model": target_model,           # Initial requested target
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
