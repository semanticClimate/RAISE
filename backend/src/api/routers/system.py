"""
RAISE System & Control Center API Router
========================================
Modular API router for system telemetry, runtime configuration, dynamic LLM
discovery, database connectivity probes, and pre-flight neural asset downloads.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from src.features.system import (
    SystemConfigRequest,
    ModelPullRequest,
    PreflightDownloadRequest,
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
    Returns live verification status and disk footprint for all 6 required
    neural assets and runtime engines (~4.6 GB Total Footprint).
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
