"""
RAISE Vault Batch Ingestion Procedures
======================================
Purpose:
  Handles batch ingestion workflows for default vault loading and
  download folder batch indexing, maintaining manifest and Postgres state.

Author: RAISE Core Architecture Team
Maintainability: Keep under 140 lines with robust error handling.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict

from src.api.context import (
    DOCUMENTS_DIR,
    DOWNLOAD_DIR,
    get_ready_documents_list,
    record_ready_document,
)
from src.features.ingestion.pipeline import AcademicPipelineIngestor

logger = logging.getLogger("raise.router.vault_batch")
from src.core.config import BACKEND_DIR
BASE_DIR = BACKEND_DIR


def execute_load_vault_defaults(rag_engine: Any, max_pages_per_doc: Optional[int] = None) -> Dict[str, Any]:
    """Ingests or loads all available academic reports from DOCUMENTS_DIR directory."""
    try:
        # If DOCUMENTS_DIR has no PDFs, auto-seed from tests/Test pdf
        pdf_files = list(DOCUMENTS_DIR.glob("*.pdf"))
        if not pdf_files:
            test_fixtures_dir = BASE_DIR / "tests" / "Test pdf"
            if test_fixtures_dir.exists():
                for fixture_pdf in sorted(test_fixtures_dir.glob("*.pdf"))[:2]:
                    target = DOCUMENTS_DIR / fixture_pdf.name
                    if not target.exists():
                        shutil.copy2(fixture_pdf, target)
            pdf_files = list(DOCUMENTS_DIR.glob("*.pdf"))

        # Fast sync: check if all documents are already manifested and ingested
        manifest_docs = get_ready_documents_list()
        already_registered = {d.get("filename") for d in manifest_docs if d.get("filename")}
        unprocessed_pdfs = [p for p in pdf_files if p.name not in already_registered]

        if not unprocessed_pdfs and manifest_docs:
            if rag_engine:
                rag_engine._load_processed_data()
            return {
                "status": "success",
                "summary": {
                    "status": "success",
                    "total_documents": len(manifest_docs),
                    "documents": manifest_docs,
                    "message": "Documents already synchronized",
                },
                "documents": manifest_docs,
            }

        with AcademicPipelineIngestor(download_dir=DOCUMENTS_DIR) as academic_pipeline:
            summary = academic_pipeline.process_all_downloads(max_pages_per_doc=max_pages_per_doc)
            for doc in summary.get("documents", []):
                fname = doc.get("document") or doc.get("pdf_filename") or doc.get("filename")
                if fname:
                    dest_path = DOCUMENTS_DIR / fname
                    size_mb = round(dest_path.stat().st_size / (1024 * 1024), 2) if dest_path.exists() else 0.5
                    record_ready_document(
                        filename=fname,
                        pages=doc.get("pages_processed", 0),
                        size_mb=size_mb,
                        chunks_count=doc.get("chunks_count", 0),
                    )
        if rag_engine:
            rag_engine._load_processed_data()

        manifest_docs = get_ready_documents_list()
        return {
            "status": "success",
            "summary": summary,
            "documents": manifest_docs,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def execute_ingest_download_folder(postgres_manager: Any, rag_engine: Any, max_pages_per_doc: Optional[int] = None) -> Dict[str, Any]:
    """Batch-ingests all PDF reports from Download/ directory."""
    try:
        academic_pipeline = AcademicPipelineIngestor(download_dir=DOWNLOAD_DIR)
        res = academic_pipeline.process_all_downloads(max_pages_per_doc=max_pages_per_doc)
        doc_list = res.get("documents", res.get("reports", []))
        for report in doc_list:
            fname = report.get("filename") or report.get("document")
            if fname:
                pdf_path = DOWNLOAD_DIR / fname
                size_mb = round(pdf_path.stat().st_size / (1024 * 1024), 2) if pdf_path.exists() else 0.0
                pages = report.get("pages_processed", 1)
                chunks = report.get("chunks_count", report.get("chunks_extracted", 0))
                clean_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(fname).stem)[:40]
                doc_id = f"doc_{clean_stem}"

                record_ready_document(
                    filename=fname,
                    pages=pages,
                    size_mb=size_mb,
                    chunks_count=chunks,
                )
                if postgres_manager:
                    postgres_manager.save_document_metadata(
                        doc_id=doc_id,
                        filename=fname,
                        chunks_count=chunks,
                        library="default",
                    )
                    postgres_manager.upsert_document_status(
                        doc_id=doc_id,
                        filename=fname,
                        phase="completed",
                        percent=100,
                        status="ready",
                        detail="Batch ingested and synchronized",
                        pages_processed=pages,
                        chunks_extracted=chunks,
                        file_size_bytes=pdf_path.stat().st_size if pdf_path.exists() else 0,
                        library="default",
                    )
        if rag_engine:
            rag_engine._load_processed_data()
        return res
    except Exception as e:
        return {"status": "error", "error": str(e)}
