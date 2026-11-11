"""
Graph & Cross-Section Signal Computation
========================================
Component: `src.chunking.graph_signals`
Architecture: Computes graph connectivity, community continuity, and cross-section dependency signals.
Max Lines: Strictly <= 400 lines
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from .config import ChunkingConfig
from .models import CandidateUnit, SignalResult

logger = logging.getLogger("raise.chunking.graph_signals")


def compute_community_continuity_signal(
    unit_a: CandidateUnit,
    unit_b: CandidateUnit,
    config: ChunkingConfig,
    node_to_community: Optional[Dict[str, str]] = None,
) -> SignalResult:
    """Computes community continuity signal based on Louvain community membership."""
    if config.ablation_disable_community_continuity:
        return SignalResult(
            name="community_continuity",
            value=0.0,
            available=False,
            method="ablation_disabled",
            missing_reason="ablation_flag_active",
        )
    if not node_to_community:
        return SignalResult(
            name="community_continuity",
            value=None,
            available=False,
            method="louvain_community_membership",
            evidence_count=0,
            quality=0.0,
            missing_reason="community_detection_unavailable_or_empty",
        )

    comm_a = node_to_community.get(unit_a.candidate_id)
    comm_b = node_to_community.get(unit_b.candidate_id)
    if comm_a and comm_b:
        return SignalResult(
            name="community_continuity",
            value=1.0 if comm_a == comm_b else 0.0,
            available=True,
            method="louvain_community_membership",
            evidence_count=1,
            quality=1.0,
        )

    return SignalResult(
        name="community_continuity",
        value=None,
        available=False,
        method="louvain_community_membership",
        evidence_count=0,
        quality=0.0,
        missing_reason="candidate_unit_not_in_community_map",
    )


def compute_cross_section_signal(
    unit_a: CandidateUnit,
    unit_b: CandidateUnit,
) -> SignalResult:
    """Computes cross-section relational dependency signal."""
    ent_ids_a = {e["id"] for e in unit_a.entities if "id" in e}
    ent_ids_b = {e["id"] for e in unit_b.entities if "id" in e}
    rel_targets_a = {r.get("target_id") or r.get("target") for r in unit_a.relationships if (r.get("target_id") or r.get("target"))}
    rel_targets_b = {r.get("target_id") or r.get("target") for r in unit_b.relationships if (r.get("target_id") or r.get("target"))}
    shared_ents = ent_ids_a & ent_ids_b
    cross_rel = (ent_ids_a & rel_targets_b) | (ent_ids_b & rel_targets_a)

    if unit_a.section_id != unit_b.section_id:
        if shared_ents or cross_rel:
            return SignalResult(
                name="cross_section",
                value=0.9,
                available=True,
                method="cross_section_entity_bridge",
                evidence_count=len(shared_ents) + len(cross_rel),
                quality=1.0,
            )
        return SignalResult(
            name="cross_section",
            value=0.0,
            available=True,
            method="cross_section_no_bridge",
            evidence_count=0,
            quality=1.0,
        )

    return SignalResult(
        name="cross_section",
        value=0.0,
        available=True,
        method="same_section_no_cross_dependency",
        evidence_count=0,
        quality=1.0,
    )
