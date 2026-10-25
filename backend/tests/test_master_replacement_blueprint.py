"""
Comprehensive Verification Suite: The Master Replacement Blueprint
==================================================================
Validates all 8 industrial open-source replacements:
  1. DuckDB: In-Memory SQL OLAP Engine & Deterministic Math
  2. Kùzu: Embedded Serverless Property Graph & openCypher
  3. GPTCache: Sub-Millisecond Semantic Vector Cache
  4. LanceDB + FastEmbed: Embedded Vector Storage & ONNX Embeddings
  5. Instructor: Grammar-Guided Pydantic Output & Citation Provenance
  6. Guardrails AI: Hallucination Mitigation & Grounding Provenance
  7. LlamaIndex: Multi-Hop SubQuestion Query Decomposition
  8. Table QA / Text-to-SQL: Schema Generation & Exact Aggregations
"""

import os
import sys
import tempfile
import time
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# =========================================================================
# 1. DUCKDB: Deterministic SQL OLAP Analytics & Arithmetic Math Engine
# =========================================================================
def test_duckdb_tabular_olap_and_arithmetic():
    from src.features.verification.table_engine import TableEngine
    from src.features.verification.math_engine import DeterministicMathEngine

    engine = TableEngine()
    headers = ["Department", "Budget_Crores", "Expenditure_Crores", "Year"]
    rows = [
        ["Biotechnology", "120.50", "110.20", "2024"],
        ["Computer Science", "185.00", "180.50", "2024"],
        ["Civil Engineering", "65.40", "60.10", "2024"],
    ]
    record = engine.register_table(
        table_id="dept_financials",
        document_id="Report_2024.pdf",
        university="IIT Madras",
        title="Departmental Expenditure Summary",
        page=12,
        headers=headers,
        rows=rows,
    )

    assert record is not None
    # 1.1 Verify exact SQL aggregations (SUM, AVG, ORDER BY)
    query = """
        SELECT Department, Budget_Crores, Expenditure_Crores
        FROM dept_financials
        WHERE Budget_Crores > 100
        ORDER BY Budget_Crores DESC
    """
    results = engine.execute_sql(query)
    assert len(results) == 2
    assert results[0]["Department"] == "Computer Science"
    assert results[0]["Budget_Crores"] == 185.00

    # 1.2 Verify exact SUM calculation via DuckDB
    sum_query = "SELECT SUM(Budget_Crores) AS total_budget FROM dept_financials"
    sum_res = engine.execute_sql(sum_query)
    assert sum_res[0]["total_budget"] == pytest.approx(370.90, rel=1e-3)

    # 1.3 Verify DeterministicMathEngine DuckDB formula execution
    exact_math = DeterministicMathEngine.execute_duckdb_sql("(185.00 - 120.50) / 120.50 * 100")
    assert exact_math is not None
    assert exact_math == pytest.approx(53.5269, rel=1e-3)


# =========================================================================
# 2. KÙZU: Embedded openCypher Property Graph Execution
# =========================================================================
def test_kuzu_embedded_opencypher_execution():
    from src.graph.kuzu_graph import KuzuGraphEngine

    kuzu_engine = KuzuGraphEngine(":memory:")
    assert kuzu_engine._initialized is True

    # 2.1 Add entities
    kuzu_engine.add_entity("e1", "IIT Madras", label="University", props={"city": "Chennai"})
    kuzu_engine.add_entity("e2", "Healthcare Innovation Center", label="Facility", props={"floor": 3})
    kuzu_engine.add_entity("e3", "5G Testbed", label="Project", props={"budget": 224.0})

    # 2.2 Add directed relationships
    kuzu_engine.add_relation("e1", "e2", rel_type="HOSTS", weight=1.0)
    kuzu_engine.add_relation("e2", "e3", rel_type="SUPPORTS", weight=0.95)

    # 2.3 Traverse graph via standard openCypher
    cypher = (
        "MATCH (u:Entity {name: 'IIT Madras'})-[r1:Relates]->(f:Entity)-[r2:Relates]->(p:Entity) "
        "RETURN u.name AS university, r1.rel_type AS rel1, f.name AS facility, r2.rel_type AS rel2, p.name AS project"
    )
    records = kuzu_engine.query(cypher)
    assert len(records) >= 1
    assert records[0]["university"] == "IIT Madras"
    assert records[0]["facility"] == "Healthcare Innovation Center"
    assert records[0]["project"] == "5G Testbed"


# =========================================================================
# 3. GPTCACHE: Semantic Vector Similarity Caching
# =========================================================================
def test_gptcache_semantic_similarity_cache():
    from src.infrastructure.cache.semantic_cache import SemanticCacheMixin

    class DummyCacheManager(SemanticCacheMixin):
        def __init__(self):
            self.is_connected = False
            self._client = None
            self._memory_store = {}
            self._memory_semantic_cache = {}

        def get_completion(self, query, mode="fast", library=None, active_docs=None):
            return self._memory_store.get(f"{query}:{mode}")

        def set_completion(self, query, mode, data, library=None, active_docs=None, ttl=86400):
            self._memory_store[f"{query}:{mode}"] = data
            return True

    cache = DummyCacheManager()
    dummy_embedding = [0.1 * i for i in range(10)]
    # Normalize
    norm = sum(x**2 for x in dummy_embedding) ** 0.5
    dummy_vec = [x / norm for x in dummy_embedding]

    cached_payload = {"answer": "The total research grants for FY 2024 were ₹ 125 crore.", "citations": [1]}
    cache.semantic_set(
        query="What were the research grants in 2024?",
        result=cached_payload,
        mode="research",
        embedding=dummy_vec,
    )

    # Test near-identical query embedding (0.999 cosine similarity)
    near_vec = [v * 0.999 for v in dummy_vec]
    hit = cache.semantic_get(
        query="Tell me the 2024 research grants",
        mode="research",
        embedding=near_vec,
        threshold=0.95,
    )
    assert hit is not None
    assert hit["answer"] == cached_payload["answer"]


