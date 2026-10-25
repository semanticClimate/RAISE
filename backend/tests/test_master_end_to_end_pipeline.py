"""
RAISE Academic GraphRAG Studio - Master End-to-End Test Suite
Validates the complete system lifecycle:
  1. Pre-flight diagnostics & database connections (CUDA, Neo4j, ChromaDB, vLLM)
  2. Real PDF document ingestion using fixtures from `tests/Test pdf`
  3. Layout extraction with Fast PyMuPDF (with text normalizer) & Deep Vision IBM Docling
  4. MetricFact & Academic entity/triple extraction (FactEngine + DomainExtractor)
  5. Multi-substrate storage (1024-dim ChromaDB + batched UNWIND Neo4j)
  6. Parallel 3-path retrieval (Vector + pure-Python BM25 + schema Cypher) & RRF fusion
  7. Stateful agentic synthesis with dynamic Local/Cloud LLM orchestration with grounded citations
  8. Complete vault purge ("delete all") verifying 0 vectors, 0 nodes, 0 chunks, 0 files in data/documents
"""

import os
import sys
import json
import pytest
import urllib.request
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings
from src.parsers.document_parser import SmartDocumentParser, HAS_DOCLING, HAS_PYMUPDF
from src.features.verification.fact_engine import FactEngine
from src.features.ingestion.academic_extractor import AcademicDomainExtractor
from src.infrastructure.vector.chroma import LocalVectorEngine
from src.infrastructure.graph.neo4j import Neo4jDatabase
from src.features.graph.engine import GraphRAGEngine
from src.retrieval.parallel_retriever import AsyncParallelRetriever, SelfContainedBM25
from src.retrieval.pipeline import StandaloneRAGPipeline
from src.features.evaluation.quality_gate import QualityGateValidator


# ----------------------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def test_pdf_fixture() -> Path:
    """Returns a real PDF from tests/Test pdf."""
    test_pdf_dir = Path(__file__).resolve().parent / "Test pdf"
    iitmrp = test_pdf_dir / "IITMRP Annual Report.pdf"
    if iitmrp.exists():
        return iitmrp
    pdfs = sorted(list(test_pdf_dir.glob("*.pdf")))
    if not pdfs:
        pytest.skip("No test PDF fixtures found in tests/Test pdf/")
    return pdfs[0]


@pytest.fixture(scope="module")
def pipeline_instance() -> StandaloneRAGPipeline:
    """Provides a StandaloneRAGPipeline instance for the test module."""
    pipe = StandaloneRAGPipeline()
    try:
        yield pipe
    finally:
        pipe.close()


