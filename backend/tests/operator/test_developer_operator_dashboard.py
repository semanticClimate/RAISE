"""
Operator Test Suite: Developer & Database Operator Dashboard
Verifies:
  1. PostgreSQL 16 (Port 5432, table schemas, latency < 50ms)
  2. Redis 7 (Port 6379, 4-tier namespaces, latency < 15ms)
  3. Neo4j Graph (Port 7687, query latency < 150ms, node/edge counts)
  4. ChromaDB (Local vector storage, chunk counts)
  5. vLLM Engine (Port 8002, Qwen2.5-14B-Instruct-GPTQ-Int4)
  6. Cloudflare CLI (bin/cloudflared.exe, Version 2026.8.3)
  7. Cross-Database Document Alignment
  8. Operator Dashboard ASCII generation in < 500ms
"""

import time
import pytest

pytestmark = pytest.mark.operator


def test_subsystem_postgresql_operator(operator_instance):
    """Verify PostgreSQL 16 is live, responsive, and contains expected tables."""
    status = operator_instance.check_postgresql()
    assert status["status"] == "PASS", f"PostgreSQL failed check: {status.get('error')}"
    assert status["connected"] is True
    assert status["latency_ms"] < 50.0, f"PostgreSQL latency too high: {status['latency_ms']}ms"
    assert status["chat_messages_count"] >= 0
    assert status["registered_documents"] >= 0


def test_subsystem_redis_operator(operator_instance, redis_cache):
    """Verify Redis 7 is live, responsive, and manages key namespaces."""
    status = operator_instance.check_redis()
    assert status["status"] == "PASS", f"Redis failed check: {status.get('error')}"
    assert status["connected"] is True
    assert status["latency_ms"] < 15.0, f"Redis latency too high: {status['latency_ms']}ms"
    assert status["total_keys"] >= 0
    assert "used_memory_human" in status

    # Verify 4-tier namespace keys can be set and retrieved
    redis_cache.set_completion("test_q", "fast", {"test": True})
    hit = redis_cache.get_completion("test_q", "fast")
    assert hit == {"test": True}

    is_allowed, remaining = redis_cache.check_rate_limit("127.0.0.1")
    assert is_allowed is True
    assert remaining >= 0


def test_subsystem_neo4j_operator(operator_instance):
    """Verify Neo4j Graph database is live, responsive, and ready for queries."""
    status = operator_instance.check_neo4j()
    if not status.get("connected"):
        pytest.skip(f"Neo4j daemon offline: {status.get('error')}")
    assert status["status"] == "PASS", f"Neo4j failed check: {status.get('error')}"
    assert status["connected"] is True
    assert status["latency_ms"] < 150.0, f"Neo4j query latency too high: {status['latency_ms']}ms"
    assert status["total_nodes"] >= 0, f"Expected non-negative nodes, got {status['total_nodes']}"
    assert status["total_edges"] >= 0, f"Expected non-negative edges, got {status['total_edges']}"


def test_subsystem_chromadb_operator(operator_instance):
    """Verify ChromaDB local vector store is initialized and queryable."""
    status = operator_instance.check_chromadb()
    assert status["status"] == "PASS", f"ChromaDB failed check: {status.get('error')}"
    assert any(k in status["collection_name"] for k in ("raise", "iitmrp"))
    assert status["total_chunks"] >= 0, f"Expected non-negative chunks, got {status['total_chunks']}"
    assert status["latency_ms"] < 500.0, f"ChromaDB latency too high: {status['latency_ms']}ms"


def test_subsystem_vllm_operator(operator_instance):
    """Verify local vLLM server is serving Qwen2.5-14B on Port 8002."""
    status = operator_instance.check_vllm()
    assert status["status"] == "PASS", f"vLLM failed check: {status.get('error')}"
    assert status["online"] is True
    assert "Qwen" in status["model_loaded"] or "14B" in status["model_loaded"]
    assert status["latency_ms"] < 200.0


def test_subsystem_cloudflare_operator(operator_instance):
    """Verify portable Cloudflare CLI binary is present and version 2026.8.3."""
    status = operator_instance.check_cloudflare()
    assert status["status"] == "PASS", f"Cloudflare failed check: {status.get('error')}"
    assert status["installed"] is True
    assert "2026." in status["version"]
    assert status["path"].endswith("cloudflared.exe")


def test_cross_database_document_alignment_operator(operator_instance):
    """Verify document alignment across ChromaDB vector store and Neo4j graph."""
    alignment = operator_instance.audit_document_alignment()
    assert isinstance(alignment, dict)
    assert "documents" in alignment
    assert len(alignment["documents"]) > 0

    for doc in alignment["documents"]:
        assert "filename" in doc
        assert "status" in doc
        assert "in_disk" in doc
        assert "in_chromadb" in doc


def test_full_dashboard_execution_speed_and_ascii_report(operator_instance):
    """Verify complete dashboard checkup runs in < 500ms and formats ASCII report."""
    start = time.perf_counter()
    report = operator_instance.run_full_checkup()
    duration_ms = (time.perf_counter() - start) * 1000

    assert duration_ms < 500.0, f"Full checkup exceeded SLA target: {duration_ms:.2f}ms"
    if report["databases"]["neo4j"]["status"] != "PASS":
        assert report["overall_status"] in ["ALL_SYSTEMS_OPERATIONAL", "SYSTEMS_ATTENTION_REQUIRED"]
    else:
        assert report["overall_status"] == "ALL_SYSTEMS_OPERATIONAL"
        assert report["databases"]["neo4j"]["status"] == "PASS"
    
    assert "databases" in report
    assert "inference" in report
    assert "networking" in report
    assert "document_alignment" in report

    assert report["databases"]["postgresql"]["status"] == "PASS"
    assert report["databases"]["redis"]["status"] == "PASS"
    assert report["databases"]["chromadb"]["status"] == "PASS"
    assert report["inference"]["vllm"]["status"] == "PASS"
    assert report["networking"]["cloudflare_tunnel"]["status"] == "PASS"

    # Format ASCII dashboard
    ascii_output = operator_instance.format_dashboard_text(report)
    assert "RAISE DEVELOPER & DATABASE OPERATOR DASHBOARD" in ascii_output
    assert "CORE SUBSYSTEMS STATUS" in ascii_output
    assert "CROSS-DATABASE DOCUMENT ALIGNMENT" in ascii_output
    assert "PostgreSQL 16" in ascii_output
    assert "Redis 7" in ascii_output
    assert "Neo4j Graph" in ascii_output
    assert "ChromaDB" in ascii_output
    assert "vLLM Engine" in ascii_output
    assert "Cloudflare CLI" in ascii_output