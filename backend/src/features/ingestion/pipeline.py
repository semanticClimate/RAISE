"""
RAISE Master Academic Ingestion Pipeline
========================================
Component: `src.features.ingestion.pipeline`
Architecture Layer: Ingestion / Master Ingestion Orchestrator

Processes university and academic PDFs from data/documents/.
Builds structure-aware chunks, extracts academic entities/relationships, populates Neo4j and ChromaDB.
Stores structured JSON artifacts in data/processed/.

Modular Architecture:
---------------------
- Isolation Guard & Consistency Auditor: `src.features.ingestion.auditor`
- Institution & Year Resolver: `src.features.ingestion.institution_resolver`
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pymupdf
except ImportError:
    pymupdf = None

# Auto-load .env variables if not already loaded
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
    else:
        load_dotenv()
except Exception:
    pass

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_VERBOSITY"] = "error"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from .academic_extractor import AcademicDomainExtractor, AcademicEntity, AcademicRelation
from src.infrastructure.graph.neo4j import Neo4jDatabase
from src.infrastructure.vector.chroma import LocalVectorEngine
from src.parsers.document_parser import SmartDocumentParser
from src.features.verification.fact_engine import FactEngine
from src.chunking.pipeline import AdaptiveChunkingPipeline
from src.infrastructure.database.postgres import PostgresManager

# Modular re-exports for 100% backward compatibility
from .auditor import should_ingest
from .institution_resolver import identify_institution
from .manifest_manager import update_manifest_entry
from .storage_sync import sync_and_persist_artifacts

logger = logging.getLogger("raise.ingestion.pipeline")


class AcademicPipelineIngestor:
    """
    End-to-end academic report processing and Neo4j graph population.
    """

    def __init__(
        self,
        download_dir: Optional[Path | str] = None,
        processed_dir: Optional[Path | str] = None,
    ):
        base_rag_dir = Path(__file__).resolve().parents[3]
        self.download_dir = Path(download_dir or base_rag_dir / "data" / "documents").resolve()
        self.output_dir = Path(processed_dir or base_rag_dir / "data" / "processed").resolve()

        # Create output directories
        (self.output_dir / "chunks").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "facts").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "graph_triples").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "neo4j").mkdir(parents=True, exist_ok=True)

        self.extractor = AcademicDomainExtractor()
        self.fact_engine = FactEngine()
        self.neo4j_db = Neo4jDatabase()
        self.vector_engine = LocalVectorEngine()
        self.smart_parser = SmartDocumentParser()
        self.adaptive_chunker = AdaptiveChunkingPipeline()
        self.postgres = PostgresManager()

    def close(self):
        """Cleanly releases underlying database connections."""
        if hasattr(self, "neo4j_db") and self.neo4j_db is not None:
            try:
                self.neo4j_db.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def identify_institution(self, pdf_path: Path, first_page_text: str) -> Tuple[str, str]:
        """Determine canonical institution name and academic/reporting year."""
        return identify_institution(pdf_path, first_page_text)

    def process_pdf(
        self,
        pdf_path: Path | str,
        max_pages: Optional[int] = None,
        engine: str = "fast",
        full_potential: bool = False,
        extract_tables: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a single academic PDF into chunks, entities, and Neo4j nodes.
        - engine: 'fast' (PyMuPDF, 2-3s) | 'deep' | 'docling' (Docling TableFormer) | 'auto'
        Allows processing without arbitrary max caps when max_pages is None.
        """
        pdf_path = Path(pdf_path)
        if not should_ingest(pdf_path):
            print(f"⛔ [Isolation Guard] Skipping excluded evaluation/benchmark file: {pdf_path.name}")
            return {
                "document": pdf_path.name,
                "status": "excluded",
                "reason": "File matches excluded evaluation/benchmark patterns",
                "pages_processed": 0,
                "chunks_count": 0,
                "entities_count": 0,
                "relations_count": 0,
                "facts_count": 0,
            }

        doc_id = re.sub(r"[^a-zA-Z0-9]", "_", pdf_path.stem)[:40]
        chunk_file = self.output_dir / "chunks" / f"{doc_id}_chunks.json"
        triple_file = self.output_dir / "graph_triples" / f"{doc_id}_triples.json"

        # If PDF is 0 bytes but cached chunks exist, load from disk cache
        if pdf_path.stat().st_size == 0:
            if chunk_file.exists():
                try:
                    all_chunks = json.loads(chunk_file.read_text(encoding="utf-8"))
                    triples_data = json.loads(triple_file.read_text(encoding="utf-8")) if triple_file.exists() else {"entities": [], "relations": []}

                    # Sync to ChromaDB
                    vector_count = self.vector_engine.ingest_chunks(all_chunks, doc_id=doc_id)

                    # Sync to Neo4j
                    gdata = {
                        "nodes": [{"id": e["entity_id"], "label": e["name"], "type": e["label"], "page": e.get("provenance", {}).get("page_number", 1), "document_id": doc_id} for e in triples_data.get("entities", [])],
                        "edges": [{"source": r["source_id"], "target": r["target_id"], "type": r["relation_type"]} for r in triples_data.get("relations", [])],
                    }
                    self.neo4j_db.sync_graph_data(gdata)

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
                    print(f"Error loading cached chunk {doc_id}: {e}")
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

        if pymupdf is None:
            raise RuntimeError(
                "PyMuPDF is required for PDF ingestion. Please run: pip install pymupdf"
            )
        doc = pymupdf.open(str(pdf_path))
        total_doc_pages = len(doc)
        if max_pages is not None and int(max_pages) > 0:
            pages_to_process = min(total_doc_pages, int(max_pages))
            page_desc = f"first {pages_to_process} of {total_doc_pages}"
        else:
            pages_to_process = total_doc_pages
            page_desc = f"all {total_doc_pages} pages (no cap)"

        first_p_txt = doc[0].get_text("text") if total_doc_pages > 0 else ""
        institution_name, reporting_period = self.identify_institution(pdf_path, first_p_txt)

        print("\n======================================================================")
        print(f" [INGESTING] {pdf_path.name}")
        print(f"   Institution: {institution_name} | Period: {reporting_period}")
        print(f"   Pages: Processing {page_desc} (Engine: {engine.upper()})")
        print("======================================================================")

        all_chunks: List[Dict[str, Any]] = []
        all_entities: List[AcademicEntity] = []
        all_relations: List[AcademicRelation] = []

        t0 = time.time()

        parsed_sections = self.smart_parser.parse_pdf(
            pdf_path,
            max_pages=pages_to_process,
            engine=engine,
            full_potential=full_potential,
            extract_tables=extract_tables,
        )
        doc.close()

        # Run Graph-Guided Adaptive Hierarchical Chunking (GGAHC)
        adaptive_result = self.adaptive_chunker.process_document(
            parsed_sections=parsed_sections,
            document_id=doc_id,
            filename=pdf_path.name,
            university=institution_name,
            reporting_period=reporting_period,
            total_pages=total_doc_pages,
        )
        child_chunks = adaptive_result["child_chunks"]
        parent_chunks = adaptive_result["parent_chunks"]
        all_chunks = adaptive_result["legacy_chunks"]

        # Save Parent Chunks and Diagnostic Report for inspection
        (self.output_dir / "chunks" / f"{doc_id}_parent_chunks.json").write_text(
            json.dumps([p.to_dict() for p in parent_chunks], indent=2), encoding="utf-8"
        )
        (self.output_dir / "chunks" / f"{doc_id}_chunking_diagnostics.json").write_text(
            json.dumps(adaptive_result["diagnostic_report"].to_dict(), indent=2), encoding="utf-8"
        )

        for chunk_record in all_chunks:
            pno = chunk_record.get("primary_page", 1)
            doc_pno = chunk_record.get("printed_page")
            cleaned_text = chunk_record.get("plain_text", "")
            heading = chunk_record.get("heading", "")
            chunk_id = chunk_record["chunk_id"]

            # Register Chunk entity in Knowledge Graph for Dynamic Neighborhood Cypher Traversal
            chunk_ent = AcademicEntity(
                entity_id=chunk_id,
                label="Chunk",
                name=f"Chunk {chunk_id}",
                properties={
                    "document_id": doc_id,
                    "primary_page": pno,
                    "printed_page": doc_pno,
                    "heading": heading,
                    "pdf_filename": pdf_path.name,
                    "parent_chunk_id": chunk_record.get("parent_chunk_id"),
                },
                provenance={"pdf_filename": pdf_path.name, "page_number": pno, "printed_page": doc_pno, "chunk_id": chunk_id},
            )
            all_entities.append(chunk_ent)

            # Extract Academic Entities & Relations
            ents, rels = self.extractor.extract_academic_knowledge(
                text=cleaned_text,
                pdf_filename=pdf_path.name,
                page_number=pno,
                section_heading=heading,
                chunk_id=chunk_id,
                university_name=institution_name,
            )
            all_entities.extend(ents)
            all_relations.extend(rels)

            # Link Chunk to extracted Academic Entities
            for e in ents:
                all_relations.append(AcademicRelation(
                    relation_id=f"rel_{chunk_id}_{e.entity_id}_mentions",
                    source_id=chunk_id,
                    source_label="Chunk",
                    relation_type="MENTIONS",
                    target_id=e.entity_id,
                    target_label=e.label,
                    provenance={"pdf_filename": pdf_path.name, "page_number": pno, "chunk_id": chunk_id},
                ))

            # Extract Quantitative Facts via FactEngine
            try:
                num_facts = self.fact_engine.extract_facts_from_text(
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
                        provenance={"pdf_filename": pdf_path.name, "page_number": pno, "printed_page": doc_pno, "chunk_id": chunk_id},
                    )
                    all_entities.append(f_ent)
                    all_relations.append(AcademicRelation(
                        relation_id=f"rel_{chunk_id}_{f_id}_reports",
                        source_id=chunk_id,
                        source_label="Chunk",
                        relation_type="HAS_FACT",
                        target_id=f_id,
                        target_label="MetricFact",
                        provenance={"pdf_filename": pdf_path.name, "page_number": pno, "printed_page": doc_pno, "chunk_id": chunk_id},
                    ))
                    all_relations.append(AcademicRelation(
                        relation_id=f"rel_{uni_id}_{f_id}_reported_metric",
                        source_id=uni_id,
                        source_label="University",
                        relation_type="REPORTED_METRIC",
                        target_id=f_id,
                        target_label="MetricFact",
                        provenance={"pdf_filename": pdf_path.name, "page_number": pno, "printed_page": doc_pno, "chunk_id": chunk_id},
                    ))
            except Exception:
                pass

        # Persist artifacts and sync ChromaDB, Neo4j, and Postgres
        (
            unique_entities,
            unique_relations,
            vector_count,
            neo4j_res,
            consistency_audit,
        ) = sync_and_persist_artifacts(
            doc_id=doc_id,
            pdf_path=pdf_path,
            output_dir=self.output_dir,
            all_chunks=all_chunks,
            all_entities=all_entities,
            all_relations=all_relations,
            vector_engine=self.vector_engine,
            neo4j_db=self.neo4j_db,
            postgres=self.postgres,
            t0=t0,
        )
        facts_count = len([e for e in unique_entities.values() if e.label == "MetricFact"])

        # Update persistent manifest
        update_manifest_entry(
            output_dir=self.output_dir,
            pdf_path=pdf_path,
            pages_processed=pages_to_process,
            chunks_count=len(all_chunks),
        )

        return {
            "document": pdf_path.name,
            "institution": institution_name,
            "period": reporting_period,
            "pages_processed": pages_to_process,
            "total_pages": total_doc_pages,
            "chunks_count": len(all_chunks),
            "entities_count": len(unique_entities),
            "relations_count": len(unique_relations),
            "facts_extracted": facts_count,
            "triples_extracted": len(unique_relations),
            "entities": [e.to_dict() for e in unique_entities.values()],
            "relationships": [r.to_dict() for r in unique_relations.values()],
            "facts": [e.to_dict() for e in unique_entities.values()],
            "triples": [r.to_dict() for r in unique_relations.values()],
            "neo4j_synced": neo4j_res.get("synced", False),
            "consistency_audit": consistency_audit,
        }

    def process_all_downloads(self, max_pages_per_doc: Optional[int] = None, engine: str = "fast") -> Dict[str, Any]:
        """
        Process every PDF report in the Download folder into the live Neo4j database.
        """
        pdfs = sorted([p for p in self.download_dir.glob("*.pdf") if should_ingest(p)])
        print("\n======================================================================")
        print(f" 🚀 STARTING FULL ACADEMIC GRAPHRAG INGESTION ({len(pdfs)} PDFS)")
        print(f" Source: {self.download_dir}")
        print(" Target: Neo4j (bolt://localhost:7687) & ChromaDB")
        print("======================================================================")

        results = []
        tot_chunks = 0
        tot_entities = 0
        tot_relations = 0

        for pdf in pdfs:
            res = self.process_pdf(pdf, max_pages=max_pages_per_doc, engine=engine)
            results.append(res)
            tot_chunks += res["chunks_count"]
            tot_entities += res["entities_count"]
            tot_relations += res["relations_count"]

        # Global summary
        print("\n======================================================================")
        print(" 📊 [ACADEMIC INGESTION COMPLETED SUCCESSFULLY]")
        print(f" Total PDF Documents Ingested: {len(results)}")
        print(f" Total Semantic Context Chunks: {tot_chunks}")
        print(f" Total Academic Entities in Neo4j: {tot_entities}")
        print(f" Total Academic Relationships in Neo4j: {tot_relations}")
        print(f" Artifacts Stored in: {self.output_dir}")
        print("======================================================================\n")

        return {
            "status": "success",
            "total_documents": len(results),
            "total_chunks": tot_chunks,
            "total_entities": tot_entities,
            "total_relations": tot_relations,
            "documents": results,
        }


if __name__ == "__main__":
    pipeline = AcademicPipelineIngestor()
    pipeline.process_all_downloads(max_pages_per_doc=25)
