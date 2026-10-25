"""
RAISE Telemetry Invariants & Multi-Layer System Verification Suite
==================================================================
Covers:
Layer 1: Unit tests for invalid states & strict MetricValue normalization
Layer 2: Telemetry invariants (zero-evidence rejection, 0/0 coverage, latency reconciliation)
Layer 3: Adversarial intent routing (campus inquiry vs conversational greeting)
Layer 4: Golden answer & numerical arithmetic verification ($218 + 175 = 393$)
Layer 5: Explicit failure classification & deterministic replay metadata
"""

import pytest
from src.cli.models import (
    MetricState,
    MetricValue,
    FailureClassification,
    NumericalAuditItem,
    TelemetryFrame,
)
from src.cli.telemetry_service import TelemetryService
from main import extract_conversational_persona


# =====================================================================
# Layer 1: Unit Tests & Invalid State Normalization
# =====================================================================

def test_metric_value_strict_normalization():
    """Verify that MetricValue never permits illegal states or silent numeric fallbacks."""
    # 1. Non-value states must NEVER hold a numeric value even if passed explicitly
    unavail = MetricValue(value=42, state=MetricState.UNAVAILABLE)
    assert unavail.value is None
    assert unavail.state == MetricState.UNAVAILABLE
    assert unavail.is_available is False

    not_app = MetricValue(value=100.0, state=MetricState.NOT_APPLICABLE)
    assert not_app.value is None
    assert not_app.state == MetricState.NOT_APPLICABLE
    assert not_app.is_available is False

    not_run = MetricValue(value=999, state=MetricState.NOT_RUN)
    assert not_run.value is None
    assert not_run.state == MetricState.NOT_RUN

    failed = MetricValue(value=123, state=MetricState.FAILED)
    assert failed.value is None
    assert failed.state == MetricState.FAILED

    # 2. Value states passed with None must automatically normalize to UNAVAILABLE
    meas_none = MetricValue.measured(None)
    assert meas_none.value is None
    assert meas_none.state == MetricState.UNAVAILABLE
    assert meas_none.is_available is False

    der_none = MetricValue.derived(None)
    assert der_none.value is None
    assert der_none.state == MetricState.UNAVAILABLE

    est_none = MetricValue.estimated(None)
    assert est_none.value is None
    assert est_none.state == MetricState.UNAVAILABLE

    # 3. Valid measured values remain intact
    valid_meas = MetricValue.measured(393, unit="acres")
    assert valid_meas.value == 393
    assert valid_meas.state == MetricState.MEASURED
    assert valid_meas.is_available is True
    assert "393 acres" in valid_meas.display()


# =====================================================================
# Layer 2: Telemetry Invariant Tests
# =====================================================================

def test_zero_evidence_cannot_pass_quality_gate():
    """Enforce that zero evidence chunks on a document query can NEVER be released as passed."""
    mock_zero_evidence_result = {
        "grounded_answer": "IIT (ISM) Dhanbad is an institute of national importance.",
        "query_intent": "RESEARCH_FACTUAL",
        "routing_strategy": "HYBRID_VECTOR",
        "citations": [],  # Zero citations!
        "telemetry": {
            "intent": "RESEARCH_FACTUAL",
            "quality_gate_decision": "accept",  # Mock claiming it accepted
        },
    }

    frame = TelemetryService.build_frame(
        result=mock_zero_evidence_result,
        query="Where is IIT (ISM) Dhanbad located, and how large is its campus?",
        turn_id="TURN-ZERO-EVID",
        session_id="DEV-SESS",
        scope="AR_2024-25.pdf",
        mode="TRACE",
    )

    # Invariants:
    # 1. Gate MUST NOT be passed
    assert frame.quality.is_gate_passed is False
    # 2. Decision MUST be refusal
    assert "refusal" in frame.quality.decision or "zero_evidence" in frame.quality.decision
    # 3. Source coverage must be NOT_APPLICABLE (not fake 0/0 PASS!)
    assert frame.quality.source_coverage_actual.state == MetricState.NOT_APPLICABLE
    # 4. Debug summary must flag retrieval miss refusal with BLOCKED status
    assert frame.debug_summary.status == "BLOCKED"
    assert frame.debug_summary.failure_class in (
        FailureClassification.ERR_RETRIEVAL_MISS,
        FailureClassification.ZERO_EVIDENCE_REFUSAL,
    )


def test_latency_timing_reconciliation_invariant():
    """Verify that total latency equals sum of sub-stages plus unattributed overhead."""
    mock_timing_result = {
        "grounded_answer": "Answer [1].",
        "citations": [{"citation_index": 1, "similarity": 0.9}],
        "telemetry": {
            "total_latency_ms": 1000.0,
            "stages": {
                "routing_ms": 10.0,
                "vector_retrieval_ms": 120.0,
                "bm25_retrieval_ms": 30.0,
                "graph_retrieval_ms": 0.0,
                "reranking_ms": 50.0,
                "synthesis_ms": 600.0,
                "quality_gate_ms": 40.0,
            }
        }
    }

    frame = TelemetryService.build_frame(
        result=mock_timing_result,
        query="Test latency reconciliation",
        turn_id="TURN-TIMING",
        session_id="DEV-SESS",
    )

    perf = frame.performance
    measured_sum = (
        perf.routing_ms
        + perf.retrieval_ms
        + perf.synthesis_ms
        + perf.quality_gate_ms
    )
    # Total must perfectly reconcile: total = measured_sum + unattributed
    assert abs(perf.total_latency_ms - (measured_sum + perf.unattributed_latency_ms)) < 1e-3
    assert perf.unattributed_latency_ms == pytest.approx(150.0, abs=1e-2)
    assert perf.instrumentation_coverage_pct == pytest.approx(85.0, abs=1e-1)


