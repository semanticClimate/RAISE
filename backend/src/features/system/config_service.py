"""
System Configuration & Environment Synchronization Service
===========================================================
Manages active LLM backend selection, credential updates, and persistent
synchronization with the root `.env` file.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import SystemConfigRequest

ROOT_DIR = Path(__file__).resolve().parents[4]
BACKEND_DIR = Path(__file__).resolve().parents[3]
ENV_FILE_PATH = BACKEND_DIR / ".env"
ROOT_ENV_FILE_PATH = ROOT_DIR / ".env"

logger = logging.getLogger("raise.features.system.config")


def is_masked_secret(val: Optional[str]) -> bool:
    """Checks whether a string is a masked telemetry display string rather than a real key."""
    if not val:
        return False
    s = val.strip()
    return "..." in s or s == "********" or (len(s) > 0 and all(c == "*" for c in s))


def mask_secret(val: Optional[str]) -> str:
    """Masks secret keys for telemetry display."""
    if not val:
        return ""
    if len(val) <= 8:
        return "********"
    return f"{val[:4]}...{val[-4:]}"


def get_current_configuration() -> Dict[str, Any]:
    """Returns current active system configuration with sensitive keys masked and dynamic providers listed."""
    from src.infrastructure.credentials.manager import get_credential_manager
    from src.infrastructure.providers.router import get_provider_router

    cm = get_credential_manager()
    p_router = get_provider_router()

    llm_backend = os.getenv("LLM_BACKEND", "groq")
    neo4j_uri = os.getenv("NEO4J_URI", "")
    redis_url = os.getenv("REDIS_URL", "")
    privacy_mode = os.getenv("PRIVACY_MODE", "false").lower() in ("true", "1", "yes")

    raw_model = os.getenv("LLM_MODEL_NAME", "llama-3.3-70b-versatile")
    last_model = p_router.last_used_model
    last_provider = p_router.last_used_provider
    available_provs = p_router.get_dynamic_available_providers()

    if privacy_mode:
        raw_model = "RAISE-Neural-Engine"
        last_model = "RAISE-Neural-Engine" if last_model else None
        last_provider = "RAISE-Cloud-Mesh" if last_provider else None
        available_provs = ["RAISE-Cloud-Mesh"]

    return {
        "llm_mode": "local_vllm" if llm_backend == "vllm" else ("local_ollama" if llm_backend == "ollama" else f"cloud_{llm_backend}"),
        "llm_model_name": raw_model,
        "last_used_provider": last_provider,
        "last_used_model": last_model,
        "available_providers": available_provs,
        "privacy_mode": privacy_mode,
        "groq_configured": cm.get_credential_status("groq") == "configured",
        "groq_masked": mask_secret(cm.get_credential("groq")),
        "gemini_configured": cm.get_credential_status("gemini") == "configured",
        "gemini_masked": mask_secret(cm.get_credential("gemini")),
        "openai_configured": cm.get_credential_status("openai") == "configured",
        "openai_masked": mask_secret(cm.get_credential("openai")),
        "anthropic_configured": cm.get_credential_status("anthropic") == "configured",
        "anthropic_masked": mask_secret(cm.get_credential("anthropic")),
        "nvidia_configured": cm.get_credential_status("nvidia") == "configured",
        "nvidia_masked": mask_secret(cm.get_credential("nvidia")),
        "cohere_configured": cm.get_credential_status("cohere") == "configured",
        "cohere_masked": mask_secret(cm.get_credential("cohere")),
        "mistral_configured": cm.get_credential_status("mistral") == "configured",
        "mistral_masked": mask_secret(cm.get_credential("mistral")),
        "vercel_configured": cm.get_credential_status("vercel") == "configured" or cm.get_credential_status("typesafe") == "configured",
        "vercel_masked": mask_secret(cm.get_credential("vercel") or cm.get_credential("typesafe")),
        "deepseek_configured": cm.get_credential_status("deepseek") == "configured",
        "deepseek_masked": mask_secret(cm.get_credential("deepseek")),
        "openrouter_configured": cm.get_credential_status("openrouter") == "configured",
        "openrouter_masked": mask_secret(cm.get_credential("openrouter")),
        "custom_configured": cm.get_credential_status("custom") == "configured",
        "custom_masked": mask_secret(cm.get_credential("custom")),
        "neo4j_uri": neo4j_uri,
        "neo4j_database": os.getenv("NEO4J_DATABASE", "neo4j"),
        "neo4j_is_cloud": "databases.neo4j.io" in neo4j_uri,
        "redis_is_cloud": "upstash.io" in redis_url,
        "first_run_completed": bool(
            cm.get_credential_status("groq") == "configured"
            or cm.get_credential_status("mistral") == "configured"
            or cm.get_credential_status("gemini") == "configured"
            or cm.get_credential_status("openai") == "configured"
            or cm.get_credential_status("anthropic") == "configured"
            or cm.get_credential_status("nvidia") == "configured"
            or cm.get_credential_status("cohere") == "configured"
            or (llm_backend in ["ollama", "vllm"] and ((BACKEND_DIR / ".runtime" / "setup_completed").exists() or (ROOT_DIR / ".runtime" / "setup_completed").exists()))
            or os.getenv("SETUP_COMPLETED", "").lower() in ("true", "1", "yes")
            or (BACKEND_DIR / ".runtime" / "setup_completed").exists()
            or (ROOT_DIR / ".runtime" / "setup_completed").exists()
        ),
    }


def save_configuration(cfg: SystemConfigRequest) -> Dict[str, Any]:
    """Updates runtime environment and writes updates safely to .env file."""
    # Read existing .env lines with fallback to root or template
    source_path = None
    if ENV_FILE_PATH.exists():
        source_path = ENV_FILE_PATH
    elif ROOT_ENV_FILE_PATH.exists():
        source_path = ROOT_ENV_FILE_PATH
    elif (ROOT_DIR / ".env.example").exists():
        source_path = ROOT_DIR / ".env.example"

    lines: List[str] = []
    if source_path and source_path.exists():
        lines = source_path.read_text(encoding="utf-8").splitlines()

    env_map: Dict[str, str] = {}
    for line in lines:
        line_str = line.strip()
        if line_str and not line_str.startswith("#") and "=" in line_str:
            k, v = line_str.split("=", 1)
            env_map[k.strip()] = v.strip()

    # Update LLM Backend
    if cfg.llm_mode == "local_ollama":
        env_map["LLM_BACKEND"] = "ollama"
        if cfg.selected_local_model:
            env_map["LLM_MODEL_NAME"] = cfg.selected_local_model
        env_map["LLM_BASE_URL"] = "http://localhost:11434/v1"
    elif cfg.llm_mode == "local_vllm":
        env_map["LLM_BACKEND"] = "vllm"
        if cfg.selected_local_model:
            env_map["LLM_MODEL_NAME"] = cfg.selected_local_model
        else:
            env_map["LLM_MODEL_NAME"] = os.getenv("VLLM_MODEL_NAME", "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4")
        env_map["VLLM_BASE_URL"] = os.getenv("VLLM_BASE_URL", "http://localhost:8002/v1")
    elif cfg.llm_mode == "cloud_gemini":
        env_map["LLM_BACKEND"] = "gemini"
        env_map["LLM_MODEL_NAME"] = "gemini-2.0-flash"
        if cfg.gemini_api_key and not is_masked_secret(cfg.gemini_api_key):
            env_map["GEMINI_API_KEY"] = cfg.gemini_api_key.strip()
    elif cfg.llm_mode == "cloud_nvidia":
        env_map["LLM_BACKEND"] = "nvidia"
        env_map["LLM_MODEL_NAME"] = "meta/llama-3.2-11b-vision-instruct"
    elif cfg.llm_mode == "cloud_cohere":
        env_map["LLM_BACKEND"] = "cohere"
        env_map["LLM_MODEL_NAME"] = "command-r-plus-08-2024"
    elif cfg.llm_mode == "cloud_mistral":
        env_map["LLM_BACKEND"] = "mistral"
        env_map["LLM_MODEL_NAME"] = "open-mistral-nemo"
    elif cfg.llm_mode == "cloud_deepseek":
        env_map["LLM_BACKEND"] = "deepseek"
        env_map["LLM_MODEL_NAME"] = "deepseek-chat"
        if cfg.deepseek_api_key and not is_masked_secret(cfg.deepseek_api_key):
            env_map["DEEPSEEK_API_KEY"] = cfg.deepseek_api_key.strip()
    elif cfg.llm_mode == "cloud_openrouter":
        env_map["LLM_BACKEND"] = "openrouter"
        env_map["LLM_MODEL_NAME"] = "anthropic/claude-3.5-sonnet"
        if cfg.openrouter_api_key and not is_masked_secret(cfg.openrouter_api_key):
            env_map["OPENROUTER_API_KEY"] = cfg.openrouter_api_key.strip()
    elif cfg.llm_mode == "cloud_openai":
        env_map["LLM_BACKEND"] = "universal"
        env_map["LLM_MODEL_NAME"] = "gpt-4o-mini"
        env_map["CUSTOM_LLM_BASE_URL"] = "https://api.openai.com/v1"
        if cfg.openai_api_key and not is_masked_secret(cfg.openai_api_key):
            env_map["OPENAI_API_KEY"] = cfg.openai_api_key.strip()
    elif cfg.llm_mode == "cloud_anthropic":
        env_map["LLM_BACKEND"] = "universal"
        env_map["LLM_MODEL_NAME"] = "claude-3-5-sonnet"
        if cfg.anthropic_api_key and not is_masked_secret(cfg.anthropic_api_key):
            env_map["ANTHROPIC_API_KEY"] = cfg.anthropic_api_key.strip()
    elif cfg.llm_mode == "cloud_vercel":
        env_map["LLM_BACKEND"] = "vercel"
        env_map["LLM_MODEL_NAME"] = "typesafe-ai/jev"
    elif cfg.llm_mode == "cloud_custom":
        env_map["LLM_BACKEND"] = "universal"
        env_map["LLM_MODEL_NAME"] = cfg.custom_model_name or "gpt-4o-mini"
        if cfg.custom_base_url:
            env_map["CUSTOM_LLM_BASE_URL"] = cfg.custom_base_url
            os.environ["CUSTOM_LLM_BASE_URL"] = cfg.custom_base_url
    else:  # cloud_groq default
        env_map["LLM_BACKEND"] = "groq"
        env_map["LLM_MODEL_NAME"] = "llama-3.3-70b-versatile"
        if cfg.groq_api_key and not is_masked_secret(cfg.groq_api_key):
            env_map["GROQ_API_KEY"] = cfg.groq_api_key.strip()

    # Update provider credentials if provided (ignoring masked placeholders)
    from src.infrastructure.credentials.manager import get_credential_manager
    from src.infrastructure.providers.router import get_provider_router
    cm = get_credential_manager()

    for prov, secret in [
        ("groq", cfg.groq_api_key),
        ("gemini", cfg.gemini_api_key),
        ("openai", cfg.openai_api_key),
        ("anthropic", cfg.anthropic_api_key),
        ("nvidia", cfg.nvidia_api_key),
        ("cohere", cfg.cohere_api_key),
        ("mistral", cfg.mistral_api_key),
        ("vercel", cfg.vercel_api_key),
        ("deepseek", cfg.deepseek_api_key),
        ("openrouter", cfg.openrouter_api_key),
        ("custom", cfg.custom_api_key),
    ]:
        if secret and secret.strip() and not is_masked_secret(secret):
            cleaned = secret.strip()
            cm.set_credential(prov, cleaned)
            env_var = f"{prov.upper()}_API_KEY"
            env_map[env_var] = cleaned
            os.environ[env_var] = cleaned

    # Refresh provider router fallback chain dynamically
    try:
        get_provider_router()._refresh_fallback_chain()
    except Exception as e:
        logger.warning(f"Could not refresh provider router: {e}")

    # Update Neo4j
    if cfg.neo4j_mode == "cloud" and cfg.neo4j_uri:
        env_map["NEO4J_URI"] = cfg.neo4j_uri
        if cfg.neo4j_user:
            env_map["NEO4J_USER"] = cfg.neo4j_user
        if cfg.neo4j_password:
            env_map["NEO4J_PASSWORD"] = cfg.neo4j_password
        if cfg.neo4j_database:
            env_map["NEO4J_DATABASE"] = cfg.neo4j_database

    # Update Redis
    redis_val = cfg.redis_url or cfg.redis_uri
    if cfg.redis_mode == "cloud" and redis_val:
        env_map["REDIS_URL"] = redis_val

    # Update Postgres
    pg_val = cfg.postgres_url or cfg.postgres_uri
    if cfg.postgres_mode == "cloud" and pg_val:
        env_map["POSTGRES_URL"] = pg_val

    # Mark first-time workstation setup completed across runtime & filesystem
    env_map["SETUP_COMPLETED"] = "true"
    os.environ["SETUP_COMPLETED"] = "true"
    try:
        for r_dir in [BACKEND_DIR / ".runtime", ROOT_DIR / ".runtime"]:
            r_dir.mkdir(parents=True, exist_ok=True)
            (r_dir / "setup_completed").write_text("true\n", encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist setup_completed marker: {e}")

    # Sync runtime os.environ
    for k, v in env_map.items():
        os.environ[k] = v

    # Write safely back to .env in both backend and root locations
    output_lines = [f"{k}={v}" for k, v in env_map.items()]
    content = "\n".join(output_lines) + "\n"
    ENV_FILE_PATH.write_text(content, encoding="utf-8")
    try:
        ROOT_ENV_FILE_PATH.write_text(content, encoding="utf-8")
    except Exception:
        pass

    return {
        "status": "success",
        "message": "System configuration saved and synced with active runtime.",
        "active_mode": env_map.get("LLM_BACKEND"),
        "active_model": env_map.get("LLM_MODEL_NAME"),
    }
