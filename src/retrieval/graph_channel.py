"""
Graph Channel Traversal for RAISE Parallel Retriever
====================================================
Component: `src.retrieval.graph_channel`
Architecture: Traverses Neo4j graph entities and properties concurrently.
Max Lines: Strictly <= 400 lines
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("raise.retrieval.graph_channel")


async def traverse_graph_channel(
    neo4j_db: Any,
    graph_engine: Any,
    query: str,
    hops: int = 2,
    active_docs: Optional[List[str]] = None,
    chunk_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Runs dynamic graph traversal across Neo4j knowledge graph using chunk neighborhoods or token fallback."""
    loop = asyncio.get_running_loop()

    effective_hops = max(1, min(int(hops), 3))

    def _graph_search() -> List[Dict[str, Any]]:
        # Strict drawer isolation: If active_docs is explicitly empty, return zero hits
        if active_docs is not None and len(active_docs) == 0:
            return []

        clean_q = re.sub(r"[^a-zA-Z0-9\s]", "", query.lower())
        tokens = [
            t for t in clean_q.split()
            if len(t) > 2 and t not in {
                "what", "tell", "which", "with", "from", "were", "this", "some", "show", "about", "have", "that"
            }
        ]

        doc_filter = active_docs[0] if (active_docs and len(active_docs) > 0) else None
        active_docs_clean = [d for d in active_docs if d] if active_docs else None
        records: List[Dict[str, Any]] = []

        if neo4j_db and getattr(neo4j_db, "connected", False):
            # 1. Dynamic GraphRAG Traversal (Neighborhood-hop by chunk IDs)
            if chunk_ids:
                dynamic_cypher = f"""
                    MATCH (c:Chunk)-[*1..{effective_hops}]-(e)
                    WHERE (c.id IN $chunk_ids OR c.chunk_id IN $chunk_ids)
                      AND NOT e:Section AND NOT e:Chunk
                      AND ($active_docs IS NULL OR size($active_docs) = 0 OR c.document_id IN $active_docs OR any(doc IN $active_docs WHERE toLower(coalesce(c.document_id, '')) CONTAINS toLower(doc)))
                    RETURN DISTINCT coalesce(c.chunk_id, c.id) AS chunk_id,
                                    coalesce(c.document_id, 'general_doc') AS doc_id,
                                    coalesce(c.page, 1) AS page,
                                    labels(e)[0] AS entity_label,
                                    coalesce(e.name, e.label, e.id) AS entity_name
                    LIMIT 30
                """
                try:
                    dynamic_recs = neo4j_db.run_cypher(
                        dynamic_cypher,
                        {"chunk_ids": chunk_ids, "active_docs": active_docs_clean},
                    )
                    seen_ent = set()
                    for r in dynamic_recs:
                        ename = r.get("entity_name")
                        cid = r.get("chunk_id")
                        if not ename or (cid, ename) in seen_ent:
                            continue
                        seen_ent.add((cid, ename))
                        elabel = r.get("entity_label") or "Entity"
                        doc_val = r.get("doc_id") or doc_filter
                        page_val = r.get("page", 1)
                        doc_pdf = doc_val if (doc_val and str(doc_val).endswith(".pdf")) else (
                            f"{doc_val}.pdf" if doc_val and doc_val not in ("general_graph", "global_doc", "general_doc") else None
                        )
                        record_text = f"Knowledge Graph Dynamic Entity [{elabel}]: {ename} (Multi-hop connected to Chunk {cid})"
                        records.append({
                            "chunk_id": str(cid),
                            "id": str(cid),
                            "plain_text": record_text,
                            "text": record_text,
                            "enriched_text": record_text,
                            "heading": f"Neo4j Knowledge Graph: {ename}",
                            "metadata": {
                                "chunk_id": str(cid),
                                "doc_id": doc_val,
                                "primary_page": page_val,
                                "heading": f"Graph Entity: {ename}",
                                "pdf_filename": doc_pdf,
                                "is_graph_entity": True,
                            },
                        })
                except Exception as ex:
                    logger.debug("Dynamic Neo4j traversal notice: %s", ex)

            # 2. Schema / Token-based graph search fallback if dynamic traversal yielded fewer hits
            if len(records) < 5:
                cypher = f"""
                    MATCH (n)
                    WHERE (n:Entity OR any(l IN labels(n) WHERE NOT l IN ['Chunk', 'Section']))
                      AND (size($tokens) = 0 OR any(tok IN $tokens WHERE toLower(coalesce(n.label, n.name, n.id, '')) CONTAINS tok))
                    OPTIONAL MATCH (n)-[r]-(m)
                    OPTIONAL MATCH (n)-[:HAS_FACT|REPORTED_METRIC|MENTIONS|CONTAINS_CHUNK*1..{effective_hops}]-(c:Chunk)
                    WHERE $active_docs IS NULL OR size($active_docs) = 0
                       OR any(doc IN $active_docs WHERE toLower(coalesce(n.document_id, c.document_id, '')) CONTAINS toLower(doc))
                    RETURN 
                        coalesce(n.id, elementId(n)) AS id,
                        coalesce(n.label, n.name, n.id) AS name,
                        labels(n)[0] AS type,
                        coalesce(n.page, c.page, 1) AS page,
                        coalesce(n.document_id, c.document_id, 'general_graph') AS doc_id,
                        type(r) AS rel_type,
                        coalesce(m.label, m.name, m.id) AS neighbor_name,
                        labels(m)[0] AS neighbor_type,
                        coalesce(n.title, n.role, n.domain, n.flagship_product, n.abbreviation, '') AS fact_detail,
                        coalesce(c.chunk_id, c.id) AS chunk_id
                    LIMIT 20
                """
                try:
                    raw_recs = neo4j_db.run_cypher(
                        cypher,
                        {"tokens": tokens[:8], "active_docs": active_docs_clean},
                    )
                    seen_nodes = set()
                    for r in raw_recs:
                        nid = r.get("id")
                        if not nid or nid in seen_nodes:
                            continue
                        seen_nodes.add(nid)
                        name = r.get("name")
                        ntype = r.get("type", "Entity")
                        page = r.get("page", 1)
                        doc = r.get("doc_id") or doc_filter or "general_graph"
                        rel = r.get("rel_type")
                        nbr = r.get("neighbor_name")
                        detail = r.get("fact_detail")
                        c_chunk_id = r.get("chunk_id")
                        target_chunk_id = str(c_chunk_id) if c_chunk_id else f"neo4j_{nid}"

                        rel_info = f" -> [{rel}] -> ({nbr})" if rel and nbr else ""
                        fact_info = f" (Details: {detail})" if detail else ""

                        doc_pdf = doc if (doc and str(doc).endswith(".pdf")) else (
                            f"{doc}.pdf" if doc and doc not in ("general_graph", "global_doc", "general_doc") else None
                        )
                        record_text = f"Knowledge Graph Entity [{ntype}]: {name}{rel_info}{fact_info}"
                        records.append({
                            "chunk_id": target_chunk_id,
                            "id": target_chunk_id,
                            "plain_text": record_text,
                            "text": record_text,
                            "enriched_text": record_text,
                            "heading": f"Neo4j Knowledge Graph: {name}",
                            "metadata": {
                                "chunk_id": target_chunk_id,
                                "doc_id": doc,
                                "primary_page": page,
                                "heading": f"Graph Entity: {name}",
                                "pdf_filename": doc_pdf,
                                "is_graph_entity": True,
                            },
                        })
                except Exception as ex:
                    logger.debug("Schema Neo4j traversal notice: %s", ex)

        if not records and graph_engine:
            try:
                centrality = graph_engine.compute_centrality_metrics(exclude_super_hubs=True)
                gdata = graph_engine.get_graph_data()

                nodes_to_search = gdata.get("nodes", [])
                nodes_to_search.sort(key=lambda n: centrality.get(n.get("id"), {}).get("pagerank", 0.0), reverse=True)

                for node in nodes_to_search:
                    name = str(node.get("name") or node.get("label") or node.get("id") or "").lower()
                    ntype = str(node.get("type") or "Entity")
                    node_doc = str(node.get("document_id") or node.get("doc_id") or "").lower()
                    if active_docs_clean and node_doc:
                        if not any(ad.lower() in node_doc or node_doc in ad.lower() for ad in active_docs_clean):
                            continue
                    if tokens and any(t in name for t in tokens):
                        nid = node.get("chunk_id") or node.get("id")
                        rec_id = f"graph_entity_{nid}"
                        record_text = f"Knowledge Graph Entity [{ntype}]: {node.get('name', node.get('id'))} (Page {node.get('page', 1)})"
                        records.append({
                            "chunk_id": rec_id,
                            "id": rec_id,
                            "plain_text": record_text,
                            "text": record_text,
                            "enriched_text": record_text,
                            "provenance": node.get("provenance", {}),
                            "heading": f"Graph Entity: {node.get('name', node.get('id'))}",
                            "metadata": {
                                "chunk_id": rec_id,
                                "doc_id": node.get("document_id"),
                                "primary_page": node.get("page", 1),
                                "heading": f"Graph Entity: {node.get('name', node.get('id'))}",
                                "is_graph_entity": True,
                            },
                        })
            except Exception as ex:
                logger.debug("In-memory graph fallback notice: %s", ex)

        return records[:15]

    return await loop.run_in_executor(None, _graph_search)
