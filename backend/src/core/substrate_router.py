"""
RAISE — Modular Substrate Router (FAST / DOCKER / CLOUD)
========================================================
Centralizes connection routing for Cache, Knowledge Graph, Relational DB,
and Document Storage across Fast (FakeRedis/SQLite/NetworkX), Docker (Production),
and Cloud deployments.
"""

from __future__ import annotations

from enum import Enum
import logging
import os
from typing import Any, Dict

logger = logging.getLogger("raise.core.substrate")


class SubstrateMode(str, Enum):
    FAST = "fast"       # FakeRedis + NetworkX + SQLite + Local Disk
    DOCKER = "docker"   # Docker Redis (:6379) + Neo4j (:7687) + Postgres (:5432)
    CLOUD = "cloud"     # Cloud Redis (Upstash) + Neo4j Aura + Cloud PG + S3/R2 Storage


def get_active_substrate_mode() -> SubstrateMode:
    raw = os.getenv("RAISE_SUBSTRATE_MODE", "fast").strip().lower()
    if raw in ("docker", "prod", "production"):
        return SubstrateMode.DOCKER
    if raw in ("cloud", "remote", "aws", "gcp"):
        return SubstrateMode.CLOUD
    return SubstrateMode.FAST


def get_redis_client() -> Any:
    """Returns FakeRedis in FAST mode, Docker Redis in DOCKER mode, or Cloud Redis in CLOUD mode."""
    mode = get_active_substrate_mode()

    if mode == SubstrateMode.FAST or os.getenv("USE_FAKEREDIS", "").lower() == "true":
        try:
            import fakeredis
            logger.info("[SUBSTRATE: FAST] Initialized in-memory FakeStrictRedis.")
            return fakeredis.FakeStrictRedis(decode_responses=True)
        except ImportError:
            logger.warning("fakeredis not installed; falling back to in-memory dict cache.")
            return None

    import redis
    redis_url = (
        os.getenv("CLOUD_REDIS_URL") or os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        if mode == SubstrateMode.CLOUD
        else os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    )
    return redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)


def get_substrate_telemetry_summary(neo4j_open: bool, redis_open: bool, pg_open: bool) -> Dict[str, str]:
    """Returns formatted badge labels for status dashboards without distorting symbols."""
    mode = get_active_substrate_mode()

    if mode == SubstrateMode.FAST:
        return {
            "mode_badge": "[FAST MODE] Zero-Docker Local Engine (FakeRedis · NetworkX · SQLite)",
            "neo4j": "[FAST-MEM]  In-memory NetworkX MultiDiGraph active",
            "redis": "[FAKEREDIS] In-process FakeStrictRedis zero-latency cache",
            "postgres": "[SQLITE]    Local persistence: backend/data/raise_local.db",
            "storage": "[LOCAL-FS]  backend/data/documents + Local ChromaDB",
        }
    if mode == SubstrateMode.CLOUD:
        aura_uri = os.getenv("NEO4J_URI", "neo4j+s://aura.databases.neo4j.io")
        bucket = os.getenv("CLOUD_STORAGE_BUCKET", "s3://raise-academic-vault")
        return {
            "mode_badge": "[CLOUD MODE] Managed Cloud Storage & Remote Clusters",
            "neo4j": f"[CLOUD-GRAPH] {aura_uri}",
            "redis": "[CLOUD-REDIS] Managed TLS Cache active",
            "postgres": "[CLOUD-PG]    Managed Cloud PostgreSQL active",
            "storage": f"[CLOUD-OBJ]   {bucket}",
        }
    # DOCKER (Production Mode)
    return {
        "mode_badge": "[DOCKER PRODUCTION MODE] Full Containerized Enterprise Stack",
        "neo4j": "[DOCKER-ON] bolt://localhost:7687" if neo4j_open else "[OFFLINE]   Start container: docker start raise-neo4j",
        "redis": "[DOCKER-ON] localhost:6379" if redis_open else "[OFFLINE]   Start container: docker start raise-redis",
        "postgres": "[DOCKER-ON] localhost:5432" if pg_open else "[OFFLINE]   Start container: docker start raise-postgres",
        "storage": "[DOCKER-VOL] Persistent Volume + Local ChromaDB",
    }
