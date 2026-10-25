"""
FineCat-NLI & Escalation Gating Verification Suite
===================================================
Tests:
1. FineCatNLIVerifier singleton initialization & classification
2. Direct lexical match fast-path (Tier 2)
3. Deterministic numeric verification (Tier 1)
4. Neutral / Contradiction handling (Tier 3)
5. Telemetry service alignment (Zero contradiction between claim audit & gate)
"""

import pytest
from src.features.evaluation.nli_verifier import FineCatNLIVerifier, nli_verifier
from src.features.evaluation.engine import (
    StructuredEvidence,
    ClaimLevelVerifier,
    LocalHeuristicEvaluator,
    NumericalClaimVerifier,
)
from src.cli.telemetry_service import TelemetryService


def test_finecat_nli_entailment_and_contradiction():
    """Verify FineCatNLIVerifier classification on known semantic pairs."""
    verifier = FineCatNLIVerifier()
    
    # Entailed pair
    p_ent = "The Indian Institute of Technology Madras Research Park occupies 393 acres of total land."
    h_ent = "The campus encompasses an overall area of 393 acres."
    res_ent = verifier.classify_pair(p_ent, h_ent)
    
    assert res_ent["verdict"] in ("ENTAILMENT", "NEUTRAL")
    assert "entailment_prob" in res_ent
    assert "contradiction_prob" in res_ent
    assert res_ent["is_contradiction"] is False

    # Contradictory pair
    p_con = "The annual report indicates that 42 startups were incubated in the fiscal year 2023."
    h_con = "The annual report states that no startups were incubated in 2023."
    res_con = verifier.classify_pair(p_con, h_con)
    
    assert res_con["is_contradiction"] is True or res_con["contradiction_prob"] > res_con["entailment_prob"]


def test_escalation_gating_tiers():
    """Verify that verify_claims assigns appropriate tiers and statuses."""
    evidence = StructuredEvidence(
        vector_chunks=[
            {
                "chunk_id": "chunk_001",
                "plain_text": "IIT Madras Research Park covers 218 acres of original campus plus 175 acres of newly acquired land, totaling 393 acres. Over 150 deep-tech startups have been incubated.",
                "primary_page": 14,
                "score": 0.92,
            }
        ]
    )
    citations_list = [
        {
            "citation_index": 1,
            "chunk_id": "chunk_001",
            "plain_text": evidence.vector_chunks[0]["plain_text"],
            "primary_page": 14,
            "score": 0.92,
        }
    ]

    # Test 1: Verbatim quote -> Tier 2 Lexical Fast-Path
    ans_exact = "IIT Madras Research Park covers 218 acres of original campus plus 175 acres of newly acquired land, totaling 393 acres [1]."
    results, f_score, num_mismatches, _ = ClaimLevelVerifier.verify_claims(
        answer=ans_exact,
        evidence=evidence,
        citations_list=citations_list,
    )
    assert len(results) >= 1
    assert results[0].is_supported is True
    assert results[0].verification_tier in ("TIER2_LEXICAL", "TIER1_NUMERIC")
    assert num_mismatches == 0

    # Test 2: Numerical Hallucination -> Tier 1 Numeric Mismatch
    ans_num_fail = "The research park has a total size of 999 acres [1]."
    res_fail, f_fail, num_mismatches_fail, _ = ClaimLevelVerifier.verify_claims(
        answer=ans_num_fail,
        evidence=evidence,
        citations_list=citations_list,
    )
    assert num_mismatches_fail >= 1
    assert any(r.status == "NUMERICAL_MISMATCH" for r in res_fail)


def test_telemetry_claim_audit_alignment():
    """
    Verify that TelemetryService builds a claims_audit that strictly matches
    the EvaluationReport.to_dict() claims, eliminating the Quality Gate contradiction.
    """
    evidence = StructuredEvidence(
        vector_chunks=[
            {
                "chunk_id": "c_alpha",
                "plain_text": "IIT (ISM) Dhanbad campus covers 393 acres.",
                "primary_page": 5,
            }
        ]
    )
    citations = [
        {
            "citation_index": 1,
            "chunk_id": "c_alpha",
            "primary_page": 5,
            "plain_text": "IIT (ISM) Dhanbad campus covers 393 acres.",
        }
    ]

    # Evaluate answer
    answer = "IIT (ISM) Dhanbad has a campus size of 393 acres [1]. It was founded by ancient astronauts in 1200 BC [1]."
    report = LocalHeuristicEvaluator.evaluate(
        query="Tell me about IIT Dhanbad campus.",
        answer=answer,
        retrieved_chunks=evidence.vector_chunks,
        citations_list=citations,
    )
    rep_dict = report.to_dict()

    # Pass into TelemetryService
    mock_result = {
        "grounded_answer": answer,
        "query_intent": "ACADEMIC_RESEARCH_FACTUAL",
        "routing_strategy": "HYBRID_VECTOR",
        "citations": citations,
        "telemetry": {
            "intent": "ACADEMIC_RESEARCH_FACTUAL",
            "quality_gate_report": rep_dict,
            "quality_gate_decision": "accept" if report.is_acceptable else "reject",
        },
    }

    frame = TelemetryService.build_frame(
        result=mock_result,
        query="Tell me about IIT Dhanbad campus.",
        turn_id="TURN-TEST-AUDIT",
        session_id="SESS-AUDIT",
        scope="AR_2024-25.pdf",
        mode="TRACE",
    )

    # Invariant checks:
    # 1. Unsupported claims count in the Quality Gate table must match the audit list
    unsupported_in_audit = [c for c in frame.quality.claims_audit if c.support_status in ("UNSUPPORTED", "CONTRADICTION", "NUMERICAL_MISMATCH")]
    assert frame.quality.unsupported_claims_count.value == len(unsupported_in_audit)
    
    # 2. Gate decision must be consistent with unsupported count
    if len(unsupported_in_audit) > 0:
        assert frame.quality.is_gate_passed is False
    else:
        assert frame.quality.is_gate_passed is True
