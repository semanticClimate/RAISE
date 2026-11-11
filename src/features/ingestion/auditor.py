"""
Ingestion Isolation Guard & Cross-Database Consistency Auditor
==============================================================
Component: `src.features.ingestion.auditor`
Architecture Layer: Ingestion / Isolation Guard & Cross-Substrate Audit

Overview:
---------
Ensures benchmark and evaluation datasets are isolated from vector/graph stores,
and validates cross-substrate consistency among Chunks, Vectors, Entities, and Graphs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("raise.ingestion.auditor")


def should_ingest(file_path: str | Path) -> bool:
    """
    Enforces strict database isolation to prevent benchmark data contamination.
    Excludes test suites, evaluation materials, benchmark QA files, and question suites.
    """
    path_str = str(file_path).lower().replace("\\", "/")
    excluded_patterns = [
        "evaluation",
        "benchmark",
        "question_suite",
        "question suite",
        "raise-bench",
        "gemini-notebook",
        "benchmark_qa",
    ]
    return not any(pattern in path_str for pattern in excluded_patterns)


class CrossDatabaseConsistencyAuditor:
    """
    Audits cross-substrate data integrity between:
      1. Chunks created in ingestion pipeline
      2. Vectors persisted in ChromaDB
      3. Entities and relationships populated in Neo4j / NetworkX
    """

    @staticmethod
    def audit_ingestion(
        doc_id: str,
        expected_chunks: int,
        vector_count: int,
        entities_count: int,
        relations_count: int,
        neo4j_synced: bool = False,
        neo4j_nodes: int = 0,
        neo4j_edges: int = 0,
    ) -> Dict[str, Any]:
        discrepancies = []
        if vector_count < expected_chunks:
            discrepancies.append(
                f"ChromaDB vector count mismatch: stored {vector_count} vs {expected_chunks} expected chunks."
            )
        if entities_count == 0 and expected_chunks > 0:
            discrepancies.append("Zero academic entities extracted for populated document.")
        if neo4j_synced and neo4j_nodes == 0 and entities_count > 0:
            discrepancies.append(
                "Neo4j live sync reported success but 0 nodes were verified in graph."
            )

        is_consistent = len(discrepancies) == 0
        return {
            "doc_id": doc_id,
            "is_consistent": is_consistent,
            "expected_chunks": expected_chunks,
            "vector_count": vector_count,
            "entities_count": entities_count,
            "relations_count": relations_count,
            "neo4j_nodes": neo4j_nodes,
            "discrepancies": discrepancies,
        }
