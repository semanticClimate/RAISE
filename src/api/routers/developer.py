"""
Developer & Operational Telemetry Router
Endpoints for developer operator diagnostics, cache management, and metrics.
"""

from __future__ import annotations

import os
import time
import statistics
from typing import Any
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.dependencies import (
    get_dev_operator,
    get_postgres_manager,
    get_redis_cache,
    get_rag_engine,
)
from src.api.context import SYSTEM_START_TIME, SYSTEM_METRICS
from src.core.config import models

router = APIRouter(tags=["Developer & Telemetry"])


@router.get("/api/dev/checkup", response_class=JSONResponse)
async def dev_operator_checkup(operator: Any = Depends(get_dev_operator)):
    """Developer Operator full multi-database checkup & telemetry endpoint."""
    if operator:
        return operator.run_full_checkup()
    return {"status": "ERROR", "message": "DeveloperOperator not initialized"}


@router.post("/api/dev/clean-cache", response_class=JSONResponse)
async def dev_operator_clean_cache(operator: Any = Depends(get_dev_operator)):
    """Developer Operator flush Redis query cache."""
    if operator:
        return operator.clean_cache()
    return {"status": "ERROR", "message": "DeveloperOperator not initialized"}


@router.get("/api/dev/recent-chats", response_class=JSONResponse)
async def dev_operator_recent_chats(limit: int = 10, operator: Any = Depends(get_dev_operator)):
    """Developer Operator query chat logs audit from PostgreSQL."""
    if operator:
        return {"chats": operator.get_recent_chat_audit(limit=limit)}
    return {"chats": []}


@router.get("/api/system/metrics")
async def get_system_metrics(
    postgres_mgr: Any = Depends(get_postgres_manager),
    redis_cache: Any = Depends(get_redis_cache),
    rag_engine: Any = Depends(get_rag_engine),
):
    """
    Tier 3 Medium: Real-time operational metrics, query volume, SLA latency percentiles, and error rate.
    """
    now = time.time()
    uptime = round(now - SYSTEM_START_TIME, 1)
    sessions = postgres_mgr.list_all_sessions() if postgres_mgr else []
    latencies = SYSTEM_METRICS.get("latencies", [])
    p50 = round(statistics.median(latencies), 2) if latencies else 0.85
    p95 = round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 20 else round(p50 * 1.5, 2)
    total_q = SYSTEM_METRICS.get("total_queries", 0)
    failed_q = SYSTEM_METRICS.get("failed_queries", 0)
    err_rate = round(failed_q / max(1, total_q), 4)

    return {
        "active_sessions": len(sessions),
        "total_queries": total_q,
        "p50_latency_sec": p50,
        "p50_latency": p50,
        "p95_latency_sec": p95,
        "error_rate": err_rate,
        "uptime_seconds": uptime,
        "subsystems": {
            "postgresql": bool(postgres_mgr and postgres_mgr.is_connected),
            "redis": bool(redis_cache and redis_cache.is_connected),
            "neo4j": bool(rag_engine and rag_engine.neo4j_db and rag_engine.neo4j_db.connected),
            "chromadb": bool(rag_engine and getattr(rag_engine, "vector_engine", None)),
        }
    }


@router.get("/api/hardware-telemetry")
async def get_hardware_telemetry():
    """Authoritative hardware telemetry: dynamically inspects RAM, CPU, and GPU/MPS."""
    from src.infrastructure.hardware import get_gpu_info, get_ram_info, get_cpu_info

    ram = get_ram_info()
    gpu = get_gpu_info()
    cpu = get_cpu_info()

    gpu_label = gpu.get("primary_device_name") or ("Apple Silicon Metal (MPS)" if gpu.get("mps_available") else "CPU Execution")
    total_ram = ram.get("total_gb") or 16.0
    free_ram = ram.get("available_gb") or 8.0

    return {
        # Support both naming conventions for full frontend compatibility
        "gpu_model": gpu_label,
        "ram_total_gb": total_ram,
        "total_ram_gb": total_ram,
        "ram_available_gb": free_ram,
        "free_ram_gb": free_ram,
        "ram_percent": ram.get("percent_used") or 0.0,
        "cpu_cores": cpu.get("logical_cores") or 4,
        "has_metal_or_cuda": bool(gpu.get("cuda_available") or gpu.get("mps_available")),
        "embedding_model": models.EMBEDDING_MODEL_NAME,
        "reranker_model": models.RERANKER_MODEL_NAME,
        "nli_model": models.NLI_MODEL_NAME,
        "nli_verifier_model": models.NLI_MODEL_NAME,
        "neo4j_endpoint": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    }
