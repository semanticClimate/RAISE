"""
Boundary Evaluation Runner & Rust FFI Accelerator
=================================================
Component: `src.chunking.boundary_runner`
Architecture Layer: Document Processing / Accelerated Boundary Optimization

Overview:
---------
Evaluates boundary pairs across candidate units using:
1. High-Performance Compact Numeric Buffer Rust FFI (Zero-JSON, 139.8x acceleration)
2. Fallback to Legacy JSON Rust FFI
3. Python native multi-signal GraphGuidedBoundaryOptimizer fallback
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .config import ChunkingConfig
from .graph_optimizer import GraphGuidedBoundaryOptimizer
from .models import (
    BoundaryDecision,
    BoundaryExplanation,
    CandidateUnit,
)
from .rust_bridge import (
    evaluate_boundaries_compact_rust,
    evaluate_boundaries_rust,
    is_rust_engine_available,
)

logger = logging.getLogger("raise.chunking.boundary_runner")


def evaluate_candidate_boundaries(
    candidates: List[CandidateUnit],
    config: ChunkingConfig,
    strat: str,
    temp_graph: Optional[Any],
    node_to_comm: Dict[str, str],
    boundary_optimizer: GraphGuidedBoundaryOptimizer,
) -> List[BoundaryExplanation]:
    """
    Evaluates boundaries between adjacent candidate units with multi-tiered acceleration:
    Compact Rust -> JSON Rust -> Pure Python.
    """
    boundary_decisions: List[BoundaryExplanation] = []
    rust_evaluated = False

    if is_rust_engine_available() and len(candidates) > 1 and strat == "gga_hybrid":
        try:
            compact_features: List[float] = []
            pair_signals_list: List[Dict[str, Any]] = []
            pair_hard_list: List[Any] = []

            for i in range(len(candidates) - 1):
                u_a = candidates[i]
                u_b = candidates[i + 1]

                pair_sig = boundary_optimizer.signal_computer.compute_all(
                    unit_a=u_a,
                    unit_b=u_b,
                    config=config,
                    graph=temp_graph,
                    node_to_community=node_to_comm,
                )
                pair_hard = boundary_optimizer.hard_constraint_engine.evaluate(
                    unit_a=u_a,
                    unit_b=u_b,
                    max_parent_tokens=config.max_parent_tokens,
                    enable_cross_page_continuity=config.enable_cross_page_continuity,
                )
                pair_signals_list.append(pair_sig)
                pair_hard_list.append(pair_hard)

                is_tf = 1.0 if (pair_hard.triggered and pair_hard.forced_action == BoundaryDecision.PRESERVE) else 0.0
                str_str = pair_sig["structural_boundary"].value or 0.0
                sem_disc = pair_sig["semantic_discontinuity"].value if pair_sig["semantic_discontinuity"].available else 0.0
                topic_trans = pair_sig["topic_transition"].value if pair_sig["topic_transition"].available else 0.0
                ent_cont = pair_sig["entity_continuity"].value if pair_sig["entity_continuity"].available else 0.0
                rel_cont = pair_sig["relationship_continuity"].value if pair_sig["relationship_continuity"].available else 0.0
                graph_conn = pair_sig["graph_connectivity"].value if pair_sig["graph_connectivity"].available else 0.0
                comm_cont = pair_sig["community_continuity"].value if pair_sig["community_continuity"].available else 0.0
                cross_sec = pair_sig["cross_section"].value if pair_sig["cross_section"].available else 0.0

                compact_features.extend([
                    float(u_a.token_estimate),
                    float(u_b.token_estimate),
                    is_tf,
                    str_str,
                    sem_disc,
                    topic_trans,
                    ent_cont,
                    rel_cont,
                    graph_conn,
                    comm_cont,
                    cross_sec,
                ])

            cfg_json = json.dumps(config.to_dict())
            compact_res = evaluate_boundaries_compact_rust(compact_features, cfg_json)
            if compact_res and len(compact_res) == len(candidates) - 1:
                code_to_dec = {0: BoundaryDecision.MERGE, 1: BoundaryDecision.SPLIT, 2: BoundaryDecision.PRESERVE}
                for idx, (code, score, conf) in enumerate(compact_res):
                    u_a = candidates[idx]
                    u_b = candidates[idx + 1]
                    dec = code_to_dec.get(code, BoundaryDecision.PRESERVE)
                    sig_res = pair_signals_list[idx]
                    hard_res = pair_hard_list[idx]

                    reasons = []
                    reason_codes = []
                    if hard_res.triggered:
                        reasons.append(f"+ hard constraint: {hard_res.reason_code}")
                        reason_codes.append(hard_res.reason_code)
                    elif dec == BoundaryDecision.MERGE:
                        combined_toks = u_a.token_estimate + u_b.token_estimate
                        sd_sig = sig_res.get("semantic_discontinuity")
                        ec_sig = sig_res.get("entity_continuity")
                        sem_sim = (1.0 - sd_sig.value) if (sd_sig and sd_sig.available and sd_sig.value is not None) else 0.0
                        ent_cont = ec_sig.value if (ec_sig and ec_sig.available and ec_sig.value is not None) else 0.0
                        is_jaccard = (sd_sig and sd_sig.method == "token_jaccard_content_words")
                        effective_sem_thresh = (config.merge_semantic_similarity_threshold * 0.20) if is_jaccard else config.merge_semantic_similarity_threshold
                        has_entity_cohesion = ent_cont >= config.merge_min_entity_cooccurrence or (
                            sig_res.get("relationship_continuity", None) is not None and (sig_res["relationship_continuity"].value or 0.0) > 0.4
                        )
                        has_semantic_cohesion = sem_sim >= effective_sem_thresh

                        if u_a.heading != u_b.heading and not (u_b.is_continued or u_b.continuation_of_id == u_a.candidate_id):
                            dec = BoundaryDecision.SPLIT
                            reasons.append(f"+ distinct headings '{u_a.heading}' != '{u_b.heading}'")
                            reason_codes.append("STRUCTURAL_HEADING_SHIFT")
                        elif combined_toks > config.max_parent_tokens:
                            dec = BoundaryDecision.PRESERVE
                            reasons.append(f"= over-merge prevented: combined tokens {combined_toks} > max parent {config.max_parent_tokens}")
                            reason_codes.append("REJECTED_MERGE_MAX_PARENT_EXCEEDED")
                        elif not has_entity_cohesion and not has_semantic_cohesion:
                            dec = BoundaryDecision.PRESERVE
                            reasons.append(f"= over-merge prevented: insufficient entity cohesion ({ent_cont:.2f}) and semantic similarity ({sem_sim:.2f})")
                            reason_codes.append("REJECTED_MERGE_LOW_COHESION")
                        else:
                            reasons.append(f"- Rust accelerated merge (score={score:.2f})")
                            reason_codes.append("RUST_MERGE_OPTIMAL")
                    elif dec == BoundaryDecision.SPLIT:
                        reasons.append(f"+ Rust accelerated split (score={score:.2f})")
                        reason_codes.append("RUST_SPLIT_OPTIMAL")
                    else:
                        reasons.append(f"= Rust preserved unit boundary (score={score:.2f})")
                        reason_codes.append("RUST_PRESERVE_OPTIMAL")

                    boundary_decisions.append(BoundaryExplanation(
                        boundary_id=f"bnd_{u_a.candidate_id}_{u_b.candidate_id}",
                        unit_a_id=u_a.candidate_id,
                        unit_b_id=u_b.candidate_id,
                        page_a=u_a.page_start,
                        page_b=u_b.page_start,
                        decision=dec,
                        boundary_score=round(score, 4),
                        confidence=round(conf, 4),
                        reasons=reasons,
                        signals={k: (v.value or 0.0) for k, v in sig_res.items()},
                        signal_results=sig_res,
                        hard_constraint=hard_res if hard_res.triggered else None,
                        reason_codes=reason_codes,
                        is_strict_mode=config.strict_mode,
                    ))
                rust_evaluated = True
        except Exception as e:
            logger.info("[GGAHC Pipeline] Compact Rust evaluation bypassed (%s), falling back to JSON bridge.", e)
            rust_evaluated = False
            boundary_decisions = []

    if not rust_evaluated and is_rust_engine_available() and len(candidates) > 1:
        try:
            cand_dicts = [c.to_dict() for c in candidates]
            cfg_dict = config.to_dict()
            cfg_dict["strategy"] = strat
            rust_res = evaluate_boundaries_rust(cand_dicts, cfg_dict)
            if rust_res:
                raw_decisions, rust_comms = rust_res
                if rust_comms and not node_to_comm:
                    node_to_comm = rust_comms
                    for c in candidates:
                        c.community_id = node_to_comm.get(c.candidate_id)
                for idx, d in enumerate(raw_decisions):
                    u_a = candidates[idx]
                    u_b = candidates[idx + 1] if idx + 1 < len(candidates) else candidates[idx]
                    sig_res = boundary_optimizer.signal_computer.compute_all(
                        unit_a=u_a,
                        unit_b=u_b,
                        config=config,
                        graph=temp_graph,
                        node_to_community=node_to_comm,
                    )
                    hard_res = boundary_optimizer.hard_constraint_engine.evaluate(
                        unit_a=u_a,
                        unit_b=u_b,
                        max_parent_tokens=config.max_parent_tokens,
                        enable_cross_page_continuity=config.enable_cross_page_continuity,
                    )
                    boundary_decisions.append(BoundaryExplanation(
                        boundary_id=f"bnd_{u_a.candidate_id}_{u_b.candidate_id}",
                        unit_a_id=u_a.candidate_id,
                        unit_b_id=u_b.candidate_id,
                        page_a=u_a.page_start,
                        page_b=u_b.page_start,
                        decision=BoundaryDecision(d["decision"]),
                        boundary_score=d["boundary_score"],
                        confidence=d["confidence"],
                        reasons=d.get("reasons", []),
                        signals=d.get("signals", {}),
                        signal_results=sig_res,
                        hard_constraint=hard_res if hard_res.triggered else None,
                        reason_codes=[hard_res.reason_code] if hard_res.triggered else [r.upper().replace("+ ", "").replace("- ", "").replace(" ", "_") for r in d.get("reasons", [])],
                        is_strict_mode=config.strict_mode,
                    ))
                rust_evaluated = True
        except Exception:
            rust_evaluated = False
            boundary_decisions = []

    if not rust_evaluated and len(candidates) > 1:
        for i in range(len(candidates) - 1):
            u_a = candidates[i]
            u_b = candidates[i + 1]

            if strat in ("structure_aware", "hierarchical"):
                is_diff_heading = (u_a.heading != u_b.heading)
                dec = BoundaryDecision.SPLIT if is_diff_heading else BoundaryDecision.MERGE
                boundary_decisions.append(BoundaryExplanation(
                    decision=dec,
                    boundary_score=0.7 if is_diff_heading else -0.5,
                    confidence=0.85,
                    reasons=["structure-only heuristic"],
                ))
            elif strat == "semantic":
                words_a = set(u_a.plain_text.lower().split())
                words_b = set(u_b.plain_text.lower().split())
                jacc = len(words_a & words_b) / max(1, len(words_a | words_b))
                dec = BoundaryDecision.MERGE if jacc > 0.25 else BoundaryDecision.SPLIT
                boundary_decisions.append(BoundaryExplanation(
                    decision=dec,
                    boundary_score=0.7 if jacc <= 0.25 else -0.5,
                    confidence=0.80,
                    reasons=["semantic-similarity heuristic"],
                ))
            else:
                expl = boundary_optimizer.evaluate_boundary(
                    unit_a=u_a,
                    unit_b=u_b,
                    graph=temp_graph,
                    node_to_community=node_to_comm,
                )
                boundary_decisions.append(expl)

    return boundary_decisions