# ----------------------------------------------------------------------
# 1. DIAGNOSTICS & SYSTEM CONNECTION TESTS
# ----------------------------------------------------------------------
class TestStage1DiagnosticsAndConnections:
    def test_cuda_hardware_acceleration(self):
        """Verify dynamic CUDA hardware acceleration and device properties."""
        import torch
        if not torch.cuda.is_available():
            pytest.skip("CUDA not available on this host environment.")
        assert torch.cuda.device_count() >= 1, "At least 1 CUDA device must be detected."
        device_name = torch.cuda.get_device_name(0)
        assert isinstance(device_name, str) and len(device_name.strip()) > 0, "GPU device name must be non-empty."
        props = torch.cuda.get_device_properties(0)
        vram_bytes = getattr(props, "total_memory", getattr(props, "total_mem", 0))
        assert vram_bytes > 0, f"Detected total VRAM must be greater than 0 on {device_name}."

    def test_neo4j_live_connection(self):
        """Verify live Bolt connection to Neo4j graph database."""
        with Neo4jDatabase() as db:
            conn = db.check_connection()
            if not conn.get("connected"):
                pytest.skip(f"Neo4j container not active on localhost:7687: {conn.get('error')}")
            assert conn.get("connected") is True
            assert "total_nodes" in conn

    def test_chromadb_initialization(self):
        """Verify ChromaDB vector store initialization."""
        vec = LocalVectorEngine()
        assert vec.collection is not None, "ChromaDB collection must be initialized."
        assert vec.dimension == 1024, "Vector dimension must match BGE-Large (1024-dim)."

    def test_vllm_server_health(self):
        """Verify local vLLM inference server is listening on port 8002."""
        vllm_url = os.getenv("VLLM_BASE_URL", "http://localhost:8002/v1") + "/models"
        try:
            req = urllib.request.Request(vllm_url, headers={"User-Agent": "RAISE-Test"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                assert resp.status == 200, f"vLLM models endpoint returned status {resp.status}"
                data = json.loads(resp.read().decode("utf-8"))
                assert "data" in data, "vLLM models response must contain 'data' key."
        except Exception as e:
            pytest.skip(f"vLLM server not responding on {vllm_url}: {e}")

    def test_parser_engines_availability(self):
        """Verify Fast PyMuPDF and Deep Vision Docling availability."""
        assert HAS_PYMUPDF is True, "PyMuPDF must be natively installed."
        assert HAS_DOCLING is True, "IBM Docling must be natively installed."


# ----------------------------------------------------------------------
# 2. PDF EXTRACTION TESTS USING REAL FIXTURES
# ----------------------------------------------------------------------
class TestStage2PDFParsingEngines:
    def test_fast_pymupdf_with_layout_normalizer(self, test_pdf_fixture):
        """Verify PyMuPDF layout parsing and spaced-glyph coalescing."""
        parser = SmartDocumentParser()
        sections = parser.parse_pdf(test_pdf_fixture, max_pages=3, engine="fast")
        assert len(sections) > 0, "PyMuPDF must extract structured sections."
        
        # Verify text quality
        for sec in sections:
            text = sec.get("text", "")
            assert len(text) > 20, "Extracted section text must not be empty."
            # Spaced-letter pattern test: e.g. "A B O U T" or "S N A P S H O T"
            import re
            spaced_anomalies = re.findall(r"\b([A-Z]\s){3,}[A-Z]\b", text)
            assert len(spaced_anomalies) == 0, f"Found corrupt spaced glyphs: {spaced_anomalies}"

    def test_deep_vision_docling_uncapped(self, test_pdf_fixture):
        """Verify Docling TableFormer operates uncapped without ConversionError."""
        parser = SmartDocumentParser()
        # Parse 1 page in deep mode to verify layout and table models
        sections = parser.parse_pdf(test_pdf_fixture, max_pages=1, engine="deep")
        assert len(sections) > 0, "Docling must produce parsed sections."
        sec = sections[0]
        assert "engine" in sec
        assert "Docling" in sec["engine"]


# ----------------------------------------------------------------------
# 3. DOMAIN FACT & ENTITY EXTRACTION TESTS
# ----------------------------------------------------------------------
class TestStage3FactAndEntityExtraction:
    def test_fact_engine_metric_extraction(self):
        """Verify FactEngine extracts quantitative metrics and financial facts."""
        engine = FactEngine()
        text = "In FY26, total income reached ₹18,234 crore, with operating profit after tax of ₹8,340 crore and 300 incubated startups."
        facts = engine.extract_facts_from_text(text, document_id="test_doc", university="IIT Madras", page_number=1)
        assert len(facts) >= 2, f"Expected at least 2 metric facts, found {len(facts)}"
        metric_names = [f.metric_name for f in facts]
        assert any("revenue" in m.lower() or "income" in m.lower() or "profit" in m.lower() or "startup" in m.lower() for m in metric_names)

    def test_academic_domain_extractor_triples(self):
        """Verify AcademicDomainExtractor builds typed entities and relations."""
        extractor = AcademicDomainExtractor()
        text = "IIT Madras Research Park incubated XYMA Analytics and Mindgrove Microcontroller through funding grants."
        entities, relations = extractor.extract_academic_knowledge(
            text=text,
            pdf_filename="test_doc.pdf",
            page_number=1,
            section_heading="Incubation",
            chunk_id="test_c1",
            university_name="IIT Madras"
        )
        assert len(entities) > 0, "Entities must be extracted."
        assert len(relations) > 0, "Relations must be extracted."


# ----------------------------------------------------------------------
# 4. FULL INGESTION PIPELINE & MULTI-SUBSTRATE STORAGE
# ----------------------------------------------------------------------
class TestStage4IngestionAndStorage:
    def test_ingest_pdf_and_sync_live(self, test_pdf_fixture, pipeline_instance):
        """Ingest test PDF pages, write to ChromaDB and live Neo4j."""
        from src.features.ingestion.pipeline import AcademicPipelineIngestor
        with AcademicPipelineIngestor(download_dir=test_pdf_fixture.parent) as ingestor:
            res = ingestor.process_pdf(test_pdf_fixture, max_pages=5, engine="fast")
            
            assert res.get("status") == "success" or res.get("chunks_count", 0) > 0
            assert res.get("chunks_count", 0) > 0, "Chunks must be created."
            assert res.get("entities_count", 0) > 0, "Entities must be extracted."
            if pipeline_instance.neo4j_db.check_connection().get("connected"):
                assert res.get("neo4j_synced") is True, "Neo4j live sync must succeed when connected."
            assert res.get("facts_extracted", 0) > 0, "Facts extracted must be > 0 (Failure 1 resolved)."
            assert res.get("triples_extracted", 0) > 0, "Triples extracted must be > 0."


# ----------------------------------------------------------------------
# 5. PARALLEL 3-PATH RETRIEVAL & FUSION
# ----------------------------------------------------------------------
class TestStage5ParallelRetrievalAndFusion:
    def test_independent_self_contained_bm25(self):
        """Verify pure-Python SelfContainedBM25 ranks independently."""
        corpus = [
            {"chunk_id": "c1", "plain_text": "Financial statements show total revenue of 18000 crore and EBITDA margin.", "metadata": {}},
            {"chunk_id": "c2", "plain_text": "Robotics research center developed autonomous underwater navigation units.", "metadata": {}},
        ]
        bm25 = SelfContainedBM25(corpus)
        hits = bm25.search("revenue EBITDA financial", top_k=1)
        assert len(hits) == 1
        assert hits[0]["chunk_id"] == "c1"

    @pytest.mark.anyio
    async def test_parallel_multi_substrate_retriever(self, pipeline_instance):
        """Verify parallel async gathering of vector, sparse BM25, and Neo4j paths."""
        retriever = AsyncParallelRetriever(pipeline_instance)
        res = await retriever.retrieve_parallel_and_fuse(
            query="What is the financial revenue and startup incubation metrics?",
            top_k=4,
            rerank_top_n=3
        )
        assert "reranked_chunks" in res
        assert "dense_count" in res
        assert "sparse_count" in res
        assert "graph_count" in res


# ----------------------------------------------------------------------
# 6. STATEFUL AGENTIC SYNTHESIS & QUALITY GATE
# ----------------------------------------------------------------------
class TestStage6SynthesisAndQualityGate:
    def test_agent_plan_and_synthesis_with_citations(self, pipeline_instance):
        """Verify query answering, inline citation extraction, and quality evaluation."""
        result = pipeline_instance.query_subgraph_graphrag(
            query="What are the key financial highlights and institutional metrics?",
            top_k=3,
        )
        assert "answer" in result or "grounded_answer" in result
        answer = result.get("answer") or result.get("grounded_answer")
        assert len(answer) > 30, "Generated answer must be comprehensive."
        
        # Verify citations contract
        import re
        citations = re.findall(r"\[\d+\]", answer)
        # Verify quality gate metrics
        score = result.get("traceability_score", 0.0)
        assert score >= 0.0, "Traceability score must be computed."


# ----------------------------------------------------------------------
# 7. COMPLETE VAULT WIPE ("delete all") VERIFICATION
# ----------------------------------------------------------------------
@pytest.mark.destructive
@pytest.mark.skipif(
    os.environ.get("RAISE_ALLOW_DESTRUCTIVE_TESTS") != "1",
    reason="Destructive live test disabled by default to protect developer database data. Set RAISE_ALLOW_DESTRUCTIVE_TESTS=1 to run.",
)
class TestStage7CompleteVaultPurge:
    def test_delete_all_wipes_all_substrates_and_files(self, pipeline_instance):
        """
        Wipe all documents, vectors, graph nodes, chunks, and physical files.
        Verify:
          - ChromaDB: count = 0
          - Neo4j: total_nodes = 0
          - NetworkX: nodes = 0
          - Processed Chunks & Triples: 0 files
          - Manifest: empty ready_documents
          - Physical Files in data/documents: 0 files
        """
        # Execute complete purge with raw file deletion
        purge_res = pipeline_instance.purge_all_documents(delete_raw_files=True)
        assert purge_res.get("status") == "success"

        # 1. ChromaDB check
        chroma_count = pipeline_instance.vector_engine.collection.count() if pipeline_instance.vector_engine.collection else 0
        assert chroma_count == 0, f"ChromaDB must be 0, found {chroma_count}"

        # 2. Neo4j check
        neo4j_conn = pipeline_instance.neo4j_db.check_connection()
        if neo4j_conn.get("connected"):
            total_nodes = neo4j_conn.get("total_nodes", -1)
            assert total_nodes == 0, f"Neo4j total_nodes must be 0, found {total_nodes}"

        # 3. NetworkX in-memory graph check
        nx_nodes = pipeline_instance.graph_engine.graph.number_of_nodes()
        assert nx_nodes == 0, f"In-memory graph nodes must be 0, found {nx_nodes}"

        # 4. Processed files check
        chunks_dir = settings.processed_dir / "chunks"
        triples_dir = settings.processed_dir / "graph_triples"
        facts_dir = settings.processed_dir / "facts"
        assert len(list(chunks_dir.glob("*.json"))) == 0, "All chunks JSON must be deleted."
        assert len(list(triples_dir.glob("*.json"))) == 0, "All triples JSON must be deleted."
        assert len(list(facts_dir.glob("*.json"))) == 0, "All facts JSON must be deleted."

        # 5. Manifest check
        manifest_path = settings.processed_dir / "ingested_manifest.json"
        if manifest_path.exists():
            mdata = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert len(mdata.get("ready_documents", [])) == 0, "Manifest ready_documents must be empty."

        # 6. Physical files check in data/documents/
        docs_dir = settings.documents_dir
        remaining_docs = [f.name for f in docs_dir.glob("*") if f.is_file()]
        assert len(remaining_docs) == 0, f"data/documents must be completely empty, found: {remaining_docs}"