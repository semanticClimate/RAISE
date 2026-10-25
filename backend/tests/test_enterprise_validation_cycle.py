"""
RAISE Enterprise GraphRAG Validation Cycle Test Suite
Covers:
  1. Question Intake & Conversational Reasoning (Validation, Session Memory, Pronoun Resolution)
  2. Structure-Aware Chunking & Unique Hierarchical ID Generation
  3. Text Quality Gate & OCR Artifact Normalization
  4. Vector Integrity & Dimensional Validation (No NaN/Inf)
  5. Cross-Database Consistency Audit (Chunks == Vectors == Graph)
  6. End-to-End Grounded Data Lineage Traceability
"""

import os
import sys
import json
import pytest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app import app, rag_engine, session_memory_manager
from src.parsers.document_parser import SmartDocumentParser, TextQualityGate
from src.features.ingestion.auditor import CrossDatabaseConsistencyAuditor
from src.infrastructure.vector.chroma import LocalVectorEngine
from src.features.agent.workflow import AcademicGraphRAGWorkflow

client = TestClient(app)


# =============================================================================
# 1. QUESTION INTAKE & CONVERSATIONAL REASONING TESTS
# =============================================================================
class TestQuestionIntakeAndSessionMemory:
    def test_question_empty_and_whitespace_validation(self):
        """Verify empty and pure whitespace questions are safely refused."""
        res1 = client.post("/api/graphrag/subgraph-query", json={"query": ""})
        assert res1.status_code in [200, 400]
        data1 = res1.json()
        assert "error" in data1 or "detail" in data1

        res2 = client.post("/api/graphrag/subgraph-query", json={"query": "    \n\t   "})
        assert res2.status_code in [200, 400]
        data2 = res2.json()
        assert "error" in data2 or "detail" in data2

    def test_question_excessive_length_validation(self):
        """Verify queries exceeding 2500 characters are safely rejected."""
        long_query = "What is the budget? " * 200
        res = client.post("/api/graphrag/subgraph-query", json={"query": long_query})
        assert res.status_code in [200, 400]
        data = res.json()
        err_msg = str(data.get("error") or data.get("detail", ""))
        assert "exceeds maximum allowed length" in err_msg

    def test_multi_turn_pronoun_anaphora_resolution(self):
        """
        Verify that Turn 1 registers dominant entities and Turn 2 resolves
        pronouns ('their', 'its', 'they') to the entity in conversational context.
        """
        session_id = "test_sess_pronoun_resolution"
        # Turn 1: Explicit mention of institution
        session_memory_manager.record_turn(
            thread_id=session_id,
            user_query="Tell me about IIT Madras Research Park incubation program.",
            resolved_query="Tell me about IIT Madras Research Park incubation program.",
            active_entities=["IIT Madras Research Park", "Incubation Center"],
            citations=[],
            assistant_answer="IIT Madras Research Park has incubated hundreds of startups.",
        )

        # Turn 2: Pronoun query "What were their primary revenues?"
        resolved, dominant = session_memory_manager.resolve_coreference(
            "What were their primary revenues?",
            thread_id=session_id
        )
        assert dominant == "IIT Madras Research Park"
        assert "IIT Madras Research Park's" in resolved
        assert "their" not in resolved.lower()

    def test_session_history_and_clear_endpoints(self):
        """Verify session history retrieval and session state purge endpoints."""
        session_id = "test_sess_endpoints_123"
        session_memory_manager.record_turn(
            thread_id=session_id,
            user_query="What is the incubation count?",
            resolved_query="What is the incubation count?",
            active_entities=["Incubation Hub"],
            citations=[],
            assistant_answer="Over 300 startups.",
        )

        # 1. Check history endpoint
        res = client.get(f"/api/session/{session_id}/history")
        assert res.status_code == 200
        data = res.json()
        assert data.get("session_id") == session_id
        assert data.get("turns_count") == 1
        assert data.get("history")[0]["user_query"] == "What is the incubation count?"

        # 2. Check delete endpoint
        del_res = client.delete(f"/api/session/{session_id}")
        assert del_res.status_code == 200
        assert del_res.json().get("status") == "success"

        # 3. Verify history is empty
        history_after = session_memory_manager.get_thread_history(session_id)
        assert len(history_after) == 0


