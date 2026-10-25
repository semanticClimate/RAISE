"""
Standard Information Retrieval (IR) Metrics Suite
=================================================
Implements standard BEIR / TREC / MTEB evaluation metrics for ranking and retrieval systems:
1. Recall@K (K = 1, 5, 10, 20)
2. Mean Reciprocal Rank (MRR@K)
3. Normalized Discounted Cumulative Gain (nDCG@K)
4. Mean Average Precision (MAP@K)
5. Precision@K

Follows standard Cranfield / BEIR formulation with binary and graded relevance.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Sequence, Set, Union


def compute_recall_at_k(
    retrieved_items: Sequence[Any],
    gold_items: Sequence[Any],
    k: int = 10,
) -> float:
    """
    Computes Recall@K:
        Recall@K = |Retrieved[:k] ∩ Gold| / |Gold|
    If Gold is empty, returns 1.0 if retrieved is also empty else 0.0.
    """
    if not gold_items:
        return 1.0 if not retrieved_items else 0.0

    gold_set = set(gold_items)
    retrieved_at_k = list(retrieved_items)[:k]
    hits = sum(1 for item in retrieved_at_k if item in gold_set)

    return hits / len(gold_set)


def compute_precision_at_k(
    retrieved_items: Sequence[Any],
    gold_items: Sequence[Any],
    k: int = 10,
) -> float:
    """
    Computes Precision@K:
        Precision@K = |Retrieved[:k] ∩ Gold| / k
    """
    if k <= 0:
        return 0.0

    gold_set = set(gold_items)
    retrieved_at_k = list(retrieved_items)[:k]
    hits = sum(1 for item in retrieved_at_k if item in gold_set)

    return hits / float(k)


def compute_mrr_at_k(
    retrieved_items: Sequence[Any],
    gold_items: Sequence[Any],
    k: int = 10,
) -> float:
    """
    Computes Reciprocal Rank @ K:
        RR@K = 1 / rank_of_first_relevant_item (1-indexed) if rank <= k else 0.0
    """
    gold_set = set(gold_items)
    for idx, item in enumerate(retrieved_items[:k], start=1):
        if item in gold_set:
            return 1.0 / float(idx)
    return 0.0


def compute_dcg_at_k(
    retrieved_items: Sequence[Any],
    gold_items: Sequence[Any],
    k: int = 10,
) -> float:
    """
    Computes Discounted Cumulative Gain @ K with binary relevance:
        DCG@K = sum_{i=1}^k (rel_i / log2(i + 1))
    """
    gold_set = set(gold_items)
    dcg = 0.0
    for idx, item in enumerate(retrieved_items[:k], start=1):
        rel = 1.0 if item in gold_set else 0.0
        if rel > 0:
            dcg += rel / math.log2(idx + 1)
    return dcg


def compute_ndcg_at_k(
    retrieved_items: Sequence[Any],
    gold_items: Sequence[Any],
    k: int = 10,
) -> float:
    """
    Computes Normalized Discounted Cumulative Gain @ K (nDCG@K):
        nDCG@K = DCG@K / IDCG@K
    where IDCG@K is the ideal DCG if all gold items appeared at the top ranks.
    """
    if not gold_items:
        return 1.0 if not retrieved_items else 0.0

    dcg = compute_dcg_at_k(retrieved_items, gold_items, k=k)
    num_gold = min(len(set(gold_items)), k)
    idcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, num_gold + 1))

    if idcg <= 0.0:
        return 0.0
    return dcg / idcg


def compute_map_at_k(
    retrieved_items: Sequence[Any],
    gold_items: Sequence[Any],
    k: int = 10,
) -> float:
    """
    Computes Average Precision @ K (AP@K):
        AP@K = sum_{i=1}^k (Precision@i * rel_i) / min(k, |Gold|)
    """
    if not gold_items:
        return 1.0 if not retrieved_items else 0.0

    gold_set = set(gold_items)
    retrieved_at_k = list(retrieved_items)[:k]
    running_hits = 0
    score_sum = 0.0

    for idx, item in enumerate(retrieved_at_k, start=1):
        if item in gold_set:
            running_hits += 1
            precision_at_i = running_hits / float(idx)
            score_sum += precision_at_i

    denominator = min(k, len(gold_set))
    if denominator <= 0:
        return 0.0
    return score_sum / float(denominator)


def compute_retrieval_metrics_battery(
    retrieved_items: Sequence[Any],
    gold_items: Sequence[Any],
    k_thresholds: Sequence[int] = (1, 5, 10, 20),
) -> Dict[str, float]:
    """
    Evaluates a single query against gold references across all standard IR thresholds.
    Returns:
        Dict with Recall@1, Recall@5, Recall@10, Recall@20, MRR@10, nDCG@10, MAP@10
    """
    results: Dict[str, float] = {}

    for k in k_thresholds:
        results[f"recall@{k}"] = round(compute_recall_at_k(retrieved_items, gold_items, k=k), 4)
        results[f"precision@{k}"] = round(compute_precision_at_k(retrieved_items, gold_items, k=k), 4)

    results["mrr@10"] = round(compute_mrr_at_k(retrieved_items, gold_items, k=10), 4)
    results["ndcg@10"] = round(compute_ndcg_at_k(retrieved_items, gold_items, k=10), 4)
    results["map@10"] = round(compute_map_at_k(retrieved_items, gold_items, k=10), 4)

    return results


def aggregate_query_metrics(metrics_list: List[Dict[str, float]]) -> Dict[str, float]:
    """
    Averages metric batteries across all evaluated queries.
    """
    if not metrics_list:
        return {}

    keys = list(metrics_list[0].keys())
    totals = {k: 0.0 for k in keys}
    count = len(metrics_list)

    for m in metrics_list:
        for k in keys:
            totals[k] += m.get(k, 0.0)

    return {k: round(totals[k] / float(count), 4) for k in keys}
