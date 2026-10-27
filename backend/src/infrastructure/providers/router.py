"""
RAISE Infrastructure — Unified Provider Router & Task Policies
Manages task-to-provider mappings, bounded exponential backoff retries,
non-secret fallback logging, and execution modes (LOCAL, CLOUD, AUTOMATIC).
"""

from __future__ import annotations

import os
import logging
import threading
import time
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Union

from src.infrastructure.providers.base import (
    LLMProvider,
)
from src.infrastructure.providers.llm import LocalVLLMProvider, LocalTransformersProvider
from src.infrastructure.providers.gemini import GeminiProvider
from src.infrastructure.providers.groq import GroqProvider
from src.infrastructure.providers.mistral import MistralProvider
from src.infrastructure.providers.universal import UniversalCloudProvider
from src.infrastructure.providers.deepseek import DeepSeekProvider
from src.infrastructure.providers.nvidia import NvidiaNIMProvider
from src.infrastructure.providers.cohere import CohereProvider
from src.infrastructure.providers.openrouter import OpenRouterProvider
from src.infrastructure.providers.token_tracker import get_token_tracker

logger = logging.getLogger("raise.infrastructure.providers.router")


class InferenceTask(str, Enum):
    """Standardized task categories supported by the router."""
    CHAT = "CHAT"
    RAG_GENERATION = "RAG_GENERATION"
    DOCUMENT_EXTRACTION = "DOCUMENT_EXTRACTION"
    SUMMARIZATION = "SUMMARIZATION"
    STRUCTURED_EXTRACTION = "STRUCTURED_EXTRACTION"
    REASONING = "REASONING"
    CODE = "CODE"
    QUERY_REWRITE = "QUERY_REWRITE"
    EMBEDDING = "EMBEDDING"
    RERANKING = "RERANKING"


class ExecutionMode(str, Enum):
    """Execution target modes."""
    LOCAL = "LOCAL"
    CLOUD = "CLOUD"
    AUTOMATIC = "AUTOMATIC"


class FallbackEvent:
    """Non-secret record of an automated failover event."""
    def __init__(self, from_provider: str, to_provider: str, task: str, reason: str):
        self.timestamp = time.time()
        self.from_provider = from_provider
        self.to_provider = to_provider
        self.task = task
        self.reason = reason

    def __str__(self) -> str:
        return f"Provider {self.from_provider} unavailable -> switched to {self.to_provider} for {self.task}. Reason: {self.reason}"