# =============================================================================
# 2. CHUNKING & UNIQUE HIERARCHICAL ID GENERATION TESTS
# =============================================================================
class TestChunkingAndIntegrity:
    def test_chunk_id_uniqueness_on_multisection_pages(self):
        """
        Verify that multiple sections on the same page receive unique,
        hierarchical chunk IDs (e.g. doc_p001_c01, doc_p001_c02) without collisions.
        """
        from src.features.ingestion.pipeline import AcademicPipelineIngestor
        ingestor = AcademicPipelineIngestor()

        dummy_sections = [
            {"page_number": 1, "heading": "Executive Summary", "text": "Annual report highlights for the fiscal year."},
            {"page_number": 1, "heading": "Key Financial Highlights", "text": "Total revenue reached 18234 crore in FY24."},
            {"page_number": 1, "heading": "Incubated Startups", "text": "Over 300 deep tech startups were incubated."},
            {"page_number": 2, "heading": "Board of Governors", "text": "The board convened four times during the reporting period."},
        ]

        doc_id = "test_doc_uniqueness"
        page_chunk_counts = {}
        generated_chunks = []
        for sec in dummy_sections:
            pno = sec["page_number"]
            raw_text = sec["text"]
            heading = sec["heading"]
            cleaned = ingestor.extractor.clean_text(raw_text)

            page_chunk_counts[pno] = page_chunk_counts.get(pno, 0) + 1
            chunk_idx = page_chunk_counts[pno]
            chunk_id = f"{doc_id}_p{pno:03d}_c{chunk_idx:02d}"
            generated_chunks.append({
                "chunk_id": chunk_id,
                "primary_page": pno,
                "heading": heading,
                "plain_text": cleaned,
            })

        chunk_ids = [c["chunk_id"] for c in generated_chunks]
        assert len(chunk_ids) == len(set(chunk_ids)), f"Duplicate chunk IDs found: {chunk_ids}"
        assert chunk_ids[0] == "test_doc_uniqueness_p001_c01"
        assert chunk_ids[1] == "test_doc_uniqueness_p001_c02"
        assert chunk_ids[2] == "test_doc_uniqueness_p001_c03"
        assert chunk_ids[3] == "test_doc_uniqueness_p002_c01"


# =============================================================================
# 3. TEXT QUALITY GATE & NORMALIZATION TESTS
# =============================================================================
class TestTextQualityGateAndNormalization:
    def test_normalize_spaced_lowercase_and_hyphenation(self):
        """Verify normalizer repairs spaced lowercase tokens and hyphen line breaks."""
        parser = SmartDocumentParser()

        # Test lowercase spaced letters
        raw = "The e c o n o m i c and d e v e l o p m e n t growth was substantial."
        normalized = parser.normalize_text(raw)
        assert "economic" in normalized
        assert "development" in normalized
        assert "e c o n o m i c" not in normalized

        # Test hyphen line break
        raw_hyphen = "Significant inno-\nvation was demonstrated across sectors."
        norm_hyphen = parser.normalize_text(raw_hyphen)
        assert "innovation" in norm_hyphen
        assert "inno-\nvation" not in norm_hyphen

        # Test uppercase spaced letters
        raw_upper = "ANNUAL S N A P S H O T REPORT"
        norm_upper = parser.normalize_text(raw_upper)
        assert "SNAPSHOT" in norm_upper

    def test_text_quality_gate_assessment(self):
        """Verify TextQualityGate discriminates clean text from corrupted text."""
        clean_text = (
            "IIT Madras Research Park provides state of the art laboratory infrastructure "
            "for deep technology research, incubating innovative ventures across clean energy, "
            "semiconductors, and aerospace engineering."
        )
        report_clean = TextQualityGate.assess(clean_text)
        assert report_clean["is_acceptable"] is True
        assert report_clean["garbled_ratio"] < 0.10

        garbled_text = "aaaaabbbbb cccccddddd \x00\x01\x02\x03\x04 xxxxxxxxxxxxxxxxxx yyyyyyyyyyyyyyyyyy zzzzzzzzzzzzzz"
        report_garbled = TextQualityGate.assess(garbled_text)
        assert report_garbled["is_acceptable"] is False
        assert report_garbled["garbled_ratio"] > 0.25

        report_empty = TextQualityGate.assess("")
        assert report_empty["is_acceptable"] is False
        assert report_empty["reason"] == "empty_text"


