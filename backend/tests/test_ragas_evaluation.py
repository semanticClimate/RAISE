import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.features.evaluation.engine import (
    LocalHeuristicEvaluator,
    RuntimeFaithfulnessQualityGate,
    NumericalClaimVerifier,
    CitationValidator,
    StructuredEvidence,
)
from src.retrieval.pipeline import StandaloneRAGPipeline
from src.features.agent.workflow import AcademicGraphRAGWorkflow

def test_evaluation_and_runtime_gate():
    print("=================================================================")
    print("[TEST] RUNNING COMPREHENSIVE RAISE EVALUATION & QUALITY GATE TESTS")
    print("=================================================================\n")

    evidence_context = [
        {"chunk_id": "chk_1", "plain_text": "Dr. Sushanta Kumar Panigrahi secured a research grant of Rs. 45 Lakhs from DST for composite materials.", "document_id": "PU_Report.pdf", "page": 4},
        {"chunk_id": "chk_2", "plain_text": "The Department of Mechanical Engineering reported 37 patents filed during 2024-25.", "document_id": "PU_Report.pdf", "page": 12},
    ]

    # -------------------------------------------------------------------------
    # TEST A: Grounded Answer (Expected: PASS)
    # -------------------------------------------------------------------------
    print("--- [TEST A] Grounded Answer Verification ---")
    grounded_ans = "Dr. Sushanta Kumar Panigrahi secured a research grant of Rs. 45 Lakhs from DST in the Department of Mechanical Engineering [[1]]."
    citations_a = [{"citation_index": 1, "document_id": "PU_Report.pdf", "primary_page": 4}]
    report_a = LocalHeuristicEvaluator.evaluate(
        query="What funding did Dr. Panigrahi receive?",
        answer=grounded_ans,
        retrieved_chunks=evidence_context,
        citations_list=citations_a,
        active_docs=["PU_Report.pdf"],
        threshold=0.80
    )
    print(f"Faithfulness: {report_a.faithfulness:.2f}, Numerical Mismatches: {report_a.numerical_mismatches}, Acceptable: {report_a.is_acceptable}")
    assert report_a.is_acceptable is True
    assert report_a.faithfulness >= 0.80

    # -------------------------------------------------------------------------
    # TEST B: Hallucinated Amount (Source: 45, Answer: 450) (Expected: FAIL)
    # -------------------------------------------------------------------------
    print("\n--- [TEST B] Hallucinated Amount Verification ---")
    hallucinated_num_ans = "Dr. Sushanta Kumar Panigrahi secured a grant of Rs. 450 Lakhs from DST [[1]]."
    report_b = LocalHeuristicEvaluator.evaluate(
        query="What funding did Dr. Panigrahi receive?",
        answer=hallucinated_num_ans,
        retrieved_chunks=evidence_context,
        citations_list=citations_a,
        active_docs=["PU_Report.pdf"],
        threshold=0.80
    )
    print(f"Numerical Mismatches: {report_b.numerical_mismatches}, Acceptable: {report_b.is_acceptable}, Reason: {report_b.rejection_reason}")
    assert report_b.is_acceptable is False
    assert report_b.numerical_mismatches >= 1

    # -------------------------------------------------------------------------
    # TEST C: Hallucinated Organization (Source: DST, Answer: NASA) (Expected: FAIL)
    # -------------------------------------------------------------------------
    print("\n--- [TEST C] Hallucinated Organization Verification ---")
    hallucinated_org_ans = "Dr. Sushanta Kumar Panigrahi was awarded funding by NASA to build satellites on Mars."
    report_c = LocalHeuristicEvaluator.evaluate(
        query="What funding did Dr. Panigrahi receive?",
        answer=hallucinated_org_ans,
        retrieved_chunks=evidence_context,
        threshold=0.80
    )
    print(f"Faithfulness: {report_c.faithfulness:.2f}, Acceptable: {report_c.is_acceptable}, Reason: {report_c.rejection_reason}")
    assert report_c.is_acceptable is False
    assert report_c.faithfulness < 0.80

    # -------------------------------------------------------------------------
    # TEST D: Unsupported Partial Claim (Expected: Partial Rejection)
    # -------------------------------------------------------------------------
    print("\n--- [TEST D] Partial Claim Support ---")
    mixed_ans = (
        "Dr. Sushanta Kumar Panigrahi secured Rs. 45 Lakhs from DST. "
        "Additionally, he won the Nobel Prize in Physics in the same year."
    )
    report_d = LocalHeuristicEvaluator.evaluate(
        query="Tell me about Dr. Panigrahi's achievements.",
        answer=mixed_ans,
        retrieved_chunks=evidence_context,
        threshold=0.80
    )
    print(f"Supported Claims: {report_d.supported_claims_count}/{report_d.total_claims_count}, Faithfulness: {report_d.faithfulness:.2f}")
    assert report_d.supported_claims_count == 1
    assert report_d.total_claims_count == 2
    assert report_d.faithfulness == 0.50

    # -------------------------------------------------------------------------
    # TEST E: Missing / Invalid Citation (Expected: FAIL)
    # -------------------------------------------------------------------------
    print("\n--- [TEST E] Invalid Citation Validation ---")
    invalid_cit_ans = "The institution filed 37 patents during 2024-25 [[99]]."
    report_e = LocalHeuristicEvaluator.evaluate(
        query="How many patents were filed?",
        answer=invalid_cit_ans,
        retrieved_chunks=evidence_context,
        citations_list=citations_a,  # only has index 1, not 99
        active_docs=["PU_Report.pdf"],
        threshold=0.80
    )
    print(f"Citation Errors: {report_e.citation_errors}, Acceptable: {report_e.is_acceptable}, Reason: {report_e.rejection_reason}")
    assert report_e.citation_errors >= 1
    assert report_e.is_acceptable is False

    # -------------------------------------------------------------------------
    # TEST F: Runtime Gate Retry Limit & Safe Refusal
    # -------------------------------------------------------------------------
    print("\n--- [TEST F] Quality Gate Retry Limit & Refusal ---")
    gate = RuntimeFaithfulnessQualityGate(threshold=0.80, max_retries=2)
    
    # Retry 1
    g1 = gate.evaluate_runtime_state(
        query="What is the space budget?",
        answer="We spent 500 Billion on Martian exploration.",
        retrieved_chunks=evidence_context,
        retry_count=0
    )
    print(f"Attempt 1: Decision = '{g1['decision']}', Next Retry Count = {g1['retry_count']}")
    assert g1["decision"] == "retry"
    assert g1["retry_count"] == 1

    # Retry 2
    g2 = gate.evaluate_runtime_state(
        query="What is the space budget?",
        answer="We spent 500 Billion on Martian exploration.",
        retrieved_chunks=evidence_context,
        retry_count=1
    )
    print(f"Attempt 2: Decision = '{g2['decision']}', Next Retry Count = {g2['retry_count']}")
    assert g2["decision"] == "retry"
    assert g2["retry_count"] == 2

    # Attempt 3 -> Max Retries Exceeded -> Safe Refusal
    g3 = gate.evaluate_runtime_state(
        query="What is the space budget?",
        answer="We spent 500 Billion on Martian exploration.",
        retrieved_chunks=evidence_context,
        retry_count=2
    )
    print(f"Attempt 3: Decision = '{g3['decision']}'")
    print(f"Safe Refusal Message: '{g3.get('answer')}'")
    assert g3["decision"] == "unable_to_verify"
    assert "I could not verify this answer against the uploaded academic sources" in g3["answer"]

    # -------------------------------------------------------------------------
    # TEST G: Empty Workspace Bypass
    # -------------------------------------------------------------------------
    print("\n--- [TEST G] Empty Workspace Invariant ---")
    pipe = StandaloneRAGPipeline()
    wf = AcademicGraphRAGWorkflow(pipe)
    res_empty = wf.run(query="What is the total budget?", active_docs=[])
    print(f"Empty Workspace Response: '{res_empty['grounded_answer']}'")
    print(f"Quality Gate Decision: '{res_empty['quality_gate_decision']}'")
    assert res_empty["grounded_answer"] == "Please upload an academic PDF to begin your research."
    assert res_empty["quality_gate_decision"] == "empty_workspace"

    # -------------------------------------------------------------------------
    # TEST H: Real LangGraph Execution with Active Docs
    # -------------------------------------------------------------------------
    print("\n--- [TEST H] Real LangGraph StateGraph Execution ---")
    res_active = wf.run(
        query="What grants were reported?",
        active_docs=["Annual_Report_2024_25_final_upload.pdf"]
    )
    print(f"LangGraph Routing: {res_active.get('routing_strategy')}")
    print(f"Quality Gate Decision: {res_active.get('quality_gate_decision')}")
    print(f"Grounded Answer: {str(res_active.get('grounded_answer'))[:120]}...")
    assert res_active["quality_gate_decision"] in ["accept", "retry", "unable_to_verify"]
    assert len(res_active["grounded_answer"]) > 10

    print("\n" + "=" * 65)
    print("[ALL 8 EVALUATION, NUMERICAL, CITATION & GATE TESTS PASSED]")
    print("=================================================================")

if __name__ == "__main__":
    test_evaluation_and_runtime_gate()
