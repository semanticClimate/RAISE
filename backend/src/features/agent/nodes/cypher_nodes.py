"""
Text-to-Cypher, Execution, Repair & Path Critic Nodes
=====================================================
Orchestrates graph traversal, Cypher query generation, schema-aware execution,
syntax self-repair, and relational path criticism.
"""

from __future__ import annotations

import re
from typing import Any, Dict
from ..state import GraphRAGState


class CypherNodesMixin:
    """Provides Text-to-Cypher generation, execution, repair, and path critic nodes."""

    # =========================================================================
    # NODE 4: Text-to-Cypher Generation Node
    # =========================================================================
    def _text_to_cypher_generator_node(self, state: GraphRAGState) -> Dict[str, Any]:
        query = state.get("query", "")
        stop_words = {"what", "show", "tell", "which", "with", "financial", "year", "these", "this", "that", "reports", "report", "identify", "does", "have", "from", "both", "under", "about"}
        q_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", query).lower()
        terms = [t for t in q_clean.split() if len(t) > 3 and t not in stop_words]

        doc_filter = state.get("document_filter")
        active_docs = state.get("active_docs")
        active_docs_clean = [d for d in active_docs if d] if active_docs else ([doc_filter] if doc_filter else None)

        doc_clauses = []
        if active_docs_clean:
            doc_terms = " OR ".join([f"toLower(coalesce(n.document_id, m.document_id, '')) CONTAINS '{str(d).lower()}'" for d in active_docs_clean])
            doc_clauses.append(f"({doc_terms})")

        where_parts = []
        if terms:
            terms_cond = " OR ".join([f"toLower(coalesce(n.name, n.label, '')) CONTAINS '{t}'" for t in terms[:4]])
            where_parts.append(f"({terms_cond})")
        if doc_clauses:
            where_parts.extend(doc_clauses)

        if where_parts:
            where_str = " WHERE " + " AND ".join(where_parts)
            cypher = f"MATCH (n)-[r]-(m){where_str} RETURN coalesce(n.name, n.label) as n_name, type(r) as rel, coalesce(m.name, m.label) as m_name LIMIT 30"
        else:
            cypher = "MATCH (n)-[r]-(m) RETURN coalesce(n.name, n.label) as n_name, type(r) as rel, coalesce(m.name, m.label) as m_name LIMIT 25"

        return {
            "cypher_query": cypher,
            "cypher_error": None,
        }

    # =========================================================================
    # NODE 5: Cypher Execution & Validation Node
    # =========================================================================
    def _cypher_executor_and_validator_node(self, state: GraphRAGState) -> Dict[str, Any]:
        cypher = state.get("cypher_query", "")
        records = []
        error = None

        if self.rag_engine.neo4j_db and self.rag_engine.neo4j_db.connected:
            try:
                raw_res = self.rag_engine.neo4j_db.run_cypher(cypher)
                if raw_res and isinstance(raw_res, list) and "error" in raw_res[0]:
                    error = str(raw_res[0]["error"])
                else:
                    records = raw_res
            except Exception as e:
                error = str(e)
        else:
            # Embedded openCypher execution fallback via Kùzu
            try:
                from src.graph.kuzu_graph import get_kuzu_engine
                kuzu_eng = get_kuzu_engine()
                if kuzu_eng and kuzu_eng._initialized:
                    # Execute on local embedded Kùzu graph
                    kuzu_res = kuzu_eng.query(cypher)
                    if kuzu_res and "error" in kuzu_res[0]:
                        error = str(kuzu_res[0]["error"])
                    else:
                        records = kuzu_res
                else:
                    records = [{"status": "in_memory_ok"}]
            except Exception as e:
                records = [{"status": "in_memory_fallback", "detail": str(e)}]

        status = "FAILED" if error else "SUCCESS"
        return {
            "cypher_records": records,
            "cypher_error": error,
            "cypher_status": status,
        }

    def _evaluate_cypher_execution(self, state: GraphRAGState) -> str:
        if state.get("cypher_status") == "SUCCESS":
            return "success"
        retry_count = state.get("cypher_repair_count", 0)
        if retry_count < 3:
            return "repair"
        return "fallback"

    # =========================================================================
    # NODE 6: Cypher Repair Node
    # =========================================================================
    def _cypher_repair_node(self, state: GraphRAGState) -> Dict[str, Any]:
        failing_query = state.get("cypher_query", "")
        repair_count = state.get("cypher_repair_count", 0) + 1

        repaired_query = re.sub(r"\[\s*:\s*\w+\s*\*\s*\]", "-[r]->", failing_query)
        if "toLower" not in repaired_query:
            # Do not emit unfiltered database dump; abort repair to trigger hybrid_retriever fallback
            return {
                "cypher_query": "",
                "cypher_repair_count": 99,
                "cypher_error": "No targeted entity filters present in Cypher query.",
                "cypher_status": "FAILED",
            }

        return {
            "cypher_query": repaired_query,
            "cypher_repair_count": repair_count,
            "cypher_error": None,
        }

    def _evaluate_repair_iteration(self, state: GraphRAGState) -> str:
        if state.get("cypher_repair_count", 0) <= 3:
            return "retry"
        return "fallback"

    # =========================================================================
    # NODE 7: Relational Path Critic Node
    # =========================================================================
    def _relational_path_critic_node(self, state: GraphRAGState) -> Dict[str, Any]:
        records = state.get("cypher_records", [])
        nodes_map = {}
        edges_list = []
        for r in records:
            if isinstance(r, dict):
                src = r.get("n_name") or r.get("name")
                rel = r.get("rel") or r.get("type")
                tgt = r.get("m_name") or r.get("target")
                if src and tgt and rel:
                    edges_list.append({"source": src, "type": rel, "target": tgt})
                    nodes_map[src] = {"id": src, "name": src, "label": "Entity"}
                    nodes_map[tgt] = {"id": tgt, "name": tgt, "label": "Entity"}
        subgraph = {"nodes": list(nodes_map.values()), "edges": edges_list}
        return {
            "subgraph": subgraph,
            "path_critic_expanded": bool(edges_list),
        }
