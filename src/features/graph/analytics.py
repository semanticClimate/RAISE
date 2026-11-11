"""
RAISE Graph Analytics & Modularity Engine
==========================================
Purpose:
  Provides community detection, centrality scoring, and hierarchical community
  summarization over in-memory NetworkX directed/undirected property graphs.

Analytics Capabilities:
  - Modularity & Community Detection:
      Applies Louvain community detection (or Clauset-Newman-Moore greedy modularity)
      to identify dense entity clusters (e.g. Governance, Bio-Incubation, Academic Depts).
  - Multi-Metric Centrality Scoring:
      Computes PageRank, degree centrality, and betweenness centrality.
      Optionally excludes super-hub institutions to prevent peripheral entity starvation.
  - Hierarchical Community Summarization:
      Synthesizes natural-language cluster summaries anchored by top hub entities
      for global-level GraphRAG reasoning.

Author: RAISE Core Architecture Team
Maintainability: Keep under 250 lines with pure NetworkX analytical routines.
"""

from __future__ import annotations
from typing import Any, Dict, List
import networkx as nx


def detect_communities(graph: nx.DiGraph, algorithm: str = "louvain") -> List[Dict[str, Any]]:
    """
    Dual-Tier Analytical Processing: Offload community detection from Neo4j to NetworkX.
    Supports Louvain modularity optimization and greedy modularity communities.
    """
    if graph.number_of_nodes() == 0:
        return []

    undirected_g = graph.to_undirected()
    communities_list = []
    
    try:
        if algorithm == "louvain" and hasattr(nx.community, "louvain_communities"):
            raw_communities = nx.community.louvain_communities(undirected_g, seed=42)
        else:
            raw_communities = list(nx.community.greedy_modularity_communities(undirected_g))
    except Exception:
        raw_communities = list(nx.connected_components(undirected_g))

    # Compute PageRank scores for hub ranking
    try:
        pagerank_scores = nx.pagerank(graph, max_iter=100, alpha=0.85)
    except Exception:
        pagerank_scores = {n: float(graph.degree(n)) for n in graph.nodes()}

    for cid, comm in enumerate(raw_communities):
        members = list(comm)
        sorted_members = sorted(members, key=lambda n: pagerank_scores.get(n, 0.0), reverse=True)
        
        member_details = []
        entity_types = {}
        for m in sorted_members:
            node_data = graph.nodes[m]
            ntype = node_data.get("type", "Entity")
            entity_types[ntype] = entity_types.get(ntype, 0) + 1
            member_details.append({
                "id": m,
                "label": node_data.get("label", m),
                "type": ntype,
                "pagerank": round(float(pagerank_scores.get(m, 0.0)), 4),
                "page": node_data.get("page", 1),
            })

        top_hubs = [m["label"] for m in member_details[:3]]
        primary_domain = max(entity_types.items(), key=lambda x: x[1])[0] if entity_types else "General"

        communities_list.append({
            "community_id": cid + 1,
            "size": len(members),
            "primary_domain": primary_domain,
            "top_hubs": top_hubs,
            "members": member_details,
        })

    return communities_list


def compute_centrality_metrics(graph: nx.DiGraph, exclude_super_hubs: bool = True) -> Dict[str, Dict[str, float]]:
    """
    Compute node centrality metrics (PageRank, Degree, Betweenness) via NetworkX.
    When exclude_super_hubs=True, prunes high-degree institutional super-hubs (e.g. IIT Madras, IITMIC)
    to prevent them from starving peripheral leaf entities.
    """
    if graph.number_of_nodes() == 0:
        return {}

    calc_graph = graph
    if exclude_super_hubs and graph.number_of_nodes() > 5:
        calc_graph = graph.copy()
        degree_dict = dict(calc_graph.degree())
        sorted_degrees = sorted(degree_dict.values(), reverse=True)
        high_degree_threshold = sorted_degrees[max(0, len(sorted_degrees) // 10)] if sorted_degrees else 20
        
        hubs_to_prune = [
            n for n, d in degree_dict.items()
            if (d >= high_degree_threshold and d >= 5) or
            calc_graph.nodes[n].get("type") in ["Institution", "University", "EcosystemEnabler", "Incubator"]
        ]
        if len(hubs_to_prune) < calc_graph.number_of_nodes():
            calc_graph.remove_nodes_from(hubs_to_prune)

    try:
        pr = nx.pagerank(calc_graph, max_iter=100, alpha=0.85)
    except Exception:
        pr = {}

    try:
        deg = nx.degree_centrality(calc_graph)
    except Exception:
        deg = {}

    try:
        bet = nx.betweenness_centrality(calc_graph, k=min(50, len(calc_graph)))
    except Exception:
        bet = {}

    metrics = {}
    for n in graph.nodes():
        metrics[n] = {
            "pagerank": round(float(pr.get(n, 0.0)), 4),
            "degree_centrality": round(float(deg.get(n, 0.0)), 4),
            "betweenness_centrality": round(float(bet.get(n, 0.0)), 4),
        }
    return metrics


def generate_hierarchical_summaries(graph: nx.DiGraph, max_communities: int = 5) -> List[Dict[str, Any]]:
    """
    Hierarchical Community Summarization for global GraphRAG queries.
    """
    communities = detect_communities(graph)
    summaries = []

    for comm in communities[:max_communities]:
        cid = comm["community_id"]
        hubs = ", ".join(comm["top_hubs"])
        domain = comm["primary_domain"]
        size = comm["size"]
        
        summary_text = (
            f"Community #{cid} ({domain} Cluster, {size} entities): "
            f"Anchored around key hubs [{hubs}]. Contains dense relational interactions "
            f"spanning institutional governance, research funding, and academic operations."
        )
        summaries.append({
            "community_id": cid,
            "domain": domain,
            "size": size,
            "top_hubs": comm["top_hubs"],
            "summary": summary_text,
        })

    return summaries
