"""
RAISE System & Control Center API Router
========================================
Modular API router for system telemetry, runtime configuration, dynamic LLM
discovery, database connectivity probes, and pre-flight neural asset downloads.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status, Body
from fastapi.responses import StreamingResponse

from src.features.system import (
    SystemConfigRequest,
    ModelPullRequest,
    PreflightDownloadRequest,
    RoutingUpdateRequest,
    get_hardware_telemetry as _probe_hardware_telemetry,
    test_all_connections as _probe_all_connections,
    get_preflight_assets as _get_preflight_assets,
    trigger_asset_download as _trigger_asset_download,
    stream_model_pull as _stream_model_pull,
    get_current_configuration as _get_current_configuration,
    save_configuration as _save_configuration,
    mask_secret as _mask_secret,
)

logger = logging.getLogger("raise.api.system")

router = APIRouter(prefix="/api/system", tags=["System & Control Center"])


@router.get("/hardware")
async def get_hardware_telemetry() -> Dict[str, Any]:
    """Dynamically probes host CPU, RAM, GPU, and checks local AI engine liveness."""
    return _probe_hardware_telemetry()


@router.get("/config")
async def get_current_configuration() -> Dict[str, Any]:
    """Returns current active system configuration with sensitive keys masked and dynamic providers listed."""
    return _get_current_configuration()


@router.post("/config")
async def save_configuration(cfg: SystemConfigRequest) -> Dict[str, Any]:
    """Updates runtime environment and writes updates safely to .env file."""
    try:
        return _save_configuration(cfg)
    except Exception as e:
        logger.error(f"Failed to update configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration update failed: {str(e)}",
        )


@router.get("/dynamic-llms")
async def get_dynamic_llms() -> List[Dict[str, Any]]:
    """Returns list of dynamically available LLMs based on active hardware and configured API keys."""
    from src.infrastructure.providers.router import get_provider_router
    p_router = get_provider_router()
    return p_router.get_dynamic_available_providers()


@router.get("/routing", operation_id="get_system_routing")
async def get_system_routing() -> Dict[str, Any]:
    """Returns the live LLM routing policy, fallback priority order, disabled providers, and health."""
    from src.infrastructure.providers.router import get_provider_router
    return get_provider_router().get_routing_status()


@router.post("/routing", operation_id="post_system_routing")
async def update_system_routing(req: RoutingUpdateRequest) -> Dict[str, Any]:
    """
    Applies user drag-and-drop fallback priority ordering, primary selection, and provider deactivation.
    Updates the live ProviderRouter in memory immediately and persists changes to .env.
    """
    from src.infrastructure.providers.router import get_provider_router
    p_router = get_provider_router()
    result = p_router.set_routing(
        fallback_order=req.fallback_order,
        disabled_providers=req.disabled_providers,
        primary_provider=req.primary_provider,
        routing_policy=req.routing_policy,
    )

    # Persist priority order and provider choice to .env
    try:
        from src.features.system.config_service import save_configuration
        from src.features.system.schemas import SystemConfigRequest
        save_configuration(SystemConfigRequest(
            primary_provider=result.get("primary_provider"),
            fallback_order=result.get("fallback_chain"),
            disabled_providers=result.get("disabled_providers"),
            routing_policy=result.get("routing_policy"),
            llm_backend=result.get("primary_provider"),
        ))
    except Exception as e:
        logger.warning(f"Could not persist routing to .env: {e}")

    return {
        "status": "success",
        "success": True,
        "message": f"LLM Routing Priority applied: '{result.get('primary_provider')}' is now Primary.",
        "primary_provider": result.get("primary_provider"),
        "pinned_primary_provider": result.get("pinned_primary_provider"),
        "fallback_order": result.get("fallback_order") or result.get("fallback_chain"),
        "fallback_chain": result.get("fallback_chain"),
        "disabled_providers": result.get("disabled_providers"),
        "routing_policy": result.get("routing_policy"),
        "providers": result.get("providers"),
        "routing": result,
    }


@router.get("/test-connections", operation_id="get_system_test_connections")
@router.post("/test-connections", operation_id="post_system_test_connections")
async def test_system_connections(req: Optional[SystemConfigRequest] = None) -> Dict[str, Any]:
    """
    Probes live connectivity for Neo4j, Redis, PostgreSQL, ChromaDB, and LLM inference.
    Executes honest network/socket handshakes with timeouts so status never turns
    green prematurely when substrates are offline or unconfigured.
    """
    return _probe_all_connections(req)


@router.post("/test-llm-key", operation_id="post_system_test_llm_key")
async def test_llm_key_endpoint(req: Optional[SystemConfigRequest] = None) -> Dict[str, Any]:
    """Tests ONLY LLM API key credentials without blocking on database connections."""
    from src.features.system.connection_service import test_llm_connection
    return {"llm": test_llm_connection(req)}


@router.get("/preflight-assets")
async def get_preflight_assets() -> Dict[str, Any]:
    """
    Returns live verification status and dynamically calculated disk footprint
    for all required neural assets and runtime engines.
    """
    return _get_preflight_assets()


@router.post("/download-assets")
async def trigger_asset_download(req: Optional[PreflightDownloadRequest] = None) -> Dict[str, Any]:
    """Triggers background parallel download of any missing neural model weights."""
    return _trigger_asset_download(req)


@router.post("/models/pull")
async def pull_model_stream(req: ModelPullRequest):
    """
    Streams SSE progress frames for model ingestion / pull.
    Compatible with frontend platformAdapter.pullModel.
    """
    return StreamingResponse(
        _stream_model_pull(
            req.model_name,
            provider=getattr(req, "provider", "huggingface") or "huggingface",
            hf_token=getattr(req, "huggingface_token", None)
        ),
        media_type="text/event-stream"
    )


@router.get("/models", operation_id="get_system_models")
async def get_system_models(include_catalog: bool = False) -> Dict[str, Any]:
    """
    Dynamic model registry endpoint consumed by frontend useDynamicModels.
    Returns actively available live models and discovered models with zero hardcoding.
    """
    from src.infrastructure.providers.router import get_provider_router
    p_router = get_provider_router()
    avail = p_router.get_dynamic_available_providers()
    return {
        "status": "success",
        "models": avail,
        "dynamic_llms": avail,
        "count": len(avail),
    }


@router.get("/models/discovered", operation_id="get_system_models_discovered")
@router.get("/models-discovered", operation_id="get_system_models_discovered_alias")
async def get_discovered_models(provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns dynamically discovered live models directly queried from configured provider APIs.
    Backed by ModelDiscoveryEngine with zero hardcoded model registries.
    """
    from src.infrastructure.llm.model_discovery import get_model_discovery_engine
    from src.infrastructure.credentials.manager import get_credential_manager
    engine = get_model_discovery_engine()
    cm = get_credential_manager()

    if provider:
        models = engine.discover_provider_models(provider)
        return {
            "provider": provider,
            "configured": cm.get_credential_status(provider) == "configured",
            "models": models,
        }

    discovered = engine.discover_all()

    return {
        "providers": discovered,
        "total_models": sum(len(m) for m in discovered.values()),
    }


