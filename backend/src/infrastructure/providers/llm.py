"""
RAISE Infrastructure — Unified Multi-Provider LLM Interface
Supports local inference engines (vLLM, Ollama) and cloud-compatible APIs (Gemini, Groq, DeepSeek, NVIDIA NIM, Cohere).
"""

from __future__ import annotations

import os
import json
import logging
import threading
import time
import urllib.request
import urllib.error
from typing import Any, AsyncGenerator, Optional

from src.core.config import settings, LLMConfig
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
        self.model_name = model_name or os.getenv("VLLM_MODEL_NAME", "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4")

    def is_available(self) -> bool:
        """Fast non-blocking check to determine if the local vLLM server is alive across common ports."""
        candidate_urls = [self.base_url]
        for fallback in ["http://localhost:8002/v1", "http://127.0.0.1:8002/v1", "http://localhost:8000/v1", "http://127.0.0.1:8000/v1", "http://localhost:8080/v1"]:
            if fallback not in candidate_urls:
                candidate_urls.append(fallback)
        for u in candidate_urls:
            try:
                req = urllib.request.Request(f"{u}/models", headers={"User-Agent": "RAISE-Provider"})
                with urllib.request.urlopen(req, timeout=0.35) as resp:
                    if resp.status == 200:
                        self.base_url = u
                        try:
                            models_data = json.loads(resp.read().decode("utf-8"))
                            if "data" in models_data and len(models_data["data"]) > 0:
                                discovered_id = models_data["data"][0].get("id")
                                if discovered_id and self.model_name == "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4":
                                    self.model_name = discovered_id
                        except Exception:
                            pass
                        return True
            except Exception:
                pass
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

        # Use responsive timeout for local daemon probe (3.0s default if localhost)
        is_loopback = any(h in self.base_url for h in ("localhost", "127.0.0.1", "0.0.0.0"))
        timeout = kwargs.get("timeout", 3.0 if is_loopback else 30.0)

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

            # Only fallback to in-process Transformers if GPU / CUDA is genuinely active
            try:
                import torch
                if torch.cuda.is_available():
                    logger.info("Attempting in-process GPU fallback via LocalTransformersProvider...")
                    fallback_local = LocalTransformersProvider()
                    return fallback_local.complete(prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature, **kwargs)
                else:
                    raise RuntimeError(f"Local vLLM endpoint is offline and system is running on CPU (no CUDA).")
            except Exception as _fb_err:
                raise RuntimeError(f"Error executing local inference: vLLM ({e}) -> LocalGPU ({_fb_err})")


class LocalTransformersProvider(BaseLLMProvider):
    """
    Direct in-process GPU LLM inference using HuggingFace Transformers on CUDA (RTX 3090, 24GB VRAM).
    Zero external server dependency, runs fully local with torch.float16 / bfloat16.
    """

    name = "local"
    cost_mode = "LOCAL GPU / ZERO BILLING"

    _shared_model = None
    _shared_tokenizer = None
    _loaded_model_name = None
    _lock = threading.Lock()

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("LOCAL_LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")

    def _ensure_loaded(self):
        with self._lock:
            if LocalTransformersProvider._shared_model is not None and LocalTransformersProvider._loaded_model_name == self.model_name:
                return

            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32

            logger.info(f"Loading in-process local LLM '{self.model_name}' on {device} ({dtype})...")
            tok = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            mod = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                dtype=dtype,
                device_map=device,
                trust_remote_code=True,
            )
            mod.eval()
            LocalTransformersProvider._shared_tokenizer = tok
            LocalTransformersProvider._shared_model = mod
            LocalTransformersProvider._loaded_model_name = self.model_name
            logger.info(f"In-process local LLM '{self.model_name}' successfully loaded into VRAM.")

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
        self.model_name = model_name or os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")

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
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

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


def get_llm_provider(config: Optional[LLMConfig] = None, provider_name: Optional[str] = None) -> LLMProvider:
    """
    Factory creating configured LLM provider according to environment settings or explicit name.
    Preserves existing signature and semantics while supporting all new providers.
    """
    cfg = config or settings.llm
    backend = (provider_name or cfg.backend).lower().strip()

    if backend in ("cloud", "openai", "openai-compatible"):
        return CloudOpenAICompatibleProvider(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model_name=cfg.model_name,
        )
    elif backend == "gemini":
        from src.infrastructure.providers.gemini import GeminiProvider
        return GeminiProvider()
    elif backend == "groq":
        from src.infrastructure.providers.groq import GroqProvider
        return GroqProvider()
    elif backend in ("nvidia", "nvidia-nim", "nim"):
        from src.infrastructure.providers.nvidia import NvidiaNIMProvider
        return NvidiaNIMProvider()
    elif backend == "cohere":
        from src.infrastructure.providers.cohere import CohereProvider
        return CohereProvider()
    elif backend == "mistral":
        from src.infrastructure.providers.mistral import MistralProvider
        return MistralProvider()
    elif backend in ("deepseek", "openrouter", "vercel", "typesafe", "jev"):
        # Deprecated / billing restricted -> fall back to primary fast cloud provider
        from src.infrastructure.providers.groq import GroqProvider
        return GroqProvider()
    elif backend in ("local", "transformers", "gpu", "hf"):
        return LocalTransformersProvider(model_name=cfg.model_name)
    elif backend in ("universal", "custom", "together", "fireworks", "perplexity"):
        return UniversalCloudProvider(custom_name=backend)
    elif backend == "ollama":
        return LocalOllamaProvider(base_url=cfg.base_url, model_name=cfg.model_name)
    else:
        # Default local vLLM (falls back to in-process LocalTransformers on GPU if vLLM offline)
        return LocalVLLMProvider(base_url=cfg.base_url, model_name=cfg.model_name)
