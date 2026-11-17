"""
RAISE Redis Session & Turn Cache Subsystem
===========================================
Purpose:
  Provides atomic, bounded turn caching (via Redis RPUSH/LTRIM) and session entity
  memory (via Redis HSET/HGETALL) for real-time multi-turn conversation threads.

Operations:
  - `get_session_messages`: Retrieves sliding window of recent conversation turns.
  - `save_session_message`: Appends turn to Redis bounded list with automated expiration.
  - `get_session_memory` / `set_session_memory`: Stores user entity variables (user_name, etc.).
  - `clear_session_messages`: Purges conversation memory for a session.

Author: RAISE Core Architecture Team
Maintainability: Keep under 180 lines with clean error resilience.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("raise.infrastructure.cache.session")


class SessionCacheMixin:
    """
    Mixin adding conversation session and entity fact persistence to RedisCacheManager.
    """

    def _make_session_messages_key(self, session_id: str) -> str:
        return f"session:{session_id}:messages"

    def _make_session_memory_key(self, session_id: str) -> str:
        return f"session:{session_id}:memory"

    def get_session_messages(self, session_id: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Ultra-fast retrieval of active conversation turns from Redis bounded list.
        """
        key = self._make_session_messages_key(session_id)
        if not self.is_connected or not self._client:
            msgs = self._memory_session_msgs.get(session_id, [])
            return msgs[-limit:] if msgs else []

        try:
            raw_items = self._client.lrange(key, -limit, -1)
            if not raw_items:
                return []
            return [json.loads(item.decode("utf-8")) for item in raw_items]
        except Exception as e:
            logger.error(f"Redis get_session_messages error: {e}")
            return []

    def save_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        mode: str = "fast",
        sources: Optional[List[str]] = None,
        max_turns: int = 20,
        ttl: int = 86400,
        latency_sec: float = 0.0,
        duration_sec: float = 0.0,
    ) -> bool:
        """
        Atomic push of turn into Redis session cache with bounded size (LTRIM) and 24h TTL.
        """
        lat = float(latency_sec or duration_sec or 0.0)
        msg_payload = {
            "role": role,
            "content": content,
            "mode": mode,
            "sources": sources or [],
            "latency_sec": lat,
            "durationSec": lat,
            "execution_time": lat,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        key = self._make_session_messages_key(session_id)
        if not self.is_connected or not self._client:
            self._memory_session_msgs.setdefault(session_id, []).append(msg_payload)
            if len(self._memory_session_msgs[session_id]) > max_turns:
                self._memory_session_msgs[session_id] = self._memory_session_msgs[session_id][-max_turns:]
            return True

        try:
            pipe = self._client.pipeline()
            pipe.rpush(key, json.dumps(msg_payload))
            pipe.ltrim(key, -max_turns, -1)
            pipe.expire(key, ttl)
            pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Redis save_session_message error: {e}")
            return False

    def get_session_memory(self, session_id: str) -> Dict[str, str]:
        """
        Retrieve session entity facts (e.g. user_name, user_role) from Redis hash.
        """
        key = self._make_session_memory_key(session_id)
        if not self.is_connected or not self._client:
            return self._memory_session_vars.get(session_id, {})

        try:
            raw_vars = self._client.hgetall(key)
            if not raw_vars:
                return {}
            return {k.decode("utf-8"): v.decode("utf-8") for k, v in raw_vars.items()}
        except Exception as e:
            logger.error(f"Redis get_session_memory error: {e}")
            return {}

    def set_session_memory(self, session_id: str, key: str, value: Any, ttl: int = 86400) -> bool:
        """
        Store session entity facts (e.g. user_name) in Redis hash with 24h TTL.
        """
        redis_key = self._make_session_memory_key(session_id)
        val_str = str(value)
        if not self.is_connected or not self._client:
            self._memory_session_vars.setdefault(session_id, {})[key] = val_str
            return True

        try:
            pipe = self._client.pipeline()
            pipe.hset(redis_key, key, val_str)
            pipe.expire(redis_key, ttl)
            pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Redis set_session_memory error: {e}")
            return False

    def clear_session_messages(self, session_id: str) -> bool:
        """
        Purge session cache and entity memory from Redis.
        """
        self._memory_session_msgs.pop(session_id, None)
        self._memory_session_vars.pop(session_id, None)
        if not self.is_connected or not self._client:
            return True

        try:
            k1 = self._make_session_messages_key(session_id)
            k2 = self._make_session_memory_key(session_id)
            self._client.delete(k1, k2)
            return True
        except Exception as e:
            logger.error(f"Redis clear_session_messages error: {e}")
            return False
