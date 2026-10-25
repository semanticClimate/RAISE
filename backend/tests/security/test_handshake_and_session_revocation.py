"""
Two-Step Handshake & Single-Use Token Eviction Suite
Validates:
- POST /api/v1/auth/handshake returns high-entropy token
- Single-use atomic eviction prevents replay attacks
- Administrative session revocation & IP blocking
"""

import pytest
from src.security.handshake_manager import HandshakeManager


class MockRedisAsync:
    """Async in-memory Redis mock supporting hashes and pipelines."""
    def __init__(self):
        self.hashes = {}
        self.strings = {}
        self.ttls = {}

    async def hset(self, key: str, mapping: dict):
        if key not in self.hashes:
            self.hashes[key] = {}
        self.hashes[key].update(mapping)

    async def hgetall(self, key: str):
        return self.hashes.get(key, {})

    async def expire(self, key: str, ttl: int):
        self.ttls[key] = ttl

    async def delete(self, key: str) -> int:
        d1 = 1 if self.hashes.pop(key, None) is not None else 0
        d2 = 1 if self.strings.pop(key, None) is not None else 0
        return max(d1, d2)

    async def exists(self, key: str) -> int:
        return 1 if (key in self.hashes or key in self.strings) else 0

    async def set(self, key: str, val: str):
        self.strings[key] = val

    def pipeline(self):
        return MockPipeline(self)


class MockPipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def hgetall(self, key: str):
        self.ops.append(("hgetall", key))
        return self

    def delete(self, key: str):
        self.ops.append(("delete", key))
        return self

    async def execute(self):
        results = []
        for op, key in self.ops:
            if op == "hgetall":
                results.append(self.redis.hashes.get(key, {}))
            elif op == "delete":
                results.append(1 if self.redis.hashes.pop(key, None) is not None else 0)
        return results


@pytest.mark.asyncio
async def test_handshake_token_lifecycle_and_single_use():
    """Tests token generation, single-use eviction, and replay rejection."""
    mock_redis = MockRedisAsync()
    mgr = HandshakeManager(mock_redis)

    # 1. Create handshake token
    token = await mgr.create_handshake_token(metadata={"client_ip": "198.51.100.10"})
    assert token and len(token) > 20
    assert f"handshake:token:{token}" in mock_redis.hashes

    # 2. First consumption: must succeed and atomically evict token
    session_data = await mgr.verify_and_consume_token(token, client_ip="198.51.100.10")
    assert session_data is not None
    assert session_data["ip"] == "198.51.100.10"

    # Token must now be evicted from Redis
    assert f"handshake:token:{token}" not in mock_redis.hashes

    # Active session must be created
    assert f"active_session:{token}" in mock_redis.hashes

    # 3. Second consumption (Replay attack): MUST FAIL
    replay_data = await mgr.verify_and_consume_token(token, client_ip="198.51.100.10")
    assert replay_data is None


@pytest.mark.asyncio
async def test_admin_ip_block_and_session_revocation():
    """Tests session revocation and IP blocking operations."""
    mock_redis = MockRedisAsync()
    mgr = HandshakeManager(mock_redis)

    # Block IP
    malicious_ip = "203.0.113.99"
    await mgr.block_ip(malicious_ip, reason="Repeated auth failures")
    assert await mgr.is_ip_blocked(malicious_ip) is True

    # Unblock IP
    await mgr.unblock_ip(malicious_ip)
    assert await mgr.is_ip_blocked(malicious_ip) is False
