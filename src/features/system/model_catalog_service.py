"""
Dynamic Local LLM Model Catalog Service
=======================================
Dynamically queries public model registries (HuggingFace Hub API / OpenRouter)
and local inference engine daemons (Ollama / vLLM / LM Studio) to provide
real-time, up-to-date open model catalogs tailored to the host system's RAM.
Zero hardcoded model catalogs.
"""

from __future__ import annotations

import os
import re
import time
import logging
from typing import Any, Dict, List, Optional
import requests
from src.core.config import (
    SUPPORTED_FAMILY_KEYWORDS,
    OPENROUTER_FAMILY_KEYWORDS,
    OFFLINE_CATALOG_FALLBACK,
)

logger = logging.getLogger("raise.features.system.model_catalog")

# In-memory cache for dynamic catalog (TTL = 15 minutes)
_CATALOG_CACHE: List[Dict[str, Any]] = []
_CATALOG_CACHE_TIME: float = 0.0
_CATALOG_CACHE_TTL: float = 900.0  # 15 minutes


def _fetch_from_local_vllm() -> List[Dict[str, Any]]:
    """Probes local vLLM OpenAI-compatible endpoint for currently loaded/downloaded models."""
    local_models = []
    vllm_base = os.getenv("VLLM_BASE_URL", os.getenv("VLLM_API_BASE", "http://127.0.0.1:8002")).rstrip("/")
    if vllm_base.endswith("/v1"):
        endpoint = f"{vllm_base}/models"
    else:
        endpoint = f"{vllm_base}/v1/models"
    try:
        r = requests.get(endpoint, timeout=0.8)
        if r.status_code == 200:
            data = r.json()
            for m in data.get("data", []):
                m_id = m.get("id", "local-vllm-model")
                max_len = m.get("max_model_len", 8192)
                param_match = re.search(r"(\d+(?:\.\d+)?)[bB]", m_id)
                param_val = float(param_match.group(1)) if param_match else 14.0
                size_gb = round(param_val * 0.6, 1) if any(k in m_id.lower() for k in ("gptq", "int4", "awq", "int8")) else round(param_val * 1.5, 1)
                min_ram = 16 if size_gb <= 12 else 32

                local_models.append({
                    "id": m_id,
                    "name": f"{m_id} ({int(param_val)}B - {max_len} ctx)",
                    "download_size_gb": size_gb,
                    "min_ram_gb": min_ram,
                    "tier": "Installed (Local Engine)",
                    "status": "READY",
                    "downloads": "On-Device (vLLM GPU)",
                    "source": "vllm_local",
                    "isInstalled": True,
                })
    except Exception:
        pass
    return local_models


def _fetch_from_local_ollama() -> List[Dict[str, Any]]:
    """Probes local Ollama daemon for currently installed models."""
    local_models = []
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=0.5)
        if r.status_code == 200:
            data = r.json()
            for m in data.get("models", []):
                size_bytes = m.get("size", 0)
                size_gb = round(size_bytes / (1024**3), 1)
                name = m.get("name", "local-model")
                param_size = m.get("details", {}).get("parameter_size", "")
                display_name = f"{name} ({param_size})" if param_size else name

                min_ram = 8 if size_gb < 3.5 else (16 if size_gb < 7.0 else 32)
                local_models.append({
                    "id": name,
                    "name": display_name,
                    "download_size_gb": size_gb,
                    "min_ram_gb": min_ram,
                    "tier": "Installed (Local Engine)",
                    "status": "READY",
                    "downloads": "On-Device",
                    "source": "ollama_local",
                })
    except Exception:
        pass
    return local_models


def _fetch_from_huggingface(limit: int = 15) -> List[Dict[str, Any]]:
    """
    Queries HuggingFace Model Hub Public REST API for top trending
    instruction-tuned open models without requiring an API key.
    """
    hf_models = []
    try:
        url = "https://huggingface.co/api/models"
        params = {
            "pipeline_tag": "text-generation",
            "search": "instruct",
            "sort": "downloads",
            "direction": -1,
            "limit": limit,
        }
        r = requests.get(url, params=params, timeout=2.5)
        if r.status_code == 200:
            for item in r.json():
                m_id = item.get("id", "")
                downloads = item.get("downloads", 0)
                m_lower = m_id.lower()

                # Filter for recognized open-weight instruct architectures
                if not any(k in m_lower for k in SUPPORTED_FAMILY_KEYWORDS):
                    continue

                # Parse parameter count (e.g. 1B, 3B, 7B, 8B, 14B)
                param_match = re.search(r"(\d+(?:\.\d+)?)[bB]", m_id)
                param_val = float(param_match.group(1)) if param_match else 7.0

                if param_val <= 3.5:
                    size_gb = round(max(0.8, param_val * 0.7), 1)
                    min_ram = 8
                    tier = "Fast & Light"
                elif param_val <= 9.0:
                    size_gb = round(param_val * 0.65, 1)
                    min_ram = 16
                    tier = "Balanced Reasoning"
                elif param_val <= 16.0:
                    size_gb = round(param_val * 0.6, 1)
                    min_ram = 24
                    tier = "High Fidelity"
                else:
                    size_gb = round(param_val * 0.55, 1)
                    min_ram = 32
                    tier = "Deep Synthesis"

                dl_str = (
                    f"{round(downloads / 1e6, 1)}M downloads"
                    if downloads >= 1e6
                    else f"{round(downloads / 1e3, 1)}k downloads"
                )
                display_name = m_id.split("/")[-1].replace("-", " ").replace("_", " ")

                hf_models.append({
                    "id": m_id,
                    "name": display_name,
                    "download_size_gb": size_gb,
                    "min_ram_gb": min_ram,
                    "tier": tier,
                    "status": "READY",
                    "downloads": dl_str,
                    "source": "huggingface_hub",
                })
    except Exception as e:
        logger.debug(f"HuggingFace public models query error: {e}")
    return hf_models


