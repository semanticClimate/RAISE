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
import re
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

    # 2b. Write structured Enterprise OKF (.md) artifact directly to data/library/
    try:
        lib_dir = output_dir.parent / "library"
        lib_dir.mkdir(parents=True, exist_ok=True)

        inst_candidates = [e.name for e in unique_entities.values() if getattr(e, "label", "") in ("Institution", "University", "Organization")]
        institution = inst_candidates[0] if inst_candidates else pdf_path.stem.replace("_", " ")
        year_matches = re.findall(r"\b(20\d\d(?:-\d\d)?)\b", pdf_path.stem)
        reporting_period = year_matches[0] if year_matches else "Current Period"
        fact_metrics = [e for e in unique_entities.values() if getattr(e, "label", "") in ("MetricFact", "FinancialMetric", "Metric")]

        okf_content = generate_enhanced_okf_markdown(
            doc_id=doc_id,
            pdf_path=pdf_path,
            institution=institution,
            reporting_period=reporting_period,
            all_chunks=all_chunks,
            unique_entities=unique_entities,
            unique_relations=unique_relations,
            fact_metrics=fact_metrics,
        )
        (lib_dir / f"{doc_id}_extracted.md").write_text(okf_content, encoding="utf-8")
    except Exception as lib_err:
        print(f"        -> Library Markdown Export Notice: {lib_err}")

    # 2c. Generate & register agent-ready Open Knowledge Format (.okf.md) catalog
    try:
        from src.features.catalog.catalog_extractor import extract_okf_profile_from_pdf
        extract_okf_profile_from_pdf(
            pdf_path=pdf_path,
            chunks=all_chunks,
            entities=list(unique_entities.values()),
            facts=fact_metrics,
            institution_name=institution,
            reporting_period=reporting_period,
        )
    except Exception as okf_err:
        print(f"        -> OKF Catalog Export Notice: {okf_err}")

    # 3. Ingest to ChromaDB Vector Store
    vector_count = vector_engine.ingest_chunks(all_chunks, doc_id=doc_id)

    # 4. Ingest to Neo4j Property Knowledge Graph
    gdata = {
        "nodes": [
            {
                "id": e.entity_id,
                "label": e.name,
                "type": e.label,
                "document_id": doc_id,
                "properties": {**(e.properties or {}), "document_id": doc_id},
                "provenance": e.provenance,
            }
            for e in unique_entities.values()
        ],
        "edges": [
            {
                "source": r.source_id,
                "target": r.target_id,
                "type": r.relation_type,
                "document_id": doc_id,
                "properties": {**(r.properties or {}), "document_id": doc_id},
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


def generate_enhanced_okf_markdown(
    doc_id: str,
    pdf_path: Path,
    institution: str,
    reporting_period: str,
    all_chunks: List[Dict[str, Any]],
    unique_entities: Dict[str, Any],
    unique_relations: Dict[str, Any],
    fact_metrics: List[Any],
) -> str:
    """Generates an Enterprise Open Knowledge File (.md) artifact."""
    lines = []
    # 1. Frontmatter
    lines.extend([
        "---",
        f"id: \"{doc_id}\"",
        f"title: \"{pdf_path.stem.replace('_', ' ')}\"",
        f"institution: \"{institution}\"",
        f"reporting_period: \"{reporting_period}\"",
        f"total_chunks: {len(all_chunks)}",
        f"total_entities: {len(unique_entities)}",
        f"total_relations: {len(unique_relations)}",
        f"generated_at: \"{time.strftime('%Y-%m-%dT%H:%M:%SZ')}\"",
        "schema_version: \"okf-v2.0\"",
        "---",
        "",
        f"# {institution} — Annual Research & Knowledge Manifest ({reporting_period})",
        "",
        "## 1. Executive Summary & Document Abstract",
        f"Comprehensive semantified representation of `{pdf_path.name}` covering institutional governance, "
        f"financial allocations, research outputs, patents, and incubated ventures.",
        "",
        "## 2. Quantitative Metric Fact Register",
        "| Metric Name | Value | Unit | Primary Page | Provenance Chunk |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ])

    for f in fact_metrics[:50]:
        val = getattr(f, "raw_value", "") or (f.get("raw_value", "") if isinstance(f, dict) else "")
        m_name = getattr(f, "metric_name", "") or (f.get("metric_name", "") if isinstance(f, dict) else "")
        m_name = str(m_name).replace("_", " ").title()
        unit = getattr(f, "unit", "-") or (f.get("unit", "-") if isinstance(f, dict) else "-")
        pno = getattr(f, "page_number", 1) or (f.get("page_number", 1) if isinstance(f, dict) else 1)
        cid = getattr(f, "chunk_id", f"{doc_id}_p{pno}") or (f.get("chunk_id", f"{doc_id}_p{pno}") if isinstance(f, dict) else f"{doc_id}_p{pno}")
        lines.append(f"| {m_name} | **{val}** | {unit} | Page {pno} | `{cid}` |")

    lines.extend([
        "",
        "## 3. Knowledge Graph Entity & Ontological Glossary",
        "| Entity Name | Ontological Type | Mentions | Linked Relations |",
        "| :--- | :--- | :--- | :--- |",
    ])

    for e in list(unique_entities.values())[:60]:
        name = getattr(e, "name", "") or (e.get("name", "") if isinstance(e, dict) else "")
        etype = getattr(e, "label", "Entity") or (e.get("label", "Entity") if isinstance(e, dict) else "Entity")
        prov = getattr(e, "provenance", {}) or (e.get("provenance", {}) if isinstance(e, dict) else {})
        pno = prov.get("page_number", 1) if isinstance(prov, dict) else 1
        eid = getattr(e, "entity_id", "") or (e.get("entity_id", "") if isinstance(e, dict) else "")
        lines.append(f"| {name} | `{etype}` | Page {pno} | `{eid}` |")

    lines.extend([
        "",
        "## 4. Structured Contextual Chunks & Tabular Passages",
        "",
    ])

    for c in all_chunks:
        pno = c.get("primary_page", 1)
        cid = c.get("chunk_id", "")
        h = c.get("heading", f"Section Page {pno}")
        txt = c.get("plain_text", "")

        lines.extend([
            f"<a id=\"{cid}\"></a>",
            f"### Chunk `{cid}` — [Page {pno}] {h}",
            f"> **Context Breadcrumb:** `{institution}` ➔ `{reporting_period}` ➔ `{h}`",
            "",
            txt,
            "",
            "---",
            "",
        ])

    return "\n".join(lines)