@router.get("/models/catalog")
async def get_models_catalog() -> List[Dict[str, Any]]:
    """
    Returns dynamic, real-time open-source LLM catalog fetched from public
    model registries (HuggingFace Hub / OpenRouter) and local daemons.
    Zero hardcoded model catalogs.
    """
    from src.features.system import get_dynamic_model_catalog
    return get_dynamic_model_catalog()


@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """Returns real-time status of all backend subsystems and configuration."""
    return _get_current_configuration()


# Backward compatibility aliases
test_connections = test_system_connections
_mask_secret = _mask_secret

@router.post("/substrates/provision")
@router.post("/provision-substrate")
async def provision_substrate_endpoint(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    On-demand substrate provisioning for Neo4j, Redis, or PostgreSQL.
    Automatically checks and starts required Docker containers or cleanly falls back.
    """
    substrate = payload.get("substrate") or payload.get("name") or "neo4j"
    from src.features.system.connection_service import auto_provision_substrate
    return auto_provision_substrate(substrate)


@router.api_route("/providers/verify", methods=["GET", "POST"])
@router.api_route("/test-provider", methods=["GET", "POST"])
@router.api_route("/test-key", methods=["GET", "POST"])
async def verify_provider_key(
    payload: Optional[Dict[str, Any]] = Body(None),
    provider: Optional[str] = None,
    key: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Live verification of a specific cloud LLM API key (Groq, Gemini, OpenAI, Anthropic, DeepSeek, OpenRouter).
    Accepts payload via JSON Body (POST) or query parameters (GET/POST).
    """
    body = payload or {}
    prov = body.get("provider") or provider or "gemini"
    resolved_key = body.get("api_key") or body.get("key") or api_key or key or ""
    from src.features.system.connection_service import probe_cloud_llm_key
    return probe_cloud_llm_key(prov, resolved_key)


@router.post("/models/load", operation_id="post_system_models_load")
async def load_and_prewarm_neural_models(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Dynamically loads and prewarms requested embedding, reranker, and NLI verifier models.
    """
    try:
        from core_registry import ModelConfigRequest, load_and_prewarm_models
        from src.core.config import models
        m_cfg = ModelConfigRequest(
            embedder_id=payload.get("embedding_model") or payload.get("embedder_id") or models.EMBEDDING_MODEL_NAME,
            reranker_id=payload.get("reranker_model") or payload.get("reranker_id") or models.RERANKER_MODEL_NAME,
            verifier_id=payload.get("nli_verifier_model") or payload.get("verifier_id") or models.NLI_MODEL_NAME,
            hf_token=payload.get("huggingface_token") or payload.get("hf_token"),
        )
        res = load_and_prewarm_models(m_cfg)
        return {
            "status": "success",
            "message": "Models loaded and prewarmed successfully.",
            "data": res,
        }
    except Exception as e:
        logger.warning(f"Error loading and prewarming models: {e}")
        return {
            "status": "error",
            "message": f"Failed to prewarm neural models: {str(e)}",
        }
