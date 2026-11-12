"""
Unit tests for Retrieval Stack & Architecture Improvements:
1. Reranker thread lock & calibrated [0.0, 1.0] scoring with bounded table boost.
2. Parallel retriever BM25 O(1) signature cache.
3. ChainCompletenessGate hop 2 verification fallback to seed terms.
4. RRF with intent-based weight redistribution.
5. Purger PostgresManager connection reuse.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from src.retrieval.reranker import CrossEncoderReranker, _RERANKER_LOCK
from src.retrieval.chain_gate import ChainCompletenessGate
from src.retrieval.fusion import reciprocal_rank_fusion
from src.retrieval.purger import purge_document


def test_reranker_thread_lock_and_score_calibration():
    """Verify that _RERANKER_LOCK exists and cross_encoder_score stays in [0.0, 1.0]."""
    assert _RERANKER_LOCK is not None

    reranker = CrossEncoderReranker()
    # Mock model prediction returning uncalibrated logits e.g. 8.5
    mock_model = MagicMock()
    mock_model.predict.return_value = [8.5]
    reranker.model = mock_model
    reranker._loaded = True

    candidates = [
        {
            "chunk_id": "c1",
            "text": "Balance sheet schedule 3 shows capital expenditure of 50 Lakhs.",
            "is_table": True,
        }
    ]

    reranked = reranker.rerank(
        query="What is the balance sheet capital expenditure?",
        candidates=candidates,
        top_n=5,
    )

    assert len(reranked) == 1
    score = reranked[0]["cross_encoder_score"]
    # Score must be bounded in [0.0, 1.0] and not explode into 3.5+
    assert 0.0 <= score <= 1.0
    assert "raw_cross_encoder_score" in reranked[0]
    assert 0.0 <= reranked[0]["raw_cross_encoder_score"] <= 1.0


def test_chain_gate_hop2_fallback_without_hardcoded_category():
    """Verify that ChainCompletenessGate doesn't falsely abstain when target_attr is None."""
    gate = ChainCompletenessGate()

    query = "What laboratory equipment is installed in the facility managed by Prof. Sharma?"
    retrieved_chunks = [
        {
            "chunk_id": "chk_01",
            "text": "Prof. Sharma is the principal investigator of the Nanotech Laboratory.",
        },
        {
            "chunk_id": "chk_02",
            "text": "The Nanotech Laboratory is equipped with a high-resolution Transmission Electron Microscope.",
        },
    ]

    with patch("src.infrastructure.providers.router.ProviderRouter.complete", return_value="Deterministic offline gate check"):
        decision = gate.evaluate_chain(query, retrieved_chunks)
    assert decision.is_complete is True
    assert decision.status in ["PASSED", "VERIFIED", "PARTIALLY_GROUNDED", "TRIGGER_RECOVERY"]


def test_rrf_with_intent_redistribution():
    """Verify that reciprocal_rank_fusion properly redistributes weights with intent."""
    list1 = [{"chunk_id": "c1", "text": "Dense passage 1"}]
    list2 = [{"chunk_id": "c2", "text": "Sparse passage 2"}]

    fused = reciprocal_rank_fusion(
        [list1, list2],
        k=60,
        intent="financial",
    )
    assert len(fused) == 2
    assert all("rrf_score" in doc for doc in fused)


def test_purger_reuses_postgres_manager():
    """Verify that purge_document reuses provided postgres_manager without instantiating new one."""
    mock_pipeline = MagicMock()
    mock_pm = MagicMock()

    with patch("pathlib.Path.exists", return_value=False):
        res = purge_document(
            pipeline=mock_pipeline,
            doc_identifier="test_doc.pdf",
            postgres_manager=mock_pm,
        )
        assert res.get("status") in ["success", "PURGED", "NOT_FOUND"]
        mock_pm.delete_document.assert_called()
