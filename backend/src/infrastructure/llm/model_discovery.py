"""
RAISE Infrastructure — Dynamic Real-Time Model Discovery Engine
================================================================
Queries provider APIs in real-time to discover available models on user accounts
and local engine daemons without hardcoding model lists.

Supports:
- Local vLLM (/v1/models)
- Local Ollama (/api/tags)
- Groq Cloud (/openai/v1/models)
- Google Gemini (generativelanguage /v1beta/models)
- Mistral AI (/v1/models)
- NVIDIA NIM (/v1/models)
- Cohere (/v1/models)
- OpenAI (/v1/models)
- OpenRouter (/api/v1/models)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional
import urllib.request
import json

from src.infrastructure.credentials.manager import get_credential_manager
from src.infrastructure.providers.http_client import safe_http_request

logger = logging.getLogger("raise.infrastructure.llm.model_discovery")

# In-memory discovery cache with 10-minute TTL
_DISCOVERY_CACHE: Dict[str, Dict[str, Any]] = {}
_DISCOVERY_CACHE_TTL = 600.0  # seconds


class ModelDiscoveryEngine:
    """
    Dynamically discovers active models directly from live provider APIs.
    Zero hardcoded model catalogs.
    """

    def __init__(self):
        self._cm = get_credential_manager()

    def discover_provider_models(self, provider: str, force_refresh: bool = False) -> List[str]:
        """
        Queries the given provider's API directly to get the live list of models.
        Results are cached in memory for 10 minutes.
        """
        now = time.time()
        cached = _DISCOVERY_CACHE.get(provider)
        if not force_refresh and cached and (now - cached.get("timestamp", 0) < _DISCOVERY_CACHE_TTL):
            return cached.get("models", [])

        models: List[str] = []
        try:
            if provider == "vllm":
                models = self._discover_vllm()
            elif provider == "ollama":
                models = self._discover_ollama()
            elif provider == "groq":
                models = self._discover_groq()
            elif provider == "gemini":
                models = self._discover_gemini()
            elif provider == "mistral":
                models = self._discover_mistral()
            elif provider == "nvidia":
                models = self._discover_nvidia()
            elif provider == "cohere":
                models = self._discover_cohere()
            elif provider == "openai":
                models = self._discover_openai()
            elif provider == "openrouter":
                models = self._discover_openrouter()
        except Exception as e:
            logger.debug(f"Dynamic discovery error for {provider}: {e}")

        # If discovery succeeds, cache and return
        if models:
            _DISCOVERY_CACHE[provider] = {"models": models, "timestamp": now}
            logger.info(f"Dynamically discovered {len(models)} models for provider '{provider}': {models[:3]}...")
            return models

        # Return cached if available, else empty list
        if cached:
            return cached.get("models", [])
        return []

    def _discover_vllm(self) -> List[str]:
        url = os.getenv("VLLM_BASE_URL", "http://localhost:8002/v1").rstrip("/") + "/models"
        resp, _ = safe_http_request(url, timeout=1.0, max_retries=0)
        data = resp.get("data", [])
        return [m.get("id") for m in data if m.get("id")]

    def _discover_ollama(self) -> List[str]:
        url = "http://127.0.0.1:11434/api/tags"
        resp, _ = safe_http_request(url, timeout=1.0, max_retries=0)
        models = resp.get("models", [])
        return [m.get("name") for m in models if m.get("name")]

    def _discover_groq(self) -> List[str]:
        key = self._cm.get_credential("groq")
        if not key:
            return []
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {key}"}
        resp, _ = safe_http_request(url, headers=headers, timeout=3.0, max_retries=0)
        data = resp.get("data", [])
        # Filter for text chat models (exclude whisper audio models)
        return [m.get("id") for m in data if m.get("id") and not m.get("id", "").startswith("whisper")]

    def _discover_gemini(self) -> List[str]:
        key = self._cm.get_credential("gemini")
        if not key:
            return []
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        resp, _ = safe_http_request(url, timeout=3.0, max_retries=0)
        models = resp.get("models", [])
        results = []
        for m in models:
            name = m.get("name", "").replace("models/", "")
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods:
                results.append(name)
        return results

    def _discover_mistral(self) -> List[str]:
        key = self._cm.get_credential("mistral")
        if not key:
            return []
        url = "https://api.mistral.ai/v1/models"
        headers = {"Authorization": f"Bearer {key}"}
        resp, _ = safe_http_request(url, headers=headers, timeout=3.0, max_retries=0)
        data = resp.get("data", [])
        return [m.get("id") for m in data if m.get("id")]

    def _discover_nvidia(self) -> List[str]:
        key = self._cm.get_credential("nvidia")
        if not key:
            return []
        url = "https://integrate.api.nvidia.com/v1/models"
        headers = {"Authorization": f"Bearer {key}"}
        resp, _ = safe_http_request(url, headers=headers, timeout=3.0, max_retries=0)
        data = resp.get("data", [])
        return [m.get("id") for m in data if m.get("id")]

    def _discover_cohere(self) -> List[str]:
        key = self._cm.get_credential("cohere")
        if not key:
            return []
        url = "https://api.cohere.com/v1/models"
        headers = {"Authorization": f"Bearer {key}"}
        resp, _ = safe_http_request(url, headers=headers, timeout=3.0, max_retries=0)
        models = resp.get("models", [])
        return [m.get("name") for m in models if m.get("name")]

    def _discover_openai(self) -> List[str]:
        key = self._cm.get_credential("openai")
        if not key:
            return []
        url = "https://api.openai.com/v1/models"
        headers = {"Authorization": f"Bearer {key}"}
        resp, _ = safe_http_request(url, headers=headers, timeout=3.0, max_retries=0)
        data = resp.get("data", [])
        return [m.get("id") for m in data if m.get("id") and ("gpt" in m.get("id", "") or "o1" in m.get("id", ""))]

    def _discover_openrouter(self) -> List[str]:
        url = "https://openrouter.ai/api/v1/models"
        resp, _ = safe_http_request(url, timeout=2.5, max_retries=0)
        data = resp.get("data", [])
        return [m.get("id") for m in data if m.get("id")]

    def get_preferred_model(self, provider: str, default_fallback: str) -> str:
        """
        Returns the active model for a provider:
        1. Checks environment variable override (e.g. GROQ_MODEL, GEMINI_MODEL).
        2. If not set, queries live discovered models from the API and selects the top match.
        3. If API is unreachable or unconfigured, falls back to default_fallback.
        """
        env_var_map = {
            "groq": "GROQ_MODEL",
            "gemini": "GEMINI_MODEL",
            "vllm": "VLLM_MODEL",
            "mistral": "MISTRAL_MODEL_NAME",
            "nvidia": "NVIDIA_MODEL_NAME",
            "cohere": "COHERE_CHAT_MODEL",
            "openai": "OPENAI_MODEL_NAME",
        }
        env_val = os.getenv(env_var_map.get(provider, ""), "").strip()
        if env_val:
            return env_val

        # Discover dynamically from live API
        live_models = self.discover_provider_models(provider)
        if live_models:
            # Prefer top instruct/chat models from discovered list
            for m in live_models:
                m_lower = m.lower()
                if "whisper" in m_lower or "embed" in m_lower or "guard" in m_lower or "moderation" in m_lower:
                    continue
                return m
            return live_models[0]

        return default_fallback

    def build_dynamic_fallback_order(self) -> List[Dict[str, str]]:
        """
        Dynamically constructs the LiteLLM fallback order based ONLY on
        providers that actually have valid credentials configured.
        Zero hardcoded static lists.
        """
        order: List[Dict[str, str]] = []

        provider_env_keys = {
            "groq": ("GROQ_API_KEY", "llama-3.3-70b-versatile"),
            "gemini": ("GEMINI_API_KEY", "gemini-2.0-flash"),
            "mistral": ("MISTRAL_API_KEY", "mistral-small-latest"),
            "nvidia": ("NVIDIA_API_KEY", "meta/llama-3.3-70b-instruct"),
            "cohere": ("COHERE_API_KEY", "command-r-plus-08-2024"),
            "openai": ("OPENAI_API_KEY", "gpt-4o"),
        }

        for prov, (api_key_env, default_fb) in provider_env_keys.items():
            if self._cm.get_credential_status(prov) == "configured":
                active_model = self.get_preferred_model(prov, default_fb)
                # Formulate LiteLLM model identifier e.g. "groq/llama-3.3-70b-versatile"
                litellm_model = f"{prov}/{active_model}" if not active_model.startswith(f"{prov}/") else active_model
                order.append({"model": litellm_model, "api_key": api_key_env})

        # Add local vLLM if reachable
        try:
            vllm_models = self._discover_vllm()
            if vllm_models:
                order.append({"model": f"openai/{vllm_models[0]}", "api_key": "NONE"})
        except Exception:
            pass

        return order


_engine: Optional[ModelDiscoveryEngine] = None


def get_model_discovery_engine() -> ModelDiscoveryEngine:
    global _engine
    if _engine is None:
        _engine = ModelDiscoveryEngine()
    return _engine
