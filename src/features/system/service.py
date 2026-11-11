"""
RAISE Developer & Database Operator Engine
==========================================
Component: `src.features.system.service`
Architecture Layer: System / Operational Telemetry & Management

Overview:
---------
Comprehensive diagnostic, telemetry, health-checking, and maintenance tool
for the multi-database stack (PostgreSQL, Redis, Neo4j, ChromaDB, vLLM).

Modular Architecture:
---------------------
- Component Health Checks: `src.features.system.health_checks`
- Document Alignment & Integrity Audits: `src.features.system.audit_service`
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.core.config import settings
from src.infrastructure.cache.redis import RedisCacheManager
from src.infrastructure.database.postgres import PostgresManager
from src.infrastructure.graph.neo4j import Neo4jDatabase
from src.infrastructure.vector.chroma import LocalVectorEngine

# Modular mixin imports
from .health_checks import SystemHealthChecksMixin
from .audit_service import SystemAuditMixin

logger = logging.getLogger("raise.system.operator")


class DeveloperOperator(SystemHealthChecksMixin, SystemAuditMixin):
    """
    Central Developer Operator for system telemetry, multi-database integrity audits,
    and administrative maintenance.
    """

    def __init__(
        self,
        postgres_mgr: Optional[PostgresManager] = None,
        redis_mgr: Optional[RedisCacheManager] = None,
        neo4j_db: Optional[Neo4jDatabase] = None,
        vector_engine: Optional[LocalVectorEngine] = None,
    ):
        self.postgres = postgres_mgr or PostgresManager()
        self.redis = redis_mgr or RedisCacheManager()
        self.neo4j = neo4j_db or Neo4jDatabase()
        self.vector_engine = vector_engine or LocalVectorEngine()
        self.bin_dir = settings.project_root.parent / "bin"
        self.docs_dir = settings.documents_dir

    def run_full_checkup(self) -> Dict[str, Any]:
        """
        Executes complete multi-database checkup and aggregates telemetry.
        """
        t_start = time.time()
        pg = self.check_postgresql()
        rd = self.check_redis()
        neo = self.check_neo4j()
        chroma = self.check_chromadb()
        vllm = self.check_vllm()
        cf = self.check_cloudflare()
        alignment = self.audit_document_alignment()

        all_ok = all(
            item.get("status") == "PASS"
            for item in [pg, rd, neo, chroma, vllm, cf]
        )

        return {
            "operator_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "overall_status": "ALL_SYSTEMS_OPERATIONAL" if all_ok else "SYSTEMS_ATTENTION_REQUIRED",
            "checkup_duration_ms": round((time.time() - t_start) * 1000, 2),
            "databases": {
                "postgresql": pg,
                "redis": rd,
                "neo4j": neo,
                "chromadb": chroma,
            },
            "inference": {
                "vllm": vllm,
            },
            "networking": {
                "cloudflare_tunnel": cf,
            },
            "document_alignment": alignment,
        }

    def clean_cache(self) -> Dict[str, Any]:
        """Flush Redis response cache."""
        ok = self.redis.clear()
        return {"status": "success" if ok else "failed", "message": "Redis query cache cleared."}
