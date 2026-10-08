"""
RAISE Telemetry Performance & Latency Breakdown Builder
========================================================
Purpose:
  Computes verified performance metrics, bottleneck stage identification,
  hierarchical execution trees, and instrumentation coverage percentages.

Author: RAISE Core Architecture Team
Maintainability: Keep under 120 lines with strict numerical accounting.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
from src.cli.models import PerformanceMetrics


def build_performance_metrics(
    stages: Dict[str, Any],
    meta: Dict[str, Any],
) -> Tuple[PerformanceMetrics, float, float, float, float, float, float, float]:
    """
    Computes PerformanceMetrics and returns (perf, t_route, t_vec, t_bm25, t_graph, t_rerank, t_retrieval, t_synth, t_qg).
    """
    t_route = float(stages.get("routing_ms", 0.0))
    t_vec = float(stages.get("vector_retrieval_ms", 0.0))
    t_bm25 = float(stages.get("bm25_retrieval_ms", 0.0))
    t_graph = float(stages.get("graph_retrieval_ms", 0.0))
    t_rerank = float(stages.get("reranking_ms", 0.0))

    t_retrieval = float(stages.get("retrieval_ms", 0.0))
    if t_retrieval == 0.0:
        t_retrieval = t_vec + t_bm25 + t_graph + t_rerank

    t_synth = float(stages.get("synthesis_ms", 0.0))
    t_qg = float(stages.get("quality_gate_ms", 0.0))
    t_total = float(
        meta.get("total_latency_ms")
        or stages.get("total_latency_ms")
        or (t_route + t_retrieval + t_synth + t_qg)
    )

    total_safe = max(t_total, 1.0)
    pct_route = (t_route / total_safe) * 100.0
    pct_retrieval = (t_retrieval / total_safe) * 100.0
    pct_synth = (t_synth / total_safe) * 100.0
    pct_qg = (t_qg / total_safe) * 100.0

    stage_pcts = {
        "Routing": pct_route,
        "Retrieval": pct_retrieval,
        "Synthesis": pct_synth,
        "Quality Gate": pct_qg,
    }
    max_stage = max(stage_pcts.items(), key=lambda x: x[1])

    breakdown_tree = {
        "routing": t_route,
        "retrieval_vector": t_vec,
        "retrieval_bm25": t_bm25,
        "retrieval_graph": t_graph,
        "retrieval_rerank": t_rerank,
        "synthesis": t_synth,
        "quality_gate": t_qg,
    }
    measured_sum = (
        t_route
        + (
            (t_vec + t_bm25 + t_graph + t_rerank)
            if (t_vec + t_bm25 + t_graph + t_rerank) > 0
            else t_retrieval
        )
        + t_synth
        + t_qg
    )
    unattributed_ms = max(0.0, round(t_total - measured_sum, 2)) if t_total > measured_sum else 0.0
    coverage_pct = round((measured_sum / total_safe) * 100.0, 1) if t_total > 0 else 100.0

    perf = PerformanceMetrics(
        routing_ms=t_route,
        retrieval_ms=t_retrieval,
        synthesis_ms=t_synth,
        quality_gate_ms=t_qg,
        total_latency_ms=t_total,
        unattributed_latency_ms=unattributed_ms,
        instrumentation_coverage_pct=min(100.0, coverage_pct),
        bottleneck_stage=max_stage[0],
        bottleneck_pct=max_stage[1],
        stage_percentages=stage_pcts,
        breakdown_tree=breakdown_tree,
    )

    return perf, t_route, t_vec, t_bm25, t_graph, t_rerank, t_retrieval, t_synth, t_qg
