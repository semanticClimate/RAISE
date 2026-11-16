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
from src.core.config import models, AVAILABLE_EMBEDDING_MODELS, AVAILABLE_RERANKER_MODELS
from .preflight_service import check_hf_model_cached

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
    postgres_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL", "")
    privacy_mode = os.getenv("PRIVACY_MODE", "false").lower() in ("true", "1", "yes")

    raw_model = os.getenv("LLM_MODEL_NAME", models.LLM_MODEL_NAME)
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
        "llm_backend": llm_backend,
        "llm_model_name": raw_model,
        "last_used_provider": last_provider,
        "last_used_model": last_model,
        "available_providers": available_provs,
        "routing": p_router.get_routing_status(),
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
        "embedding_model": os.getenv("EMBEDDING_MODEL", models.EMBEDDING_MODEL_NAME),
        "embedding_device": os.getenv("EMBEDDING_DEVICE", "auto"),
        "reranker_model": os.getenv("RERANKER_MODEL", models.RERANKER_MODEL_NAME),
        "reranker_device": os.getenv("RERANKER_DEVICE", "auto"),
        "nli_model": os.getenv("NLI_MODEL", models.NLI_MODEL_NAME),
        "nli_verifier_model": os.getenv("NLI_VERIFIER_MODEL", os.getenv("NLI_MODEL", models.NLI_MODEL_NAME)),
        "nli_device": os.getenv("NLI_DEVICE", "auto"),
        "neural_device": os.getenv("NEURAL_DEVICE") or os.getenv("EMBEDDING_DEVICE", "auto"),
        "neo4j_mode": os.getenv("NEO4J_MODE", "in_memory_fallback" if not neo4j_uri else "cloud"),
        "postgres_mode": os.getenv("POSTGRES_MODE", "in_memory_fallback" if not postgres_url else "cloud"),
        "redis_mode": os.getenv("REDIS_MODE", "in_memory_fallback" if not redis_url else "cloud"),
        "huggingface_configured": bool(os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")),
        "huggingface_masked": mask_secret(os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")),
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
        "neural_registry": {
            "embedding": [
                {
                    "id": repo,
                    "name": repo.split("/")[-1].replace("-", " ").title(),
                    "cached": check_hf_model_cached(repo),
                    "status": "Cached & Ready" if check_hf_model_cached(repo) else "Requires Download",
                    "specifications": (
                        "768-dim • 8,192 tokens context"
                        if any(token in repo.lower() for token in models.EMBEDDING_MODEL_NAME.lower().split("/"))
                        else (
                            "1024-dim • 512 tokens max"
                            if any(token in repo.lower() for token in ("1024", "large", "m3"))
                            else (
                                "384-dim • 256 tokens max"
                                if "minilm" in repo.lower()
                                else "768-dim • Dense Embeddings"
                            )
                        )
                    ),
                }
                for repo in dict.fromkeys(AVAILABLE_EMBEDDING_MODELS.values())
            ],
            "reranker": [
                {
                    "id": repo,
                    "name": repo.split("/")[-1].replace("-", " ").title(),
                    "cached": check_hf_model_cached(repo),
                    "status": "Cached & Ready" if check_hf_model_cached(repo) else "Requires Download",
                    "specifications": (
                        "8,192 tokens max • Cross-Attention (matches 8k embedder context)"
                        if "v2-m3" in repo
                        else "512 tokens max • Cross-Attention"
                    ),
                }
                for repo in dict.fromkeys(AVAILABLE_RERANKER_MODELS.values())
            ] + [
                {
                    "id": "In-Memory Heuristic Reranker",
                    "name": "In-Memory Heuristic Reranker",
                    "cached": True,
                    "status": "Built-in (Zero-Dependency)",
                    "specifications": "In-process lexical overlap & contextual co-occurrence fallback",
                }
            ],
            "verifier": [
                {
                    "id": models.NLI_MODEL_NAME,
                    "name": models.NLI_MODEL_NAME.split("/")[-1].replace("-", " ").title(),
                    "cached": check_hf_model_cached(models.NLI_MODEL_NAME),
                    "status": "Cached & Ready" if check_hf_model_cached(models.NLI_MODEL_NAME) else "Requires Download",
                    "specifications": "RoBERTa / Cross-Attention • Pairwise citation chunk verification",
                },
                {
                    "id": "In-Memory Verifier",
                    "name": "In-Memory Verifier",
                    "cached": True,
                    "status": "Built-in (Zero-Dependency)",
                    "specifications": "Zero-dependency local verification fallback",
                }
            ],
            "custom_model_supported": True,
        },
    }


def save_configuration(cfg: SystemConfigRequest) -> Dict[str, Any]:
    """Updates runtime environment and writes updates safely to .env file."""
    # Read existing .env lines with fallback to root or template
    source_path = None
    if ENV_FILE_PATH.exists():
        source_path = ENV_FILE_PATH
    elif ROOT_ENV_FILE_PATH.exists():
        source_path = ROOT_ENV_FILE_PATH
    elif (BACKEND_DIR / ".env.example").exists():
        source_path = BACKEND_DIR / ".env.example"
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

    # Determine desired backend and mode from either llm_backend or llm_mode
    target_backend = (cfg.llm_backend or "").strip().lower()
    raw_mode = (cfg.llm_mode or "").strip().lower()

    has_explicit_llm_request = bool(target_backend or raw_mode)
    if not has_explicit_llm_request:
        # Preserve active environment configuration and pinned router primary
        from src.infrastructure.providers.router import get_provider_router
        active_router = get_provider_router()
        pinned = getattr(active_router, "pinned_primary_provider", None) or os.getenv("PINNED_PRIMARY_PROVIDER", "").strip().lower()
        existing_backend = pinned or env_map.get("LLM_BACKEND", "").strip().lower() or os.getenv("LLM_BACKEND", "").strip().lower()
        target_backend = existing_backend or "vllm"
        raw_mode = env_map.get("EXECUTION_MODE", "").strip().lower()

    if not target_backend and raw_mode:
        if raw_mode.startswith("cloud_"):
            target_backend = raw_mode[6:]
        elif raw_mode.startswith("local_"):
            target_backend = raw_mode[6:]
        elif raw_mode in ("ollama", "vllm", "local"):
            target_backend = raw_mode

    selected_local = (cfg.selected_local_model or cfg.ollama_model or "").strip()

    # Route desired LLM backend
    if target_backend == "ollama" or raw_mode == "local_ollama":
        env_map["LLM_BACKEND"] = "ollama"
        env_map["LLM_PROVIDER"] = "ollama"
        env_map["EXECUTION_MODE"] = "LOCAL"
        env_map["LLM_MODEL_NAME"] = selected_local or "llama3.2:3b"
        env_map["LLM_BASE_URL"] = "http://localhost:11434/v1"
    elif target_backend in ("vllm", "local") or raw_mode in ("local_vllm", "vllm", "local"):
        env_map["LLM_BACKEND"] = "vllm"
        env_map["LLM_PROVIDER"] = "vllm"
        env_map["EXECUTION_MODE"] = "LOCAL"
        if selected_local and selected_local != "llama3.2:3b":
            env_map["LLM_MODEL_NAME"] = selected_local
        else:
            env_map["LLM_MODEL_NAME"] = os.getenv("VLLM_MODEL_NAME", models.LLM_MODEL_NAME)
        env_map["VLLM_BASE_URL"] = os.getenv("VLLM_BASE_URL", "http://localhost:8002/v1")
    elif target_backend == "gemini" or raw_mode == "cloud_gemini":
        env_map["LLM_BACKEND"] = "gemini"
        env_map["LLM_PROVIDER"] = "gemini"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = models.GEMINI_MODEL_NAME
        if cfg.gemini_api_key and not is_masked_secret(cfg.gemini_api_key):
            env_map["GEMINI_API_KEY"] = cfg.gemini_api_key.strip()
    elif target_backend == "nvidia" or raw_mode == "cloud_nvidia":
        env_map["LLM_BACKEND"] = "nvidia"
        env_map["LLM_PROVIDER"] = "nvidia"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = models.NVIDIA_MODEL_NAME
    elif target_backend == "cohere" or raw_mode == "cloud_cohere":
        env_map["LLM_BACKEND"] = "cohere"
        env_map["LLM_PROVIDER"] = "cohere"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = models.COHERE_MODEL_NAME
    elif target_backend == "mistral" or raw_mode == "cloud_mistral":
        env_map["LLM_BACKEND"] = "mistral"
        env_map["LLM_PROVIDER"] = "mistral"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = models.MISTRAL_MODEL_NAME
    elif target_backend == "deepseek" or raw_mode == "cloud_deepseek":
        env_map["LLM_BACKEND"] = "deepseek"
        env_map["LLM_PROVIDER"] = "deepseek"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = models.DEEPSEEK_MODEL_NAME
        if cfg.deepseek_api_key and not is_masked_secret(cfg.deepseek_api_key):
            env_map["DEEPSEEK_API_KEY"] = cfg.deepseek_api_key.strip()
    elif target_backend == "openrouter" or raw_mode == "cloud_openrouter":
        env_map["LLM_BACKEND"] = "openrouter"
        env_map["LLM_PROVIDER"] = "openrouter"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = models.OPENROUTER_MODEL_NAME
        if cfg.openrouter_api_key and not is_masked_secret(cfg.openrouter_api_key):
            env_map["OPENROUTER_API_KEY"] = cfg.openrouter_api_key.strip()
    elif target_backend in ("openai", "gpt") or raw_mode == "cloud_openai":
        env_map["LLM_BACKEND"] = "universal"
        env_map["LLM_PROVIDER"] = "openai"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = models.OPENAI_MODEL_NAME
        env_map["CUSTOM_LLM_BASE_URL"] = "https://api.openai.com/v1"
        if cfg.openai_api_key and not is_masked_secret(cfg.openai_api_key):
            env_map["OPENAI_API_KEY"] = cfg.openai_api_key.strip()
    elif target_backend in ("anthropic", "claude") or raw_mode == "cloud_anthropic":
        env_map["LLM_BACKEND"] = "universal"
        env_map["LLM_PROVIDER"] = "anthropic"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = models.ANTHROPIC_MODEL_NAME
        if cfg.anthropic_api_key and not is_masked_secret(cfg.anthropic_api_key):
            env_map["ANTHROPIC_API_KEY"] = cfg.anthropic_api_key.strip()
    elif target_backend == "vercel" or raw_mode == "cloud_vercel":
        env_map["LLM_BACKEND"] = "vercel"
        env_map["LLM_PROVIDER"] = "vercel"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = "typesafe-ai/jev"
    elif target_backend in ("custom", "universal") or raw_mode == "cloud_custom":
        env_map["LLM_BACKEND"] = "universal"
        env_map["LLM_PROVIDER"] = "custom"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = cfg.custom_model_name or models.OPENAI_MODEL_NAME
        if cfg.custom_base_url:
            env_map["CUSTOM_LLM_BASE_URL"] = cfg.custom_base_url
            os.environ["CUSTOM_LLM_BASE_URL"] = cfg.custom_base_url
    elif raw_mode == "automatic":
        env_map["EXECUTION_MODE"] = "AUTOMATIC"
        env_map["LLM_BACKEND"] = "groq"
        env_map["LLM_PROVIDER"] = "groq"
        env_map["LLM_MODEL_NAME"] = models.GROQ_MODEL_NAME
    elif has_explicit_llm_request:  # cloud_groq explicit fallback
        env_map["LLM_BACKEND"] = "groq"
        env_map["LLM_PROVIDER"] = "groq"
        env_map["EXECUTION_MODE"] = "CLOUD"
        env_map["LLM_MODEL_NAME"] = models.GROQ_MODEL_NAME
        if cfg.groq_api_key and not is_masked_secret(cfg.groq_api_key):
            env_map["GROQ_API_KEY"] = cfg.groq_api_key.strip()
    else:
        # Preserve active backend and execution mode without forcing cloud overwrite
        if "LLM_BACKEND" not in env_map and target_backend:
            env_map["LLM_BACKEND"] = target_backend

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
        router = get_provider_router()
        from src.infrastructure.providers.router import ExecutionMode
        target_mode_str = env_map.get("EXECUTION_MODE", "AUTOMATIC").upper()
        if target_mode_str == "LOCAL":
            router.set_execution_mode(ExecutionMode.LOCAL)
            router.set_cloud_allowed(False)
        elif target_mode_str == "CLOUD":
            router.set_execution_mode(ExecutionMode.CLOUD)
            router.set_cloud_allowed(True)
        else:
            router.set_execution_mode(ExecutionMode.AUTOMATIC)
            router.set_cloud_allowed(True)
        primary_hint = (
            getattr(router, "pinned_primary_provider", None)
            or (cfg.primary_provider if cfg.primary_provider else None)
            or env_map.get("LLM_BACKEND")
        )
        router._refresh_fallback_chain(primary_hint)
        if cfg.fallback_order or cfg.disabled_providers is not None or cfg.primary_provider or cfg.routing_policy:
            router.set_routing(
                fallback_order=cfg.fallback_order,
                disabled_providers=cfg.disabled_providers,
                primary_provider=cfg.primary_provider,
                routing_policy=cfg.routing_policy,
            )
            if cfg.fallback_order:
                env_map["LLM_FALLBACK_ORDER"] = ",".join(cfg.fallback_order)
            if cfg.routing_policy:
                env_map["ROUTING_POLICY"] = cfg.routing_policy
            if cfg.primary_provider:
                env_map["RAISE_LLM_PROVIDER"] = cfg.primary_provider
                env_map["LLM_PROVIDER"] = cfg.primary_provider
    except Exception as e:
        logger.warning(f"Could not refresh provider router: {e}")

    # Update Neural Models and Acceleration Devices
    if cfg.embedding_model:
        clean_emb = cfg.embedding_model.strip()
        env_map["EMBEDDING_MODEL"] = clean_emb
        env_map["DEFAULT_EMBEDDING_MODEL"] = clean_emb
        os.environ["EMBEDDING_MODEL"] = clean_emb
        os.environ["DEFAULT_EMBEDDING_MODEL"] = clean_emb

    if cfg.reranker_model:
        clean_rerank = cfg.reranker_model.strip()
        env_map["RERANKER_MODEL"] = clean_rerank
        os.environ["RERANKER_MODEL"] = clean_rerank

    nli_target = cfg.nli_verifier_model or cfg.nli_model
    if nli_target:
        clean_nli = nli_target.strip()
        env_map["NLI_VERIFIER_MODEL"] = clean_nli
        env_map["NLI_MODEL"] = clean_nli
        os.environ["NLI_VERIFIER_MODEL"] = clean_nli
        os.environ["NLI_MODEL"] = clean_nli

    device_target = cfg.neural_device or cfg.embedding_device or cfg.reranker_device or cfg.nli_device
    if device_target:
        clean_dev = device_target.strip()
        env_map["NEURAL_DEVICE"] = clean_dev
        os.environ["NEURAL_DEVICE"] = clean_dev
        env_map["EMBEDDING_DEVICE"] = clean_dev
        os.environ["EMBEDDING_DEVICE"] = clean_dev
        env_map["RERANKER_DEVICE"] = clean_dev
        os.environ["RERANKER_DEVICE"] = clean_dev
        env_map["NLI_DEVICE"] = clean_dev
        os.environ["NLI_DEVICE"] = clean_dev

    if cfg.huggingface_token and not is_masked_secret(cfg.huggingface_token):
        hf_clean = cfg.huggingface_token.strip()
        env_map["HUGGINGFACE_TOKEN"] = hf_clean
        env_map["HF_TOKEN"] = hf_clean
        os.environ["HUGGINGFACE_TOKEN"] = hf_clean
        os.environ["HF_TOKEN"] = hf_clean

    # Update Neo4j Substrate
    if cfg.neo4j_mode:
        env_map["NEO4J_MODE"] = cfg.neo4j_mode
        os.environ["NEO4J_MODE"] = cfg.neo4j_mode
    if cfg.neo4j_mode == "cloud" and cfg.neo4j_uri:
        env_map["NEO4J_URI"] = cfg.neo4j_uri
        os.environ["NEO4J_URI"] = cfg.neo4j_uri
        if cfg.neo4j_user:
            env_map["NEO4J_USER"] = cfg.neo4j_user
            os.environ["NEO4J_USER"] = cfg.neo4j_user
        if cfg.neo4j_password:
            env_map["NEO4J_PASSWORD"] = cfg.neo4j_password
            os.environ["NEO4J_PASSWORD"] = cfg.neo4j_password
        if cfg.neo4j_database:
            env_map["NEO4J_DATABASE"] = cfg.neo4j_database
            os.environ["NEO4J_DATABASE"] = cfg.neo4j_database

    # Update Redis Substrate
    if cfg.redis_mode:
        env_map["REDIS_MODE"] = cfg.redis_mode
        os.environ["REDIS_MODE"] = cfg.redis_mode
    redis_val = cfg.redis_url or cfg.redis_uri
    if cfg.redis_mode == "cloud" and redis_val:
        env_map["REDIS_URL"] = redis_val
        os.environ["REDIS_URL"] = redis_val

    # Update Postgres Substrate (Session Memory)
    if cfg.postgres_mode:
        env_map["POSTGRES_MODE"] = cfg.postgres_mode
        os.environ["POSTGRES_MODE"] = cfg.postgres_mode
    pg_val = cfg.postgres_url or cfg.postgres_uri
    if cfg.postgres_mode == "cloud" and pg_val:
        env_map["POSTGRES_URL"] = pg_val
        env_map["DATABASE_URL"] = pg_val
        os.environ["POSTGRES_URL"] = pg_val
        os.environ["DATABASE_URL"] = pg_val

    # Mark first-time setup completed across runtime & filesystem
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
    try:
        ENV_FILE_PATH.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist to backend .env: {e}")

    try:
        ROOT_ENV_FILE_PATH.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist to root .env: {e}")

    return {
        "status": "success",
        "message": "System configuration saved and synced with active runtime.",
        "active_mode": env_map.get("LLM_BACKEND"),
        "active_model": env_map.get("LLM_MODEL_NAME"),
    }
