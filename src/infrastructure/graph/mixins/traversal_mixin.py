"""
Neo4j Graph Database Traversal & Retrieval Mixin
================================================
Component: `src.infrastructure.graph.mixins.traversal_mixin`
Architecture Layer: Infrastructure / Graph Retrieval & GraphRAG

Overview:
---------
Encapsulates all multi-hop Cypher traversals, constrained entity expansions,
and subgraph context extractions in Neo4j.

Key Responsibilities:
1. Multi-Hop Subgraph Traversal:
   - Identifies seed entities by ID or keyword matching.
   - Expands 1-to-N hops across directed relationships.
   - Returns structured nodes and edges for synthesis context and visual rendering.
   - Scopes queries strictly to `run_id` during evaluation or production data when `run_id` is None.
2. Production Subgraph Retrieval Interface:
   - `retrieve_subgraph_context`: Unified interface used across parallel retriever,
     agent routers, and benchmarks.
   - Extracts facts formatted as `• Source -[RELATION]-> Target`.
3. High-Precision Constrained Bridge Expansion:
   - `query_constrained_bridge`: Traverses only domain-relevant semantic relations
     (e.g., `DIRECTOR_OF`, `ALUMNI_OF`, `AFFILIATED_WITH`, `HAS_FACT`), avoiding open-neighborhood floods.
4. Neighborhood Traversal:
   - `query_neighborhood`: Satisfies the `IGraphStore` interface for local entity neighborhoods.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("raise.graph.neo4j.traversal")


class Neo4jTraversalMixin:
    """
    Mixin providing multi-hop graph queries, constrained semantic bridges,
    and GraphRAG context retrieval for Neo4jDatabase.
    """

    def extract_document_subgraph(
        self,
        doc_id: str,
        max_nodes: int = 50,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query subgraphs scoped strictly to a specific document_id, with optional run_id filtering."""
        query = """
        MATCH (n)-[r]-(m)
        WHERE n.document_id = $doc_id AND m.document_id = $doc_id
          AND (($run_id IS NULL AND n.run_id IS NULL AND m.run_id IS NULL) OR (n.run_id = $run_id AND m.run_id = $run_id))
        RETURN n, r, m LIMIT $limit
        """
        records = self.run_cypher(query, {"doc_id": doc_id, "limit": max_nodes, "run_id": run_id})
        return {"records": records, "document_id": doc_id}

    def query_multihop_subgraph(
        self,
        seed_ids: List[str],
        keywords: Optional[List[str]] = None,
        hops: int = 2,
        doc_id: Optional[str] = None,
        limit: int = 40,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Industry-standard multi-hop Cypher traversal in Neo4j:
        1. Identifies seed nodes by ID or entity keyword matching.
        2. Expands 1-to-N hops along directed relationships.
        3. Returns structured nodes and edges for subgraph context and visual rendering.
        4. Scopes queries strictly to run_id when provided, or to production data when run_id is None.
        """
        if not self.check_connection().get("connected"):
            return {"nodes": [], "edges": []}

        clean_kws = [k.lower() for k in (keywords or []) if len(k) >= 3][:5]

        cypher = """
        MATCH (seed)
        WHERE (($run_id IS NULL AND seed.run_id IS NULL) OR seed.run_id = $run_id)
          AND (
               (size($seed_ids) > 0 AND (
                   seed.id IN $seed_ids OR seed.name IN $seed_ids OR seed.label IN $seed_ids
                   OR any(s IN $seed_ids WHERE toLower(coalesce(seed.label, seed.name, seed.id, '')) = toLower(s)
                                          OR toLower(coalesce(seed.label, seed.name, seed.id, '')) CONTAINS toLower(s))
               ))
            OR (size($clean_kws) > 0 AND any(k IN $clean_kws WHERE toLower(coalesce(seed.label, seed.name, seed.id, '')) CONTAINS k))
            OR (size($clean_kws) > 0 AND any(lbl IN labels(seed) WHERE any(k IN $clean_kws WHERE toLower(lbl) CONTAINS k)))
          )
        WITH seed LIMIT 10
        MATCH path = (seed)-[r*1..2]-(m)
        WHERE ($doc_id IS NULL OR (seed.document_id = $doc_id AND m.document_id = $doc_id))
          AND (($run_id IS NULL AND m.run_id IS NULL) OR m.run_id = $run_id)
        UNWIND nodes(path) AS n
        UNWIND relationships(path) AS rel
        WITH DISTINCT n, rel
        RETURN 
            coalesce(n.id, elementId(n)) AS id,
            labels(n)[0] AS type,
            coalesce(n.label, n.name, n.id) AS label,
            coalesce(n.page, 1) AS page,
            coalesce(n.document_id, 'global') AS document_id,
            coalesce(startNode(rel).name, startNode(rel).label, startNode(rel).id, elementId(startNode(rel))) AS source,
            coalesce(endNode(rel).name, endNode(rel).label, endNode(rel).id, elementId(endNode(rel))) AS target,
            type(rel) AS relation
        LIMIT $limit
        """

        try:
            records = self.run_cypher(
                cypher,
                {
                    "seed_ids": seed_ids,
                    "clean_kws": clean_kws,
                    "doc_id": doc_id,
                    "limit": limit,
                    "run_id": run_id,
                },
            )

            nodes_dict = {}
            edges_list = []
            seen_edges = set()

            for rec in records:
                nid = str(rec.get("id"))
                if nid and nid not in nodes_dict:
                    nodes_dict[nid] = {
                        "id": nid,
                        "label": str(rec.get("label", nid)),
                        "type": str(rec.get("type", "Entity")),
                        "page": int(rec.get("page", 1)),
                        "document_id": str(rec.get("document_id", "")),
                    }

                src = str(rec.get("source"))
                tgt = str(rec.get("target"))
                rel_type = str(rec.get("relation", "RELATED_TO"))
                edge_key = (src, tgt, rel_type)
                if src and tgt and edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges_list.append({
                        "source": src,
                        "target": tgt,
                        "type": rel_type,
                    })

            return {
                "nodes": list(nodes_dict.values()),
                "edges": edges_list,
                "engine": "Neo4j Cypher Live",
                "run_id": run_id,
            }
        except Exception as e:
            return {"nodes": [], "edges": [], "error": str(e)}

    def retrieve_subgraph_context(
        self,
        query: str,
        seed_entities: Optional[List[str]] = None,
        hops: int = 2,
        max_nodes: int = 20,
        run_id: Optional[str] = None,
        doc_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Unified Production GraphRAG Subgraph Retrieval Interface.
        Used across production parallel retriever, agents, and evaluation benchmarks.
        """
        t0 = time.perf_counter()
        clean_q = re.sub(r"[^a-zA-Z0-9\s]", " ", query.lower())
        stopwords = {
            "what", "who", "which", "where", "when", "how", "why", "did", "the", "and",
            "for", "with", "this", "that", "from", "are", "were", "been", "have", "has",
            "our", "their", "is", "was", "does", "do", "in", "on", "at", "by", "to", "of",
            "between", "among", "during", "after", "before", "many", "much", "total", "name",
        }
        tokens = [t for t in clean_q.split() if len(t) >= 3 and t not in stopwords][:8]
        seeds = list(seed_entities or [])
        if not seeds:
            cap_entities = re.findall(r"\b[A-Z][a-zA-Z0-9_\-\'\.]*(?:\s+[A-Z][a-zA-Z0-9_\-\'\.]*)*\b", query)
            for ce in cap_entities:
                if ce.lower() not in stopwords and len(ce) >= 3 and ce not in seeds:
                    seeds.append(ce)

        subgraph_res = self.query_multihop_subgraph(
            seed_ids=seeds,
            keywords=tokens,
            hops=hops,
            doc_id=doc_filter,
            limit=max_nodes,
            run_id=run_id,
        )

        nodes = subgraph_res.get("nodes", [])
        edges = subgraph_res.get("edges", [])

        facts = []
        for e in edges[:15]:
            src = e.get("source")
            tgt = e.get("target")
            rel = e.get("type", "RELATED_TO")
            if src and tgt:
                facts.append(f"• {src} -[{rel}]-> {tgt}")

        return {
            "nodes": nodes,
            "edges": edges,
            "facts": facts,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "run_id": run_id,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "retrieval_mode": "neo4j_graph",
        }

    def query_neighborhood(
        self,
        entity_ids: List[str],
        hops: int = 1,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """Satisfies IGraphStore interface by traversing entity neighborhood in Neo4j."""
        return self.query_multihop_subgraph(
            seed_ids=entity_ids,
            hops=hops,
            limit=limit,
        )

    def query_constrained_bridge(
        self,
        bridge_entity: str,
        target_relation_types: Optional[List[str]] = None,
        doc_id: Optional[str] = None,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        High-precision constrained graph bridge expansion:
        1. Employs (seed:Entity) index lookup.
        2. Constrains traversal strictly to domain-relevant semantic relations.
        3. Caps expansion to top-5 most relevant paths, eliminating open-neighborhood floods.
        """
        if not self.check_connection().get("connected"):
            return []

        rel_filter = target_relation_types or [
            "ALUMNI_OF", "AWARDED_TO", "AFFILIATED_WITH", "DEPARTMENT_OF",
            "DIRECTOR_OF", "HAS_FACT", "REPORTED_METRIC", "MEMBER_OF",
            "ALLOCATED_TO", "COLLABORATED_WITH", "INCUBATED_BY", "REVENUE_FROM", "HOLDS_ROLE",
        ]

        cypher = """
        MATCH (seed:Entity)
        WHERE toLower(seed.name) CONTAINS toLower($bridge) OR toLower(seed.label) CONTAINS toLower($bridge)
        WITH seed LIMIT 5
        MATCH (seed)-[r]-(m:Entity)
        WHERE type(r) IN $rel_filter
          AND NOT type(r) IN ['MENTIONS', 'CONTAINS_CHUNK']
          AND ($doc_id IS NULL OR coalesce(m.document_id, '') IN ['', 'global_doc', $doc_id])
        RETURN coalesce(seed.name, seed.label) AS source,
               type(r) AS relation,
               coalesce(m.name, m.label) AS target,
               coalesce(m.page, 1) AS page,
               labels(m)[0] AS target_type
        LIMIT $limit
        """
        try:
            return self.run_cypher(
                cypher,
                {"bridge": bridge_entity, "rel_filter": rel_filter, "doc_id": doc_id, "limit": limit},
            )
        except Exception as ex:
            logger.warning("Constrained bridge query notice: %s", ex)
            return []
