"""
RAISE Token Bucket Rate Limiter Subsystem
==========================================
Purpose:
  Provides atomic token-bucket rate limiting across API endpoints using Redis hashes
  with an in-memory fallback.

Algorithm:
  Evaluates elapsed time since last request, refills tokens according to `refill_per_sec`,
  caps at `max_tokens`, and decrements 1 token per admitted request.

Author: RAISE Core Architecture Team
Maintainability: Keep under 120 lines with robust pipeline operations.
"""

from __future__ import annotations
import time
import logging
from typing import Optional, Tuple

logger = logging.getLogger("raise.infrastructure.cache.rate_limiter")


class TokenBucketLimiterMixin:
    """
    Mixin providing atomic Token Bucket rate limiting.
    """

    def check_rate_limit(self, ip_address: str = "", max_tokens: int = 60, refill_per_sec: float = 1.0, client_ip: Optional[str] = None) -> Tuple[bool, int]:
        """
        Token Bucket rate-limiting algorithm per system-architecture.md Section 4.1.
        Returns (is_allowed, remaining_tokens).
        """
        target_ip = ip_address or client_ip or "127.0.0.1"
        key = self._make_rate_key(target_ip)
        now = time.time()

        if not self.is_connected or not self._client:
            # In-memory Token Bucket fallback
            bucket = self._memory_cache.get(key)
            if not bucket or not isinstance(bucket.get("data"), dict):
                bucket = {"data": {"tokens": max_tokens, "last_updated": now}, "expires_at": now + 3600}
                self._memory_cache[key] = bucket

            data = bucket["data"]
            elapsed = now - data.get("last_updated", now)
            tokens = min(max_tokens, data.get("tokens", max_tokens) + elapsed * refill_per_sec)
            data["last_updated"] = now

            if tokens >= 1.0:
                data["tokens"] = tokens - 1.0
                return True, int(data["tokens"])
            else:
                data["tokens"] = tokens
                return False, 0

        try:
            # Atomic evaluation via Redis hash
            pipe = self._client.pipeline()
            pipe.hgetall(key)
            results = pipe.execute()
            data = results[0] or {}

            last_updated = float(data.get(b"last_updated", now))
            tokens = float(data.get(b"tokens", max_tokens))

            elapsed = now - last_updated
            tokens = min(max_tokens, tokens + elapsed * refill_per_sec)

            if tokens >= 1.0:
                new_tokens = tokens - 1.0
                p2 = self._client.pipeline()
                p2.hset(key, mapping={"tokens": str(new_tokens), "last_updated": str(now)})
                p2.expire(key, 3600)
                p2.execute()
                return True, int(new_tokens)
            else:
                p2 = self._client.pipeline()
                p2.hset(key, mapping={"tokens": str(tokens), "last_updated": str(now)})
                p2.expire(key, 3600)
                p2.execute()
                return False, 0
        except Exception as e:
            logger.error(f"Rate limiting check error: {e}")
            return True, max_tokens
