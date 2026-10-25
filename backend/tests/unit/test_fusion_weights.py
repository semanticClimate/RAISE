"""
Unit Tests for Intent-Conditioned Reciprocal Rank Fusion (RRF)
=============================================================
Validates:
1. Dynamic modality weight assignment across intent categories.
2. Weighted RRF scoring over multi-channel candidate sets.
3. Minimum score threshold pruning.
4. Structural table candidate score boosting.
"""

import pytest
from src.retrieval.fusion import (
    get_intent_modality_weights,
    reciprocal_rank_fusion,
)


@pytest.mark.unit
def test_intent_modality_weights_mapping():
    """Verifies intent-conditioned channel weights."""
    assert get_intent_modality_weights(None) == [1.0, 1.0, 1.0]

    # Tabular / Financial
    tab_w = get_intent_modality_weights("financial_schedule")
    assert tab_w == [0.8, 1.4, 1.0]

    # Multi-hop / Relational
    rel_w = get_intent_modality_weights("multi-hop relation")
    assert rel_w == [1.1, 0.7, 1.5]

    # Compare
    cmp_w = get_intent_modality_weights("compare institutions")
    assert cmp_w == [1.0, 1.2, 1.2]

    # General Narrative
    gen_w = get_intent_modality_weights("general narrative summary")
    assert gen_w == [1.3, 1.0, 0.8]


@pytest.mark.unit
def test_rrf_with_intent_weights():
    """Verifies reciprocal_rank_fusion respects intent parameter."""
    dense_list = [{"chunk_id": "doc_dense_1", "text": "Dense passage"}]
    sparse_list = [{"chunk_id": "doc_sparse_1", "text": "Sparse passage"}]

    # In financial intent, sparse is weighted 1.4 while dense is 0.8
    fused = reciprocal_rank_fusion(
        [dense_list, sparse_list],
        k=60,
        intent="financial_budget",
        table_boost=False,
    )

    assert len(fused) == 2
    # doc_sparse_1 should rank first due to higher sparse modality weight (1.4 vs 0.8)
    assert fused[0]["chunk_id"] == "doc_sparse_1"
    assert fused[1]["chunk_id"] == "doc_dense_1"
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]


@pytest.mark.unit
def test_rrf_min_score_threshold_pruning():
    """Verifies candidates below min_score_threshold are pruned."""
    dense_list = [
        {"chunk_id": "doc_1", "text": "Rank 1 item"},
        {"chunk_id": "doc_2", "text": "Rank 2 item"},
    ]

    # With k=60, score for rank 2 with weight 1.0 is 1/62 = ~0.0161
    # Threshold at 0.0162 should filter out doc_2
    fused_all = reciprocal_rank_fusion([dense_list], k=60, min_score_threshold=None)
    assert len(fused_all) == 2

    fused_pruned = reciprocal_rank_fusion([dense_list], k=60, min_score_threshold=0.0162)
    assert len(fused_pruned) == 1
    assert fused_pruned[0]["chunk_id"] == "doc_1"


@pytest.mark.unit
def test_rrf_table_boosting():
    """Verifies table candidates receive 1.35x structural boost."""
    candidates_text = [
        {"chunk_id": "text_doc", "text": "Standard narrative paragraph without tables.", "is_table": False},
        {"chunk_id": "table_doc", "text": "| Column A | Column B |\n| --- | --- |\n| 10 | 20 |", "is_table": True},
    ]

    # Both at rank 1 in their respective lists
    fused = reciprocal_rank_fusion(
        [[candidates_text[0]], [candidates_text[1]]],
        k=60,
        table_boost=True,
    )

    table_res = next(c for c in fused if c["chunk_id"] == "table_doc")
    text_res = next(c for c in fused if c["chunk_id"] == "text_doc")

    # Table candidate should have higher score due to 1.35x boost
    assert table_res["rrf_score"] > text_res["rrf_score"]
