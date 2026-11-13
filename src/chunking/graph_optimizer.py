"""
Temporary Knowledge Graph Construction & Boundary Optimizer (Stage 6, Stage 11, Stage 12, Stage 13).
=====================================================================================================
Component: `src.chunking.graph_optimizer`
Architecture Layer: Document Processing / Graph-Guided Boundary Optimization

Overview:
---------
Orchestrates multi-signal graph analysis and dynamic weight renormalization to evaluate
adjacent CandidateUnits (A, B) and output explainable BoundaryExplanations:
  - MERGE: Cohesive units merged into unified semantic passages.
  - SPLIT: Distinct sections/topics split at natural transitions.
  - PRESERVE: Balanced signals or structural boundaries preserved as standalone units.

Modular Architecture:
---------------------
- Temporary Knowledge Graph Builder: `src.chunking.graph_builder`
- Hard Structural Constraints Engine: `src.chunking.hard_constraints`
- Multi-Signal Availability Computer: `src.chunking.signals`
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .config import ChunkingConfig
from .models import (
    BoundaryDecision,
    BoundaryExplanation,
    CandidateUnit,
)

# Modular re-exports for 100% backward compatibility
from .graph_builder import TemporaryGraphBuilder
from .hard_constraints import HardConstraintEngine
from .signals import SignalAvailabilityComputer

logger = logging.getLogger("raise.chunking.graph_optimizer")


class GraphGuidedBoundaryOptimizer:
    """
    Evaluates pairs of adjacent candidate information units (A, B) using multi-signal graph analysis
    and dynamic weight renormalization:
      BoundaryScore(A, B) =
          w_sem * SemanticDiscontinuity
        + w_struct * StructuralBoundaryStrength
        + w_topic * TopicTransition
        - w_ent * EntityContinuity
        - w_rel * RelationshipContinuity
        - w_conn * GraphConnectivity
        - w_comm * CommunityContinuity
        - w_cross * CrossSectionDependency

    HIGH BoundaryScore -> SPLIT
    LOW BoundaryScore  -> MERGE
    """

    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        self.graph_builder = TemporaryGraphBuilder()
        self.hard_constraint_engine = HardConstraintEngine()
        self.signal_computer = SignalAvailabilityComputer()

    def evaluate_boundary(
        self,
        unit_a: CandidateUnit,
        unit_b: CandidateUnit,
        graph: Optional[Any] = None,
        node_to_community: Optional[Dict[str, str]] = None,
    ) -> BoundaryExplanation:
        """
        Calculates boundary score, determines decision (MERGE, SPLIT, PRESERVE),
        and provides an explainable reason trace and deterministic audit ledger.
        """
        boundary_id = f"bnd_{unit_a.candidate_id}_{unit_b.candidate_id}"

        # 1. Evaluate Hard Constraints First
        hard_result = self.hard_constraint_engine.evaluate(
            unit_a=unit_a,
            unit_b=unit_b,
            max_parent_tokens=self.config.max_parent_tokens,
            enable_cross_page_continuity=self.config.enable_cross_page_continuity,
        )

        if hard_result.triggered:
            action = hard_result.forced_action or BoundaryDecision.PRESERVE
            if action == BoundaryDecision.PRESERVE:
                score = 0.85 if unit_a.is_table or unit_b.is_table else 0.80
                reasons = [
                    f"+ preserved {hard_result.constraint_type.lower().replace('_', ' ')} as first-class information unit"
                ]
            elif action == BoundaryDecision.SPLIT:
                score = 1.0
                reasons = [f"+ hard constraint split: {hard_result.reason_code}"]
            else:  # MERGE
                score = -1.0
                reasons = [f"- hard constraint merge: {hard_result.reason_code}"]

            return BoundaryExplanation(
                boundary_id=boundary_id,
                unit_a_id=unit_a.candidate_id,
                unit_b_id=unit_b.candidate_id,
                page_a=unit_a.page_start,
                page_b=unit_b.page_start,
                decision=action,
                boundary_score=score,
                confidence=1.0,
                reasons=reasons,
                reason_codes=[hard_result.reason_code or "HARD_CONSTRAINT"],
                signals={"structural_boundary": 1.0 if action == BoundaryDecision.PRESERVE else 0.0},
                hard_constraint=hard_result,
                is_strict_mode=self.config.strict_mode,
            )

        # 2. Compute Measurable Signals (No fabricated values)
        signal_results = self.signal_computer.compute_all(
            unit_a=unit_a,
            unit_b=unit_b,
            config=self.config,
            graph=graph,
            node_to_community=node_to_community,
        )

        # 3. Dynamic Weight Renormalization
        configured_weights = {
            "semantic_discontinuity": self.config.weight_semantic_discontinuity,
            "structural_boundary": self.config.weight_structural_boundary,
            "topic_transition": self.config.weight_topic_transition,
            "entity_continuity": self.config.weight_entity_continuity,
            "relationship_continuity": self.config.weight_relationship_continuity,
            "graph_connectivity": self.config.weight_graph_connectivity,
            "community_continuity": self.config.weight_community_continuity,
            "cross_section": self.config.weight_cross_section,
        }

        signal_signs = {
            "semantic_discontinuity": 1.0,
            "structural_boundary": 1.0,
            "topic_transition": 1.0,
            "entity_continuity": -1.0,
            "relationship_continuity": -1.0,
            "graph_connectivity": -1.0,
            "community_continuity": -1.0,
            "cross_section": -1.0,
        }

        # Filter active signals
        active_signals = {
            k: res for k, res in signal_results.items()
            if res.available and res.value is not None
        }

        total_configured_weight = sum(configured_weights.values())
        active_configured_weight = sum(configured_weights[k] for k in active_signals)

        normalized_weights: Dict[str, float] = {}
        if active_configured_weight > 0.0:
            scale_factor = total_configured_weight / active_configured_weight
            for k in active_signals:
                normalized_weights[k] = configured_weights[k] * scale_factor

            score = sum(
                normalized_weights[k] * signal_signs[k] * active_signals[k].value
                for k in active_signals
            )
            available_weight_ratio = active_configured_weight / total_configured_weight
        else:
            score = 0.0
            available_weight_ratio = 0.0

        # Determine Decision and Margin
        reasons: List[str] = []
        reason_codes: List[str] = []

        if score >= self.config.split_threshold:
            decision = BoundaryDecision.SPLIT
            margin = abs(score - self.config.split_threshold)
        elif score <= self.config.merge_threshold:
            combined_child_tokens = unit_a.token_estimate + unit_b.token_estimate
            sd_res = signal_results.get("semantic_discontinuity")
            ec_res = signal_results.get("entity_continuity")
            rc_res = signal_results.get("relationship_continuity")

            sem_sim = (1.0 - sd_res.value) if (sd_res and sd_res.available and sd_res.value is not None) else 0.0
            ent_cont = ec_res.value if (ec_res and ec_res.available and ec_res.value is not None) else 0.0
            rel_cont = rc_res.value if (rc_res and rc_res.available and rc_res.value is not None) else 0.0

            is_jaccard = bool(sd_res and sd_res.method == "token_jaccard_content_words")
            effective_sem_thresh = (self.config.merge_semantic_similarity_threshold * 0.20) if is_jaccard else self.config.merge_semantic_similarity_threshold

            has_entity_cohesion = ent_cont >= self.config.merge_min_entity_cooccurrence or rel_cont > 0.4
            has_semantic_cohesion = sem_sim >= effective_sem_thresh

            if unit_a.heading != unit_b.heading and not (unit_b.is_continued or unit_b.continuation_of_id == unit_a.candidate_id):
                decision = BoundaryDecision.SPLIT
                margin = abs(score - self.config.split_threshold)
                reasons.append(f"+ distinct section headings '{unit_a.heading}' != '{unit_b.heading}'")
                reason_codes.append("STRUCTURAL_HEADING_SHIFT")
            elif combined_child_tokens > self.config.max_child_tokens:
                decision = BoundaryDecision.PRESERVE
                margin = 0.0
                reasons.append(f"= over-merge prevented: combined tokens {combined_child_tokens} > max child {self.config.max_child_tokens}")
                reason_codes.append("REJECTED_MERGE_MAX_CHILD_EXCEEDED")
            elif not has_entity_cohesion and not has_semantic_cohesion:
                decision = BoundaryDecision.PRESERVE
                margin = 0.0
                reasons.append(f"= over-merge prevented: insufficient entity cohesion ({ent_cont:.2f}) and semantic similarity ({sem_sim:.2f})")
                reason_codes.append("REJECTED_MERGE_LOW_COHESION")
            else:
                decision = BoundaryDecision.MERGE
                margin = abs(self.config.merge_threshold - score)
        else:
            decision = BoundaryDecision.PRESERVE
            margin = 0.0

        agreement = min(1.0, 0.5 + 0.5 * margin)
        confidence = max(0.20, min(0.99, available_weight_ratio * agreement))

        # Build Explainable Reason Trace & Machine-Readable Reason Codes
        legacy_signals = {
            k: (res.value if res.value is not None else 0.0)
            for k, res in signal_results.items()
        }
        if "structural_boundary" in legacy_signals:
            legacy_signals["structural_strength"] = legacy_signals["structural_boundary"]

        sb_val = legacy_signals.get("structural_boundary", 0.0)
        tt_val = legacy_signals.get("topic_transition", 0.0)
        ec_val = legacy_signals.get("entity_continuity", 0.0)
        rc_val = legacy_signals.get("relationship_continuity", 0.0)
        gc_val = legacy_signals.get("graph_connectivity", 0.0)
        cc_val = legacy_signals.get("community_continuity", 0.0)
        sd_val = legacy_signals.get("semantic_discontinuity", 0.0)

        if decision == BoundaryDecision.SPLIT:
            if sb_val > 0.5:
                reasons.append("+ strong structural boundary")
                reason_codes.append("STRUCTURAL_HEADING_SHIFT")
            if tt_val > 0.5:
                reasons.append("+ strong topic transition")
                reason_codes.append("TOPIC_TRANSITION")
            if "entity_continuity" in active_signals and ec_val < 0.2:
                reasons.append("+ low entity overlap")
                reason_codes.append("LOW_ENTITY_OVERLAP")
            if "relationship_continuity" in active_signals and rc_val < 0.2:
                reasons.append("+ low relationship continuity")
                reason_codes.append("LOW_RELATIONSHIP_CONTINUITY")
            if "community_continuity" in active_signals and cc_val == 0.0:
                reasons.append("+ different graph communities")
                reason_codes.append("DIFFERENT_COMMUNITIES")
            if not reason_codes:
                reasons.append("+ split boundary threshold met")
                reason_codes.append("SPLIT_THRESHOLD_EXCEEDED")
        elif decision == BoundaryDecision.MERGE:
            if ec_val > 0.4:
                reasons.append("- high entity continuity")
                reason_codes.append("ENTITY_COHESION")
            if rc_val > 0.4:
                reasons.append("- shared relationship / event")
                reason_codes.append("RELATIONSHIP_COHESION")
            if gc_val > 0.5:
                reasons.append("- strong graph connectivity")
                reason_codes.append("GRAPH_TOPOLOGY_COHESION")
            if cc_val > 0.5:
                reasons.append("- same graph community")
                reason_codes.append("COMMUNITY_MEMBERSHIP_COHESION")
            if "semantic_discontinuity" in active_signals and sd_val < 0.35:
                reasons.append("- strong semantic similarity")
                reason_codes.append("SEMANTIC_COHESION")
            if not reason_codes:
                reasons.append("- merge boundary threshold met")
                reason_codes.append("MERGE_THRESHOLD_MET")
        else:
            if not reason_codes:
                reasons.append("= balanced signals; preserve candidate unit boundary")
                reason_codes.append("BALANCED_SIGNALS_PRESERVE")

        return BoundaryExplanation(
            boundary_id=boundary_id,
            unit_a_id=unit_a.candidate_id,
            unit_b_id=unit_b.candidate_id,
            page_a=unit_a.page_start,
            page_b=unit_b.page_start,
            decision=decision,
            boundary_score=score,
            confidence=confidence,
            reasons=reasons,
            signals=legacy_signals,
            signal_results=signal_results,
            configured_weights=configured_weights,
            normalized_weights=normalized_weights,
            reason_codes=reason_codes,
            is_strict_mode=self.config.strict_mode,
        )
