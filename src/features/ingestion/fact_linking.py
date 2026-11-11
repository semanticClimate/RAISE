"""
Quantitative Fact Linking and Ingestion Cache Recovery
======================================================
Component: `src.features.ingestion.fact_linking`
Architecture: Helper utilities for fact extraction and zero-byte cached artifact replay
Line Ceiling: Strictly <= 400 lines
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .academic_models import AcademicEntity, AcademicRelation

logger = logging.getLogger("raise.ingestion.fact_linking")


def load_cached_pdf_data(
    pdf_path: Path,
    doc_id: str,
    output_dir: Path,
    vector_engine: Any,
    neo4j_db: Any,
) -> Dict[str, Any]:
    """Loads previously extracted chunk and graph triples for 0-byte cache fixtures."""
    chunk_file = output_dir / "chunks" / f"{doc_id}_chunks.json"
    triple_file = output_dir / "graph_triples" / f"{doc_id}_triples.json"

    if chunk_file.exists():
        try:
            all_chunks = json.loads(chunk_file.read_text(encoding="utf-8"))
            triples_data = (
                json.loads(triple_file.read_text(encoding="utf-8"))
                if triple_file.exists()
                else {"entities": [], "relations": []}
            )

            # Sync to ChromaDB
            vector_engine.ingest_chunks(all_chunks, doc_id=doc_id)

            # Sync to Neo4j
            gdata = {
                "nodes": [
                    {
                        "id": e["entity_id"],
                        "label": e["name"],
                        "type": e["label"],
                        "page": e.get("provenance", {}).get("page_number", 1),
                        "document_id": doc_id,
                    }
                    for e in triples_data.get("entities", [])
                ],
                "edges": [
                    {
                        "source": r["source_id"],
                        "target": r["target_id"],
                        "type": r["relation_type"],
                    }
                    for r in triples_data.get("relations", [])
                ],
            }
            neo4j_db.sync_graph_data(gdata)

            return {
                "document": pdf_path.name,
                "institution": pdf_path.stem.replace("_", " ").title(),
                "period": "2024-25",
                "pages_processed": len(all_chunks),
                "total_pages": len(all_chunks),
                "chunks_count": len(all_chunks),
                "entities_count": len(triples_data.get("entities", [])),
                "relations_count": len(triples_data.get("relations", [])),
                "neo4j_synced": True,
            }
        except Exception as e:
            logger.error("Error loading cached chunk %s: %s", doc_id, e)

    return {
        "document": pdf_path.name,
        "institution": pdf_path.stem.replace("_", " ").title(),
        "period": "2024-25",
        "pages_processed": 0,
        "total_pages": 0,
        "chunks_count": 0,
        "entities_count": 0,
        "relations_count": 0,
        "neo4j_synced": False,
    }


def extract_and_link_facts(
    fact_engine: Any,
    cleaned_text: str,
    doc_id: str,
    institution_name: str,
    pno: int,
    doc_pno: int,
    chunk_id: str,
    pdf_filename: str,
    all_entities: List[AcademicEntity],
    all_relations: List[AcademicRelation],
) -> None:
    """Extracts numerical facts from text and connects them with entities and relations."""
    try:
        num_facts = fact_engine.extract_facts_from_text(
            text=cleaned_text,
            document_id=doc_id,
            university=institution_name,
            page_number=pno,
            section_id=f"sec_{doc_id}_{pno}",
        )
        uni_id = f"uni_{re.sub(r'[^a-zA-Z0-9]', '_', institution_name.lower())[:30]}"
        for nf in num_facts:
            f_id = nf.fact_id
            f_name = f"{nf.metric_name.replace('_', ' ').title()}: {nf.raw_value}"
            f_ent = AcademicEntity(
                entity_id=f_id,
                label="MetricFact",
                name=f_name,
                properties=nf.to_dict(),
                provenance={
                    "pdf_filename": pdf_filename,
                    "page_number": pno,
                    "printed_page": doc_pno,
                    "chunk_id": chunk_id,
                },
            )
            all_entities.append(f_ent)
            all_relations.append(
                AcademicRelation(
                    relation_id=f"rel_{chunk_id}_{f_id}_reports",
                    source_id=chunk_id,
                    source_label="Chunk",
                    relation_type="HAS_FACT",
                    target_id=f_id,
                    target_label="MetricFact",
                    provenance={
                        "pdf_filename": pdf_filename,
                        "page_number": pno,
                        "printed_page": doc_pno,
                        "chunk_id": chunk_id,
                    },
                )
            )
            all_relations.append(
                AcademicRelation(
                    relation_id=f"rel_{uni_id}_{f_id}_reported_metric",
                    source_id=uni_id,
                    source_label="University",
                    relation_type="REPORTED_METRIC",
                    target_id=f_id,
                    target_label="MetricFact",
                    provenance={
                        "pdf_filename": pdf_filename,
                        "page_number": pno,
                        "printed_page": doc_pno,
                        "chunk_id": chunk_id,
                    },
                )
            )
    except Exception as e:
        logger.debug("Fact extraction skipped on page %d: %s", pno, e)


__all__ = ["load_cached_pdf_data", "extract_and_link_facts"]