def test_no_fake_graph_verification_on_zero_nodes():
    """Ensure that when Neo4j visits 0 nodes, graph metrics report NOT_APPLICABLE rather than fake 0 verified."""
    mock_no_graph_result = {
        "grounded_answer": "Answer [1].",
        "citations": [{"citation_index": 1, "similarity": 0.88}],
        "telemetry": {
            "graph_nodes_count": 0,
            "stages": {"routing_ms": 5.0, "synthesis_ms": 50.0},
        }
    }

    frame = TelemetryService.build_frame(
        result=mock_no_graph_result,
        query="Single hop query",
        turn_id="TURN-GRAPH",
        session_id="DEV-SESS",
    )

    assert frame.retrieval.graph.nodes_visited.state == MetricState.NOT_APPLICABLE
    assert frame.retrieval.graph.edges_traversed.state == MetricState.NOT_APPLICABLE
    assert frame.retrieval.graph.cypher_query.state == MetricState.NOT_APPLICABLE


# =====================================================================
# Layer 3: Adversarial Intent Routing Tests
# =====================================================================

@pytest.mark.parametrize("adversarial_research_query", [
    "Where is IIT (ISM) Dhanbad located, and how large is its campus?",
    "Where is the campus located?",
    "How large is the campus?",
    "What departments are on campus?",
    "When was the campus established?",
    "Which campus has more students?",
    "What is the campus area?",
    "Tell me about the campus.",
])
def test_adversarial_campus_queries_never_route_to_greeting(adversarial_research_query: str):
    """
    Ensure the 'Campus' bug can never re-occur:
    Queries containing 'campus' and informational phrasing must NEVER be classified as persona introductions or greetings.
    """
    intent = extract_conversational_persona(adversarial_research_query)
    assert intent["type"] == "research_query", f"Failed for query: {adversarial_research_query}"


@pytest.mark.parametrize("pure_conversational_query", [
    "Hello",
    "Hi",
    "Who are you?",
    "What can you do?",
    "My name is Alice",
    "Call me Siddharth",
])
def test_pure_conversational_queries_route_correctly(pure_conversational_query: str):
    """Ensure genuine greetings and persona name intros continue to route cleanly to conversational mode."""
    intent = extract_conversational_persona(pure_conversational_query)
    assert intent["type"] in ("greeting", "name_intro", "bot_identity", "name_recall")


# =====================================================================
# Layer 4: Numerical Consistency & Arithmetic Audit
# =====================================================================

def test_numerical_consistency_arithmetic_verification():
    """Verify that arithmetic equations in the campus answer (218 + 175 = 393) are verified automatically."""
    answer_text = (
        "IIT (ISM) Dhanbad is spread over an area of 393 acres, "
        "consisting of 218 acres of existing campus and 175 acres under acquisition/development [1]."
    )
    mock_result = {
        "grounded_answer": answer_text,
        "citations": [
            {
                "citation_index": 1,
                "text": "Campus area is 393 acres, consisting of 218 acres existing and 175 acres under acquisition.",
                "primary_page": 11,
                "similarity": 0.88,
            }
        ],
        "telemetry": {
            "intent": "RESEARCH_FACTUAL",
            "quality_gate_decision": "accept",
        },
    }

    frame = TelemetryService.build_frame(
        result=mock_result,
        query="How is the 393-acre campus divided?",
        turn_id="TURN-ARITHMETIC",
        session_id="DEV-SESS",
    )

    num_audit = frame.quality.numerical_audit
    assert num_audit is not None
    assert num_audit.arithmetic_status == "PASS"
    assert num_audit.numeric_consistency == "PASS"
    # Check that the specific 218 + 175 = 393 relation was recognized
    assert any("218" in r and "175" in r and "393" in r for r in num_audit.relationships)


# =====================================================================
# Layer 5: Failure Classification & Deterministic Replay
# =====================================================================

def test_unsupported_claims_trigger_failure_classification():
    """Verify that answers containing uncited sentences are classified with WARNING or CITATION_FAILURE."""
    answer_with_uncited = (
        "IIT (ISM) Dhanbad is located in Dhanbad [1]. "
        "It was declared the greatest institute in the galaxy by unknown sources."  # Missing citation!
    )
    mock_result = {
        "grounded_answer": answer_with_uncited,
        "citations": [{"citation_index": 1, "similarity": 0.85, "primary_page": 11}],
        "telemetry": {"intent": "RESEARCH_FACTUAL", "quality_gate_decision": "accept"},
    }

    frame = TelemetryService.build_frame(
        result=mock_result,
        query="Tell me about IIT Dhanbad",
        turn_id="TURN-UNCITED",
        session_id="DEV-SESS",
    )

    # Invariants:
    assert len(frame.quality.unsupported_claims) == 1
    assert "greatest institute" in frame.quality.unsupported_claims[0]
    assert frame.debug_summary.status == "WARNING"
    assert frame.debug_summary.failure_class == FailureClassification.CITATION_FAILURE
    assert frame.debug_summary.fix_priority == "P2"

    # Deterministic replay fields must all exist
    frame_dict = frame.to_dict()
    assert frame_dict["debug_summary"]["request_id"] == "TURN-UNCITED"
    assert frame_dict["debug_summary"]["pipeline_version"] in ["v3.1-Forensic", "1.0.0"]
    assert frame_dict["debug_summary"]["failure_class"] == "CITATION_FAILURE"
