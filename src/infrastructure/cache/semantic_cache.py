"""
RAISE Redis Semantic Cache Subsystem
=====================================
Purpose:
  Provides semantic vector-similarity query caching on top of Redis and in-memory fallbacks.
  If an incoming user prompt has high cosine similarity (>= threshold, default 0.95)
  with a previously answered query in the same operational mode, retrieves cached result directly.

Architecture:
  - Exact match lookup first.
  - Candidate retrieval from Redis set 'cache:semantic:keys' or memory fallback.
  - Normalized dot-product / cosine similarity scoring across query embeddings.
  - Bounded in-memory LRU ring (200 entries) when Redis is disconnected.

Author: RAISE Core Architecture Team
Maintainability: Keep under 200 lines with clean typing and logging.
"""

from __future__ import annotations
import json
import time
import logging
from typing import Any, Dict, List, Optional

try:
    import gptcache
    HAS_GPTCACHE = True
except Exception:
    gptcache = None
    HAS_GPTCACHE = False

logger = logging.getLogger("raise.infrastructure.cache.semantic")


class SemanticCacheMixin:
    """
    Mixin adding GPTCache and vector similarity caching capabilities to RedisCacheManager.
    """

    def semantic_get(
        self,
        query: str,
        mode: str,
        embedding: Optional[List[float]],
        threshold: float = 0.95,
        library: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached response by exact match first, then by embedding cosine similarity (> threshold).
        Returns matching cached payload or None.
        """
        # 1. Exact match check
        exact = self.get_completion(query, mode=mode, library=library, active_docs=active_docs)
        if exact:
            return exact

        if not embedding:
            return None

        candidates = []
        if self.is_connected and self._client:
            try:
                keys = self._client.smembers("cache:semantic:keys")
                if keys:
                    for k in list(keys)[-100:]:
                        k_str = k.decode("utf-8") if isinstance(k, bytes) else k
                        val = self._client.get(k_str)
                        if val:
                            try:
                                candidates.append(json.loads(val.decode("utf-8")))
                            except Exception:
                                pass
            except Exception as e:
                logger.debug(f"Redis semantic get lookup error: {e}")

        if not candidates and hasattr(self, "_memory_semantic_cache"):
            candidates = list(self._memory_semantic_cache.values())

        if not candidates:
            return None

        # Dot-product similarity across unit-normalized embeddings
        best_score = -1.0
        best_match = None

        def dot_product(v1, v2):
            return sum(a * b for a, b in zip(v1, v2))

        norm_req_docs = sorted(list(set(active_docs or [])))

        for cand in candidates:
            if cand.get("mode") != mode:
                continue
            # Scope validation: Enforce exact matching of library and active document scopes
            if library is not None and cand.get("library") != library:
                continue
            cand_docs = sorted(list(set(cand.get("active_docs") or [])))
            if cand_docs != norm_req_docs:
                continue

            cand_emb = cand.get("embedding")
            if not cand_emb or len(cand_emb) != len(embedding):
                continue
            sim = dot_product(embedding, cand_emb)
            if sim > best_score:
                best_score = sim
                best_match = cand

        # Safeguard: Prevent semantic cache from trapping follow-up clarifying queries with specificity shifts (e.g. "give me the names of..." vs "overview")
        effective_threshold = threshold
        q_lower = query.lower()
        cand_q = str(best_match.get("query") if best_match else "").lower()
        has_q_spec = any(kw in q_lower for kw in ["name", "names", "list", "who", "which", "give me", "specifically", "detail"])
        has_cand_spec = any(kw in cand_q for kw in ["name", "names", "list", "who", "which", "give me", "specifically", "detail"])
        if has_q_spec != has_cand_spec:
            effective_threshold = max(threshold, 0.985)

        if best_score >= effective_threshold and best_match:
            logger.info(f"Redis Semantic Cache HIT (similarity: {best_score:.4f} >= {effective_threshold}) for '{query[:40]}'")
            return best_match.get("data")

        return None

    def semantic_set(
        self,
        query: str,
        result: Optional[Dict[str, Any]] = None,
        mode: str = "fast",
        embedding: Optional[List[float]] = None,
        library: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
        ttl: int = 86400,
        data: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Stores response in both exact key cache and semantic similarity candidate index.
        """
        payload = result if result is not None else (data or {})
        effective_ttl = ttl_seconds if ttl_seconds is not None else ttl
        self.set_completion(query, mode, payload, library=library, active_docs=active_docs, ttl=effective_ttl)

        if not embedding:
            return True

        if not hasattr(self, "_memory_semantic_cache"):
            self._memory_semantic_cache = {}

        import hashlib
        q_hash = hashlib.sha256(f"{query.strip().lower()}:{mode}".encode("utf-8")).hexdigest()[:16]
        entry = {
            "query": query,
            "mode": mode,
            "embedding": embedding,
            "library": library,
            "active_docs": active_docs or [],
            "data": payload,
            "created_at": time.time(),
        }

        # Memory fallback (bounded to 200 items)
        if len(self._memory_semantic_cache) > 200:
            oldest_k = next(iter(self._memory_semantic_cache))
            self._memory_semantic_cache.pop(oldest_k, None)
        self._memory_semantic_cache[q_hash] = entry

        if self.is_connected and self._client:
            try:
                sem_key = f"cache:semantic:{mode}:{q_hash}"
                self._client.set(sem_key, json.dumps(entry), ex=ttl)
                self._client.sadd("cache:semantic:keys", sem_key)
            except Exception as e:
                logger.debug(f"Redis semantic set error: {e}")

        return True
