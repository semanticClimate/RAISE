"""
RAISE Infrastructure — Google Gemini Provider Adapter
Supports Gemini models (gemini-2.0-flash, gemini-1.5-pro) via Google's OpenAI-compatible endpoint.
"""

from __future__ import annotations

import os
import logging
from typing import Any, AsyncGenerator, Optional

from src.infrastructure.credentials.manager import get_credential_manager
from src.infrastructure.providers.base import LLMProvider, ProviderHealth
from src.infrastructure.providers.http_client import safe_http_request, ProviderHTTPError

logger = logging.getLogger("raise.infrastructure.providers.gemini")

DEFAULT_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


class GeminiProvider(LLMProvider):
    """Google Gemini model provider adapter."""

    name = "gemini"
    cost_mode = "CLOUD / USER ACCOUNT"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model_name = model_name or os.getenv("GEMINI_MODEL_NAME", DEFAULT_GEMINI_MODEL)
        self.base_url = (base_url or os.getenv("GEMINI_BASE_URL", DEFAULT_GEMINI_ENDPOINT)).rstrip("/")

    def _resolve_api_key(self) -> Optional[str]:
        if self.api_key:
            return self.api_key
        return get_credential_manager().get_credential("gemini")

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
            raise ProviderHTTPError("Gemini API key is not configured.", classification="NOT_CONFIGURED")

        # Try native GenerativeLanguage API first with prioritized models
        raw_candidates = [
            self.model_name,
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3.7-flash",
            "gemini-3.8-flash",
            "gemini-flash-latest",
        ]
        # Deduplicate while preserving order
        candidate_models = []
        for m in raw_candidates:
            if m and m not in candidate_models:
                candidate_models.append(m)

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
        }

        last_error = None
        for cand_m in candidate_models:
            try:
                native_url = f"https://generativelanguage.googleapis.com/v1beta/models/{cand_m}:generateContent"
                resp, _ = safe_http_request(
                    native_url,
                    payload=payload,
                    headers={"x-goog-api-key": key},
                    timeout=kwargs.get("timeout", 15.0),
                    max_retries=1,
                )
                parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                if text_parts:
                    self.model_name = cand_m
                    return "".join(text_parts).strip()
            except ProviderHTTPError as pe:
                last_error = pe
                if pe.status_code in (401, 403):
                    # Hard auth failure: don't loop on invalid credentials
                    raise pe
                # For 404 (deprecated), 503 (high demand), 429 (rate limited on that model): try next model
                logger.debug(f"Gemini model {cand_m} failed (HTTP {pe.status_code}): {pe}. Falling back to next candidate.")
                continue
            except Exception as native_err:
                last_error = native_err
                logger.debug(f"Gemini model {cand_m} error: {native_err}. Falling back to next candidate.")
                continue

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {key}"}

        resp, _ = safe_http_request(
            f"{self.base_url}/chat/completions",
            payload=payload,
            headers=headers,
            timeout=kwargs.get("timeout", 15.0),
            max_retries=1,
        )
        return resp["choices"][0]["message"]["content"]

    async def complete_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        # Fallback to single completion chunk for standard compatibility
        text = self.complete(prompt, system_prompt, max_tokens, temperature, **kwargs)
        yield text

    def health_check(self, timeout: float = 10.0) -> ProviderHealth:
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

        # Try native endpoint first
        try:
            native_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
            payload_native = {"contents": [{"parts": [{"text": "Hello"}]}], "generationConfig": {"maxOutputTokens": 5}}
            resp, latency_ms = safe_http_request(native_url, payload=payload_native, headers={"x-goog-api-key": key}, timeout=timeout, max_retries=0)
            return ProviderHealth(
                provider=self.name,
                configured=True,
                credential_valid=True,
                endpoint_reachable=True,
                model_available=True,
                functional_test=True,
                status="READY",
                latency_ms=round(latency_ms, 1),
                cost_mode=self.cost_mode,
            )
        except Exception as _native_e:
            pass

        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": "Respond exactly with: PROVIDER_TEST_OK"}],
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
            return ProviderHealth(
                provider=self.name,
                configured=True,
                credential_valid=False,
                endpoint_reachable=False,
                model_available=False,
                functional_test=False,
                status="UNKNOWN",
                error_message=f"Error: {type(e).__name__}",
                cost_mode=self.cost_mode,
            )
