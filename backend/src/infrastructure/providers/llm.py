"""
RAISE Infrastructure — Unified Multi-Provider LLM Interface
Supports local inference engines (vLLM, Ollama) and cloud-compatible APIs (Gemini, Groq, DeepSeek, NVIDIA NIM, Cohere).
"""

from __future__ import annotations

import os
import json
import logging
import socket
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, AsyncGenerator, Optional

from src.core.config import settings, LLMConfig, models
from src.infrastructure.providers.base import LLMProvider, ProviderHealth

logger = logging.getLogger("raise.infrastructure.providers.llm")


class BaseLLMProvider(LLMProvider):
    """Abstract baseline for local and cloud LLM inference providers."""

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError

    async def complete_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError
        yield ""

    def health_check(self, timeout: float = 5.0) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            configured=True,
            credential_valid=True,
            endpoint_reachable=False,
            model_available=False,
            functional_test=False,
            status="UNKNOWN",
            cost_mode=self.cost_mode,
        )


class LocalVLLMProvider(BaseLLMProvider):
    """Local high-throughput vLLM engine running on GPU."""

    name = "vllm"
    cost_mode = "LOCAL / NO EXTERNAL API BILLING"

    def __init__(self, base_url: Optional[str] = None, model_name: Optional[str] = None):
        self.base_url = (base_url or os.getenv("VLLM_BASE_URL", "http://localhost:8002/v1")).rstrip("/")
        self.model_name = model_name or os.getenv("VLLM_MODEL_NAME", models.VLLM_MODEL_NAME)

    def is_available(self) -> bool:
        """Fast non-blocking check to determine if the local vLLM server is alive across common ports and Docker networks."""
        now = time.time()
        if hasattr(self, "_last_check_time") and (now - self._last_check_time) < 10.0:
            return bool(getattr(self, "_last_available", False))

        candidate_urls = [self.base_url]
        for candidate in getattr(settings.llm, "vllm_candidate_urls", ()):
            if candidate and candidate not in candidate_urls:
                candidate_urls.append(candidate)
        for fallback in [
            "http://127.0.0.1:8002/v1",
            "http://localhost:8002/v1",
        ]:
            if fallback not in candidate_urls:
                candidate_urls.append(fallback)
        if os.path.exists("/.dockerenv"):
            for container_host in ["http://raise-vllm-prod:8000/v1", "http://host.docker.internal:8002/v1"]:
                if container_host not in candidate_urls:
                    candidate_urls.append(container_host)
        probe_timeout = float(getattr(settings.llm, "probe_timeout", 0.15))
        for u in candidate_urls:
            try:
                # Fast TCP pre-flight to prevent slow DNS connect timeouts
                parsed = urllib.parse.urlparse(u)
                raw_host = parsed.hostname or "127.0.0.1"
                host = "127.0.0.1" if raw_host in ("localhost", "127.0.0.1") else raw_host
                port = parsed.port or 8002
                with socket.create_connection((host, port), timeout=probe_timeout):
                    pass
            except Exception:
                continue

            try:
                req = urllib.request.Request(f"{u.rstrip('/')}/models", headers={"User-Agent": "RAISE-Provider"})
                with urllib.request.urlopen(req, timeout=probe_timeout) as resp:
                    if resp.status == 200:
                        self.base_url = u.rstrip("/")
                        os.environ["VLLM_BASE_URL"] = self.base_url
                        try:
                            models_data = json.loads(resp.read().decode("utf-8"))
                            if "data" in models_data and len(models_data["data"]) > 0:
                                discovered_id = models_data["data"][0].get("id")
                                if discovered_id and (
                                    self.model_name == models.LLM_MODEL_NAME
                                    or self.model_name == models.VLLM_MODEL_NAME
                                    or self.model_name == os.getenv("VLLM_MODEL_NAME")
                                    or self.model_name == "default"
                                    or not self.model_name
                                ):
                                    self.model_name = discovered_id
                        except Exception:
                            pass
                        self._last_check_time = now
                        self._last_available = True
                        return True
            except Exception:
                pass
        self._last_check_time = now
        self._last_available = False
        return False

    async def complete_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens directly from vLLM server with fast non-blocking SSE."""
        import httpx
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

        url = f"{self.base_url}/chat/completions"
        timeout = httpx.Timeout(60.0, connect=3.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    raise RuntimeError(f"vLLM HTTP {resp.status_code}: {err_body.decode('utf-8', errors='replace')}")
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        pass

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> str:
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

        # Allow ample timeout for heavy local LLM context prefill and generation (default 60.0s)
        caller_timeout = kwargs.get("timeout")
        timeout = max(float(caller_timeout), 60.0) if caller_timeout else 60.0

        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "RAISE-Provider"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            err_str = str(e)
            is_refused = "10061" in err_str or "actively refused" in err_str.lower() or "connection refused" in err_str.lower()
            if is_refused:
                logger.warning(f"Local vLLM endpoint ({self.base_url}) is offline (connection refused).")
            else:
                logger.warning(f"Local vLLM endpoint ({self.base_url}) unavailable: {e}.")

            # Propagate error cleanly to ProviderRouter so configured fallback chain is respected
            raise RuntimeError(f"Local vLLM inference failed at {self.base_url}: {e}")

    def health_check(self, timeout: float = 5.0) -> ProviderHealth:
        """Ping local vLLM endpoint and perform micro inference."""
        t_start = time.perf_counter()
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 5,
            "temperature": 0.0,
        }
        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                return ProviderHealth(
                    provider=self.name,
                    configured=True,
                    credential_valid=True,
                    endpoint_reachable=True,
                    model_available=True,
                    functional_test=True,
                    status="READY",
                    latency_ms=round(elapsed_ms, 1),
                    cost_mode=self.cost_mode,
                )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            return ProviderHealth(
                provider=self.name,
                configured=True,
                credential_valid=True,
                endpoint_reachable=False,
                model_available=False,
                functional_test=False,
                status="ENDPOINT_UNREACHABLE",
                latency_ms=round(elapsed_ms, 1),
                error_message=f"Local vLLM offline: {type(e).__name__}",
                cost_mode=self.cost_mode,
            )


class LocalTransformersProvider(BaseLLMProvider):
    """
    Direct in-process GPU / accelerator LLM inference using HuggingFace Transformers.
    Dynamically utilizes available host hardware (CUDA, Apple Silicon MPS, or CPU).
    Zero external server dependency, runs fully local with torch.float16 / bfloat16.
    """

    name = "local"
    cost_mode = "LOCAL GPU / ZERO BILLING"

    _shared_model = None
    _shared_tokenizer = None
    _loaded_model_name = None
    _lock = threading.Lock()

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("LOCAL_LLM_MODEL", models.LLM_MODEL_NAME)

    def is_available(self) -> bool:
        """Check if local environment supports torch inference."""
        try:
            m_lower = (self.model_name or "").lower()
            if any(cloud in m_lower for cloud in ["gemini", "openai", "claude", "command-r"]):
                return False
            import torch
            return bool(torch.cuda.is_available() or os.getenv("ALLOW_CPU_LOCAL_LLM", "true").lower() in ("true", "1"))
        except Exception:
            return False

    def _ensure_loaded(self):
        with self._lock:
            if LocalTransformersProvider._shared_model is not None and LocalTransformersProvider._loaded_model_name == self.model_name:
                return

            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32

            logger.info(f"Loading in-process local LLM '{self.model_name}' on {device} ({dtype})...")
            tok = None
            mod = None
            for local_only in [True, False]:
                try:
                    tok = AutoTokenizer.from_pretrained(
                        self.model_name,
                        trust_remote_code=True,
                        local_files_only=local_only,
                    )
                    mod = AutoModelForCausalLM.from_pretrained(
                        self.model_name,
                        dtype=dtype,
                        device_map=device,
                        trust_remote_code=True,
                        local_files_only=local_only,
                    )
                    break
                except Exception as _load_err:
                    err_msg = str(_load_err)
                    if "QuantizeConfig" in err_msg or "quant" in err_msg.lower():
                        logger.warning(
                            f"In-process local LLM '{self.model_name}' requires external quantization packages: {_load_err}. "
                            "Please use running vLLM or Ollama instance for quantized models."
                        )
                    if not local_only:
                        raise RuntimeError(f"Could not load in-process local LLM '{self.model_name}': {_load_err}")
            if tok is None or mod is None:
                raise RuntimeError(f"Could not load local LLM {self.model_name}")
            mod.eval()
            LocalTransformersProvider._shared_tokenizer = tok
            LocalTransformersProvider._shared_model = mod
            LocalTransformersProvider._loaded_model_name = self.model_name
            logger.info(f"In-process local LLM '{self.model_name}' successfully loaded into VRAM/RAM.")

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> str:
        try:
            self._ensure_loaded()
            import torch

            tok = LocalTransformersProvider._shared_tokenizer
            mod = LocalTransformersProvider._shared_model

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            input_text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tok([input_text], return_tensors="pt").to(mod.device)

            with torch.no_grad():
                outputs = mod.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=max(temperature, 0.01) if temperature > 0 else None,
                    do_sample=(temperature > 0),
                    pad_token_id=tok.eos_token_id,
                )
            generated_ids = [
                output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, outputs)
            ]
            response = tok.batch_decode(generated_ids, skip_special_tokens=True)[0]
            return response.strip()
        except Exception as e:
            logger.error(f"In-process local LLM generation failed: {e}")
            raise RuntimeError(f"Error executing local inference: {e}")

    async def complete_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        text = self.complete(prompt, system_prompt, max_tokens, temperature, **kwargs)
        yield text

    def health_check(self, timeout: float = 5.0) -> ProviderHealth:
        import torch
        if not torch.cuda.is_available():
            return ProviderHealth(
                provider=self.name,
                configured=False,
                credential_valid=False,
                endpoint_reachable=False,
                model_available=False,
                functional_test=False,
                status="NO_CUDA",
                cost_mode=self.cost_mode,
            )
        return ProviderHealth(
            provider=self.name,
            configured=True,
            credential_valid=True,
            endpoint_reachable=True,
            model_available=True,
            functional_test=True,
            status="READY",
            cost_mode=self.cost_mode,
        )


class CloudOpenAICompatibleProvider(BaseLLMProvider):
    """
    Cloud-compatible LLM provider for OpenAI or generic OpenAI-compatible gateways.
    """

    name = "openai-compatible"
    cost_mode = "CLOUD / USER ACCOUNT"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model_name = model_name or os.getenv("LLM_MODEL_NAME", models.OPENAI_MODEL_NAME)

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> str:
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

        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": "RAISE-CloudProvider",
                },
            )
            with urllib.request.urlopen(req, timeout=kwargs.get("timeout", 60.0)) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Cloud LLM completion failed: {e}")
            raise RuntimeError(f"Cloud LLM error: {e}")

    async def complete_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        text = self.complete(prompt, system_prompt, max_tokens, temperature, **kwargs)
        yield text


class LocalOllamaProvider(BaseLLMProvider):
    """Local Ollama instance on port 11434."""

    name = "ollama"
    cost_mode = "LOCAL / NO EXTERNAL API BILLING"

    def __init__(self, base_url: Optional[str] = None, model_name: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", models.OLLAMA_MODEL_NAME)

    def is_available(self) -> bool:
        """Fast non-blocking check to determine if local Ollama server is alive and has models."""
        now = time.time()
        if hasattr(self, "_last_check_time") and (now - self._last_check_time) < 10.0:
            return bool(getattr(self, "_last_available", False))

        candidate_urls = [self.base_url]
        ollama_cfg_url = getattr(settings.llm, "ollama_base_url", "http://127.0.0.1:11434")
        if ollama_cfg_url not in candidate_urls:
            candidate_urls.append(ollama_cfg_url)
        for fallback in ["http://127.0.0.1:11434", "http://localhost:11434"]:
            if fallback not in candidate_urls:
                candidate_urls.append(fallback)
        if os.path.exists("/.dockerenv") and "http://host.docker.internal:11434" not in candidate_urls:
            candidate_urls.append("http://host.docker.internal:11434")
        probe_timeout = float(getattr(settings.llm, "probe_timeout", 0.15))
        for u in candidate_urls:
            try:
                # Fast TCP pre-flight to avoid HTTP connect timeouts
                parsed = urllib.parse.urlparse(u)
                raw_host = parsed.hostname or "127.0.0.1"
                host = "127.0.0.1" if raw_host in ("localhost", "127.0.0.1") else raw_host
                port = parsed.port or 11434
                with socket.create_connection((host, port), timeout=probe_timeout):
                    pass
            except Exception:
                continue

            try:
                # 1. Probe Ollama native tags endpoint
                req = urllib.request.Request(f"{u.rstrip('/')}/api/tags", headers={"User-Agent": "RAISE-Provider"})
                with urllib.request.urlopen(req, timeout=probe_timeout) as resp:
                    if resp.status == 200:
                        self.base_url = u.rstrip("/")
                        os.environ["OLLAMA_BASE_URL"] = self.base_url
                        data = json.loads(resp.read().decode("utf-8"))
                        model_list = [m.get("name") for m in data.get("models", []) if m.get("name")]
                        if model_list and (not self.model_name or self.model_name == models.OLLAMA_MODEL_NAME):
                            self.model_name = model_list[0]
                        self._last_check_time = now
                        self._last_available = True
                        return True
            except Exception:
                pass
            try:
                # 2. Probe Ollama OpenAI-compatible models endpoint
                req = urllib.request.Request(f"{u.rstrip('/')}/v1/models", headers={"User-Agent": "RAISE-Provider"})
                with urllib.request.urlopen(req, timeout=probe_timeout) as resp:
                    if resp.status == 200:
                        self.base_url = u.rstrip("/")
                        os.environ["OLLAMA_BASE_URL"] = self.base_url
                        data = json.loads(resp.read().decode("utf-8"))
                        model_list = [m.get("id") for m in data.get("data", []) if m.get("id")]
                        if model_list and (not self.model_name or self.model_name == models.OLLAMA_MODEL_NAME):
                            self.model_name = model_list[0]
                        self._last_check_time = now
                        self._last_available = True
                        return True
            except Exception:
                pass
        self._last_check_time = now
        self._last_available = False
        return False

    def health_check(self, timeout: float = 5.0) -> ProviderHealth:
        """Ping local Ollama endpoint."""
        alive = self.is_available()
        return ProviderHealth(
            provider=self.name,
            configured=True,
            credential_valid=True,
            endpoint_reachable=alive,
            model_available=alive,
            functional_test=alive,
            status="READY" if alive else "ENDPOINT_UNREACHABLE",
            cost_mode=self.cost_mode,
        )

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=kwargs.get("timeout", 60.0)) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "")
        except Exception as e:
            logger.warning(f"Ollama completion failed: {e}")
            raise RuntimeError(f"Ollama error: {e}")

    async def complete_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        text = self.complete(prompt, system_prompt, max_tokens, temperature, **kwargs)
        yield text


class FailoverLLMProvider(BaseLLMProvider):
    """
    Circuit-breaking resilient LLM Provider wrapper.
    Chains a primary provider with fallbacks (e.g. Cloud -> Local vLLM/Ollama,
    or Local-First -> Cloud).
    Tracks rate limits (HTTP 429), timeouts, and auth errors with thread-safe
    cooldown to prevent wasting time on dead providers across multi-file runs.
    """

    _cooldowns: Dict[str, float] = {}
    _lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        primary: LLMProvider,
        fallbacks: Optional[List[LLMProvider]] = None,
        cooldown_seconds: Optional[float] = None,
    ):
        self.primary = primary
        self.fallbacks = fallbacks or []
        self.cooldown_seconds = (
            cooldown_seconds
            if cooldown_seconds is not None
            else getattr(settings.llm, "cooldown_seconds", 60.0)
        )
        self.name = getattr(primary, "name", "failover_llm")
        self.cost_mode = getattr(primary, "cost_mode", "HYBRID FAILOVER")

    def _is_cooling_down(self, provider_name: str) -> bool:
        with self._lock:
            until = self._cooldowns.get(provider_name, 0.0)
            return time.time() < until

    def _mark_cooldown(self, provider_name: str, duration: Optional[float] = None) -> None:
        secs = duration if duration is not None else self.cooldown_seconds
        with self._lock:
            self._cooldowns[provider_name] = time.time() + secs
        logger.warning(f"Provider '{provider_name}' entered failover cooldown for {secs:.0f}s.")

    def _is_failover_worthy(self, exc: Exception) -> bool:
        err_msg = str(exc).lower()
        failover_indicators = (
            "429",
            "rate limit",
            "quota",
            "resource exhausted",
            "auth_failed",
            "401",
            "connection refused",
            "actively refused",
            "10061",
            "timed out",
            "timeout",
            "service unavailable",
            "503",
            "502",
        )
        return any(ind in err_msg for ind in failover_indicators)

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> str:
        chain = [self.primary] + self.fallbacks
        last_exc: Optional[Exception] = None

        for idx, provider in enumerate(chain):
            pname = getattr(provider, "name", f"provider_{idx}")
            if self._is_cooling_down(pname):
                logger.info(f"Skipping cooling provider '{pname}' ({idx + 1}/{len(chain)}), cascading to fallback...")
                continue

            try:
                result = provider.complete(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                if result:
                    return result
            except Exception as exc:
                last_exc = exc
                logger.warning(f"Provider '{pname}' completion failed: {exc}")
                if self._is_failover_worthy(exc):
                    self._mark_cooldown(pname)

        if last_exc:
            raise RuntimeError(f"All LLM providers in failover chain exhausted: {last_exc}") from last_exc
        raise RuntimeError("All LLM providers in failover chain are currently in cooldown.")

    async def complete_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        chain = [self.primary] + self.fallbacks
        last_exc: Optional[Exception] = None

        for idx, provider in enumerate(chain):
            pname = getattr(provider, "name", f"provider_{idx}")
            if self._is_cooling_down(pname):
                continue

            yielded_any = False
            try:
                async for chunk in provider.complete_stream(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                ):
                    yielded_any = True
                    yield chunk
                return
            except Exception as exc:
                last_exc = exc
                logger.warning(f"Provider '{pname}' stream failed: {exc}")
                if self._is_failover_worthy(exc):
                    self._mark_cooldown(pname)
                if yielded_any:
                    raise

        if last_exc:
            raise RuntimeError(f"All LLM stream providers exhausted: {last_exc}") from last_exc
        raise RuntimeError("All LLM stream providers currently in cooldown.")

    def health_check(self, timeout: float = 5.0) -> ProviderHealth:
        primary_health = self.primary.health_check(timeout=timeout)
        if primary_health.status == "READY":
            return primary_health
        for fb in self.fallbacks:
            fb_health = fb.health_check(timeout=timeout)
            if fb_health.status == "READY":
                return ProviderHealth(
                    provider=f"{self.primary.name}->{fb.name}",
                    configured=True,
                    credential_valid=True,
                    endpoint_reachable=True,
                    model_available=True,
                    functional_test=True,
                    status="READY",
                    cost_mode=fb.cost_mode,
                )
        return primary_health


def get_llm_provider(config: Optional[LLMConfig] = None, provider_name: Optional[str] = None) -> LLMProvider:
    """
    Factory creating configured LLM provider according to environment settings or explicit name.
    Wraps provider in a circuit-breaking FailoverLLMProvider with local/cloud fallback anchors.
    """
    cfg = config or settings.llm
    backend = (provider_name or os.getenv("LLM_BACKEND") or cfg.backend).lower().strip()
    routing_mode = os.getenv("LLM_ROUTING_MODE", getattr(cfg, "routing_mode", "CLOUD_FIRST")).upper().strip()

    # Determine base primary provider
    primary: LLMProvider
    if backend in ("cloud", "openai", "openai-compatible"):
        primary = CloudOpenAICompatibleProvider(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model_name=cfg.model_name,
        )
    elif backend == "gemini":
        from src.infrastructure.providers.gemini import GeminiProvider
        primary = GeminiProvider()
    elif backend == "groq":
        from src.infrastructure.providers.groq import GroqProvider
        primary = GroqProvider()
    elif backend in ("nvidia", "nvidia-nim", "nim"):
        from src.infrastructure.providers.nvidia import NvidiaNIMProvider
        primary = NvidiaNIMProvider()
    elif backend == "cohere":
        from src.infrastructure.providers.cohere import CohereProvider
        primary = CohereProvider()
    elif backend == "mistral":
        from src.infrastructure.providers.mistral import MistralProvider
        primary = MistralProvider()
    elif backend in ("deepseek", "openrouter", "vercel", "typesafe", "jev"):
        from src.infrastructure.providers.groq import GroqProvider
        primary = GroqProvider()
    elif backend in ("local", "transformers", "gpu", "hf"):
        primary = LocalTransformersProvider(model_name=cfg.model_name)
    elif backend in ("universal", "custom", "together", "fireworks", "perplexity"):
        try:
            from src.infrastructure.providers.universal import UniversalCloudProvider
            primary = UniversalCloudProvider(custom_name=backend)
        except Exception:
            from src.infrastructure.providers.groq import GroqProvider
            primary = GroqProvider()
    elif backend == "ollama":
        primary = LocalOllamaProvider(base_url=cfg.base_url, model_name=cfg.model_name)
    else:
        primary = LocalVLLMProvider(base_url=cfg.base_url, model_name=cfg.model_name)

    if os.getenv("DISABLE_LLM_FAILOVER", "").lower() in ("true", "1", "yes"):
        return primary

    fallbacks: List[LLMProvider] = []
    vllm_fb = LocalVLLMProvider(base_url=cfg.base_url, model_name=cfg.model_name)
    ollama_fb = LocalOllamaProvider(base_url=cfg.base_url, model_name=cfg.model_name)

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()

    if routing_mode == "LOCAL_FIRST":
        if backend not in ("vllm", "ollama", "local"):
            if vllm_fb.is_available():
                fallbacks.append(primary)
                primary = vllm_fb
            elif ollama_fb.is_available():
                fallbacks.append(primary)
                primary = ollama_fb
            else:
                fallbacks.extend([vllm_fb, ollama_fb])
        else:
            if backend == "vllm":
                fallbacks.append(ollama_fb)
            elif backend == "ollama":
                fallbacks.append(vllm_fb)
            if gemini_key:
                from src.infrastructure.providers.gemini import GeminiProvider
                fallbacks.append(GeminiProvider())
            if groq_key:
                from src.infrastructure.providers.groq import GroqProvider
                fallbacks.append(GroqProvider())
    else:
        if backend in ("gemini", "groq", "cohere", "mistral", "nvidia", "cloud", "openai"):
            if backend != "groq" and groq_key:
                from src.infrastructure.providers.groq import GroqProvider
                fallbacks.append(GroqProvider())
            if backend != "gemini" and gemini_key:
                from src.infrastructure.providers.gemini import GeminiProvider
                fallbacks.append(GeminiProvider())
            fallbacks.append(vllm_fb)
            fallbacks.append(ollama_fb)
        else:
            if backend == "vllm":
                fallbacks.append(ollama_fb)
            elif backend == "ollama":
                fallbacks.append(vllm_fb)
            if gemini_key:
                from src.infrastructure.providers.gemini import GeminiProvider
                fallbacks.append(GeminiProvider())
            if groq_key:
                from src.infrastructure.providers.groq import GroqProvider
                fallbacks.append(GroqProvider())

    return FailoverLLMProvider(
        primary=primary,
        fallbacks=fallbacks,
        cooldown_seconds=cfg.cooldown_seconds,
    )
