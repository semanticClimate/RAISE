"""
Multi-Signal Graph & Semantic Availability Computer
===================================================
Component: `src.chunking.signals`
Architecture Layer: Document Processing / Multi-Signal Boundary Analysis

Overview:
---------
Computes deterministic, reproducible signals between adjacent CandidateUnits.
Strictly forbids fabricated defaults: if evidence is insufficient, marks
available=False and provides explicit missing_reason.

Signals Computed:
1. Structural Boundary Strength: Heading depth shifts & page transitions.
2. Semantic Discontinuity: Token Jaccard content-word overlap divergence.
3. Topic Transition: Lexical divergence under identical/altered headings.
4. Entity Continuity: Bipartite entity ID and named entity overlaps.
5. Relationship Continuity: Shared target entities and relational implications.
6. Graph Connectivity: Shortest-path topological distance in temporary NetworkX graph.
7. Community Continuity: Shared Louvain / connected-component community membership.
8. Cross-Section Dependency: Entity and relational bridges crossing formal section IDs.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from .config import ChunkingConfig
from .models import CandidateUnit, SignalResult
from .graph_signals import compute_community_continuity_signal, compute_cross_section_signal

logger = logging.getLogger("raise.chunking.signals")


class SignalAvailabilityComputer:
    """
    Computes deterministic, reproducible signals between adjacent CandidateUnits.
    Strictly forbids fabricated defaults: if evidence is insufficient, marks
    available=False and provides explicit missing_reason.
    """

    @staticmethod
    def compute_all(
        unit_a: CandidateUnit,
        unit_b: CandidateUnit,
        config: ChunkingConfig,
        graph: Optional[Any] = None,
        node_to_community: Optional[Dict[str, str]] = None,
    ) -> Dict[str, SignalResult]:
        signals: Dict[str, SignalResult] = {}

        # 1. Structural Boundary Strength
        if unit_a.heading != unit_b.heading:
            signals["structural_boundary"] = SignalResult(
                name="structural_boundary",
                value=0.85,
                available=True,
                method="heading_hierarchy_comparison",
                evidence_count=1,
                quality=1.0,
            )
        elif unit_a.page_end != unit_b.page_start:
            signals["structural_boundary"] = SignalResult(
                name="structural_boundary",
                value=0.35,
                available=True,
                method="page_transition",
                evidence_count=1,
                quality=1.0,
            )
        else:
            signals["structural_boundary"] = SignalResult(
                name="structural_boundary",
                value=0.0,
                available=True,
                method="contiguous_same_section",
                evidence_count=1,
                quality=1.0,
            )

        # 2. Semantic Discontinuity
        words_a = set(re.findall(r"\b[a-zA-Z]{3,}\b", unit_a.plain_text.lower()))
        words_b = set(re.findall(r"\b[a-zA-Z]{3,}\b", unit_b.plain_text.lower()))
        stop_words = {"the", "and", "for", "with", "this", "that", "from", "are", "were", "been", "have", "has", "our", "their"}
        words_a -= stop_words
        words_b -= stop_words

        if len(words_a) < config.min_content_words_for_semantic or len(words_b) < config.min_content_words_for_semantic:
            signals["semantic_discontinuity"] = SignalResult(
                name="semantic_discontinuity",
                value=None,
                available=False,
                method="token_jaccard_content_words",
                evidence_count=0,
                quality=0.0,
                missing_reason=f"insufficient_content_words (A={len(words_a)}, B={len(words_b)})",
            )
        else:
            intersection = words_a & words_b
            union = words_a | words_b
            jaccard = len(intersection) / len(union) if union else 0.0
            sem_discontinuity = max(0.0, 1.0 - (jaccard * 3.0))
            signals["semantic_discontinuity"] = SignalResult(
                name="semantic_discontinuity",
                value=sem_discontinuity,
                available=True,
                method="token_jaccard_content_words",
                evidence_count=len(intersection),
                quality=min(1.0, len(union) / 20.0),
            )

        # 3. Topic Transition
        if unit_a.heading != unit_b.heading:
            signals["topic_transition"] = SignalResult(
                name="topic_transition",
                value=0.70,
                available=True,
                method="heading_topic_shift",
                evidence_count=1,
                quality=1.0,
            )
        elif signals["semantic_discontinuity"].available and signals["semantic_discontinuity"].value is not None:
            if signals["semantic_discontinuity"].value > 0.75:
                signals["topic_transition"] = SignalResult(
                    name="topic_transition",
                    value=0.60,
                    available=True,
                    method="lexical_divergence_topic_shift",
                    evidence_count=signals["semantic_discontinuity"].evidence_count,
                    quality=signals["semantic_discontinuity"].quality,
                )
            else:
                signals["topic_transition"] = SignalResult(
                    name="topic_transition",
                    value=0.0,
                    available=True,
                    method="same_heading_low_divergence",
                    evidence_count=signals["semantic_discontinuity"].evidence_count,
                    quality=1.0,
                )
        else:
            signals["topic_transition"] = SignalResult(
                name="topic_transition",
                value=None,
                available=False,
                method="topic_shift",
                evidence_count=0,
                quality=0.0,
                missing_reason="insufficient_lexical_evidence",
            )

        # 4. Entity Continuity
        if config.ablation_disable_entity_continuity:
            signals["entity_continuity"] = SignalResult(
                name="entity_continuity",
                value=0.0,
                available=False,
                method="ablation_disabled",
                missing_reason="ablation_flag_active",
            )
        else:
            ent_ids_a = {e["id"] for e in unit_a.entities if "id" in e}
            ent_ids_b = {e["id"] for e in unit_b.entities if "id" in e}
            names_a = {e.get("name", "").lower() for e in unit_a.entities if len(e.get("name", "")) > 3}
            names_b = {e.get("name", "").lower() for e in unit_b.entities if len(e.get("name", "")) > 3}
            shared_ents = ent_ids_a & ent_ids_b
            all_ents = ent_ids_a | ent_ids_b
            shared_names = names_a & names_b

            if not all_ents and not names_a and not names_b:
                signals["entity_continuity"] = SignalResult(
                    name="entity_continuity",
                    value=None,
                    available=False,
                    method="graph_entity_overlap",
                    evidence_count=0,
                    quality=0.0,
                    missing_reason="no_entities_extracted_in_adjacent_units",
                )
            else:
                base_ratio = len(shared_ents) / len(all_ents) if all_ents else 0.0
                if shared_names and base_ratio < 0.75:
                    ent_val = max(base_ratio, 0.75)
                else:
                    ent_val = base_ratio
                signals["entity_continuity"] = SignalResult(
                    name="entity_continuity",
                    value=ent_val,
                    available=True,
                    method="graph_entity_overlap",
                    evidence_count=len(shared_ents) + len(shared_names),
                    quality=min(1.0, len(all_ents) / 5.0) if all_ents else 0.5,
                )

        # 5. Relationship Continuity
        if config.ablation_disable_relationship_continuity:
            signals["relationship_continuity"] = SignalResult(
                name="relationship_continuity",
                value=0.0,
                available=False,
                method="ablation_disabled",
                missing_reason="ablation_flag_active",
            )
        else:
            rel_targets_a = {r.get("target_id") or r.get("target") for r in unit_a.relationships if (r.get("target_id") or r.get("target"))}
            rel_targets_b = {r.get("target_id") or r.get("target") for r in unit_b.relationships if (r.get("target_id") or r.get("target"))}
            ent_ids_a = {e["id"] for e in unit_a.entities if "id" in e}
            ent_ids_b = {e["id"] for e in unit_b.entities if "id" in e}
            shared_rel_targets = rel_targets_a & rel_targets_b
            cross_rel = (ent_ids_a & rel_targets_b) | (ent_ids_b & rel_targets_a)

            if not rel_targets_a and not rel_targets_b and not cross_rel:
                shared_ents = ent_ids_a & ent_ids_b
                if shared_ents:
                    signals["relationship_continuity"] = SignalResult(
                        name="relationship_continuity",
                        value=0.50,
                        available=True,
                        method="shared_entity_relational_implication",
                        evidence_count=len(shared_ents),
                        quality=0.5,
                    )
                else:
                    signals["relationship_continuity"] = SignalResult(
                        name="relationship_continuity",
                        value=None,
                        available=False,
                        method="graph_relationship_overlap",
                        evidence_count=0,
                        quality=0.0,
                        missing_reason="no_relationships_extracted_in_adjacent_units",
                    )
            else:
                if shared_rel_targets or cross_rel:
                    rel_val = 0.85
                    ev_count = len(shared_rel_targets) + len(cross_rel)
                else:
                    rel_val = 0.0
                    ev_count = 0
                signals["relationship_continuity"] = SignalResult(
                    name="relationship_continuity",
                    value=rel_val,
                    available=True,
                    method="graph_relationship_overlap",
                    evidence_count=ev_count,
                    quality=min(1.0, (len(rel_targets_a | rel_targets_b)) / 4.0),
                )

        # 6. Graph Connectivity & Shortest Path in Temporary Graph
        if not HAS_NETWORKX or graph is None or len(graph.nodes) == 0:
            ent_ids_a = {e["id"] for e in unit_a.entities if "id" in e}
            ent_ids_b = {e["id"] for e in unit_b.entities if "id" in e}
            shared_ents = ent_ids_a & ent_ids_b
            if shared_ents:
                signals["graph_connectivity"] = SignalResult(
                    name="graph_connectivity",
                    value=0.75,
                    available=True,
                    method="shared_entity_bipartite_fallback",
                    evidence_count=len(shared_ents),
                    quality=0.75,
                )
            else:
                signals["graph_connectivity"] = SignalResult(
                    name="graph_connectivity",
                    value=None,
                    available=False,
                    method="networkx_shortest_path",
                    evidence_count=0,
                    quality=0.0,
                    missing_reason="graph_not_constructed",
                )
        elif graph.has_node(unit_a.candidate_id) and graph.has_node(unit_b.candidate_id):
            try:
                if nx.has_path(graph, unit_a.candidate_id, unit_b.candidate_id):
                    dist = nx.shortest_path_length(graph, unit_a.candidate_id, unit_b.candidate_id)
                    if dist == 2:
                        conn_val = 1.0
                    elif dist <= 4:
                        conn_val = 0.6
                    else:
                        conn_val = 0.2
                    signals["graph_connectivity"] = SignalResult(
                        name="graph_connectivity",
                        value=conn_val,
                        available=True,
                        method="networkx_shortest_path",
                        evidence_count=1,
                        quality=1.0,
                    )
                else:
                    signals["graph_connectivity"] = SignalResult(
                        name="graph_connectivity",
                        value=0.0,
                        available=True,
                        method="networkx_shortest_path",
                        evidence_count=0,
                        quality=1.0,
                    )
            except Exception as e:
                signals["graph_connectivity"] = SignalResult(
                    name="graph_connectivity",
                    value=None,
                    available=False,
                    method="networkx_shortest_path",
                    evidence_count=0,
                    quality=0.0,
                    missing_reason=f"graph_traversal_error: {str(e)}",
                )
        else:
            ent_ids_a = {e["id"] for e in unit_a.entities if "id" in e}
            ent_ids_b = {e["id"] for e in unit_b.entities if "id" in e}
            shared_ents = ent_ids_a & ent_ids_b
            if shared_ents:
                signals["graph_connectivity"] = SignalResult(
                    name="graph_connectivity",
                    value=0.75,
                    available=True,
                    method="shared_entity_bipartite_fallback",
                    evidence_count=len(shared_ents),
                    quality=0.75,
                )
            else:
                signals["graph_connectivity"] = SignalResult(
                    name="graph_connectivity",
                    value=None,
                    available=False,
                    method="networkx_shortest_path",
                    evidence_count=0,
                    quality=0.0,
                    missing_reason="candidate_nodes_missing_from_graph",
                )

        # 7. Community Continuity
        signals["community_continuity"] = compute_community_continuity_signal(
            unit_a=unit_a,
            unit_b=unit_b,
            config=config,
            node_to_community=node_to_community,
        )

        # 8. Cross-Section Dependency
        signals["cross_section"] = compute_cross_section_signal(
            unit_a=unit_a,
            unit_b=unit_b,
        )

        return signals
