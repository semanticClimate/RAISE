"""
RAISE Ingestion Storage Synchronizer
====================================
Purpose:
  Persists processed ingestion artifacts (chunks, academic triples, facts)
  to disk and synchronizes them across ChromaDB vector store, Neo4j knowledge
  graph, and PostgreSQL metadata stores with automated consistency auditing.

Author: RAISE Core Architecture Team
Maintainability: Keep under 150 lines with full exception safety.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .academic_extractor import AcademicEntity, AcademicRelation
from .auditor import CrossDatabaseConsistencyAuditor


def sync_and_persist_artifacts(
    doc_id: str,
    pdf_path: Path,
    output_dir: Path,
    all_chunks: List[Dict[str, Any]],
    all_entities: List[AcademicEntity],
    all_relations: List[AcademicRelation],
    vector_engine: Any,
    neo4j_db: Any,
    postgres: Any,
    t0: float,
) -> Tuple[Dict[str, AcademicEntity], Dict[str, AcademicRelation], int, Dict[str, Any], Dict[str, Any]]:
    """
    Deduplicates entities/relations, writes JSON artifacts to disk,
    syncs ChromaDB, Neo4j, and Postgres, and runs consistency auditing.
    """
    # 1. Deduplicate Entities and Relations by ID
    unique_entities: Dict[str, AcademicEntity] = {e.entity_id: e for e in all_entities}
    unique_relations: Dict[str, AcademicRelation] = {r.relation_id: r for r in all_relations}

    # 2. Save Processed Artifacts to disk
    (output_dir / "chunks" / f"{doc_id}_chunks.json").write_text(
        json.dumps(all_chunks, indent=2), encoding="utf-8"
    )
    (output_dir / "graph_triples" / f"{doc_id}_triples.json").write_text(
        json.dumps({
            "entities": [e.to_dict() for e in unique_entities.values()],
            "relations": [r.to_dict() for r in unique_relations.values()],
        }, indent=2), encoding="utf-8"
    )

    # 2b. Write structured markdown extract directly to data/library/
    try:
        lib_dir = output_dir.parent / "library"
        lib_dir.mkdir(parents=True, exist_ok=True)
        md_lines = [
            f"# Extracted Knowledge Artifact: {pdf_path.name}",
            f"- Document ID: `{doc_id}`",
            f"- Ingestion Timestamp: `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
            f"- Total Chunks: {len(all_chunks)}",
            f"- Entities Discovered: {len(unique_entities)}",
            f"- Relations Extracted: {len(unique_relations)}",
            "",
            "## Structured Document Sections & Content\n",
        ]
        for c in all_chunks:
            pno = c.get("primary_page", 1)
            h = c.get("heading", f"Page {pno}")
            txt = c.get("plain_text", "")
            md_lines.append(f"### [Page {pno}] {h}\n\n{txt}\n")
        (lib_dir / f"{doc_id}_extracted.md").write_text("\n".join(md_lines), encoding="utf-8")
    except Exception as lib_err:
        print(f"        -> Library Markdown Export Notice: {lib_err}")

    # 3. Ingest to ChromaDB Vector Store
    vector_count = vector_engine.ingest_chunks(all_chunks, doc_id=doc_id)

    # 4. Ingest to Neo4j Property Knowledge Graph
    gdata = {
        "nodes": [
            {
                "id": e.entity_id,
                "label": e.name,
                "type": e.label,
                "properties": e.properties,
                "provenance": e.provenance,
            }
            for e in unique_entities.values()
        ],
        "edges": [
            {
                "source": r.source_id,
                "target": r.target_id,
                "type": r.relation_type,
                "properties": r.properties,
            }
            for r in unique_relations.values()
        ],
        "node_count": len(unique_entities),
        "edge_count": len(unique_relations),
    }

    neo4j_res = neo4j_db.sync_graph_data(gdata)
    elapsed = round(time.time() - t0, 2)
    facts_count = len([e for e in unique_entities.values() if e.label == "MetricFact"])

    # 5. Ingest to PostgreSQL
    pg_synced = False
    try:
        postgres.save_document(
            doc_id=doc_id,
            filename=pdf_path.name,
            chunks_count=len(all_chunks),
            library="default",
        )
        postgres.upsert_document_status(
            doc_id=doc_id,
            filename=pdf_path.name,
            phase="ready",
            percent=100,
            status="ready",
            detail=f"Ingested {len(all_chunks)} chunks, {len(unique_entities)} entities",
            library="default",
        )
        pg_synced = True
    except Exception as e:
        print(f"        -> PostgreSQL Sync Notice: {e}")

    print(
        f"   [OK] Ingested in {elapsed}s: {len(all_chunks)} chunks (ChromaDB: {vector_count}), "
        f"{len(unique_entities)} entities, {len(unique_relations)} rels, {facts_count} facts "
        f"(Neo4j: {neo4j_res.get('synced', False)}, PG: {pg_synced})"
    )

    # 6. Audit Cross-Database Consistency
    consistency_audit = CrossDatabaseConsistencyAuditor.audit_ingestion(
        doc_id=doc_id,
        expected_chunks=len(all_chunks),
        vector_count=vector_count,
        entities_count=len(unique_entities),
        relations_count=len(unique_relations),
        neo4j_synced=neo4j_res.get("synced", False),
        neo4j_nodes=neo4j_res.get("nodes_written", 0),
        neo4j_edges=neo4j_res.get("edges_written", 0),
    )

    return unique_entities, unique_relations, vector_count, neo4j_res, consistency_audit
