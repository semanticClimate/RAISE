"""
Unit Tests for ChainCompletenessGate & Evidence-Driven Multi-Hop Extractor.
Validates:
1. Query requirements analysis (single-hop vs multi-hop, target attribute identification).
2. Evidence bridge entity extraction from Neo4j subgraph and chunk texts.
3. Pre-synthesis chain completeness gating and status transitions.
4. Deterministic honest abstention firewall when recovery fails.
5. Constrained graph bridge expansion in Neo4j database.
"""

import pytest
from unittest.mock import MagicMock
from src.retrieval.chain_gate import ChainCompletenessGate, ChainGateResult
from src.infrastructure.graph.neo4j import Neo4jDatabase


@pytest.mark.unit
def test_analyze_query_requirements_single_hop():
    """Verifies single-hop queries are identified with correct target attributes."""
    gate = ChainCompletenessGate()
    analysis = gate.analyze_query_requirements("What was the total expenditure in 2024?")
    
    assert analysis["is_multihop"] is False
    assert analysis["required_hops"] == 1
    assert analysis["target_attribute"] == "expenditure"
    assert "expenditure" in [s.lower() for s in analysis["seed_terms"]] or "2024" in analysis["seed_terms"]


@pytest.mark.unit
def test_analyze_query_requirements_multi_hop():
    """Verifies multi-hop queries are identified by relational phrase indicators."""
    gate = ChainCompletenessGate()
    analysis = gate.analyze_query_requirements("What was the budget of the center led by Dr. Raman?")
    
    assert analysis["is_multihop"] is True
    assert analysis["required_hops"] == 2
    assert analysis["target_attribute"] == "expenditure"


@pytest.mark.unit
def test_extract_evidence_bridge_from_subgraph():
    """Verifies bridge entity is discovered from Neo4j subgraph edges when one endpoint is in query."""
    gate = ChainCompletenessGate()
    subgraph = {
        "edges": [
            {"source": "Dr. Raman", "target": "Photonics Laboratory", "type": "DIRECTS"}
        ]
    }

    bridge = gate.extract_evidence_bridge_entity(
        query="What was the budget allocated to the project led by Dr. Raman?",
        retrieved_chunks=[],
        subgraph=subgraph,
    )

    assert bridge is not None
    entity_name, rel_type, conf = bridge
    assert entity_name == "Photonics Laboratory"
    assert rel_type == "DIRECTS"
    assert conf >= 0.85


@pytest.mark.unit
def test_extract_evidence_bridge_from_chunk_text():
    """Verifies bridge entity is extracted from chunk text when subgraph has no edges."""
    gate = ChainCompletenessGate()
    chunks = [
        {
            "chunk_id": "c1",
            "text": "The Photonics Laboratory was established in 2020 and received major research awards.",
            "primary_page": 2,
        }
    ]

    bridge = gate.extract_evidence_bridge_entity(
        query="What is the funding of the initiative led by Dr. Raman?",
        retrieved_chunks=chunks,
        subgraph=None,
    )

    assert bridge is not None
    entity_name, rel_type, conf = bridge
    assert entity_name == "Photonics Laboratory"
    assert conf >= 0.80


@pytest.mark.unit
def test_evaluate_chain_single_hop_passes_when_evidence_present():
    """Verifies that single-hop queries with relevant evidence pass the completeness gate."""
    gate = ChainCompletenessGate()
    chunks = [
        {"chunk_id": "c1", "text": "Total institutional expenditure reached 340.5 Rs. Crore.", "primary_page": 3}
    ]

    res = gate.evaluate_chain(
        query="What was the total expenditure in 2024?",
        retrieved_chunks=chunks,
        is_recovery_pass=False,
    )

    assert res.is_complete is True
    assert res.status == "PASSED"
    assert res.completed_hops >= 1


@pytest.mark.unit
def test_evaluate_chain_triggers_recovery_on_missing_bridge():
    """Verifies that multi-hop queries missing the second hop trigger recovery."""
    gate = ChainCompletenessGate()
    subgraph = {
        "edges": [
            {"source": "Dr. Raman", "target": "Photonics Laboratory", "type": "DIRECTS"}
        ]
    }
    chunks = [
        {"chunk_id": "c1", "text": "Dr. Raman led the initiative.", "primary_page": 1}
    ]

    res = gate.evaluate_chain(
        query="What was the budget of the center led by Dr. Raman?",
        retrieved_chunks=chunks,
        subgraph=subgraph,
        is_recovery_pass=False,
    )

    assert res.is_complete is False
    assert res.status == "TRIGGER_RECOVERY"
    assert res.discovered_bridge_entity == "Photonics Laboratory"
    assert res.targeted_hop2_query is not None
    assert "Photonics Laboratory" in res.targeted_hop2_query


@pytest.mark.unit
def test_evaluate_chain_abstains_when_recovery_pass_still_missing():
    """Verifies deterministic honest abstention when recovery pass still fails to find evidence."""
    gate = ChainCompletenessGate()
    chunks = []  # Zero chunks even after recovery pass

    res = gate.evaluate_chain(
        query="What was the budget of the center led by Dr. Raman?",
        retrieved_chunks=chunks,
        is_recovery_pass=True,
    )

    assert res.is_complete is False
    assert res.status == "ABSTAIN_INSUFFICIENT"


@pytest.mark.unit
def test_neo4j_constrained_bridge_query():
    """Verifies Neo4jDatabase.query_constrained_bridge runs parameterized Cypher expansion."""
    db = Neo4jDatabase()
    db.check_connection = MagicMock(return_value={"connected": True})
    db.run_cypher = MagicMock(return_value=[
        {
            "bridge_entity": "Photonics Laboratory",
            "rel": "ALLOCATED_TO",
            "target_entity": "Department of Physics",
            "target_label": "Department",
            "doc_id": "Report_2024.pdf",
            "page": 5,
        }
    ])

    results = db.query_constrained_bridge("Photonics Laboratory", target_relation_types=["ALLOCATED_TO"])
    assert len(results) == 1
    assert results[0]["target_entity"] == "Department of Physics"
    assert results[0]["page"] == 5
    db.run_cypher.assert_called_once()