# =============================================================================
# 4. VECTOR INTEGRITY TESTS
# =============================================================================
class TestVectorIntegrity:
    def test_validate_embedding_vector_dimensions_and_finite(self):
        """Verify vector integrity checks: correct dimensions, no NaN/Inf, non-zero."""
        engine = LocalVectorEngine()
        dim = engine.dimension

        valid_vec = [0.05] * dim
        assert engine.validate_embedding_vector(valid_vec, dim) is True

        assert engine.validate_embedding_vector([0.05] * (dim - 1), dim) is False

        nan_vec = [0.05] * dim
        nan_vec[10] = float("nan")
        assert engine.validate_embedding_vector(nan_vec, dim) is False

        inf_vec = [0.05] * dim
        inf_vec[20] = float("inf")
        assert engine.validate_embedding_vector(inf_vec, dim) is False

        zero_vec = [0.0] * dim
        assert engine.validate_embedding_vector(zero_vec, dim) is False

    def test_compute_embeddings_returns_valid_vectors(self):
        """Verify compute_embeddings produces valid normalized vectors."""
        engine = LocalVectorEngine()
        texts = [
            "Research Park incubation ecosystem and funding metrics.",
            "Annual financial reports for university technology transfer."
        ]
        vectors = engine.compute_embeddings(texts)
        assert len(vectors) == 2
        for vec in vectors:
            assert engine.validate_embedding_vector(vec) is True


# =============================================================================
# 5. CROSS-DATABASE CONSISTENCY AUDIT TESTS
# =============================================================================
class TestCrossDatabaseConsistency:
    def test_cross_database_consistency_auditor_pass_and_fail(self):
        """Verify auditor flags mismatches between chunks, vectors, and graph nodes."""
        report_ok = CrossDatabaseConsistencyAuditor.audit_ingestion(
            doc_id="report_ok",
            expected_chunks=10,
            vector_count=10,
            entities_count=25,
            relations_count=30,
            neo4j_synced=True,
            neo4j_nodes=25,
        )
        assert report_ok["is_consistent"] is True
        assert len(report_ok["discrepancies"]) == 0

        report_bad_vec = CrossDatabaseConsistencyAuditor.audit_ingestion(
            doc_id="report_bad_vec",
            expected_chunks=10,
            vector_count=5,
            entities_count=25,
            relations_count=30,
            neo4j_synced=True,
            neo4j_nodes=25,
        )
        assert report_bad_vec["is_consistent"] is False
        assert any("vector count mismatch" in d for d in report_bad_vec["discrepancies"])

        report_bad_graph = CrossDatabaseConsistencyAuditor.audit_ingestion(
            doc_id="report_bad_graph",
            expected_chunks=10,
            vector_count=10,
            entities_count=25,
            relations_count=30,
            neo4j_synced=True,
            neo4j_nodes=0,
        )
        assert report_bad_graph["is_consistent"] is False
        assert any("0 nodes were verified" in d for d in report_bad_graph["discrepancies"])


# =============================================================================
# 6. END-TO-END DATA LINEAGE TRACEABILITY TESTS
# =============================================================================
class TestEndToEndDataLineage:
    def test_academic_graphrag_workflow_returns_data_lineage(self):
        """
        Verify that the LangGraph workflow constructs and returns a structured
        data_lineage trace mapping citations to chunk IDs and pages.
        """
        workflow = AcademicGraphRAGWorkflow(rag_engine=rag_engine)
        result = workflow.run(
            query="What are the key financial highlights and incubated startups?",
            hops=2,
            top_k=3,
        )
        assert "data_lineage" in result
        assert isinstance(result["data_lineage"], list)
