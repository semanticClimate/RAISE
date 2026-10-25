"""
Shared Pytest Fixtures for RAISE CLI & Developer Studio Testing.
Guarantees zero database contamination, offline model isolation, and clean stdout capture.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# Enforce offline flags
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["RAISE_DEV_PURGE_TOKEN"] = ""  # Strictly unset for test safety

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli.models import (
    MetricState,
    MetricValue,
    TelemetryFrame,
    FailureClassification,
)
from src.cli.renderer import ObsMode
from src.cli.commands import SessionTracker


@pytest.fixture
def mock_pipeline():
    """Provides a completely mocked StandaloneRAGPipeline preventing live DB connections."""
    pipeline = MagicMock()
    pipeline.vector_engine.get_active_workspace_documents.return_value = [
        "AR_2024-25_Combined_English_Mail.pdf",
        "IITMRP Annual Report.pdf",
    ]
    pipeline.neo4j_db.connected = True
    pipeline.neo4j_db.run_cypher.return_value = [{"nodes": 1500, "rels": 3200}]
    pipeline.vector_engine.collection.count.return_value = 850
    
    pipeline.query_subgraph_graphrag.return_value = {
        "grounded_answer": "The peak compute capacity reached 15.4 Petaflops [1].",
        "citations": [
            {
                "citation_index": 1,
                "document": "IITMRP Annual Report.pdf",
                "primary_page": 4,
                "printed_page": "4",
                "section_heading": "High-Performance Supercomputing",
                "chunk_id": "chunk_0042",
                "similarity": 0.892,
                "text": "The institute deployed 128 supercomputing nodes with peak compute capacity of 15.4 Petaflops.",
            }
        ],
        "quality_gate_decision": "accept",
        "timings": {
            "routing_ms": 12.5,
            "vector_retrieval_ms": 35.2,
            "bm25_retrieval_ms": 18.1,
            "graph_retrieval_ms": 42.0,
            "reranking_ms": 15.4,
            "synthesis_ms": 210.6,
            "quality_gate_ms": 28.3,
            "total_latency_ms": 362.1,
        },
    }
    return pipeline


@pytest.fixture
def mock_memory():
    """Provides a mocked ReasoningMemory."""
    mem = MagicMock()
    mem.trajectories = []
    return mem


@pytest.fixture
def test_session():
    """Provides a clean SessionTracker initialized to TRACE mode."""
    return SessionTracker(mode=ObsMode.TRACE)


@pytest.fixture
def clean_traces_dir(tmp_path, monkeypatch):
    """Redirects trace export files to a temporary directory."""
    test_traces = tmp_path / "traces"
    test_traces.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("src.cli.commands.TRACES_DIR", test_traces)
    return test_traces


@pytest.fixture(autouse=True)
def safety_purge_shield(monkeypatch):
    """Ensures superuser purge token is never accidentally available during test runs."""
    monkeypatch.delenv("RAISE_DEV_PURGE_TOKEN", raising=False)
    monkeypatch.delenv("RAISE_ALLOW_DESTRUCTIVE_TESTS", raising=False)
