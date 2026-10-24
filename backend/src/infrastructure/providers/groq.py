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
    "deepseek-r1-distill-llama-70b",
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
        self.model_name = model_name or os.getenv("GROQ_MODEL_NAME", DEFAULT_GROQ_MODEL)
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
        for cand in candidates:
            payload = {
                "model": cand,
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
                self.model_name = cand
                return resp["choices"][0]["message"]["content"]
            except ProviderHTTPError as pe:
                last_error = pe
                if pe.status_code in (429, 401, 403, 402):
                    raise pe
                logger.debug(f"Groq candidate {cand} failed: {pe}")
                continue
            except Exception as ex:
                last_error = ex
                logger.debug(f"Groq candidate {cand} exception: {ex}")
                continue

        if last_error:
            if isinstance(last_error, ProviderHTTPError):
                raise last_error
            raise ProviderHTTPError(f"Groq completion failed across candidates: {last_error}", classification="MODEL_UNAVAILABLE")
        raise ProviderHTTPError("Groq completion failed with no candidates available.", classification="MODEL_UNAVAILABLE")

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

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "RAISE-MultiBackend/2.5",
        }

        try:
            import httpx
            import json
            timeout = httpx.Timeout(kwargs.get("timeout", 45.0), connect=3.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as resp:
                    if resp.status_code == 429:
                        raise ProviderHTTPError("HTTP 429 (RATE_LIMITED)", status_code=429, classification="RATE_LIMITED")
                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        raise ProviderHTTPError(f"HTTP {resp.status_code}: {err_text.decode('utf-8', errors='replace')[:200]}", status_code=resp.status_code)

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

        candidates = [self.model_name] + [m for m in CANDIDATE_GROQ_MODELS if m != self.model_name]
        last_http_err = None
        for cand in candidates:
            payload = {
                "model": cand,
                "messages": [{"role": "user", "content": "Return exactly: PROVIDER_TEST_OK"}],
                "max_tokens": 5,
                "temperature": 0.0,
            }
            headers = {"Authorization": f"Bearer {key}"}

            try:
                resp, latency_ms = safe_http_request(
                    f"{self.base_url}/chat/completions",
                    payload=payload,
                    headers=headers,
                    timeout=timeout,
                    max_retries=0,
                )
                self.model_name = cand
                content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
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
                last_http_err = e
                if e.classification in ("AUTH_FAILED", "RATE_LIMITED", "BILLING_EXHAUSTED"):
                    break
                continue
            except Exception as e:
                last_http_err = e
                continue

        if isinstance(last_http_err, ProviderHTTPError):
            return ProviderHealth(
                provider=self.name,
                configured=True,
                credential_valid=(last_http_err.classification != "AUTH_FAILED"),
                endpoint_reachable=(last_http_err.classification != "ENDPOINT_UNREACHABLE"),
                model_available=(last_http_err.classification != "MODEL_UNAVAILABLE"),
                functional_test=False,
                status=last_http_err.classification,
                error_message=str(last_http_err),
                cost_mode=self.cost_mode,
            )
        return ProviderHealth(
            provider=self.name,
            configured=True,
            credential_valid=False,
            endpoint_reachable=False,
            model_available=False,
            functional_test=False,
            status="UNKNOWN",
            error_message=f"Error: {type(last_http_err).__name__}" if last_http_err else "No candidates responded",
            cost_mode=self.cost_mode,
        )