# =========================================================================
# 4. LANCEDB + FASTEMBED: Embedded Columnar Vector Store & ONNX Embeddings
# =========================================================================
def test_lancedb_fastembed_vector_store():
    from src.infrastructure.vector.lancedb_store import LanceDBVectorStore

    temp_dir = tempfile.mkdtemp()
    store = LanceDBVectorStore(db_path=temp_dir, table_name="test_chunks")

    # Ingest test chunks
    chunks = [
        {
            "id": "c1",
            "text": "The Ministry of Education granted ₹ 125 crore to the Advanced Quantum Computing Center.",
            "metadata": {"chunk_id": "c1", "primary_page": 4, "pdf_filename": "IITM_Report.pdf"},
        },
        {
            "id": "c2",
            "text": "The campus dining facility underwent renovation to expand seating capacity.",
            "metadata": {"chunk_id": "c2", "primary_page": 19, "pdf_filename": "IITM_Report.pdf"},
        },
    ]
    ingested_count = store.ingest_chunks(chunks, doc_id="IITM_Report")
    assert ingested_count == 2

    # Query using search
    query = "quantum computing funding grants"
    results = store.search(query, top_k=2)
    assert len(results) >= 1
    # Top chunk should be quantum computing chunk
    assert results[0]["id"] == "c1"
    assert "₹ 125 crore" in results[0]["text"]


# =========================================================================
# 5. INSTRUCTOR: Grammar-Guided Pydantic Schemas & Citation Provenance
# =========================================================================
def test_instructor_grounded_response_schema():
    from src.features.agent.citation_sanitizer import FactClaim, GroundedResponse

    # Validate strict schema contract
    claim1 = FactClaim(
        statement="The sponsored research grants reached ₹ 154.20 crore.",
        quote_from_document="Sponsored research grants totaled 154.20 crore during the financial year.",
        source_chunk_id="chk_fin_01",
        page_number=48,
    )
    response = GroundedResponse(
        answer="In FY 2024-25, sponsored research grants reached ₹ 154.20 crore [1].",
        verified_claims=[claim1],
    )

    d = response.model_dump()
    assert d["answer"].startswith("In FY 2024-25")
    assert len(d["verified_claims"]) == 1
    assert d["verified_claims"][0]["source_chunk_id"] == "chk_fin_01"
    assert d["verified_claims"][0]["page_number"] == 48


# =========================================================================
# 6. GUARDRAILS AI: Hallucination Mitigation & Grounding Provenance
# =========================================================================
def test_guardrails_anti_hallucination_validation():
    from src.features.evaluation.quality_gate import RigorousQualityGate

    gate = RigorousQualityGate()
    retrieved_contexts = [
        "The Department of Biotechnology operates 14 advanced wet lab facilities with ₹ 68 crore grants."
    ]

    # Valid grounded response
    good_resp = "The Department of Biotechnology manages 14 wet lab facilities."
    v_good = gate.validate_with_guardrails(good_resp, retrieved_contexts)
    assert v_good["valid"] is True

    # Ungrounded hallucinatory response with zero lexical or factual connection
    bad_resp = "Underwater volcanic exploration discovered titanium deposits."
    v_bad = gate.validate_with_guardrails(bad_resp, retrieved_contexts)
    assert v_bad["valid"] is False
    assert "Provenance" in v_bad.get("reason", "")


# =========================================================================
# 7. LLAMAININDEX: Multi-Hop SubQuestion Query Decomposition
# =========================================================================
def test_llamaindex_subquestion_decomposition():
    from src.features.query.decomposer import QueryDecomposerNode

    decomposer = QueryDecomposerNode()

    # 7.1 Test comparative multi-entity decomposition
    cmp_query = "Compare IIT Madras research grants in 2023 vs Panjab University in 2024"
    sub_qs = decomposer.decompose(cmp_query)
    assert len(sub_qs) == 2
    assert "IIT Madras" in sub_qs[0]
    assert "Panjab University" in sub_qs[1]

    # 7.2 Test LlamaIndex SubQuestion generation
    sq_objects = decomposer.decompose_subquestions(cmp_query)
    assert len(sq_objects) == 2
    assert hasattr(sq_objects[0], "sub_question") or "sub_question" in sq_objects[0]


# =========================================================================
# 8. TEXT-TO-SQL: Schema Generation & Table QA
# =========================================================================
def test_text_to_sql_schema_generation():
    from src.features.verification.table_engine import TableEngine

    engine = TableEngine()
    engine.register_table(
        table_id="patents_table",
        document_id="Patent_Report.pdf",
        university="Panjab University",
        title="Patents Filed and Granted",
        page=28,
        headers=["Category", "Filed_Count", "Granted_Count"],
        rows=[
            ["Medical Devices", "24", "12"],
            ["AI & Robotics", "45", "30"],
        ],
    )

    schema_prompt = engine.generate_sql_schema_prompt("patents_table")
    assert "CREATE TABLE patents_table" in schema_prompt
    assert "filed_count DOUBLE" in schema_prompt
    assert "granted_count DOUBLE" in schema_prompt
