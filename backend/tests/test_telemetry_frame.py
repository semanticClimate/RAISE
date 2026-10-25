"""
Unit Tests for RAISE TelemetryFrame, MetricState Provenance, and TelemetryService.
Verifies:
1. Zero synthetic fake-number fallbacks (UNAVAILABLE/NOT_APPLICABLE properly preserved).
2. Proper MetricState tagging (MEASURED, DERIVED, ESTIMATED, UNAVAILABLE, NOT_APPLICABLE).
3. TelemetryFrame serialization to dictionary for API/JSON export.
4. Clean rendering without exceptions.
"""

import pytest
from src.cli.models import (
    MetricState,
    MetricValue,
    TelemetryFrame,
)
from src.cli.telemetry_service import TelemetryService
from src.cli.renderer import TelemetryRenderer, ObsMode


def test_metric_value_provenance_states():
    # Measured
    m = MetricValue.measured(42, unit="chunks")
    assert m.is_available is True
    assert m.state == MetricState.MEASURED
    assert m.display() == "42 chunks"

    # Derived
    d = MetricValue.derived(18.4, unit="%")
    assert d.is_available is True
    assert d.state == MetricState.DERIVED
    assert "[DERIVED]" in d.display()

    # Estimated
    e = MetricValue.estimated(1200, unit="tokens")
    assert e.is_available is True
    assert e.state == MetricState.ESTIMATED
    assert "[ESTIMATED]" in e.display()

    # Unavailable (NEVER replace with a fake number!)
    u = MetricValue.unavailable(unit="ms")
    assert u.is_available is False
    assert u.state == MetricState.UNAVAILABLE
    assert "-- [UNAVAILABLE]" in u.display()

    # Not Applicable
    na = MetricValue.not_applicable()
    assert na.is_available is False
    assert na.state == MetricState.NOT_APPLICABLE
    assert "-- [NOT_APPLICABLE]" in na.display()


def test_telemetry_service_honest_building():
    # Simulate a pipeline result where some metrics were measured and others were omitted
    mock_result = {
        "grounded_answer": "IIT Madras secured 45 sponsored projects [1].",
        "query_intent": "FACTUAL",
        "routing_strategy": "HYBRID_VECTOR",
        "citations": [
            {
                "citation_index": 1,
                "pdf_filename": "Annual_Report_2024.pdf",
                "primary_page": 12,
                "heading": "Sponsored Research",
                "chunk_id": "chunk_001",
                "similarity": 0.892,
                "distance": 0.108,
            }
        ],
        "telemetry": {
            "intent": "FACTUAL",
            "intent_confidence": 0.95,
            "vector_candidates": 10,
            "top_k": 5,
            "stages": {
                "routing_ms": 12.5,
                "vector_retrieval_ms": 45.0,
                "synthesis_ms": 150.0,
                "quality_gate_ms": 10.0,
            },
            "quality_gate_report": {
                "faithfulness": 0.94,
                "unsupported_claims_count": 0,
                "numerical_claims_verified": 1,
                "numerical_claims_total": 1,
            },
        },
    }

    frame = TelemetryService.build_frame(
        result=mock_result,
        query="How many sponsored projects did IIT Madras secure?",
        turn_id="RAISE-T0001",
        session_id="DEV-SESSION-01",
        scope="ALL DOCUMENTS",
        mode="TRACE",
    )

    # Assert basic frame metadata
    assert frame.turn_id == "RAISE-T0001"
    assert frame.session_id == "DEV-SESSION-01"
    assert frame.intent.intent.value == "FACTUAL"
    assert frame.intent.intent.state == MetricState.MEASURED

    # Vector distance was provided in citation: min distance must be MEASURED
    assert frame.retrieval.vector.distance_min.is_available is True
    assert frame.retrieval.vector.distance_min.state == MetricState.MEASURED
    assert abs(frame.retrieval.vector.distance_min.value - 0.108) < 1e-4

    # Graph was NOT queried because routing was HYBRID_VECTOR and no graph nodes returned:
    # Graph metrics must be NOT_APPLICABLE rather than fake numbers!
    assert frame.retrieval.graph.nodes_visited.state == MetricState.NOT_APPLICABLE
    assert frame.retrieval.graph.edges_traversed.state == MetricState.NOT_APPLICABLE

    # Rerank score delta was NOT provided: it must be UNAVAILABLE rather than fake 18.4%!
    assert frame.retrieval.rerank.score_improvement_pct.state == MetricState.UNAVAILABLE

    # Synthesis speed is mathematically derived from completion tokens and synthesis time
    assert frame.synthesis.generation_speed_tok_s.state == MetricState.DERIVED

    # Quality Gate
    assert frame.quality.is_gate_passed is True
    assert frame.quality.faithfulness_score.value == 0.94
    assert frame.quality.numerical_claims_verified.value == 1

    # Provenance
    assert len(frame.provenance.citations) == 1
    assert frame.provenance.citations[0].document == "Annual_Report_2024.pdf"
    assert frame.provenance.citations[0].primary_page == 12

    # Serialization test
    frame_dict = frame.to_dict()
    assert isinstance(frame_dict, dict)
    assert frame_dict["turn_id"] == "RAISE-T0001"
    assert "retrieval" in frame_dict
    assert "quality" in frame_dict


def test_telemetry_renderer_execution():
    # Ensure rendering runs without any exceptions across all modes
    mock_result = {
        "grounded_answer": "Test answer [1].",
        "citations": [
            {
                "citation_index": 1,
                "pdf_filename": "Report.pdf",
                "primary_page": 5,
                "heading": "Summary",
                "chunk_id": "c1",
                "similarity": 0.85,
            }
        ],
        "telemetry": {
            "intent": "TEST",
            "stages": {"routing_ms": 5.0, "synthesis_ms": 20.0},
        },
    }

    frame = TelemetryService.build_frame(
        result=mock_result,
        query="test query",
        turn_id="T1",
        session_id="S1",
    )

    # Must execute cleanly across all modes
    TelemetryRenderer.render(frame, mode=ObsMode.NORMAL)
    TelemetryRenderer.render(frame, mode=ObsMode.VERBOSE)
    TelemetryRenderer.render(frame, mode=ObsMode.TRACE)
    TelemetryRenderer.render(frame, mode=ObsMode.DEBUG)
