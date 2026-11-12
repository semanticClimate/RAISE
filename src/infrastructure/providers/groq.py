"""
RAISE Infrastructure — Groq Provider Adapter
Ultra-low-latency LPU inference adapter for Groq Cloud API.
"""

from __future__ import annotations

import os
import logging
from typing import Any, AsyncGenerator, Optional

from src.infrastructure.credentials.manager import get_credential_manager
from src.infrastructure.providers.base import LLMProvider, ProviderHealth
from src.infrastructure.providers.http_client import safe_http_request, ProviderHTTPError

logger = logging.getLogger("raise.infrastructure.providers.groq")

DEFAULT_GROQ_ENDPOINT = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
CANDIDATE_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
]


class GroqProvider(LLMProvider):
    """Groq LPU accelerated inference provider adapter."""

    name = "groq"
    cost_mode = "CLOUD / USER ACCOUNT"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model_name = model_name or os.getenv("GROQ_MODEL_NAME") or os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL
        self.base_url = (base_url or os.getenv("GROQ_BASE_URL", DEFAULT_GROQ_ENDPOINT)).rstrip("/")

    def _resolve_api_key(self) -> Optional[str]:
        if self.api_key:
            return self.api_key
        return get_credential_manager().get_credential("groq")

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> str:
        key = self._resolve_api_key()
        if not key:
            raise ProviderHTTPError("Groq API key is not configured.", classification="NOT_CONFIGURED")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        candidates = [self.model_name] + [m for m in CANDIDATE_GROQ_MODELS if m != self.model_name]
        last_error = None

        for candidate in candidates:
            payload = {
                "model": candidate,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            headers = {"Authorization": f"Bearer {key}"}

            try:
                resp, _ = safe_http_request(
                    f"{self.base_url}/chat/completions",
                    payload=payload,
                    headers=headers,
                    timeout=kwargs.get("timeout", 45.0),
                )
                if candidate != self.model_name:
                    logger.info(f"Groq auto-updated model to active candidate: {candidate}")
                    self.model_name = candidate
                return resp["choices"][0]["message"]["content"]
            except ProviderHTTPError as e:
                last_error = e
                if e.classification == "MODEL_UNAVAILABLE" or e.status_code in (400, 404):
                    continue
                raise
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error
        raise ProviderHTTPError("No Groq candidate models were accessible.", classification="MODEL_UNAVAILABLE")

    async def complete_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        key = self._resolve_api_key()
        if not key:
            raise ProviderHTTPError("Groq API key is not configured.", classification="NOT_CONFIGURED")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        candidates = [self.model_name] + [m for m in CANDIDATE_GROQ_MODELS if m != self.model_name]
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "RAISE-MultiBackend/2.5",
        }

        try:
            import httpx
            import json
            timeout = httpx.Timeout(kwargs.get("timeout", 45.0), connect=3.0)
            
            for candidate in candidates:
                payload = {
                    "model": candidate,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                }
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    ) as resp:
                        if resp.status_code == 429:
                            raise ProviderHTTPError("HTTP 429 (RATE_LIMITED)", status_code=429, classification="RATE_LIMITED")
                        if resp.status_code in (400, 404):
                            # Try next candidate model
                            continue
                        if resp.status_code != 200:
                            err_text = await resp.aread()
                            raise ProviderHTTPError(f"HTTP {resp.status_code}: {err_text.decode('utf-8', errors='replace')[:200]}", status_code=resp.status_code)

                        if candidate != self.model_name:
                            logger.info(f"Groq stream auto-updated model to active candidate: {candidate}")
                            self.model_name = candidate

                        async for line in resp.aiter_lines():
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta:
                                    yield delta
                            except Exception:
                                continue
                        return
        except ProviderHTTPError:
            raise
        except Exception as e:
            logger.warning(f"Groq streaming exception: {e}. Falling back to sync completion.")
            text = self.complete(prompt, system_prompt, max_tokens, temperature, **kwargs)
            yield text

    def health_check(self, timeout: float = 5.0) -> ProviderHealth:
        """Perform non-destructive configuration, connectivity, and minimal functional test."""
        key = self._resolve_api_key()
        if not key:
            return ProviderHealth(
                provider=self.name,
                configured=False,
                credential_valid=False,
                endpoint_reachable=False,
                model_available=False,
                functional_test=False,
                status="NOT_CONFIGURED",
                error_message="API key missing from environment and Windows Credential Locker",
                cost_mode=self.cost_mode,
            )

        headers = {"Authorization": f"Bearer {key}"}
        candidates = [self.model_name] + [m for m in CANDIDATE_GROQ_MODELS if m != self.model_name]
        last_error = None

        for candidate in candidates:
            payload = {
                "model": candidate,
                "messages": [{"role": "user", "content": "Return exactly: PROVIDER_TEST_OK"}],
                "max_tokens": 5,
                "temperature": 0.0,
            }
            try:
                resp, latency_ms = safe_http_request(
                    f"{self.base_url}/chat/completions",
                    payload=payload,
                    headers=headers,
                    timeout=timeout,
                    max_retries=0,
                )
                content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
                if candidate != self.model_name:
                    logger.info(f"Groq health check updated model to working candidate {candidate}")
                    self.model_name = candidate
                return ProviderHealth(
                    provider=self.name,
                    configured=True,
                    credential_valid=True,
                    endpoint_reachable=True,
                    model_available=True,
                    functional_test="PROVIDER_TEST_OK" in content or len(content) > 0,
                    status="READY",
                    latency_ms=round(latency_ms, 1),
                    cost_mode=self.cost_mode,
                )
            except ProviderHTTPError as e:
                last_error = e
                if e.classification == "MODEL_UNAVAILABLE" or e.status_code in (400, 404):
                    continue
                return ProviderHealth(
                    provider=self.name,
                    configured=True,
                    credential_valid=(e.classification != "AUTH_FAILED"),
                    endpoint_reachable=(e.classification != "ENDPOINT_UNREACHABLE"),
                    model_available=(e.classification != "MODEL_UNAVAILABLE"),
                    functional_test=False,
                    status=e.classification,
                    error_message=str(e),
                    cost_mode=self.cost_mode,
                )
            except Exception as e:
                last_error = e
                continue

        return ProviderHealth(
            provider=self.name,
            configured=True,
            credential_valid=False,
            endpoint_reachable=False,
            model_available=False,
            functional_test=False,
            status="UNKNOWN",
            error_message=f"Error: {last_error}",
            cost_mode=self.cost_mode,
        )
