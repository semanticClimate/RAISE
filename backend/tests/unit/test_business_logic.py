"""
Unit Test Suite: Algorithmic Engines & Business Logic
Verifies:
  1. Deterministic Math Engine (Growth Rate, Sums, Formulas)
  2. Table Engine (Cell-Coordinate Binding [R1:C3])
  3. Graph Centrality (Hub-Pruned PageRank Debiasing)
  4. Cypher Security Guardrails (Injection Prevention)
  5. Hybrid Fusion & Cross-Encoder Reranking
"""

import pytest
from src.features.verification.table_engine import TableEngine
from src.features.verification.math_engine import DeterministicMathEngine
from src.features.graph.engine import GraphRAGEngine
from src.features.agent.tools import CypherSecurityGuardrail
from src.retrieval.fusion import hybrid_fuse_and_rerank

pytestmark = pytest.mark.unit


def test_unit_deterministic_math_growth_rate():
    """Verify deterministic calculation of percentage growth rate."""
    query = "What was the growth rate of Sponsored Research Grants between FY 2023-24 and FY 2024-25?"
    intent = DeterministicMathEngine.detect_math_intent(query)
    assert intent == "GROWTH_RATE"

    calc = DeterministicMathEngine.compute("GROWTH_RATE", [120.50, 154.20])
    assert calc.calculated_value == 27.9668
    assert "27.97%" in calc.formatted_result
    assert "((154.2 - 120.5) / 120.5) * 100" in calc.formula_expression


def test_unit_deterministic_math_sum():
    """Verify deterministic multi-stream summation."""
    query = "What is the total combined revenue across all streams?"
    intent = DeterministicMathEngine.detect_math_intent(query)
    assert intent == "SUM"

    calc = DeterministicMathEngine.compute("SUM", [154.20, 92.40, 58.60], units="Rs. Crore")
    assert calc.calculated_value == 305.20
    assert "305.2" in calc.formatted_result


def test_unit_table_coordinate_binding(sample_financial_table_rows):
    """Verify cell coordinate binding [R1:C3] for financial statements."""
    headers, rows = sample_financial_table_rows
    engine = TableEngine()
    record = engine.register_table(
        table_id="tbl_stmt_unit",
        document_id="financials_2025.pdf",
        university="Panjab University",
        title="Statement of Revenues",
        page=48,
        headers=headers,
        rows=rows,
        currency="INR Crore"
    )

    coord_md = record.to_coordinate_bound_markdown()
    assert "[R1:C3]" in coord_md

    cell = record.lookup_cell(row=1, col=3)
    assert cell is not None
    assert cell.numeric_value == 154.20
    assert cell.header_col == "FY 2024-25 (Rs. Cr)"


def test_unit_pagerank_hub_pruned_debiasing():
    """Verify super-hub nodes do not cannibalize centrality rankings."""
    ge = GraphRAGEngine()
    ge.graph.add_node("Central Hub", type="Institution", label="Central Hub")
    for i in range(12):
        s_name = f"Venture_{i}"
        ge.graph.add_node(s_name, type="Startup", label=s_name)
        ge.graph.add_edge("Central Hub", s_name, relation="INCUBATED")

    ge.graph.add_edge("Venture_0", "Venture_1", relation="COLLABORATES")
    ge.graph.add_edge("Venture_1", "Venture_2", relation="COLLABORATES")

    metrics = ge.compute_centrality_metrics(exclude_super_hubs=True)
    assert "Venture_0" in metrics
    assert "Venture_1" in metrics
    assert metrics["Venture_1"]["pagerank"] > 0


def test_unit_cypher_security_guardrails():
    """Verify mutating injections and administrative exfiltration are blocked."""
    # Valid read-only query
    q_valid = "MATCH (p:Person)-[:PRINCIPAL_INVESTIGATOR]->(g:Grant) RETURN p, g LIMIT 10"
    res_valid = CypherSecurityGuardrail.validate_and_parameterize(q_valid)
    assert res_valid["valid"] is True

    # Mutating injection attempt
    q_mutating = "MATCH (n) DETACH DELETE n // bypass"
    res_mutating = CypherSecurityGuardrail.validate_and_parameterize(q_mutating)
    assert res_mutating["valid"] is False
    assert "mutat" in res_mutating["reason"].lower() or "forbidden" in res_mutating["reason"].lower()

    # Administrative metadata exfiltration attempt
    q_admin = "CALL dbms.security.listUsers()"
    res_admin = CypherSecurityGuardrail.validate_and_parameterize(q_admin)
    assert res_admin["valid"] is False


def test_unit_hybrid_fusion_reciprocal_rank():
    """Verify reciprocal rank fusion combines dense, sparse, and graph substrates."""
    query = "What grants were received by Dr. Panigrahi?"
    dense = [{"chunk_id": "chk_101", "plain_text": "Grant Rs. 45 Lakhs.", "score": 0.89}]
    sparse = [{"chunk_id": "chk_101", "plain_text": "Grant Rs. 45 Lakhs.", "score": 12.4}]
    graph = [{"chunk_id": "chk_101", "plain_text": "Panigrahi Grant DST", "score": 1.0}]

    passages = hybrid_fuse_and_rerank(query, dense, sparse, graph, top_n=1, rrf_k=60)
    assert len(passages) == 1
    assert passages[0]["chunk_id"] == "chk_101"