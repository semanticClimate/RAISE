"""
Unit tests for Neo4j schema definitions, node labels, relationship types, and indexing logic.
"""

from unittest.mock import MagicMock
from src.infrastructure.graph.schema import (
    NODE_LABELS,
    RELATIONSHIP_TYPES,
    INDEX_CYPHER_STATEMENTS,
    CONSTRAINT_CYPHER_STATEMENTS,
    ensure_basic_indexes
)


def test_schema_definitions():
    assert len(NODE_LABELS) >= 35
    assert "Institution" in NODE_LABELS
    assert "AnnualReport" in NODE_LABELS
    assert "Section" in NODE_LABELS
    assert "Grant" in NODE_LABELS
    assert "Patent" in NODE_LABELS

    assert len(RELATIONSHIP_TYPES) >= 50
    assert "PUBLISHED" in RELATIONSHIP_TYPES
    assert "HAS_SECTION" in RELATIONSHIP_TYPES
    assert "FUNDED_GRANT" in RELATIONSHIP_TYPES
    assert "INCUBATED" in RELATIONSHIP_TYPES
    assert "UTILIZES_FACILITY" in RELATIONSHIP_TYPES


def test_ensure_basic_indexes():
    mock_db = MagicMock()
    mock_db.run_cypher.return_value = [{"status": "ok"}]

    results = ensure_basic_indexes(mock_db)

    expected_total = len(CONSTRAINT_CYPHER_STATEMENTS) + len(INDEX_CYPHER_STATEMENTS)
    assert len(results) == expected_total
    assert mock_db.run_cypher.call_count == expected_total