def _fetch_from_openrouter(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Queries OpenRouter's public models endpoint for popular open-weights
    instruction-tuned models without requiring an API key.
    """
    or_models = []
    try:
        url = "https://openrouter.ai/api/v1/models"
        r = requests.get(url, timeout=2.5)
        if r.status_code == 200:
            data = r.json().get("data", [])
            for item in data:
                m_id = item.get("id", "")
                m_lower = m_id.lower()
                if not any(k in m_lower for k in OPENROUTER_FAMILY_KEYWORDS):
                    continue

                param_match = re.search(r"(\d+(?:\.\d+)?)[bB]", m_id)
                param_val = float(param_match.group(1)) if param_match else 7.0

                if param_val <= 3.5:
                    size_gb = round(max(0.8, param_val * 0.7), 1)
                    min_ram = 8
                    tier = "Fast & Light"
                elif param_val <= 9.0:
                    size_gb = round(param_val * 0.65, 1)
                    min_ram = 16
                    tier = "Balanced Reasoning"
                else:
                    size_gb = round(param_val * 0.6, 1)
                    min_ram = 24
                    tier = "High Fidelity"

                context_len = item.get("context_length", 32768)
                name = item.get("name") or m_id.split("/")[-1]

                or_models.append({
                    "id": m_id,
                    "name": name,
                    "download_size_gb": size_gb,
                    "min_ram_gb": min_ram,
                    "tier": tier,
                    "status": "READY",
                    "downloads": f"{context_len // 1024}k context",
                    "source": "openrouter_public",
                })
                if len(or_models) >= limit:
                    break
    except Exception as e:
        logger.debug(f"OpenRouter public models query error: {e}")
    return or_models


def get_dynamic_model_catalog(total_ram_gb: float = 16.0) -> List[Dict[str, Any]]:
    """
    Returns an aggregated, hardware-tailored model catalog dynamically fetched
    from public model registries and local daemons.
    Caches results in-memory for 15 minutes to preserve sub-millisecond response latency.
    """
    global _CATALOG_CACHE, _CATALOG_CACHE_TIME

    now = time.time()
    if _CATALOG_CACHE and (now - _CATALOG_CACHE_TIME) < _CATALOG_CACHE_TTL:
        # Return hardware-filtered cached copy
        return [m for m in _CATALOG_CACHE if m["min_ram_gb"] <= max(16.0, total_ram_gb)]

    aggregated: List[Dict[str, Any]] = []
    seen_ids = set()

    # 1. Prioritize locally installed models if vLLM or Ollama is running
    vllm_installed = _fetch_from_local_vllm()
    for m in vllm_installed:
        if m["id"] not in seen_ids:
            seen_ids.add(m["id"])
            aggregated.append(m)

    local_installed = _fetch_from_local_ollama()
    for m in local_installed:
        if m["id"] not in seen_ids:
            seen_ids.add(m["id"])
            aggregated.append(m)

    # 2. Query HuggingFace Hub public models API
    hf_results = _fetch_from_huggingface(limit=15)
    for m in hf_results:
        clean_key = m["name"].lower().replace(" ", "")
        if clean_key not in seen_ids and m["id"] not in seen_ids:
            seen_ids.add(clean_key)
            seen_ids.add(m["id"])
            aggregated.append(m)

    # 3. Fallback: Query OpenRouter public endpoint if HuggingFace returned empty
    if len(aggregated) < 3:
        or_results = _fetch_from_openrouter(limit=8)
        for m in or_results:
            clean_key = m["name"].lower().replace(" ", "")
            if clean_key not in seen_ids and m["id"] not in seen_ids:
                seen_ids.add(clean_key)
                seen_ids.add(m["id"])
                aggregated.append(m)

    # 4. Safe offline fallback if machine is completely air-gapped with zero internet
    if not aggregated:
        aggregated = [dict(item) for item in OFFLINE_CATALOG_FALLBACK]

    _CATALOG_CACHE = aggregated
    _CATALOG_CACHE_TIME = now

    # Filter to models fitting host RAM
    filtered = [m for m in aggregated if m["min_ram_gb"] <= max(16.0, total_ram_gb)]
    return filtered if filtered else aggregated[:5]