class ProviderRouter:
    """
    Central router dispatching inference requests across local vLLM and cloud providers.
    """

    def __init__(
        self,
        mode: Optional[ExecutionMode] = None,
        cloud_allowed: Optional[bool] = None,
    ):
        env_backend = os.getenv("LLM_BACKEND", "").lower().strip()
        env_mode = os.getenv("EXECUTION_MODE", "").upper().strip()

        if mode is not None:
            self.mode = mode
        elif env_mode in ("CLOUD", "LOCAL", "AUTOMATIC"):
            self.mode = ExecutionMode(env_mode)
        elif env_backend in ("groq", "gemini", "deepseek", "nvidia", "cohere", "openrouter"):
            self.mode = ExecutionMode.CLOUD
        else:
            self.mode = ExecutionMode.AUTOMATIC

        self.cloud_allowed = cloud_allowed if cloud_allowed is not None else (self.mode != ExecutionMode.LOCAL)
        self.fallback_history: List[FallbackEvent] = []

        # Instantiate provider registry
        self.providers: Dict[str, LLMProvider] = {
            "vllm": LocalVLLMProvider(),
            "local": LocalTransformersProvider(),
            "gemini": GeminiProvider(),
            "groq": GroqProvider(),
            "mistral": MistralProvider(),
            "nvidia": NvidiaNIMProvider(),
            "cohere": CohereProvider(),
            "deepseek": DeepSeekProvider(),
            "openrouter": OpenRouterProvider(),
            "universal": UniversalCloudProvider(),
        }

        # Active primary provider selection (ignoring billing-restricted providers)
        primary_cloud = env_backend if (env_backend in self.providers and env_backend not in ("deepseek", "openrouter")) else "groq"

        # Task routing policy mapping (Production Defaults for 8 Pipeline Phases)
        # DeepSeek is NOT used as default because it has NO permanent free tier (returns HTTP 402 once trial expires).
        # Cloud defaults route to high-throughput free/developer tiers: Groq, Mistral, NVIDIA NIM, Cohere, Gemini.
        from src.infrastructure.credentials.manager import get_credential_manager
        _cm = get_credential_manager()

        self.task_policy: Dict[InferenceTask, str] = {
            InferenceTask.CHAT: primary_cloud if self.cloud_allowed else "vllm",  # Phase 1: Low-latency chat
            InferenceTask.RAG_GENERATION: primary_cloud if self.cloud_allowed else "vllm",  # Phase 2: RAG Answer Synthesis
            InferenceTask.DOCUMENT_EXTRACTION: "gemini",  # Phase 3: Doc Layout & Vision
            InferenceTask.QUERY_REWRITE: primary_cloud if self.cloud_allowed else "vllm",  # Phase 4: Query Intake & Reformulation
            InferenceTask.REASONING: primary_cloud if self.cloud_allowed else "vllm",  # Phase 5: Multi-Hop Relational Reasoning
            InferenceTask.CODE: "mistral" if _cm.get_credential_status("mistral") == "configured" and self.cloud_allowed else (primary_cloud if self.cloud_allowed else "vllm"),  # Phase 6: Code & Formal Cypher
            InferenceTask.SUMMARIZATION: primary_cloud if self.cloud_allowed else "vllm",  # Phase 7: Community / Executive Summaries
            InferenceTask.RERANKING: "cohere",  # Phase 8: Neural Cross-Attention Reranking
            InferenceTask.STRUCTURED_EXTRACTION: primary_cloud if self.cloud_allowed else "vllm",
            InferenceTask.EMBEDDING: "vllm",  # Local BGE-Large
        }

        # Provider health, cooldown & disabled tracking
        self.provider_cooldowns: Dict[str, float] = {}
        # Disable DeepSeek & OpenRouter permanently if billing restricted (HTTP 402 / $0 balance)
        self.disabled_providers: Set[str] = {"deepseek", "openrouter"}
        self.last_used_provider: str = ""
        self.last_used_model: str = ""

        # Thread-safe round-robin model rotation across all configured models
        self.round_robin_enabled = os.getenv("LLM_ROUND_ROBIN", "false").lower() in ("true", "1", "yes") or env_backend in ("round_robin", "all")
        self._rr_lock = threading.Lock()
        self._round_robin_index = 0

        # Construct dynamic fallback chain based on user-provided keys
        self.fallback_chain: List[str] = []
        self._refresh_fallback_chain(primary_cloud)

    def _refresh_fallback_chain(self, primary_cloud: Optional[str] = None) -> None:
        """
        Dynamically constructs the fallback chain based on user-provided API keys.
        Orders all configured providers so every model gets called sequentially in a line.
        """
        from src.infrastructure.credentials.manager import get_credential_manager
        cm = get_credential_manager()
        prim = primary_cloud or (self.fallback_chain[0] if self.fallback_chain else "groq")

        # Multi-model sequence line: Groq, NVIDIA NIM, Mistral, Cohere, Gemini
        ordered_candidates = ["mistral", "cohere", "nvidia", "gemini", "groq"]
        active = []
        if prim in ("vllm", "local") or self.mode == ExecutionMode.LOCAL:
            active.append("vllm")

        if prim in ordered_candidates and prim not in self.disabled_providers and cm.get_credential_status(prim) == "configured":
            if prim not in active:
                active.append(prim)

        for cand in ordered_candidates:
            if cand in self.disabled_providers:
                continue
            if cm.get_credential_status(cand) == "configured":
                if cand not in active:
                    active.append(cand)

        for paid in ["openrouter", "universal"]:
            if paid not in self.disabled_providers and cm.get_credential_status(paid) == "configured":
                if paid not in active:
                    active.append(paid)

        vllm_alive = False
        try:
            vllm_alive = self.providers["vllm"].is_available()
        except Exception:
            pass

        if "vllm" not in active:
            if (vllm_alive and not any(cm.get_credential_status(k) == "configured" for k in ordered_candidates)) or self.mode in (ExecutionMode.LOCAL, ExecutionMode.AUTOMATIC):
                if vllm_alive:
                    active.insert(0, "vllm")
                else:
                    active.append("vllm")
            else:
                active.append("vllm")

        if "local" not in active:
            active.append("local")

        self.fallback_chain = active
        logger.info(f"Dynamic fallback chain updated: {self.fallback_chain}")

    def get_dynamic_available_providers(self) -> List[Dict[str, Any]]:
        """
        Dynamically returns ONLY the LLMs that are actively usable by the user.
        If a user writes their key, the LLM dynamically appears here.
        Restricted/disabled providers are excluded.
        """
        from src.infrastructure.credentials.manager import get_credential_manager
        cm = get_credential_manager()
        available = []

        cloud_meta = {
            "groq": {"name": "Groq LPU (High-Throughput)", "tier": "Free Tier", "default_model": "qwen/qwen3.8-27b"},
            "mistral": {"name": "Mistral AI", "tier": "Free / Developer Tier", "default_model": "open-mistral-nemo"},
            "nvidia": {"name": "NVIDIA NIM", "tier": "Developer Free Tier (1,000 Credits)", "default_model": "meta/llama-3.2-11b-vision-instruct"},
            "cohere": {"name": "Cohere Command", "tier": "Evaluation Free Tier", "default_model": "command-r-plus-08-2024"},
            "gemini": {"name": "Google Gemini", "tier": "Free Tier (Rate-Limited Quota)", "default_model": "gemini-2.0-flash"},
            "deepseek": {"name": "DeepSeek API", "tier": "Prepaid Only (No Permanent Free Tier)", "default_model": "deepseek-chat"},
            "openrouter": {"name": "OpenRouter Gateway", "tier": "Prepaid Only (Account Credits)", "default_model": "anthropic/claude-3-haiku"},
            "universal": {"name": "Universal Custom Cloud API", "tier": "Custom OpenAI-Compatible", "default_model": "gpt-4o-mini"},
        }

        # Check local GPU providers (In-process Transformers & vLLM)
        if "local" in self.providers and "local" not in self.disabled_providers:
            available.append({
                "provider": "local",
                "display_name": "Local GPU (In-Process PyTorch/CUDA, RTX 3090)",
                "model": getattr(self.providers["local"], "model_name", "Qwen/Qwen2.5-1.5B-Instruct"),
                "status": "READY",
                "is_active": self.mode == ExecutionMode.LOCAL,
                "tier": "Local Zero-Cost (24GB VRAM)",
            })

        if "vllm" in self.providers and "vllm" not in self.disabled_providers:
            vllm_alive = self.providers["vllm"].is_available()
            available.append({
                "provider": "vllm",
                "display_name": "Local vLLM Container (Docker)",
                "model": getattr(self.providers["vllm"], "model_name", "Qwen2.5-14B"),
                "status": "READY" if (vllm_alive or self.mode == ExecutionMode.LOCAL) else "LOCAL_OFFLINE",
                "is_active": vllm_alive or self.mode == ExecutionMode.LOCAL,
                "tier": "Docker Local Inference",
            })

        for p_id, info in cloud_meta.items():
            if p_id in self.disabled_providers:
                continue
            status = cm.get_credential_status(p_id)
            if status == "configured":
                prov_obj = self.providers.get(p_id)
                m_name = getattr(prov_obj, "model_name", info["default_model"]) if prov_obj else info["default_model"]
                available.append({
                    "provider": p_id,
                    "display_name": info["name"],
                    "model": m_name,
                    "status": "READY",
                    "is_active": self.task_policy.get(InferenceTask.RAG_GENERATION) == p_id,
                    "tier": info["tier"],
                })

        return available

    def get_last_completion_info(self) -> Dict[str, Any]:
        """Return the actual provider name and model identifier used for the most recent completion."""
        return {
            "provider": self.last_used_provider or "unknown",
            "model": self.last_used_model or "default",
        }

    def set_task_provider(self, task: Union[InferenceTask, str], provider_name: str) -> None:
        """Assign specific provider to an inference task."""
        t = InferenceTask(task) if isinstance(task, str) else task
        prov = provider_name.lower().strip()
        if prov in self.providers:
            self.task_policy[t] = prov
            logger.info(f"Router policy updated: {t.value} -> {prov}")
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    def set_execution_mode(self, mode: Union[ExecutionMode, str]) -> None:
        """Change global execution target."""
        self.mode = ExecutionMode(mode) if isinstance(mode, str) else mode
        self.cloud_allowed = (self.mode != ExecutionMode.LOCAL)
        logger.info(f"Router execution mode set to: {self.mode.value}")

    def set_cloud_allowed(self, allowed: bool) -> None:
        """Toggle cloud inference permission safeguard."""
        self.cloud_allowed = allowed
        logger.info(f"Cloud inference permission changed: {allowed}")

    def get_provider_for_task(self, task: Union[InferenceTask, str]) -> LLMProvider:
        """Select primary provider according to execution mode, task policy, and live cooldown state."""
        t = InferenceTask(task) if isinstance(task, str) else task

        if self.mode == ExecutionMode.LOCAL:
            return self.providers["vllm"]

        target_name = self.task_policy.get(t, "vllm")

        # If Cloud mode or Automatic mode, check billing guardrail
        if target_name != "vllm" and not self.cloud_allowed and self.mode != ExecutionMode.CLOUD:
            logger.info(f"Cloud inference confirmation required for {target_name}. Defaulting to Local vLLM.")
            return self.providers["vllm"]

        now = time.time()
        from src.infrastructure.credentials.manager import get_credential_manager
        cm = get_credential_manager()

        # Multi-model Round-Robin rotation across every configured model in a line
        healthy_chain = []
        for cand in self.fallback_chain:
            if cand in self.disabled_providers or self.provider_cooldowns.get(cand, 0) > now or cand not in self.providers:
                continue
            is_local = cand in ("vllm", "local")
            if is_local:
                if self.mode == ExecutionMode.CLOUD:
                    continue
                if not getattr(self.providers[cand], "is_available", lambda: True)():
                    continue
                healthy_chain.append(cand)
            else:
                if self.mode == ExecutionMode.LOCAL:
                    continue
                if not self.cloud_allowed:
                    continue
                if cm.get_credential_status(cand) == "configured":
                    healthy_chain.append(cand)

        if self.round_robin_enabled and healthy_chain and t in (InferenceTask.RAG_GENERATION, InferenceTask.CHAT):
            with self._rr_lock:
                target_name = healthy_chain[self._round_robin_index % len(healthy_chain)]
                self._round_robin_index = (self._round_robin_index + 1) % len(healthy_chain)
                return self.providers[target_name]

        # If target cloud provider has no credentials configured, route to first configured cloud provider or vLLM
        if target_name not in ("vllm", "local") and cm.get_credential_status(target_name) != "configured":
            for cand in self.fallback_chain:
                if cand not in self.disabled_providers and self.provider_cooldowns.get(cand, 0) <= now:
                    if cand in ("vllm", "local"):
                        if self.mode != ExecutionMode.CLOUD and cand in self.providers and getattr(self.providers[cand], "is_available", lambda: True)():
                            target_name = cand
                            break
                    elif cm.get_credential_status(cand) == "configured" and self.mode != ExecutionMode.LOCAL and self.cloud_allowed:
                        target_name = cand
                        break
            else:
                if self.mode != ExecutionMode.CLOUD and getattr(self.providers["vllm"], "is_available", lambda: True)():
                    target_name = "vllm"

        # Check if preferred provider is on rate-limit cooldown or disabled; if so, pick next healthy fallback
        if target_name in self.disabled_providers or self.provider_cooldowns.get(target_name, 0) > now:
            for cand in self.fallback_chain:
                if cand != target_name and cand not in self.disabled_providers and self.provider_cooldowns.get(cand, 0) <= now and cand in self.providers:
                    if cand in ("vllm", "local"):
                        if self.mode == ExecutionMode.CLOUD or not getattr(self.providers[cand], "is_available", lambda: True)():
                            continue
                    else:
                        if self.mode == ExecutionMode.LOCAL or not self.cloud_allowed or cm.get_credential_status(cand) != "configured":
                            continue
                    logger.info(f"Provider '{target_name}' unavailable (cooldown/disabled). Routing {t.value} to '{cand}'.")
                    target_name = cand
                    break

        return self.providers.get(target_name, self.providers["vllm"])

    def complete(
        self,
        prompt: str,
        task: Union[InferenceTask, str] = InferenceTask.RAG_GENERATION,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> str:
        """
        Execute completion with bounded retry and automated non-secret fallback.
        """
        t = InferenceTask(task) if isinstance(task, str) else task
        primary_provider = self.get_provider_for_task(t)
        logger.info(f"[INFERENCE] Executing task '{t.value}' via Provider: '{primary_provider.name}'")

        try:
            result = primary_provider.complete(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
            if not result or any(result.startswith(pfx) for pfx in ("Error executing inference", "Cloud LLM error", "Ollama error", "Inference execution error")):
                raise RuntimeError(result or "Empty response from primary provider")

            # Track successful provider & model metadata
            self.last_used_provider = primary_provider.name
            self.last_used_model = getattr(primary_provider, "model_name", "default")

            # Record token usage per LLM
            get_token_tracker().record_inference(
                provider=primary_provider.name,
                prompt_text=f"{system_prompt or ''}\n{prompt}",
                completion_text=result,
                model=getattr(primary_provider, "model_name", None),
            )
            return result
        except Exception as primary_err:
            err_msg = str(primary_err)
            logger.warning(f"Primary provider '{primary_provider.name}' failed for {t.value}: {err_msg}")

            # Apply rate-limit cooldown if 429 encountered
            if "429" in err_msg or "RATE_LIMITED" in err_msg or "quota" in err_msg.lower():
                cooldown_secs = 15.0 if primary_provider.name == "groq" else 60.0
                self.provider_cooldowns[primary_provider.name] = time.time() + cooldown_secs
                logger.info(f"Activated {int(cooldown_secs)}s cooldown for provider '{primary_provider.name}'.")
            elif "401" in err_msg or "AUTH_FAILED" in err_msg or "invalid_api_key" in err_msg.lower() or "402" in err_msg or "BILLING_RESTRICTED" in err_msg or "credit card" in err_msg.lower() or "403" in err_msg:
                self.disabled_providers.add(primary_provider.name)
                logger.warning(f"Permanently disabled billing-restricted provider '{primary_provider.name}'.")

            # Try each provider in the fallback chain
            errors = [f"{primary_provider.name}: {err_msg}"]
            now = time.time()
            from src.infrastructure.credentials.manager import get_credential_manager
            cm = get_credential_manager()
            for candidate_name in self.fallback_chain:
                if candidate_name == primary_provider.name or candidate_name in self.disabled_providers:
                    continue
                if candidate_name in ("vllm", "local"):
                    if self.mode == ExecutionMode.CLOUD:
                        continue
                    if not getattr(self.providers[candidate_name], "is_available", lambda: True)():
                        continue
                else:
                    if self.mode == ExecutionMode.LOCAL:
                        continue
                    if not self.cloud_allowed:
                        continue
                    if cm.get_credential_status(candidate_name) != "configured":
                        continue
                # Skip candidates actively on cooldown
                if self.provider_cooldowns.get(candidate_name, 0) > now:
                    continue
                candidate_prov = self.providers.get(candidate_name)
                if not candidate_prov:
                    continue

                fb_event = FallbackEvent(
                    from_provider=primary_provider.name,
                    to_provider=candidate_name,
                    task=t.value,
                    reason=err_msg,
                )
                self.fallback_history.append(fb_event)
                logger.info(str(fb_event))

                try:
                    res = candidate_prov.complete(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        **kwargs,
                    )
                    if not res or any(res.startswith(pfx) for pfx in ("Error executing inference", "Cloud LLM error", "Ollama error", "Inference execution error")):
                        raise RuntimeError(res or f"Empty response from {candidate_name}")

                    # Track successful fallback provider & model metadata
                    self.last_used_provider = candidate_prov.name
                    self.last_used_model = getattr(candidate_prov, "model_name", "default")

                    get_token_tracker().record_inference(
                        provider=candidate_prov.name,
                        prompt_text=f"{system_prompt or ''}\n{prompt}",
                        completion_text=res,
                        model=getattr(candidate_prov, "model_name", None),
                    )
                    return res
                except Exception as fb_err:
                    fb_str = str(fb_err)
                    if "429" in fb_str or "RATE_LIMITED" in fb_str or "quota" in fb_str.lower():
                        self.provider_cooldowns[candidate_name] = time.time() + 60.0
                    elif "402" in fb_str or "BILLING_RESTRICTED" in fb_str or "credit card" in fb_str.lower() or ("403" in fb_str and candidate_name in ("deepseek", "openrouter")):
                        self.disabled_providers.add(candidate_name)
                        logger.warning(f"Permanently disabled billing-restricted fallback '{candidate_name}'.")
                    errors.append(f"{candidate_name}: {fb_err}")
                    logger.warning(f"Fallback candidate '{candidate_name}' failed: {fb_err}")

            all_errs = "; ".join(errors)
            if "not configured" in all_errs and ("offline" in all_errs or "refused" in all_errs or "10061" in all_errs or "CUDA is unavailable" in all_errs):
                return (
                    "Inference execution error: No functional LLM provider available. "
                    "Please configure an API key (Groq, Gemini, NVIDIA, Mistral) in Settings or start a local Ollama/vLLM instance."
                )
            return f"Inference execution error: All providers in fallback chain failed: {all_errs}"

    async def complete_stream(
        self,
        prompt: str,
        task: Union[InferenceTask, str] = InferenceTask.CHAT,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Execute streaming completion."""
        t = InferenceTask(task) if isinstance(task, str) else task
        primary_provider = self.get_provider_for_task(t)

        try:
            async for chunk in primary_provider.complete_stream(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            ):
                yield chunk
        except Exception as e:
            logger.warning(f"Streaming error on provider '{primary_provider.name}': {e}. Falling back to sync completion.")
            fallback_text = self.complete(prompt, task=t, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature, **kwargs)
            yield fallback_text


# Global Singleton Router
_router_instance: Optional[ProviderRouter] = None


def get_provider_router() -> ProviderRouter:
    """Return singleton ProviderRouter instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ProviderRouter()
    return _router_instance
