"""
Tests TelemetryRenderer: ANSI color formatting, 8 layers, box cards, and ASCII tree.
"""

import pytest
from src.cli.models import (
    FailureClassification,
    HopEvidenceItem,
)
from src.cli.telemetry_service import TelemetryService
from src.cli.renderer import TelemetryRenderer, ObsMode, C


@pytest.mark.unit
@pytest.mark.cli
def test_telemetry_renderer_trace_mode_renders_all_layers(capsys):
    """Verifies that render() in TRACE mode outputs 8 layers and forensic cards."""
    raw_result = {
        "grounded_answer": "Peak compute capacity reached 15.4 Petaflops [1].",
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
        "timings": {
            "routing_ms": 12.0,
            "vector_retrieval_ms": 35.0,
            "synthesis_ms": 200.0,
            "quality_gate_ms": 25.0,
            "total_latency_ms": 272.0,
        },
    }

    frame = TelemetryService.build_frame(
        result=raw_result,
        query="What is the compute capacity?",
        turn_id="RAISE-T0001",
        session_id="DEV-RENDER-01",
        scope="IITMRP Annual Report.pdf",
        mode="TRACE",
    )

    TelemetryRenderer.render(frame, ObsMode.TRACE)
    captured = capsys.readouterr().out

    # Verify key layers are rendered
    assert "01 — REQUEST" in captured
    assert "02 — INTENT & ROUTING" in captured
    assert "03 — RETRIEVAL" in captured
    assert "04 — EVIDENCE GRAPH" in captured
    assert "05 — CONTEXT ASSEMBLY" in captured
    assert "06 — QUALITY GATE" in captured
    assert "07 — PROVENANCE CHAIN" in captured
    assert "08 — PIPELINE PERFORMANCE" in captured
    assert "RAISE FORENSIC DEBUG & AUDIT SUMMARY" in captured


@pytest.mark.unit
@pytest.mark.cli
def test_telemetry_renderer_reasoning_chain_card(capsys):
    """Verifies that reasoning chain and completeness gate cards render when hops are present."""
    raw_result = {
        "grounded_answer": "Answer [1].",
        "citations": [{"citation_index": 1, "document": "Doc.pdf", "primary_page": 1, "text": "evidence"}],
        "timings": {"total_latency_ms": 50.0},
    }
    frame = TelemetryService.build_frame(
        result=raw_result,
        query="Multi-hop query",
        turn_id="RAISE-T0002",
        session_id="DEV-RENDER-02",
    )
    frame.hop_evidence_chain = [
        HopEvidenceItem(
            hop_id=1,
            source_entity="Director",
            relation="DIRECTED",
            target_entity="Research Center",
            status="VERIFIED",
            confidence=0.95,
        )
    ]
    frame.chain_completeness_gate = {
        "status": "PASSED",
        "required_hops": 2,
        "completed_hops": 2,
        "discovered_bridge_entity": "Dr. S. Raman",
    }

    TelemetryRenderer.render(frame, ObsMode.TRACE)
    captured = capsys.readouterr().out

    assert "REASONING CHAIN & COMPLETENESS GATE" in captured
    assert "EVIDENCE BRIDGE" in captured
    assert "Dr. S. Raman" in captured
    assert "Director ──(DIRECTED)──► Research Center" in captured


@pytest.mark.unit
@pytest.mark.cli
def test_telemetry_renderer_normal_mode_is_quiet(capsys):
    """Verifies that NORMAL mode does not render the deep 8-layer console."""
    frame = TelemetryService.build_frame(
        result={"grounded_answer": "Simple text"},
        query="Simple query",
        turn_id="RAISE-T0003",
        session_id="DEV-QUIET",
    )
    TelemetryRenderer.render(frame, ObsMode.NORMAL)
    captured = capsys.readouterr().out
    assert captured == ""
