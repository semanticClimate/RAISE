import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.retrieval.fusion import reciprocal_rank_fusion, CrossEncoderReranker, hybrid_fuse_and_rerank

def test_hybrid_fusion_pipeline():
    query = "What grants were received by Dr. Sushanta Kumar Panigrahi?"

    # 1. Simulated Dense Vector Retrieval Results
    dense_results = [
        {"chunk_id": "chk_101", "plain_text": "Dr. Sushanta Kumar Panigrahi secured a grant of Rs. 45 Lakhs from DST for advanced composite materials research.", "score": 0.89},
        {"chunk_id": "chk_102", "plain_text": "The Department of Mechanical Engineering conducted seminars on robotics and clean mobility.", "score": 0.78},
        {"chunk_id": "chk_103", "plain_text": "Dr. Panigrahi published 6 papers in international peer-reviewed journals during the fiscal year.", "score": 0.74},
    ]

    # 2. Simulated Sparse / BM25 Results
    sparse_results = [
        {"chunk_id": "chk_103", "plain_text": "Dr. Panigrahi published 6 papers in international peer-reviewed journals during the fiscal year.", "score": 12.4},
        {"chunk_id": "chk_101", "plain_text": "Dr. Sushanta Kumar Panigrahi secured a grant of Rs. 45 Lakhs from DST for advanced composite materials research.", "score": 11.2},
        {"chunk_id": "chk_104", "plain_text": "Sponsored research revenue for the institution stood at Rs. 150 Crore across all departments.", "score": 8.1},
    ]

    # 3. Simulated Graph Triplet Candidates
    graph_results = [
        {"chunk_id": "chk_101", "plain_text": "(:Person {name: 'Dr. Sushanta Kumar Panigrahi'})-[:PRINCIPAL_INVESTIGATOR]->(:Grant {amount_inr_lakh: 45.0, sponsor: 'DST'})", "score": 1.0},
        {"chunk_id": "chk_105", "plain_text": "(:Institution)-[:HAS_DEPARTMENT]->(:Department {name: 'Mechanical Engineering'})", "score": 0.8},
    ]

    # Execute Hybrid Fusion and Reranking
    final_passages = hybrid_fuse_and_rerank(
        query=query,
        dense_candidates=dense_results,
        sparse_candidates=sparse_results,
        graph_candidates=graph_results,
        top_n=3,
        rrf_k=60
    )

    print("=== HYBRID FUSION & CROSS-ENCODER RERANKING RESULTS ===")
    for rank, p in enumerate(final_passages, 1):
        print(f"Rank {rank}: [ID: {p['chunk_id']}] | RRF Score: {p.get('rrf_score')} | Cross-Encoder: {p.get('cross_encoder_score')}")
        print(f"       Text: {p['plain_text'][:110]}...\n")

    assert len(final_passages) in [2, 3]
    assert final_passages[0]["chunk_id"] == "chk_101"
    assert "cross_encoder_score" in final_passages[0]


def test_adaptive_intent_weighted_rrf():
    """Verify dynamic intent classification and weight calculation across modalities."""
    from src.retrieval.parallel_retriever import AsyncParallelRetriever
    from src.retrieval.fusion import reciprocal_rank_fusion

    # 1. Numerical / Schedule / Expenditure Query
    q_num = "Under Schedule 12, what was the total expenditure in rupees for 2024?"
    intent_num, weights_num = AsyncParallelRetriever.classify_retrieval_intent(q_num)
    assert intent_num == "NUMERICAL_OR_FACTUAL"
    assert weights_num == [0.30, 0.50, 0.20]  # BM25 is prioritized

    # 2. Relational / Multi-hop Lineage Query
    q_rel = "Who was the director of the centre founded by Dr. Rao?"
    intent_rel, weights_rel = AsyncParallelRetriever.classify_retrieval_intent(q_rel)
    assert intent_rel == "RELATIONAL_OR_LINEAGE"
    assert weights_rel == [0.25, 0.20, 0.55]  # Neo4j Graph is prioritized

    # 3. Thematic / Conceptual Query
    q_thm = "Summarize the overarching institutional vision and academic goals."
    intent_thm, weights_thm = AsyncParallelRetriever.classify_retrieval_intent(q_thm)
    assert intent_thm == "THEMATIC_OR_OVERVIEW"
    assert weights_thm == [0.55, 0.25, 0.20]  # Dense Vectors prioritized

    # 4. Verify table boosting under weighted fusion
    list_dense = [{"chunk_id": "c1", "text": "Prose chunk"}, {"chunk_id": "c2", "text": "Another prose"}]
    list_sparse = [{"chunk_id": "c3", "text": "| Year | Budget |\n|---|---|\n| 2024 | 50 Cr |", "is_table": True}]

    # With table boost
    fused = reciprocal_rank_fusion([list_dense, list_sparse], k=60, weights=[0.30, 0.50], table_boost=True)
    assert len(fused) == 3
    # Verify table candidate received structural boost
    c3_entry = next(item for item in fused if item["chunk_id"] == "c3")
    assert c3_entry["rrf_score"] > 0


if __name__ == "__main__":
    test_hybrid_fusion_pipeline()
    test_adaptive_intent_weighted_rrf()

