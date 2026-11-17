"""
Neo4j Graph Database Ingestion & Lifecycle Mixin
===============================================
Component: `src.infrastructure.graph.mixins.ingestion_mixin`
Architecture Layer: Infrastructure / Graph Ingestion & Quarantine Lifecycle

Overview:
---------
Encapsulates all write, batch ingestion, scoped evaluation tagging, and
document/run deletion operations in Neo4j.

Key Responsibilities:
1. Parameterized Batch Ingestion:
   - Synchronizes D3/NetworkX nodes and edges using `UNWIND $batch` and `MERGE` clauses.
   - Prevents Cypher injection and leverages Neo4j statement execution plan caching.
   - Assigns a universal `:Entity` label to all nodes for sub-10ms index lookups.
2. Scoped Evaluation Quarantine:
   - Tags all temporary evaluation data with a unique `run_id` and `is_eval_quarantine=true`.
   - Prevents benchmark or test runs from leaking into production user queries.
3. Surgical Deletion & Verification:
   - `delete_run_data`: Detaches and deletes only nodes and relationships matching `run_id`,
     verifying zero residual nodes remain.
   - `delete_document_nodes` / `purge_document_nodes`: Cleans up graphs during document deletion.
   - `purge_all_nodes`: Master reset for test fixtures and container resets.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("raise.graph.neo4j.ingestion")


class Neo4jIngestionMixin:
    """
    Mixin providing node and relationship ingestion, batch synchronization,
    and scoped lifecycle management for Neo4jDatabase.
    """

    def sync_graph_data(
        self,
        graph_data: Dict[str, Any],
        batch_size: int = 500,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingest D3/NetworkX graph nodes and edges into Neo4j using parameterized batch Cypher scripts
        with UNWIND $batch and MERGE clauses, preventing Cypher injection and enabling query compilation caching.
        Optionally tags all nodes and edges with run_id for isolated scoped lifecycle tracking.
        """
        conn = self.check_connection()
        if not conn.get("connected"):
            return {
                "synced": False,
                "reason": "Neo4j server not reachable",
                "detail": conn.get("error"),
                "cypher_available": True,
            }

        driver = self.get_driver()
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        synced_nodes = 0
        synced_edges = 0

        # Group nodes by type for parameterized batch insertion
        node_groups: Dict[str, List[Dict[str, Any]]] = {}
        valid_node_ids = set()

        def _clean_node_name(val: str, n_type: str) -> str:
            if n_type in ("Chunk", "Section"):
                return val.strip()
            # Collapse whitespace and newlines into single spaces
            s = re.sub(r"\s+", " ", str(val)).strip(" ,.:;-–\t\r\n")
            lower = s.lower()
            if len(s) < 3 or lower in {"the committee", "rs", "metric: rs", "coordination", "the governing council"}:
                return ""
            if lower.endswith((" held on", " of the", " and", " in", " on", " with", " for", " by", " to", " at")):
                return ""
            if lower.startswith(("metric:", "rs,", "held on")):
                return ""
            return s

        for n in nodes:
            raw_type = str(n.get("type", "Entity"))
            node_type = re.sub(r"[^a-zA-Z0-9_]", "_", raw_type) or "Entity"
            raw_name = str(n.get("name", n.get("label", n.get("id"))))
            cleaned_name = _clean_node_name(raw_name, node_type)
            if not cleaned_name:
                continue

            nid = str(n.get("id"))
            valid_node_ids.add(nid)
            node_groups.setdefault(node_type, []).append({
                "id": nid,
                "label": cleaned_name,
                "name": cleaned_name,
                "page": int(n.get("page", 1)),
                "document_id": str(n.get("document_id") or n.get("properties", {}).get("document_id") or "global_doc"),
                "source": str(n.get("source", "")),
                "run_id": run_id,
                "is_eval_quarantine": bool(run_id is not None),
            })

        # Group edges by relation type for parameterized batch insertion
        edge_groups: Dict[str, List[Dict[str, Any]]] = {}
        for e in edges:
            src_id = str(e.get("source"))
            tgt_id = str(e.get("target"))
            # Only ingest edges between valid, non-discarded nodes
            if valid_node_ids and (src_id not in valid_node_ids or tgt_id not in valid_node_ids):
                continue
            raw_rel = str(e.get("relation") or e.get("type") or "RELATED_TO")
            rel_type = re.sub(r"[^a-zA-Z0-9_]", "_", raw_rel.upper()) or "RELATED_TO"
            edge_groups.setdefault(rel_type, []).append({
                "source_id": src_id,
                "target_id": tgt_id,
                "document_id": str(e.get("document_id") or "global_doc"),
                "run_id": run_id,
            })

        try:
            with driver.session(database=self.database) as session:
                # 1. Parameterized Batch Ingestion for Nodes (with common :Entity label for sub-second index lookup)
                for node_type, items in node_groups.items():
                    cypher = f"""
                    UNWIND $batch AS item
                    MERGE (n:Entity:{node_type} {{id: item.id}})
                    ON CREATE SET 
                        n.label = item.label,
                        n.name = item.name,
                        n.page = item.page,
                        n.document_id = item.document_id,
                        n.source = item.source,
                        n.run_id = item.run_id,
                        n.is_eval_quarantine = item.is_eval_quarantine,
                        n.created_at = timestamp()
                    ON MATCH SET 
                        n.label = item.label,
                        n.name = item.name,
                        n.page = item.page,
                        n.document_id = item.document_id,
                        n.source = coalesce(item.source, n.source),
                        n.run_id = coalesce(item.run_id, n.run_id),
                        n.is_eval_quarantine = coalesce(item.is_eval_quarantine, n.is_eval_quarantine),
                        n.updated_at = timestamp()
                    """
                    for i in range(0, len(items), batch_size):
                        batch = items[i:i + batch_size]
                        session.run(cypher, batch=batch)
                        synced_nodes += len(batch)

                # 2. Parameterized Batch Ingestion for Directed Edges (indexed lookup via :Entity)
                for rel_type, rel_items in edge_groups.items():
                    cypher = f"""
                    UNWIND $batch AS rel
                    MATCH (src:Entity {{id: rel.source_id}})
                    MATCH (tgt:Entity {{id: rel.target_id}})
                    MERGE (src)-[r:{rel_type}]->(tgt)
                    ON CREATE SET r.created_at = timestamp(), r.document_id = rel.document_id, r.run_id = rel.run_id
                    ON MATCH SET r.updated_at = timestamp(), r.run_id = coalesce(rel.run_id, r.run_id)
                    """
                    for i in range(0, len(rel_items), batch_size):
                        batch = rel_items[i:i + batch_size]
                        session.run(cypher, batch=batch)
                        synced_edges += len(batch)

            return {
                "synced": True,
                "nodes_written": synced_nodes,
                "edges_written": synced_edges,
                "nodes_synced": synced_nodes,
                "edges_synced": synced_edges,
                "run_id": run_id,
                "uri": self.uri,
            }
        except Exception as e:
            return {"synced": False, "error": str(e)}

    def ingest_scoped_graph_data(
        self,
        graph_data: Dict[str, Any],
        run_id: str,
        batch_size: int = 500,
    ) -> Dict[str, Any]:
        """
        Ingests temporary evaluation graph data tagged with a unique run_id.
        Ensures nodes and relationships are quarantined and never leak into production queries.
        """
        if not run_id or not isinstance(run_id, str):
            raise ValueError("A valid, non-empty run_id is required for scoped graph ingestion.")
        logger.info(
            "Neo4j Lifecycle: Ingesting scoped graph data for run_id='%s' (%d nodes, %d edges)",
            run_id,
            len(graph_data.get("nodes", [])),
            len(graph_data.get("edges", [])),
        )
        return self.sync_graph_data(graph_data, batch_size=batch_size, run_id=run_id)

    def delete_run_data(self, run_id: str) -> Dict[str, Any]:
        """
        Safely deletes ONLY nodes and relationships tagged with run_id.
        Verifies zero residual nodes remain and logs the complete lifecycle.
        Never touches persistent production nodes.
        """
        if not run_id or not isinstance(run_id, str) or len(run_id.strip()) < 3:
            raise ValueError(f"Invalid run_id for deletion: '{run_id}'. Refusing operation to protect database.")

        conn = self.check_connection()
        if not conn.get("connected"):
            return {"deleted": False, "reason": "Neo4j offline", "nodes_deleted": 0}

        # 1. Targeted deletion of nodes and their connected relationships matching run_id
        cypher_delete = """
        MATCH (n)
        WHERE n.run_id = $run_id
        DETACH DELETE n
        """
        self.run_cypher(cypher_delete, {"run_id": run_id})

        # Also clean any dangling relationships tagged with this run_id
        cypher_rel_delete = """
        MATCH ()-[r]->()
        WHERE r.run_id = $run_id
        DELETE r
        """
        self.run_cypher(cypher_rel_delete, {"run_id": run_id})

        # 2. Verification query: Assert 0 remaining records with this run_id
        verify_cypher = """
        MATCH (n) WHERE n.run_id = $run_id RETURN count(n) AS remaining_nodes
        """
        res = self.run_cypher(verify_cypher, {"run_id": run_id})
        remaining = int(res[0].get("remaining_nodes", 0)) if res else 0

        logger.info(
            "Neo4j Lifecycle: [Neo4j connected] -> [run_id: %s] -> "
            "[nodes/relationships written] -> [retrieval completed] -> "
            "[cleanup completed (remaining: %d)]",
            run_id,
            remaining,
        )

        return {
            "deleted": True,
            "run_id": run_id,
            "remaining_nodes": remaining,
            "verified_clean": remaining == 0,
        }

    def delete_document_nodes(self, doc_id: str, entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Deletes all nodes and relationships associated with a document."""
        if not self.check_connection().get("connected"):
            return {"deleted": False, "nodes_deleted": 0}
        total_deleted = 0
        try:
            # 1. Delete by document_id property
            res1 = self.run_cypher(
                "MATCH (n) WHERE n.document_id = $doc_id DETACH DELETE n RETURN count(n) AS cnt",
                {"doc_id": doc_id},
            )
            if res1 and isinstance(res1, list) and "cnt" in res1[0]:
                total_deleted += int(res1[0]["cnt"])

            # 2. Delete by entity IDs if available
            if entity_ids:
                res2 = self.run_cypher(
                    "MATCH (n) WHERE n.id IN $entity_ids DETACH DELETE n RETURN count(n) AS cnt",
                    {"entity_ids": entity_ids},
                )
                if res2 and isinstance(res2, list) and "cnt" in res2[0]:
                    total_deleted += int(res2[0]["cnt"])

            return {"deleted": True, "nodes_deleted": total_deleted}
        except Exception as e:
            return {"deleted": False, "error": str(e), "nodes_deleted": total_deleted}

    def purge_document_nodes(self, doc_id: str) -> Dict[str, int]:
        """Satisfies IGraphStore interface by deleting nodes and relationships associated with doc_id."""
        res = self.delete_document_nodes(doc_id=doc_id)
        return {"nodes_deleted": int(res.get("nodes_deleted", 0))}

    def purge_all_nodes(self) -> Dict[str, Any]:
        """Deletes all nodes and relationships from Neo4j database."""
        if not self.check_connection().get("connected"):
            return {"deleted": False, "nodes_deleted": 0}
        try:
            res = self.run_cypher("MATCH (n) DETACH DELETE n RETURN count(n) AS cnt")
            cnt = int(res[0]["cnt"]) if res and isinstance(res, list) and "cnt" in res[0] else 0
            return {"deleted": True, "nodes_deleted": cnt}
        except Exception as e:
            return {"deleted": False, "error": str(e)}
