"""
RAISE Infrastructure — Unified Provider Router & Task Policies
Manages task-to-provider mappings, bounded exponential backoff retries,
non-secret fallback logging, and execution modes (LOCAL, CLOUD, AUTOMATIC).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import threading
import time
import urllib.parse
import urllib.request
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Union

from src.infrastructure.providers.base import (
    LLMProvider,
)
from src.infrastructure.providers.llm import LocalVLLMProvider, LocalTransformersProvider, LocalOllamaProvider
from src.infrastructure.providers.gemini import GeminiProvider
from src.infrastructure.providers.groq import GroqProvider
from src.infrastructure.providers.mistral import MistralProvider
from src.infrastructure.providers.universal import UniversalCloudProvider
from src.infrastructure.providers.deepseek import DeepSeekProvider
from src.infrastructure.providers.nvidia import NvidiaNIMProvider
from src.infrastructure.providers.cohere import CohereProvider
from src.infrastructure.providers.openrouter import OpenRouterProvider
from src.infrastructure.providers.token_tracker import get_token_tracker
from src.infrastructure.credentials.manager import get_credential_manager
from src.core.config import models

logger = logging.getLogger("raise.infrastructure.providers.router")


class ProviderExhaustedError(RuntimeError):
    """Raised when all inference providers in the active fallback chain fail."""
    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.errors = errors or []


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
        env_backend = (
            os.getenv("LLM_BACKEND", "")
            or os.getenv("RAISE_LLM_PROVIDER", "")
            or os.getenv("LLM_PROVIDER", "")
        ).lower().strip()
        env_mode = os.getenv("EXECUTION_MODE", "").upper().strip()

        if mode is not None:
            self.mode = mode
        elif env_mode in ("CLOUD", "LOCAL", "AUTOMATIC"):
            self.mode = ExecutionMode(env_mode)
        elif env_backend in ("vllm", "ollama", "local") and os.getenv("EXECUTION_MODE", "").upper() == "LOCAL":
            self.mode = ExecutionMode.LOCAL
        else:
            self.mode = ExecutionMode.AUTOMATIC

        self.cloud_allowed = cloud_allowed if cloud_allowed is not None else (self.mode != ExecutionMode.LOCAL)
        self.local_allowed = os.getenv("EXECUTION_MODE", "").upper() != "CLOUD_ONLY"
        self.fallback_history: List[FallbackEvent] = []

        # Instantiate provider registry (Requirement 3: LocalOllamaProvider registered)
        self.providers: Dict[str, LLMProvider] = {
            "vllm": LocalVLLMProvider(),
            "local": LocalTransformersProvider(),
            "ollama": LocalOllamaProvider(),
            "gemini": GeminiProvider(),
            "groq": GroqProvider(),
            "mistral": MistralProvider(),
            "nvidia": NvidiaNIMProvider(),
            "cohere": CohereProvider(),
            "deepseek": DeepSeekProvider(),
            "openrouter": OpenRouterProvider(),
            "universal": UniversalCloudProvider(),
        }

        # Active primary provider selection (Requirement 1: No hardcoded blacklists)
        _cm = get_credential_manager()
        configured_clouds = [cand for cand in ["groq", "gemini", "mistral", "nvidia", "cohere", "deepseek", "openrouter", "universal"] if _cm.get_credential_status(cand) == "configured"]

        if env_backend in self.providers and (
            env_backend in ("vllm", "ollama", "local")
            or _cm.get_credential_status(env_backend) == "configured"
            or not configured_clouds
        ):
            primary_cloud = env_backend
        elif configured_clouds:
            primary_cloud = configured_clouds[0]
        else:
            primary_cloud = "gemini" if "gemini" in self.providers else "groq"

        # Probe local engines (vLLM and Ollama)
        vllm_alive = False
        try:
            vllm_alive = self.providers["vllm"].is_available()
        except Exception:
            pass

        ollama_alive = False
        try:
            ollama_alive = self.providers["ollama"].is_available()
        except Exception:
            pass

        local_target = "vllm" if vllm_alive else ("ollama" if ollama_alive else ("vllm" if "vllm" in self.providers else "local"))

        routing_policy = os.getenv("ROUTING_POLICY", os.getenv("ROUTING_PREFERENCE", os.getenv("LLM_ROUTING_MODE", ""))).upper().strip()
        user_chose_local = (
            (routing_policy == "LOCAL_FIRST")
            or (self.mode == ExecutionMode.LOCAL)
            or (env_backend in ("vllm", "ollama", "local"))
        )
        local_first = user_chose_local

        if user_chose_local and (vllm_alive or ollama_alive):
            default_target = local_target
        elif configured_clouds and self.cloud_allowed and self.mode != ExecutionMode.LOCAL:
            default_target = primary_cloud
        else:
            default_target = local_target if (vllm_alive or ollama_alive) else primary_cloud

        self.task_policy: Dict[InferenceTask, str] = {
            InferenceTask.CHAT: os.getenv("TASK_POLICY_CHAT", default_target),
            InferenceTask.RAG_GENERATION: os.getenv("TASK_POLICY_RAG_GENERATION", default_target),
            InferenceTask.DOCUMENT_EXTRACTION: os.getenv(
                "TASK_POLICY_DOCUMENT_EXTRACTION",
                "gemini" if (self.cloud_allowed and self.mode != ExecutionMode.LOCAL and not local_first) else local_target
            ),
            InferenceTask.QUERY_REWRITE: os.getenv("TASK_POLICY_QUERY_REWRITE", default_target),
            InferenceTask.REASONING: os.getenv("TASK_POLICY_REASONING", default_target),
            InferenceTask.CODE: os.getenv(
                "TASK_POLICY_CODE",
                "mistral" if (_cm.get_credential_status("mistral") == "configured" and self.cloud_allowed and self.mode != ExecutionMode.LOCAL and not local_first) else default_target
            ),
            InferenceTask.SUMMARIZATION: os.getenv("TASK_POLICY_SUMMARIZATION", default_target),
            InferenceTask.RERANKING: os.getenv(
                "TASK_POLICY_RERANKING",
                "cohere" if (self.cloud_allowed and self.mode != ExecutionMode.LOCAL and not local_first) else local_target
            ),
            InferenceTask.STRUCTURED_EXTRACTION: os.getenv("TASK_POLICY_STRUCTURED_EXTRACTION", default_target),
            InferenceTask.EMBEDDING: os.getenv("TASK_POLICY_EMBEDDING", local_target),
        }

        # Provider health, cooldown & disabled tracking (Requirement 1: clean empty set at init)
        self.provider_cooldowns: Dict[str, float] = {}
        self.disabled_providers: Set[str] = set()
        self.pinned_primary_provider: Optional[str] = (
            os.getenv("PINNED_PRIMARY_PROVIDER", "").strip().lower() or None
        )
        self.last_used_provider: str = ""
        self.last_used_model: str = ""

        # Thread-safe round-robin model rotation across all configured models
        self.round_robin_enabled = os.getenv("LLM_ROUND_ROBIN", "false").lower() in ("true", "1", "yes") or env_backend in ("round_robin", "all")
        self._rr_lock = threading.Lock()
        self._round_robin_index = 0

        # Construct dynamic fallback chain based on active engines and user keys
        self.fallback_chain: List[str] = []
        self._refresh_fallback_chain(default_target)

    def _refresh_fallback_chain(self, primary_cloud: Optional[str] = None) -> None:
        """
        Dynamically constructs the fallback chain based on active local engines and user-provided API keys.
        - Prioritizes local GPU engine (vLLM on :8002) when alive to minimize latency, eliminate cloud quota exhaustion, and run locally.
        - Only includes cloud providers whose genuine keys are present and configured (cm.get_credential_status(cand) == 'configured').
        - Excludes dead/offline local engines (e.g. offline ollama) and avoids slow CPU 'local' unless strictly needed.
        """
        cm = get_credential_manager()

        # 1. Probe local engines
        vllm_alive = False
        if "vllm" in self.providers and "vllm" not in self.disabled_providers:
            try:
                vllm_alive = self.providers["vllm"].is_available()
            except Exception:
                vllm_alive = False

        ollama_alive = False
        if "ollama" in self.providers and "ollama" not in self.disabled_providers:
            try:
                ollama_alive = self.providers["ollama"].is_available()
            except Exception:
                ollama_alive = False

        alive_local = []
        if vllm_alive:
            alive_local.append("vllm")
        if ollama_alive:
            alive_local.append("ollama")

        # 2. Collect verified configured cloud candidates in priority sequence
        ordered_candidates = ["groq", "gemini", "nvidia", "mistral", "cohere", "deepseek", "openrouter", "universal"]
        configured_clouds = []
        for cand in ordered_candidates:
            if cand in self.disabled_providers:
                continue
            if cm.get_credential_status(cand) == "configured":
                configured_clouds.append(cand)

        # 3. Determine ordering preference: default to cloud-first unless user specifically chose local engines
        # or if zero cloud API keys exist. This prevents heavy GPU/RAM overload on low-spec hardware.
        routing_policy = os.getenv("ROUTING_POLICY", os.getenv("ROUTING_PREFERENCE", os.getenv("LLM_ROUTING_MODE", ""))).upper().strip()
        user_chose_local = (
            (routing_policy == "LOCAL_FIRST")
            or (self.mode == ExecutionMode.LOCAL)
            or (os.getenv("LLM_BACKEND", "").lower().strip() in ("vllm", "ollama", "local"))
        )
        prefer_local = user_chose_local or (not configured_clouds and len(alive_local) > 0)

        # Check for user-defined explicit fallback sequence from .env or UI orchestrator
        env_order_str = os.getenv("LLM_FALLBACK_ORDER", "").strip()
        user_order = [p.strip().lower() for p in env_order_str.split(",") if p.strip()] if env_order_str else []

        active = []
        if user_order:
            for p in user_order:
                if p in self.disabled_providers:
                    continue
                if p == "vllm" and vllm_alive and "vllm" not in active:
                    active.append("vllm")
                elif p == "ollama" and ollama_alive and "ollama" not in active:
                    active.append("ollama")
                elif p in configured_clouds and p not in active:
                    active.append(p)
                elif p == "local" and "local" in self.providers and "local" not in active:
                    active.append("local")
            # Append any remaining alive local or configured cloud engines not mentioned in user_order
            remaining_pool = (alive_local + configured_clouds) if prefer_local else (configured_clouds + alive_local)
            for rem in remaining_pool:
                if rem not in active and rem not in self.disabled_providers:
                    active.append(rem)
        elif prefer_local:
            # Local first: vllm (and/or ollama if running)
            for eng in alive_local:
                if eng not in active:
                    active.append(eng)
            # Then verified configured cloud providers
            for cand in configured_clouds:
                if cand not in active:
                    active.append(cand)
        else:
            # Cloud first: configured cloud providers
            for cand in configured_clouds:
                if cand not in active:
                    active.append(cand)
            # Then local engines
            for eng in alive_local:
                if eng not in active:
                    active.append(eng)

        # 4. If user explicitly pinned a primary provider, lock and preserve it as #1
        pinned = getattr(self, "pinned_primary_provider", None) or os.getenv("PINNED_PRIMARY_PROVIDER", "").strip().lower()
        if pinned and pinned in self.providers and pinned not in self.disabled_providers:
            prim = pinned
        else:
            prim = primary_cloud or (self.fallback_chain[0] if self.fallback_chain else None)

        if prim and prim in self.providers and prim not in self.disabled_providers:
            if prim in ("vllm", "ollama") and prim not in alive_local:
                pass  # Do not promote dead local engine to primary
            else:
                if prim in active:
                    active.remove(prim)
                active.insert(0, prim)

        # 5. Fallback safeguard: ensure active is never empty
        if not active:
            if alive_local:
                active.extend(alive_local)
            elif configured_clouds:
                active.extend(configured_clouds)
            elif "local" in self.providers and "local" not in self.disabled_providers:
                active.append("local")

        self.fallback_chain = active
        logger.info(f"Dynamic fallback chain updated: {self.fallback_chain}")

    def _get_cloud_meta(self) -> Dict[str, Dict[str, str]]:
        """
        Externalized cloud provider metadata and dynamically resolved default models.
        (Requirement 2: Model defaults read from env vars or instantiated provider objects)
        """
        groq_model = os.getenv("GROQ_MODEL_NAME") or getattr(self.providers.get("groq"), "model_name", None) or models.GROQ_MODEL_NAME
        gemini_model = os.getenv("GEMINI_MODEL_NAME") or getattr(self.providers.get("gemini"), "model_name", None) or models.GEMINI_MODEL_NAME
        mistral_model = os.getenv("MISTRAL_MODEL_NAME") or getattr(self.providers.get("mistral"), "model_name", None) or models.MISTRAL_MODEL_NAME
        nvidia_model = os.getenv("NVIDIA_MODEL_NAME") or getattr(self.providers.get("nvidia"), "model_name", None) or models.NVIDIA_MODEL_NAME
        cohere_model = os.getenv("COHERE_MODEL_NAME") or getattr(self.providers.get("cohere"), "model_name", None) or models.COHERE_MODEL_NAME
        deepseek_model = os.getenv("DEEPSEEK_MODEL_NAME") or getattr(self.providers.get("deepseek"), "model_name", None) or models.DEEPSEEK_MODEL_NAME
        openrouter_model = os.getenv("OPENROUTER_MODEL_NAME") or getattr(self.providers.get("openrouter"), "model_name", None) or models.OPENROUTER_MODEL_NAME
        universal_model = os.getenv("UNIVERSAL_MODEL_NAME") or getattr(self.providers.get("universal"), "model_name", None) or models.OPENAI_MODEL_NAME

        return {
            "groq": {"name": "Groq LPU (High-Throughput)", "tier": "Free Tier", "default_model": groq_model},
            "gemini": {"name": "Google Gemini", "tier": "Free Tier (Rate-Limited Quota)", "default_model": gemini_model},
            "mistral": {"name": "Mistral AI", "tier": "Free / Developer Tier", "default_model": mistral_model},
            "nvidia": {"name": "NVIDIA NIM", "tier": "Developer Free Tier (1,000 Credits)", "default_model": nvidia_model},
            "cohere": {"name": "Cohere Command", "tier": "Evaluation Free Tier", "default_model": cohere_model},
            "deepseek": {"name": "DeepSeek API", "tier": "Pay-As-You-Go / API Credits", "default_model": deepseek_model},
            "openrouter": {"name": "OpenRouter Gateway", "tier": "Universal Gateway / Credits", "default_model": openrouter_model},
            "universal": {"name": "Universal Custom Cloud API", "tier": "Custom OpenAI-Compatible", "default_model": universal_model},
        }

    def get_dynamic_available_providers(self) -> List[Dict[str, Any]]:
        """
        Dynamically returns ONLY the LLMs that are actively usable by the user.
        If a user writes their key, the LLM dynamically appears here.
        Restricted/disabled providers are excluded.
        """
        cm = get_credential_manager()
        available = []

        cloud_meta = self._get_cloud_meta()

        # Check local GPU / accelerator / container providers
        from src.infrastructure.hardware import get_gpu_info
        gpu_info = get_gpu_info()
        device_label = "CPU Only"
        tier_label = "Host System Memory"

        if gpu_info.get("mps_available"):
            device_label = "Apple Silicon Metal (MPS)"
            tier_label = "Unified Memory (Zero-Cost)"
        elif gpu_info.get("cuda_available") and gpu_info.get("devices"):
            primary_gpu = gpu_info["devices"][0]
            device_label = f"NVIDIA GPU ({primary_gpu.get('name')})"
            tier_label = f"{primary_gpu.get('total_vram_gb', 0)}GB VRAM"

        # 1. In-process PyTorch Local Model
        if "local" in self.providers and "local" not in self.disabled_providers:
            model_name = getattr(self.providers["local"], "model_name", None) or os.getenv("LLM_MODEL_NAME", models.LLM_MODEL_NAME)
            is_ready = bool(getattr(self.providers["local"], "pipeline", None) is not None)
            available.append({
                "provider": "local",
                "display_name": f"Local Accelerator ({device_label})",
                "model": model_name,
                "status": "READY" if is_ready else "LOCAL_OFFLINE",
                "is_active": self.mode == ExecutionMode.LOCAL and is_ready,
                "tier": tier_label,
            })

        # 2. Probe Ollama dynamically from OLLAMA_BASE_URL (Requirement 3: Config-driven)
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        try:
            req = urllib.request.Request(f"{ollama_base}/api/tags", headers={"User-Agent": "RAISE"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    models = data.get("models", [])
                    for m in models:
                        m_name = m.get("name")
                        available.append({
                            "provider": "ollama",
                            "display_name": f"Ollama ({device_label})",
                            "model": m_name,
                            "status": "READY",
                            "is_active": self.mode == ExecutionMode.LOCAL or self.task_policy.get(InferenceTask.RAG_GENERATION) == "ollama",
                            "tier": "Ollama Local Engine",
                        })
        except Exception:
            pass

        # 3. Probe vLLM Container dynamically from VLLM_BASE_URL (Requirement 3: Dynamic host/port parsing)
        vllm_base = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
        vllm_parsed = urllib.parse.urlparse(vllm_base)
        vllm_host = vllm_parsed.hostname or "127.0.0.1"
        vllm_port = vllm_parsed.port or (443 if vllm_parsed.scheme == "https" else 8002)

        vllm_alive = False
        # Prevent self-loop if vllm_port is 8000 (FastAPI server port)
        if vllm_port != 8000:
            try:
                models_endpoint = f"{vllm_base}/models" if vllm_base.endswith("/v1") else f"{vllm_base}/v1/models"
                req = urllib.request.Request(models_endpoint, headers={"User-Agent": "RAISE"})
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    if resp.status == 200:
                        vllm_alive = True
            except Exception:
                try:
                    with socket.create_connection((vllm_host, vllm_port), timeout=0.3):
                        vllm_alive = True
                except Exception:
                    pass

        if vllm_alive or ("vllm" in self.providers and "vllm" not in self.disabled_providers and self.providers["vllm"].is_available()):
            available.append({
                "provider": "vllm",
                "display_name": f"Local vLLM Container ({device_label})",
                "model": getattr(self.providers.get("vllm"), "model_name", None) or os.getenv("VLLM_MODEL_NAME", models.LLM_MODEL_NAME),
                "status": "READY",
                "is_active": self.mode == ExecutionMode.LOCAL or vllm_alive,
                "tier": "Docker Local Inference",
            })
        elif "vllm" in self.providers and "vllm" not in self.disabled_providers:
            available.append({
                "provider": "vllm",
                "display_name": f"Local vLLM Container ({device_label})",
                "model": getattr(self.providers.get("vllm"), "model_name", None) or os.getenv("VLLM_MODEL_NAME", models.LLM_MODEL_NAME),
                "status": "LOCAL_OFFLINE",
                "is_active": False,
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
        self.local_allowed = os.getenv("EXECUTION_MODE", "").upper() != "CLOUD_ONLY"
        logger.info(f"Router execution mode set to: {self.mode.value}")

    def set_cloud_allowed(self, allowed: bool) -> None:
        """Toggle cloud inference permission safeguard."""
        self.cloud_allowed = allowed
        logger.info(f"Cloud inference permission changed: {allowed}")

    def set_local_allowed(self, allowed: bool) -> None:
        """Toggle local inference permission safeguard."""
        self.local_allowed = allowed
        logger.info(f"Local inference permission changed: {allowed}")

    def get_routing_status(self) -> Dict[str, Any]:
        """Returns full routing policy, ordered fallback chain, disabled list, and provider states."""
        cm = get_credential_manager()
        primary = self.task_policy.get(InferenceTask.RAG_GENERATION, self.fallback_chain[0] if self.fallback_chain else "vllm")
        providers_info = []

        all_known = ["vllm", "gemini", "groq", "ollama", "local", "nvidia", "mistral", "cohere", "deepseek", "openrouter"]
        for p_id in all_known:
            if p_id not in self.providers:
                continue
            prov_obj = self.providers[p_id]
            is_disabled = p_id in self.disabled_providers
            is_active = (p_id == primary)
            order_index = self.fallback_chain.index(p_id) + 1 if p_id in self.fallback_chain else 999

            if p_id == "vllm":
                is_avail = False
                try:
                    is_avail = prov_obj.is_available()
                except Exception:
                    pass
                status = "READY" if is_avail else "OFFLINE"
                display_name = "Local vLLM Container (GPU)"
                tier = "Local High-Throughput (Zero API Cost)"
            elif p_id == "ollama":
                is_avail = False
                try:
                    is_avail = prov_obj.is_available()
                except Exception:
                    pass
                status = "READY" if is_avail else "OFFLINE"
                display_name = "Local Ollama Engine"
                tier = "Local On-Device"
            elif p_id == "local":
                is_ready = bool(getattr(prov_obj, "pipeline", None) is not None)
                status = "READY" if is_ready else "STANDBY"
                display_name = "Local PyTorch Transformers"
                tier = "In-Process GPU/CPU"
            else:
                cred_status = cm.get_credential_status(p_id)
                status = "CONFIGURED" if cred_status == "configured" else "NOT_CONFIGURED"
                cloud_meta = self._get_cloud_meta().get(p_id, {})
                display_name = cloud_meta.get("name", p_id.capitalize())
                tier = cloud_meta.get("tier", "Cloud API")

            providers_info.append({
                "id": p_id,
                "displayName": display_name,
                "model": getattr(prov_obj, "model_name", "default"),
                "status": status,
                "isActive": is_active,
                "isDisabled": is_disabled,
                "order": order_index,
                "tier": tier,
                "isLocal": p_id in ("vllm", "ollama", "local"),
            })

        providers_info.sort(key=lambda x: (x["isDisabled"], x["order"]))

        providers_dict = {}
        for p in providers_info:
            pid = p["id"]
            providers_dict[pid] = {
                "configured": p["status"] in ("READY", "CONFIGURED"),
                "model": p["model"],
                "status": p["status"],
                "tier": p["tier"],
                "cooldown_until": self.provider_cooldowns.get(pid),
                "cooldown_reason": "Rate limit (429) hit" if self.provider_cooldowns.get(pid, 0) > time.time() else ("Disabled by user" if pid in self.disabled_providers else None),
                "is_primary": p["isActive"],
                "is_disabled": p["isDisabled"],
                "is_in_fallback_chain": not p["isDisabled"] and pid in self.fallback_chain,
                "order_rank": p["order"],
            }

        return {
            "status": "success",
            "message": "Dynamic routing status loaded.",
            "primary_provider": primary,
            "pinned_primary_provider": getattr(self, "pinned_primary_provider", None),
            "fallback_order": self.fallback_chain,
            "fallback_chain": self.fallback_chain,
            "disabled_providers": list(self.disabled_providers),
            "routing_policy": os.getenv("ROUTING_POLICY", "LOCAL_FIRST" if self.mode == ExecutionMode.LOCAL else "CLOUD_FIRST"),
            "execution_mode": self.mode.value,
            "providers": providers_dict,
            "providers_list": providers_info,
        }

    def set_routing(
        self,
        fallback_order: Optional[List[str]] = None,
        disabled_providers: Optional[List[str]] = None,
        primary_provider: Optional[str] = None,
        routing_policy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Applies dynamic user ordering and disabling to the provider router."""
        if disabled_providers is not None:
            self.disabled_providers = {p.lower().strip() for p in disabled_providers if p}

        clean_order = []
        if fallback_order is not None:
            for p in fallback_order:
                cp = p.lower().strip()
                if cp in self.providers and cp not in self.disabled_providers and cp not in clean_order:
                    clean_order.append(cp)
            if clean_order:
                self.fallback_chain = clean_order

        if primary_provider is not None:
            prim = primary_provider.lower().strip()
            if prim in self.providers:
                self.pinned_primary_provider = prim
                os.environ["PINNED_PRIMARY_PROVIDER"] = prim
                for t in InferenceTask:
                    self.task_policy[t] = prim
                if prim in self.disabled_providers:
                    self.disabled_providers.remove(prim)
                if prim in self.fallback_chain:
                    self.fallback_chain.remove(prim)
                self.fallback_chain.insert(0, prim)
        elif clean_order:
            self.pinned_primary_provider = clean_order[0]
            os.environ["PINNED_PRIMARY_PROVIDER"] = clean_order[0]
            for t in InferenceTask:
                self.task_policy[t] = clean_order[0]

        if routing_policy:
            rp = routing_policy.upper().strip()
            os.environ["ROUTING_POLICY"] = rp
            if rp == "LOCAL_FIRST":
                self.mode = ExecutionMode.LOCAL
                self.cloud_allowed = True
            elif rp == "CLOUD_FIRST":
                self.mode = ExecutionMode.CLOUD
                self.cloud_allowed = True

        logger.info(
            f"Router dynamic update applied. Primary: {self.task_policy.get(InferenceTask.RAG_GENERATION)}, "
            f"Fallback: {self.fallback_chain}, Disabled: {self.disabled_providers}"
        )
        return self.get_routing_status()

    def get_provider_for_task(self, task: Union[InferenceTask, str]) -> LLMProvider:
        """Select primary provider according to execution mode, task policy, and live cooldown state."""
        t = InferenceTask(task) if isinstance(task, str) else task

        fallback_vllm = self.providers.get("vllm") or (next(iter(self.providers.values())) if self.providers else None)
        if self.mode == ExecutionMode.LOCAL:
            return fallback_vllm

        target_name = self.task_policy.get(t, "vllm")

        # If Cloud mode or Automatic mode, check billing guardrail
        if target_name != "vllm" and not self.cloud_allowed and self.mode != ExecutionMode.CLOUD:
            logger.info(f"Cloud inference confirmation required for {target_name}. Defaulting to Local vLLM.")
            return fallback_vllm

        now = time.time()
        cm = get_credential_manager()

        # Multi-model Round-Robin rotation across every configured model in a line
        healthy_chain = []
        for cand in self.fallback_chain:
            if cand in self.disabled_providers or self.provider_cooldowns.get(cand, 0) > now or cand not in self.providers:
                continue
            is_local = cand in ("vllm", "ollama", "local")
            if is_local:
                if not getattr(self, "local_allowed", True):
                    continue
                if not getattr(self.providers[cand], "is_available", lambda: True)():
                    continue
                healthy_chain.append(cand)
            else:
                if (self.mode == ExecutionMode.LOCAL and not self.cloud_allowed) or not self.cloud_allowed:
                    continue
                if cm.get_credential_status(cand) == "configured":
                    healthy_chain.append(cand)

        if self.round_robin_enabled and healthy_chain and t in (InferenceTask.RAG_GENERATION, InferenceTask.CHAT):
            with self._rr_lock:
                target_name = healthy_chain[self._round_robin_index % len(healthy_chain)]
                self._round_robin_index = (self._round_robin_index + 1) % len(healthy_chain)
                return self.providers[target_name]

        # If target cloud provider has no credentials configured, route to first configured cloud provider or vLLM
        if target_name not in ("vllm", "ollama", "local") and cm.get_credential_status(target_name) != "configured":
            for cand in self.fallback_chain:
                if cand not in self.disabled_providers and self.provider_cooldowns.get(cand, 0) <= now:
                    if cand in ("vllm", "ollama", "local"):
                        if getattr(self, "local_allowed", True) and cand in self.providers and getattr(self.providers[cand], "is_available", lambda: True)():
                            target_name = cand
                            break
                    elif cm.get_credential_status(cand) == "configured" and ((self.mode != ExecutionMode.LOCAL) or self.cloud_allowed) and self.cloud_allowed:
                        target_name = cand
                        break
            else:
                if getattr(self, "local_allowed", True) and "vllm" in self.providers and getattr(self.providers["vllm"], "is_available", lambda: True)():
                    target_name = "vllm"

        # Check if preferred provider is on rate-limit cooldown or disabled; if so, pick next healthy fallback
        if target_name in self.disabled_providers or self.provider_cooldowns.get(target_name, 0) > now:
            for cand in self.fallback_chain:
                if cand != target_name and cand not in self.disabled_providers and self.provider_cooldowns.get(cand, 0) <= now and cand in self.providers:
                    if cand in ("vllm", "ollama", "local"):
                        if not getattr(self, "local_allowed", True) or not getattr(self.providers[cand], "is_available", lambda: True)():
                            continue
                    else:
                        if ((self.mode == ExecutionMode.LOCAL and not self.cloud_allowed) or not self.cloud_allowed) or cm.get_credential_status(cand) != "configured":
                            continue
                    logger.info(f"Provider '{target_name}' unavailable (cooldown/disabled). Routing {t.value} to '{cand}'.")
                    target_name = cand
                    break

        if target_name in self.disabled_providers:
            for eng in ("ollama", "vllm"):
                if eng in self.providers and eng not in self.disabled_providers:
                    try:
                        if getattr(self.providers[eng], "is_available", lambda: False)():
                            target_name = eng
                            break
                    except Exception:
                        pass

        fallback_prov = self.providers.get("vllm") or (next(iter(self.providers.values())) if self.providers else None)
        return self.providers.get(target_name, fallback_prov)

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
            if primary_provider.name in self.disabled_providers:
                raise RuntimeError(f"Provider '{primary_provider.name}' is disabled due to authentication/billing restriction.")

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
                _cm_cd = get_credential_manager()
                num_configured_clouds = sum(1 for c in ["groq", "gemini", "mistral", "nvidia", "cohere", "openrouter"] if _cm_cd.get_credential_status(c) == "configured")
                # If only 1 provider is configured, use a short backoff (3s) rather than locking out the entire pipeline
                cooldown_secs = 3.0 if num_configured_clouds <= 1 else (15.0 if primary_provider.name == "groq" else 60.0)
                self.provider_cooldowns[primary_provider.name] = time.time() + cooldown_secs
                logger.info(f"Activated {int(cooldown_secs)}s cooldown for provider '{primary_provider.name}'.")
            elif ("401" in err_msg or "AUTH_FAILED" in err_msg or "invalid_api_key" in err_msg.lower() or "402" in err_msg or "BILLING_RESTRICTED" in err_msg or "credit card" in err_msg.lower() or "403" in err_msg) and primary_provider.name not in ("vllm", "ollama", "local"):
                self.disabled_providers.add(primary_provider.name)
                logger.warning(f"Permanently disabled billing/auth-restricted provider '{primary_provider.name}'.")
            elif "404" in err_msg or "MODEL_UNAVAILABLE" in err_msg or "not found" in err_msg.lower() or "timed out" in err_msg.lower() or "timeout" in err_msg.lower() or "connection refused" in err_msg.lower() or "10061" in err_msg:
                self.provider_cooldowns[primary_provider.name] = time.time() + 60.0
                logger.warning(f"Activated 60s cooldown for unreachable/unavailable provider '{primary_provider.name}'.")

            # Try each provider in the fallback chain
            errors = [f"{primary_provider.name}: {err_msg}"]
            now = time.time()
            cm = get_credential_manager()
            for candidate_name in self.fallback_chain:
                if candidate_name == primary_provider.name or candidate_name in self.disabled_providers:
                    continue
                if candidate_name in ("vllm", "ollama", "local"):
                    if not getattr(self, "local_allowed", True):
                        continue
                    if not getattr(self.providers[candidate_name], "is_available", lambda: True)():
                        continue
                else:
                    if (self.mode == ExecutionMode.LOCAL and not self.cloud_allowed) or not self.cloud_allowed:
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
                    elif ("401" in fb_str or "AUTH_FAILED" in fb_str or "invalid_api_key" in fb_str.lower() or "402" in fb_str or "BILLING_RESTRICTED" in fb_str or "credit card" in fb_str.lower() or "403" in fb_str) and candidate_name not in ("vllm", "ollama", "local"):
                        self.disabled_providers.add(candidate_name)
                        logger.warning(f"Permanently disabled invalid/unauthorized fallback '{candidate_name}'.")
                    elif "404" in fb_str or "MODEL_UNAVAILABLE" in fb_str or "timed out" in fb_str.lower() or "timeout" in fb_str.lower() or "connection refused" in fb_str.lower() or "10061" in fb_str:
                        self.provider_cooldowns[candidate_name] = time.time() + 60.0
                        logger.warning(f"Activated 60s cooldown for unreachable fallback '{candidate_name}'.")
                    errors.append(f"{candidate_name}: {fb_err}")
                    logger.warning(f"Fallback candidate '{candidate_name}' failed: {fb_err}")

            # Auto-probe and promote local daemons (Ollama / vLLM) if cloud failed
            if getattr(self, "local_allowed", True):
                for local_cand in ("ollama", "vllm"):
                    if local_cand not in self.providers or local_cand in self.disabled_providers:
                        continue
                    try:
                        cand_prov = self.providers[local_cand]
                        if cand_prov.is_available():
                            logger.info(f"[ROUTER] Auto-probing detected responsive local engine '{local_cand}'. Promoting to active provider.")
                            if local_cand not in self.fallback_chain:
                                self.fallback_chain.insert(0, local_cand)
                            fb_event = FallbackEvent(
                                from_provider=primary_provider.name,
                                to_provider=local_cand,
                                task=t.value,
                                reason="Automated failover to responsive local engine following cloud failure",
                            )
                            self.fallback_history.append(fb_event)
                            res = cand_prov.complete(
                                prompt=prompt,
                                system_prompt=system_prompt,
                                max_tokens=max_tokens,
                                temperature=temperature,
                                **kwargs,
                            )
                            if res and not any(res.startswith(pfx) for pfx in ("Error executing inference", "Cloud LLM error", "Ollama error", "Inference execution error")):
                                self.last_used_provider = local_cand
                                self.last_used_model = getattr(cand_prov, "model_name", "default")
                                get_token_tracker().record_inference(
                                    provider=local_cand,
                                    prompt_text=f"{system_prompt or ''}\n{prompt}",
                                    completion_text=res,
                                    model=getattr(cand_prov, "model_name", None),
                                )
                                return res
                    except Exception as probe_err:
                        errors.append(f"{local_cand}: {probe_err}")

            all_errs = "; ".join(errors)
            if "not configured" in all_errs and ("offline" in all_errs or "refused" in all_errs or "10061" in all_errs or "CUDA is unavailable" in all_errs):
                raise ProviderExhaustedError(
                    f"NO_LLM_AVAILABLE: No functional LLM provider available. Please configure an API key (Groq, Gemini, NVIDIA, Mistral) in Settings or start a local Ollama/vLLM instance. Details: {all_errs}",
                    errors=errors,
                )
            raise ProviderExhaustedError(f"NO_LLM_AVAILABLE: All inference providers in fallback chain failed: {all_errs}", errors=errors)

    async def complete_stream(
        self,
        prompt: str,
        task: Union[InferenceTask, str] = InferenceTask.CHAT,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Execute streaming completion with non-blocking async fallback."""
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
            logger.warning(f"Streaming error on provider '{primary_provider.name}': {e}. Falling back to sync completion via thread pool.")
            fallback_text = await asyncio.to_thread(
                self.complete,
                prompt=prompt,
                task=t,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
            yield fallback_text


# Global Singleton Router
_router_instance: Optional[ProviderRouter] = None


def get_provider_router() -> ProviderRouter:
    """Return singleton ProviderRouter instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ProviderRouter()
    return _router_instance
