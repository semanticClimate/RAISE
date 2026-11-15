"""
RAISE Redis Cache & Session State Infrastructure
=================================================
Purpose:
  Provides sub-millisecond query response caching, semantic vector caching,
  token-bucket rate limiting, and chat session state management with a 3-tier fallback:
    1. Localhost Redis (localhost:6379)
    2. Cloud Redis (Managed Cloud Provider / Upstash / Redis Cloud)
    3. Python In-Memory Redis (fakeredis)

Architecture:
  - `src.infrastructure.cache.semantic_cache.SemanticCacheMixin`:
      Exact match + normalized cosine similarity vector search over answered queries.
  - `src.infrastructure.cache.session_cache.SessionCacheMixin`:
      Atomic push (RPUSH/LTRIM) for multi-turn chat sessions and entity key-value memory.
  - `src.infrastructure.cache.rate_limiter.TokenBucketLimiterMixin`:
      Token-bucket rate limiting per IP address.
  - `src.infrastructure.database.async_models`:
      Asynchronous SQLModel models (`SessionMetadata`, `MessageHistory`) and `get_async_engine`.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import redis
from redis.exceptions import ConnectionError as RedisConnectionError

try:
    import fakeredis
    HAS_FAKEREDIS = True
    _SHARED_FAKE_SERVER = fakeredis.FakeServer()
except ImportError:
    HAS_FAKEREDIS = False
    _SHARED_FAKE_SERVER = None

from src.infrastructure.cache.rate_limiter import TokenBucketLimiterMixin
from src.infrastructure.cache.semantic_cache import SemanticCacheMixin
from src.infrastructure.cache.session_cache import SessionCacheMixin
from src.infrastructure.database.async_models import (
    HAS_ASYNC_DB,
    MessageHistory,
    SessionMetadata,
    get_async_engine,
)
from src.storage.interfaces import ICacheStore

logger = logging.getLogger("raise.infrastructure.cache.redis")

__all__ = [
    "RedisCacheManager",
    "SessionMetadata",
    "MessageHistory",
    "get_async_engine",
    "get_redis_client",
    "HAS_ASYNC_DB",
]

_HAS_LOGGED_REDIS_CONNECTION = False


def _fast_port_open(host: str, port: int, timeout: float = 0.03) -> bool:
    """Fast loopback TCP probe to eliminate multi-second socket timeout stalls."""
    try:
        import socket
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def get_redis_client(
    local_url: Optional[str] = None,
    cloud_url: Optional[str] = None,
) -> Any:
    """
    Creates and returns a Redis client following the 3-tier storage architecture:
      Tier 1: Localhost Redis (redis://localhost:6379/0) - probed via 30ms TCP check
      Tier 2: Cloud Redis (CLOUD_REDIS_URL / REDIS_CLOUD_URL) - TLS ready (rediss://)
      Tier 3: Python In-Memory Redis (fakeredis with module-level _SHARED_FAKE_SERVER)
    """
    global _HAS_LOGGED_REDIS_CONNECTION

    storage_mode = os.getenv("RAISE_STORAGE_MODE", "auto").lower()
    is_testing = os.getenv("TESTING", "").lower() in ("true", "1")

    # Fast / In-Memory Tier: Zero socket probing, instant return
    if storage_mode in ("fast", "memory", "test") or is_testing:
        if HAS_FAKEREDIS and _SHARED_FAKE_SERVER is not None:
            try:
                client = fakeredis.FakeStrictRedis(server=_SHARED_FAKE_SERVER)
                if not _HAS_LOGGED_REDIS_CONNECTION:
                    logger.info("Connected to FakeRedis (Python Memory - Shared Server)")
                    _HAS_LOGGED_REDIS_CONNECTION = True
                return client
            except Exception as exc:
                logger.debug("FakeStrictRedis init failed: %s", exc)
        return None

    local_url = local_url or os.getenv("LOCAL_REDIS_URL") or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
    cloud_url = cloud_url or os.getenv("CLOUD_REDIS_URL") or os.getenv("REDIS_CLOUD_URL")

    # Tier 2: Cloud-only preference
    if storage_mode == "cloud" and cloud_url:
        try:
            client = redis.Redis.from_url(cloud_url, socket_timeout=2.0)
            client.ping()
            if not _HAS_LOGGED_REDIS_CONNECTION:
                logger.info("Connected to Cloud Redis at %s", cloud_url)
                _HAS_LOGGED_REDIS_CONNECTION = True
            return client
        except (RedisConnectionError, Exception) as exc:
            logger.debug("Cloud Redis connection failed: %s. Falling back to FakeRedis...", exc)

    # Tier 1: Local Redis (Docker or Host Daemon)
    # Perform fast 30ms TCP check to eliminate 2-second socket timeout stalls
    host = "127.0.0.1"
    port = 6379
    if local_url and "://" in local_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(local_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 6379
        except Exception:
            pass

    if _fast_port_open(host, port, timeout=0.03):
        try:
            client = redis.Redis.from_url(local_url, socket_timeout=1.5)
            client.ping()
            if not _HAS_LOGGED_REDIS_CONNECTION:
                logger.info("Connected to Local Redis at %s", local_url)
                _HAS_LOGGED_REDIS_CONNECTION = True
            return client
        except (RedisConnectionError, Exception) as exc:
            logger.debug("Local Redis failed (%s). Falling back to Cloud / Memory...", exc)

    # Tier 2: Cloud Redis Fallback (if configured and not already tried)
    if cloud_url and storage_mode != "cloud":
        try:
            client = redis.Redis.from_url(cloud_url, socket_timeout=2.0)
            client.ping()
            if not _HAS_LOGGED_REDIS_CONNECTION:
                logger.info("Connected to Cloud Redis at %s", cloud_url)
                _HAS_LOGGED_REDIS_CONNECTION = True
            return client
        except (RedisConnectionError, Exception) as exc:
            logger.debug("Cloud Redis failed (%s). Falling back to FakeRedis...", exc)

    # Tier 3: Python In-Memory Redis (fakeredis with shared FakeServer singleton)
    if HAS_FAKEREDIS and _SHARED_FAKE_SERVER is not None:
        try:
            client = fakeredis.FakeStrictRedis(server=_SHARED_FAKE_SERVER)
            if not _HAS_LOGGED_REDIS_CONNECTION:
                logger.info("Connected to FakeRedis (Python Memory - Shared Server)")
                _HAS_LOGGED_REDIS_CONNECTION = True
            return client
        except Exception as exc:
            logger.warning("FakeRedis initialization failed: %s", exc)

    return None


class RedisCacheManager(SemanticCacheMixin, SessionCacheMixin, TokenBucketLimiterMixin, ICacheStore):
    """
    Sub-millisecond query response cache using Redis with 3-tier fallback
    (Localhost -> Cloud -> FakeRedis in-memory).
    """

    _instance: Optional[RedisCacheManager] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not args and not kwargs and cls._instance is not None:
            return cls._instance
        with cls._lock:
            if not args and not kwargs and cls._instance is not None:
                return cls._instance
            instance = super().__new__(cls)
            if not args and not kwargs:
                cls._instance = instance
            return instance

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: int = 0,
    ):
        if getattr(self, "_initialized", False):
            return

        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = int(port or os.getenv("REDIS_PORT", "6379"))
        self.db = db

        self.tier: str = "memory"
        self.is_connected: bool = False
        self._client: Optional[Any] = None

        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._memory_session_msgs: Dict[str, List[Dict[str, Any]]] = {}
        self._memory_session_vars: Dict[str, Dict[str, str]] = {}
        self._memory_semantic_cache: Dict[str, Dict[str, Any]] = {}

        self._connect()
        self._initialized = True

    def _connect(self):
        local_url = os.getenv("LOCAL_REDIS_URL") or os.getenv("REDIS_URL") or f"redis://{self.host}:{self.port}/{self.db}"
        self._client = get_redis_client(local_url=local_url)

        if self._client is not None:
            self.is_connected = True
            is_fake = False
            if HAS_FAKEREDIS:
                fake_classes = tuple(
                    cls for cls in (getattr(fakeredis, "FakeRedis", None), getattr(fakeredis, "FakeStrictRedis", None))
                    if cls is not None
                )
                if fake_classes and isinstance(self._client, fake_classes):
                    is_fake = True
            if is_fake:
                self.tier = "memory"
            else:
                self.tier = "local"
        else:
            self.is_connected = False
            self.tier = "memory"

    def _make_completion_key(
        self,
        query: str,
        mode: str,
        library: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
    ) -> str:
        q_norm = query.strip().lower()
        lib_tag = f":{library}" if library else ""
        doc_tag = f":{','.join(sorted(active_docs))}" if active_docs else ":empty"
        import hashlib
        q_hash = hashlib.sha256(f"{q_norm}{doc_tag}".encode("utf-8")).hexdigest()[:16]
        return f"cache:completion:{mode}{lib_tag}:{q_hash}"

    def _make_vector_key(self, vector_id: str) -> str:
        return f"cache:vector:{vector_id}"

    def _make_rate_key(self, ip_address: str) -> str:
        return f"rate:bucket:{ip_address}"

    def _make_job_key(self, job_id: str) -> str:
        return f"job:status:{job_id}"

    def _make_key(
        self,
        query: str,
        mode: str,
        library: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
    ) -> str:
        return self._make_completion_key(query, mode, library, active_docs=active_docs)

    def get(
        self,
        query: str,
        mode: str,
        library: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        return self.get_completion(query, mode, library, active_docs=active_docs)

    def get_completion(
        self,
        query: str,
        mode: str,
        library: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        key = self._make_completion_key(query, mode, library, active_docs=active_docs)
        if not self.is_connected or not self._client:
            item = self._memory_cache.get(key)
            if item and item.get("expires_at", 0) > time.time():
                return item.get("data")
            return None

        try:
            cached_val = self._client.get(key)
            if cached_val:
                return json.loads(cached_val.decode("utf-8") if isinstance(cached_val, bytes) else cached_val)
        except Exception as e:
            logger.error("Redis get completion error for %s: %s", key, e)
        return None

    def set(
        self,
        query: str,
        mode: str,
        data: Dict[str, Any],
        library: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
        ttl: int = 86400,
    ) -> bool:
        return self.set_completion(query, mode, data, library, active_docs=active_docs, ttl=ttl)

    def set_completion(
        self,
        query: str,
        mode: str,
        result: Dict[str, Any],
        library: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
        ttl: int = 86400,
    ) -> bool:
        key = self._make_completion_key(query, mode, library, active_docs=active_docs)
        if not self.is_connected or not self._client:
            self._memory_cache[key] = {
                "data": result,
                "expires_at": time.time() + ttl,
            }
            return True

        try:
            payload = json.dumps(result)
            self._client.set(key, payload, ex=ttl)
            return True
        except Exception as e:
            logger.error("Redis set completion error for %s: %s", key, e)
            return False

    def publish_abort(self, session_id: Optional[str], request_id: Optional[str] = None) -> bool:
        """Publishes chat cancellation signal across worker processes via Redis Pub/Sub."""
        payload = json.dumps({"session_id": session_id, "request_id": request_id, "timestamp": time.time()})
        if self.is_connected and self._client:
            try:
                self._client.publish("channel:chat:abort", payload)
                return True
            except Exception as e:
                logger.debug("Redis publish abort error: %s", e)
        return False

    def get_vector(self, vector_id: str) -> Optional[List[float]]:
        key = self._make_vector_key(vector_id)
        if not self.is_connected or not self._client:
            item = self._memory_cache.get(key)
            if item and item.get("expires_at", 0) > time.time():
                return item.get("data")
            return None
        try:
            val = self._client.get(key)
            if val:
                return json.loads(val.decode("utf-8") if isinstance(val, bytes) else val)
        except Exception as e:
            logger.error("Redis vector get error: %s", e)
        return None

    def set_vector(self, vector_id: str, vector: List[float], ttl: int = 604800) -> bool:
        key = self._make_vector_key(vector_id)
        if not self.is_connected or not self._client:
            self._memory_cache[key] = {"data": vector, "expires_at": time.time() + ttl}
            return True
        try:
            self._client.set(key, json.dumps(vector), ex=ttl)
            return True
        except Exception as e:
            logger.error("Redis vector set error: %s", e)
            return False

    def set_job_status(self, job_id: str, status_data: Dict[str, Any], ttl: int = 10800) -> bool:
        key = self._make_job_key(job_id)
        if not self.is_connected or not self._client:
            self._memory_cache[key] = {"data": status_data, "expires_at": time.time() + ttl}
            return True
        try:
            self._client.set(key, json.dumps(status_data), ex=ttl)
            return True
        except Exception as e:
            logger.error("Redis set job status error: %s", e)
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        key = self._make_job_key(job_id)
        if not self.is_connected or not self._client:
            item = self._memory_cache.get(key)
            if item and item.get("expires_at", 0) > time.time():
                return item.get("data")
            return None
        try:
            val = self._client.get(key)
            if val:
                return json.loads(val.decode("utf-8") if isinstance(val, bytes) else val)
        except Exception as e:
            logger.error("Redis get job status error: %s", e)
        return None

    def clear(self) -> bool:
        self._memory_cache.clear()
        self._memory_session_msgs.clear()
        self._memory_session_vars.clear()
        self._memory_semantic_cache.clear()
        if not self.is_connected or not self._client:
            return True
        try:
            self._client.flushdb()
            return True
        except Exception as e:
            logger.error("Redis clear error: %s", e)
            return False
