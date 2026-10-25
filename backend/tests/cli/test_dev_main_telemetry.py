"""
Tests TelemetryService.build_frame, MetricState tagging, and trace JSON export.
Ensures zero fake numbers are synthesized.
"""

import json
from pathlib import Path
import pytest
from src.cli.models import MetricState, MetricValue
from src.cli.renderer import ObsMode
from src.cli.telemetry_service import TelemetryService
from src.cli.commands import SessionTracker


@pytest.mark.unit
@pytest.mark.cli
def test_telemetry_service_honest_metric_states():
    """Verifies that measured vs unavailable metrics are truthfully tagged."""
    raw_result = {
        "grounded_answer": "Research expenditure was 340.5 Rs. Crore.",
        "citations": [
            {"chunk_id": "c1", "similarity": 0.85, "primary_page": 3, "text": "Expenditure: 340.5 Rs. Crore."}
        ],
        "timings": {
            "routing_ms": 10.0,
            "vector_retrieval_ms": 25.0,
            "synthesis_ms": 150.0,
            "quality_gate_ms": 15.0,
            "total_latency_ms": 200.0,
        },
    }

    frame = TelemetryService.build_frame(
        result=raw_result,
        query="What was the total research outlay?",
        turn_id="RAISE-T0001",
        session_id="DEV-TEST-001",
        scope="Sample_Report.pdf",
        mode="TRACE",
    )

    # 1. Measured metrics
    assert frame.performance.total_latency_ms == 200.0
    assert frame.performance.routing_ms == 10.0

    # 2. Graph retrieval was not present in raw timings -> must be NOT_APPLICABLE
    assert frame.retrieval.graph.latency_ms.state == MetricState.NOT_APPLICABLE
    assert frame.retrieval.graph.nodes_visited.state == MetricState.NOT_APPLICABLE

    # 3. Context tokens approximated via heuristic -> must be ESTIMATED
    assert frame.context_assembly.context_tokens.state == MetricState.ESTIMATED
    assert frame.context_assembly.context_tokens.value is not None


@pytest.mark.unit
@pytest.mark.cli
def test_trace_json_serialization_and_export(clean_traces_dir, test_session):
    """Verifies that export_traces generates valid, complete JSON without schema errors."""
    raw_result = {
        "grounded_answer": "The solar installation capacity is 4.2 Megawatt [1].",
        "citations": [{"citation_index": 1, "document": "Report.pdf", "primary_page": 5, "text": "4.2 MW Solar"}],
        "timings": {"routing_ms": 5.0, "synthesis_ms": 80.0, "total_latency_ms": 85.0},
    }

    frame = TelemetryService.build_frame(
        result=raw_result,
        query="What is the solar capacity?",
        turn_id=test_session.next_turn_id(),
        session_id=test_session.session_id,
    )
    test_session.record_turn(frame)

    exported_path = test_session.export_traces("test_trace_01.json")
    assert Path(exported_path).exists()

    data = json.loads(Path(exported_path).read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["turn_id"] == "RAISE-T0001"
    assert data[0]["answer"] == "The solar installation capacity is 4.2 Megawatt [1]."
    assert data[0]["performance"]["total_latency_ms"] == 85.0


@pytest.mark.unit
@pytest.mark.cli
def test_conversational_persona_zero_db_bypass_frame():
    """Verifies that zero-db bypass conversational queries produce valid TelemetryFrames."""
    frame = TelemetryService.build_frame(
        result={
            "grounded_answer": "Hello Sid! I am RAISE.",
            "query_intent": "CONVERSATIONAL",
            "routing_strategy": "ZERO_DB_BYPASS",
            "timings": {"routing_ms": 2.0, "synthesis_ms": 1.0},
        },
        query="my name is Sid",
        turn_id="RAISE-T0001",
        session_id="DEV-CONV",
        scope="CONVERSATIONAL",
        mode="TRACE",
    )

    assert frame.intent.intent.value == "CONVERSATIONAL"
    assert frame.retrieval.vector.candidates.state == MetricState.UNAVAILABLE
    assert frame.debug_summary.status == "PASS"
    assert frame.debug_summary.expected_intent == "CONVERSATIONAL"
