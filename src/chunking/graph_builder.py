"""
Temporary Knowledge Graph Construction & Community Detection
============================================================
Component: `src.chunking.graph_builder`
Architecture Layer: Document Processing / Chunking & Graph Signal Extraction

Overview:
---------
Constructs a temporary NetworkX bipartite / projection graph of Candidate Units and Entities.
Used exclusively for boundary optimization, shortest-path topological distance measurement,
and Louvain community detection prior to chunk boundary finalization.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from .models import CandidateUnit

logger = logging.getLogger("raise.chunking.graph_builder")


class TemporaryGraphBuilder:
    """
    Constructs an intermediate NetworkX bipartite / projection graph of Candidate Units and Entities.
    Used exclusively for boundary optimization and community detection before chunk finalization.
    """

    def __init__(self):
        pass

    def build_graph(self, candidates: List[CandidateUnit]) -> Any:
        """Constructs a NetworkX graph connecting candidates to mentioned entities and entity-to-entity relations."""
        if not HAS_NETWORKX:
            return None

        G = nx.Graph()

        for cand in candidates:
            cid = cand.candidate_id
            G.add_node(cid, node_type="candidate", heading=cand.heading, page=cand.page_start)

            for ent in cand.entities:
                eid = ent["id"]
                G.add_node(eid, node_type="entity", label=ent.get("label", "Entity"), name=ent.get("name", eid))
                G.add_edge(cid, eid, relation="MENTIONS")

            for rel in cand.relationships:
                sid = rel["source_id"]
                tid = rel["target_id"]
                rtype = rel.get("relation_type", "RELATED_TO")
                if sid != cid and tid != cid:
                    G.add_node(sid, node_type="entity")
                    G.add_node(tid, node_type="entity")
                    G.add_edge(sid, tid, relation=rtype)

        return G

    def detect_communities(self, G: Any) -> Dict[str, str]:
        """
        Detects communities across the temporary graph using Louvain or connected components.
        Returns a mapping from node_id -> community_id.
        """
        if not HAS_NETWORKX or G is None or len(G.nodes) == 0:
            return {}

        try:
            from networkx.algorithms.community import louvain_communities
            communities = louvain_communities(G, seed=42)
            node_to_comm: Dict[str, str] = {}
            for c_idx, comm in enumerate(communities, start=1):
                c_label = f"comm_{c_idx:02d}"
                for node in comm:
                    node_to_comm[str(node)] = c_label
            return node_to_comm
        except Exception:
            node_to_comm = {}
            for c_idx, comp in enumerate(nx.connected_components(G), start=1):
                c_label = f"comp_{c_idx:02d}"
                for node in comp:
                    node_to_comm[str(node)] = c_label
            return node_to_comm
