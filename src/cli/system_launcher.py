"""
RAISE — System Launcher & Infrastructure Health Probes
======================================================
Subsystem container auto-start orchestration and local neural inference
health monitoring for Neo4j, vLLM, and Docker daemon infrastructure.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from typing import Any, Dict

from src.cli.renderer import C
from src.core.config import models

logger = logging.getLogger("RAISE_Launcher")


__all__ = [
    "auto_start_containers",
    "check_vllm_health",
    "get_synthesizer_status",
]


def auto_start_containers() -> None:
    """
    Checks if Neo4j and vLLM Docker containers are running. If inactive, attempts
    to start them automatically via the Docker CLI and polls Bolt port 7687
    until the database is fully responsive.
    """
    # Fast path: check if Neo4j port 7687 is already open and responding
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", 7687)) == 0 or s.connect_ex(("localhost", 7687)) == 0:
                return
    except Exception:
        pass

    # Ensure docker executable is available on PATH
    if not shutil.which("docker"):
        return

    try:
        print(f"{C.ACCENT}🐳 [Auto-Starter]{C.RESET} Checking container infrastructure...")
        proc = subprocess.run(
            ["docker", "start", "raise-neo4j-prod", "raise-vllm-prod"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=8,
        )
        if proc.returncode != 0 and (
            "daemon is running" in proc.stderr or "dockerDesktopLinuxEngine" in proc.stderr
        ):
            print(
                f"  {C.WARN}⚠️  [Auto-Starter] Docker Desktop engine is booting up. Waiting for daemon...{C.RESET}"
            )
            for _ in range(3):
                time.sleep(1.5)
                retry_proc = subprocess.run(
                    ["docker", "start", "raise-neo4j-prod", "raise-vllm-prod"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                )
                if retry_proc.returncode == 0:
                    break
    except Exception as e:
        logger.warning(f"Auto-starter docker error: {e}")
        return

    # Poll for Neo4j Bolt port 7687 readiness
    print(
        f"  {C.INFO}⏳ [Auto-Starter]{C.RESET} Waiting for Neo4j database to open Bolt port 7687...",
        end="",
        flush=True,
    )
    start_time = time.time()
    neo4j_ready = False
    while time.time() - start_time < 8:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.4)
                if s.connect_ex(("127.0.0.1", 7687)) == 0:
                    neo4j_ready = True
                    break
        except Exception:
            pass
        print(f"{C.INFO}.{C.RESET}", end="", flush=True)
        time.sleep(0.6)

    if neo4j_ready:
        print(f" {C.SUCCESS}[READY]{C.RESET}")
    else:
        print(f" {C.WARN}[TIMEOUT: Continuing with in-memory graph fallback]{C.RESET}")


def check_vllm_health() -> Dict[str, Any]:
    """
    Pings the local vLLM OpenAI-compatible endpoint to check if the neural model
    is loaded, retrieving model ID, max context length, and round-trip latency.
    """
    vllm_url = os.getenv("VLLM_API_BASE", "http://localhost:8002/v1").rstrip("/") + "/models"
    t0 = time.time()
    try:
        req = urllib.request.Request(vllm_url, headers={"User-Agent": "RAISE-Studio"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = round((time.time() - t0) * 1000, 1)
            models = data.get("data", [])
            model_id = models[0].get("id", "Unknown") if models else "None"
            max_len = models[0].get("max_model_len", 8192) if models else 8192
            return {
                "connected": True,
                "model_id": model_id,
                "max_model_len": max_len,
                "latency_ms": elapsed,
            }
    except Exception as e:
        return {
            "connected": False,
            "model_id": "Offline",
            "max_model_len": 0,
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "error": str(e),
        }


def get_synthesizer_status() -> Dict[str, Any]:
    """
    Dynamically probes and determines the active synthesizer status across both
    Local vLLM and Cloud AI providers (Groq, Gemini, DeepSeek, NVIDIA NIM, Cohere, etc.).
    Returns a dictionary with status, active provider, model name, and formatted display string.
    """
    vllm_info = check_vllm_health()
    vllm_connected = bool(vllm_info.get("connected"))

    env_backend = (os.getenv("LLM_BACKEND") or "").lower().strip()

    # Cloud providers map: key_env_vars, display_name, default_model
    cloud_candidates = {
        "groq": {
            "key_vars": ["GROQ_API_KEY"],
            "name": "Groq",
            "model": models.GROQ_MODEL_NAME,
        },
        "gemini": {
            "key_vars": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
            "name": "Gemini",
            "model": models.GEMINI_MODEL_NAME,
        },
        "deepseek": {
            "key_vars": ["DEEPSEEK_API_KEY"],
            "name": "DeepSeek",
            "model": models.DEEPSEEK_MODEL_NAME,
        },
        "nvidia": {
            "key_vars": ["NVIDIA_API_KEY"],
            "name": "NVIDIA NIM",
            "model": models.NVIDIA_MODEL_NAME,
        },
        "openrouter": {
            "key_vars": ["OPENROUTER_API_KEY"],
            "name": "OpenRouter",
            "model": models.OPENROUTER_MODEL_NAME,
        },
        "cohere": {
            "key_vars": ["COHERE_API_KEY"],
            "name": "Cohere",
            "model": models.COHERE_MODEL_NAME,
        },
        "mistral": {
            "key_vars": ["MISTRAL_API_KEY"],
            "name": "Mistral",
            "model": models.MISTRAL_MODEL_NAME,
        },
    }

    def is_cloud_configured(p_id: str) -> bool:
        cand = cloud_candidates.get(p_id)
        if not cand:
            return False
        return any(bool(os.getenv(k, "").strip()) for k in cand["key_vars"])

    active_provider = None
    active_type = None
    model_name = None
    display_name = None

    # Priority 1: User explicitly specified LLM_BACKEND
    if env_backend:
        if env_backend == "vllm":
            if vllm_connected:
                active_provider = "vllm"
                active_type = "local"
                model_name = vllm_info["model_id"]
                display_name = "Local vLLM"
        elif env_backend in cloud_candidates and is_cloud_configured(env_backend):
            active_provider = env_backend
            active_type = "cloud"
            info = cloud_candidates[env_backend]
            display_name = info["name"]
            model_name = info["model"]

    # Priority 2: If no explicit backend or explicit backend unavailable, check connected vLLM
    if not active_provider and vllm_connected:
        active_provider = "vllm"
        active_type = "local"
        model_name = vllm_info["model_id"]
        display_name = "Local vLLM"

    # Priority 3: Fallback through configured cloud providers
    if not active_provider:
        for p_id, info in cloud_candidates.items():
            if is_cloud_configured(p_id):
                active_provider = p_id
                active_type = "cloud"
                display_name = info["name"]
                model_name = info["model"]
                break

    # Build display string
    if active_type == "local":
        disp = f"{C.SUCCESS}ONLINE{C.RESET} {C.MUTED}(Local vLLM - {model_name}){C.RESET}"
    elif active_type == "cloud":
        disp = f"{C.SUCCESS}ACTIVE{C.RESET} {C.MUTED}(Cloud: {display_name} - {model_name}){C.RESET}"
    else:
        disp = f"{C.WARN}STANDBY{C.RESET} {C.MUTED}(Rule-based synthesis active — no LLM configured){C.RESET}"

    return {
        "active": active_provider is not None,
        "type": active_type or "standby",
        "provider": active_provider or "none",
        "model": model_name or "none",
        "display_name": display_name or "None",
        "display_string": disp,
        "vllm_info": vllm_info,
    }
