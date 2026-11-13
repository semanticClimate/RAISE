"""
RAISE Advanced GraphRAG Engine
===============================
Purpose:
  Extracts Organizations, Leaders, Patents, Initiatives, Funding, Programs, Departments, and Regulations.
  Builds typed multi-hop property graphs with Cypher generation for Neo4j.
  Supports Multi-Hop Subgraph Traversal and Graph-Context Assembly.

Architecture:
  - `src.features.graph.builder`: Triple ingestion and chunk entity extraction.
  - `src.features.graph.analytics`: Louvain community detection, PageRank, and cluster summarization.
  - `GraphRAGEngine`: Master coordinator holding the in-memory NetworkX DiGraph, managing subgraph
    neighborhood expansions, and generating idempotent Cypher scripts.

Author: RAISE Core Architecture Team
Maintainability: Keep under 250 lines with full typing and backward compatibility.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

import networkx as nx

try:
    import neo4j
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False

from src.features.graph.builder import (
    slugify,
    build_from_academic_triples,
    build_from_chunks,
)
from src.features.graph.analytics import (
    detect_communities,
    compute_centrality_metrics,
    generate_hierarchical_summaries,
)

__all__ = ["GraphRAGEngine", "slugify"]


class GraphRAGEngine:
    """
    State-of-the-Art Property Graph & Entity Extraction Engine.
    Converts semantic document sections into structured knowledge graphs.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.doc_id = "default"
        self.node_provenance: Dict[str, Dict[str, Any]] = {}

    def build_from_academic_triples(
        self,
        triples_data: List[Dict[str, Any]],
        doc_id: str = "default",
    ) -> Dict[str, Any]:
        """Populate NetworkX graph from extracted academic entity and relation triples."""
        self.doc_id = doc_id
        build_from_academic_triples(
            graph=self.graph,
            node_provenance=self.node_provenance,
            triples_data=triples_data,
            doc_id=doc_id,
        )
        return self.get_graph_data()

    def build_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
        taxonomy_report: Optional[Dict[str, Any]] = None,
        doc_id: str = "default",
    ) -> Dict[str, Any]:
        """Perform deep multi-entity extraction and construct directed relationship graph."""
        self.doc_id = doc_id
        build_from_chunks(
            graph=self.graph,
            chunks=chunks,
            taxonomy_report=taxonomy_report,
            doc_id=doc_id,
        )
        return self.get_graph_data()

    def extract_subgraph(
        self,
        seed_node_ids: List[str],
        hops: int = 2,
        max_nodes: int = 40,
    ) -> Dict[str, Any]:
        """
        Traverse neighbourhood of seed nodes up to 'hops' relationship steps.
        Returns sub-graph and structured text summary.
        """
        subgraph_nodes: Set[str] = set()
        
        valid_seeds = [nid for nid in seed_node_ids if self.graph.has_node(nid)]
        if not valid_seeds:
            valid_seeds = sorted(self.graph.nodes(), key=lambda n: self.graph.degree(n), reverse=True)[:5]

        # Multi-Hop Neighborhood Expansion (BFS)
        frontier = set(valid_seeds)
        subgraph_nodes.update(frontier)

        for _ in range(hops):
            next_frontier = set()
            for current_node in frontier:
                for succ in self.graph.successors(current_node):
                    if succ not in subgraph_nodes:
                        next_frontier.add(succ)
                for pred in self.graph.predecessors(current_node):
                    if pred not in subgraph_nodes:
                        next_frontier.add(pred)
            subgraph_nodes.update(next_frontier)
            frontier = next_frontier
            if len(subgraph_nodes) >= max_nodes:
                break

        # Extract induced subgraph
        sub_g = self.graph.subgraph(list(subgraph_nodes)[:max_nodes])

        nodes = []
        for n, d in sub_g.nodes(data=True):
            nodes.append({
                "id": n,
                "label": d.get("label", n),
                "type": d.get("type", "Node"),
                "color": d.get("color", "#64748b"),
                "size": d.get("size", 16),
                "page": d.get("page", 1),
                "properties": d.get("properties", {}),
                "provenance": d.get("provenance", {}),
            })

        edges = []
        structured_triples = []
        for u, v, d in sub_g.edges(data=True):
            rel = d.get("relation") or d.get("type") or "RELATED_TO"
            edges.append({
                "source": u,
                "target": v,
                "relation": rel,
            })
            u_lbl = sub_g.nodes[u].get("label", u)
            v_lbl = sub_g.nodes[v].get("label", v)
            structured_triples.append(f"({u_lbl}) -[:{rel}]-> ({v_lbl})")

        # Assemble structured context text
        assembled_context_lines = [
            "### Knowledge Graph Subgraph Context",
            f"**Total Traversed Nodes**: {len(nodes)} | **Directed Relations**: {len(edges)}",
            "",
            "**Key Graph Entities & Facts**:",
        ]
        for n in nodes[:15]:
            n_type = n["type"]
            n_lbl = n["label"]
            prov = n.get("provenance", {})
            doc = prov.get("pdf_filename", "Report")
            pg = prov.get("page_number", n.get("page", 1))
            assembled_context_lines.append(f"- **{n_lbl}** ({n_type}) — [Doc: {doc}, Page {pg}]")

        assembled_context_lines.append("\n**Directed Entity Relationships**:")
        for trip in structured_triples[:20]:
            assembled_context_lines.append(f"- {trip}")

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
            "structured_triples": structured_triples,
            "assembled_text_context": "\n".join(assembled_context_lines),
        }

    def get_graph_data(self) -> Dict[str, Any]:
        """Export complete graph in D3.js force-directed graph node-link format."""
        nodes = []
        for n, d in self.graph.nodes(data=True):
            nodes.append({
                "id": n,
                "label": d.get("label", n),
                "type": d.get("type", "Node"),
                "color": d.get("color", "#64748b"),
                "size": d.get("size", 14),
                "page": d.get("page", 1),
                "properties": d.get("properties", {}),
                "provenance": d.get("provenance", {}),
            })

        edges = []
        for u, v, d in self.graph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "relation": d.get("relation") or d.get("type") or "RELATED_TO",
            })

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    def detect_communities(self, algorithm: str = "louvain") -> List[Dict[str, Any]]:
        """Dual-Tier Analytical Processing: Offload community detection from Neo4j to NetworkX."""
        return detect_communities(self.graph, algorithm=algorithm)

    def compute_centrality_metrics(self, exclude_super_hubs: bool = True) -> Dict[str, Dict[str, float]]:
        """Compute node centrality metrics (PageRank, Degree, Betweenness) via NetworkX."""
        return compute_centrality_metrics(self.graph, exclude_super_hubs=exclude_super_hubs)

    def generate_hierarchical_summaries(self, max_communities: int = 5) -> List[Dict[str, Any]]:
        """Hierarchical Community Summarization for global GraphRAG queries."""
        return generate_hierarchical_summaries(self.graph, max_communities=max_communities)

    def generate_cypher_script(self) -> str:
        """Generate complete idempotent Cypher script for Neo4j."""
        lines = [
            "// ========================================================",
            "// RAISE GraphRAG - Neo4j Knowledge Graph Ingestion Script",
            f"// Nodes: {self.graph.number_of_nodes()} | Edges: {self.graph.number_of_edges()}",
            "// ========================================================\n",
        ]

        for n, d in self.graph.nodes(data=True):
            ntype = d.get("type", "Entity").replace(" ", "_")
            lbl = d.get("label", n).replace('"', '\\"')
            lines.append(f'MERGE (n_{slugify(n)}:{ntype} {{id: "{n}"}}) ON CREATE SET n_{slugify(n)}.label = "{lbl}"')

        lines.append("")
        for u, v, d in self.graph.edges(data=True):
            rel = (d.get("relation") or d.get("type") or "RELATED_TO").upper().replace(" ", "_")
            lines.append(f'MERGE (n_{slugify(u)})-[:{rel}]->(n_{slugify(v)})')

        return "\n".join(lines)

    def remove_document_nodes(self, doc_id: str, entity_ids: Optional[List[str]] = None) -> int:
        """Removes all nodes associated with a document from the NetworkX graph."""
        to_remove = set()
        if entity_ids:
            to_remove.update(entity_ids)
        for n, d in list(self.graph.nodes(data=True)):
            if d.get("document_id") == doc_id or str(n).startswith(f"{doc_id}_"):
                to_remove.add(n)
        
        valid_remove = [n for n in to_remove if self.graph.has_node(n)]
        self.graph.remove_nodes_from(valid_remove)
        for n in valid_remove:
            self.node_provenance.pop(n, None)
        return len(valid_remove)

    def clear(self):
        """Clears all nodes and edges from the graph."""
        self.graph.clear()
        self.node_provenance.clear()
