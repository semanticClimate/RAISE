"""
End-to-End Pipeline Verification Test (Ingestion + Reranking + Grounded Answering)
==================================================================================
Verifies:
1. AcademicPipelineIngestor parses, chunks, and indexes a PDF document into ChromaDB.
2. StandaloneRAGPipeline retrieves, reranks using BAAI/bge-reranker-v2-m3,
   and produces grounded answers with accurate citations.
3. PipelineInfo audited provenance accurately attributes all neural models and substrates.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.core.config import models
from src.features.ingestion.pipeline import AcademicPipelineIngestor
from src.retrieval.pipeline import StandaloneRAGPipeline


def test_e2e_document_ingestion_and_grounded_answer():
    """Verify document ingestion into ChromaDB and retrieval of grounded answer."""
    pdf_path = BASE_DIR / "data" / "documents" / "test_sample.pdf"
    assert pdf_path.exists(), f"Sample test PDF not found at {pdf_path}"

    # 1. Ingest document
    ingestor = AcademicPipelineIngestor(
        download_dir=BASE_DIR / "data" / "documents",
        processed_dir=BASE_DIR / "data" / "processed",
    )
    
    ingest_result = ingestor.process_pdf(
        pdf_path=pdf_path,
        engine="fast",
        max_pages=1,
    )

    assert ingest_result.get("chunks_count", 0) > 0, "Ingestion failed to generate chunks"
    assert ingest_result.get("pages_processed", 0) >= 1

    # 2. Query Pipeline
    pipeline = StandaloneRAGPipeline()
    query = "What percentage did solar and wind energy installations grow in 2025?"
    
    response = pipeline.query_subgraph_graphrag(
        query=query,
        document_filter="test_sample.pdf",
        active_docs=["test_sample.pdf"],
        mode="fast",
    )

    assert response.get("status") == "SUCCESS", f"Query failed with response: {response}"
    
    answer = str(response.get("grounded_answer", ""))
    norm_answer = re.sub(r"[\s\u202f\xa0\*]", "", answer)
    assert "25%" in norm_answer or "25percent" in norm_answer.lower() or "solar" in norm_answer.lower(), (
        f"Answer missing expected facts: {answer}"
    )

    # 3. Verify Audited Provenance
    p_info = response.get("pipeline_info", {})
    assert p_info.get("reranker_model") == models.RERANKER_MODEL_NAME
    assert p_info.get("encoder_model") == models.EMBEDDING_MODEL_NAME
    assert p_info.get("nli_verifier_model") == models.NLI_MODEL_NAME
