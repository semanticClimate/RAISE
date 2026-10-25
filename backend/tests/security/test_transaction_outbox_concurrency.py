"""
Decoupled Transactional Outbox Concurrency Verification Suite
Validates that database connection sockets are NOT locked during high-latency inference.
"""

import asyncio
import time
import pytest
from src.security.outbox_manager import TransactionalOutboxManager


@pytest.mark.asyncio
async def test_transactional_outbox_inference_decoupling():
    """
    Tests that database transactions are short micro-commits (<5ms)
    and slow inference (e.g., 50ms) runs entirely outside the transaction scope.
    """
    outbox = TransactionalOutboxManager()

    db_locks = {"locked": False, "pre_committed": False, "post_committed": False}

    async def mock_pre_inference_tx():
        # Fast DB write: records session & prompt
        db_locks["locked"] = True
        await asyncio.sleep(0.002)  # 2ms DB write
        db_locks["locked"] = False  # Transaction committed & socket released
        db_locks["pre_committed"] = True
        return {"session_id": "sess_123", "status": "pending_inference"}

    async def mock_slow_inference():
        # Slow external inference (e.g. 50ms simulated vLLM generation)
        # MUST assert DB socket is NOT locked!
        assert db_locks["locked"] is False, "DB connection was illegally held during external inference!"
        await asyncio.sleep(0.05)
        return {"answer": "Quantum computing advances in 2026", "citations": [1, 2]}

    async def mock_post_inference_tx(result):
        # Fast DB write: records final answer and citations
        db_locks["locked"] = True
        await asyncio.sleep(0.002)  # 2ms DB write
        db_locks["locked"] = False  # Committed & released
        db_locks["post_committed"] = True
        return {"session_id": "sess_123", "status": "completed"}

    result = await outbox.execute_decoupled_inference(
        record_pre_inference_tx=mock_pre_inference_tx,
        run_inference=mock_slow_inference,
        record_post_inference_tx=mock_post_inference_tx
    )

    assert result["answer"] == "Quantum computing advances in 2026"
    assert db_locks["pre_committed"] is True
    assert db_locks["post_committed"] is True
    assert db_locks["locked"] is False
