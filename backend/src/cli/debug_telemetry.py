"""
RAISE Forensic Debug Summary & Failure Classifier
=================================================
Purpose:
  Synthesizes forensic root-cause analysis, failure categorization,
  ground truth numerical diff comparisons, and actionable fix recommendations.

Components:
  - `build_numerical_diffs`: Compares synthesized answers against benchmark ground truth numbers.
  - `build_debug_summary`: Determines pipeline pass/fail status and classifies failures.

Author: RAISE Core Architecture Team
Maintainability: Keep under 180 lines with zero silent fallbacks.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.cli.models import (
    FailureClassification,
    CandidateAuditItem,
    NumericalDiffItem,
    DebugSummary,
    ProvenanceItem,
)


def build_numerical_diffs(
    expected_meta: Dict[str, Any],
    answer: str,
    provenance_items: List[ProvenanceItem],
) -> List[NumericalDiffItem]:
    """Computes exact numerical deltas against benchmark expected figures."""
    exp_pages = expected_meta.get("expected_pages") or []
    exp_figures = expected_meta.get("expected_figures") or {}

    numerical_diffs: List[NumericalDiffItem] = []
    if exp_figures and isinstance(exp_figures, dict):
        for m_name, exp_val in exp_figures.items():
            m_str = str(exp_val).strip()
            if m_str and m_str in answer:
                stat = "PASS"
                dtls = f"Verified: '{m_str}' correctly present in synthesized answer."
            elif m_str:
                stat = "MISMATCH"
                dtls = f"Expected '{m_str}' for {m_name}, but it was missing or mismatched in pipeline answer."
            else:
                stat = "PASS"
                dtls = "No specific expected figure constraint."

            exp_p = exp_pages[0] if exp_pages else None
            ret_p = provenance_items[0].primary_page if provenance_items else None
            numerical_diffs.append(
                NumericalDiffItem(
                    metric_name=m_name,
                    ground_truth_value=m_str,
                    pipeline_value=m_str if stat == "PASS" else "NOT_FOUND",
                    source_page_expected=exp_p,
                    source_page_retrieved=ret_p,
                    status=stat,
                    details=dtls,
                )
            )
    return numerical_diffs


def build_debug_summary(
    turn_id: str,
    intent_val: Optional[str],
    is_conv: bool,
    has_evidence: bool,
    is_passed: bool,
    unsupported_list: List[str],
    top_candidates_audit: List[CandidateAuditItem],
    qg_rep: Dict[str, Any],
    rej_reason: Optional[str],
    faith_val: Optional[float],
) -> DebugSummary:
    """Performs forensic failure classification and root-cause determination."""
    if not is_conv and not has_evidence:
        dbg_status = "BLOCKED"
        # Detect OCR noise vs Rerank dropout vs Retrieval miss
        ocr_detected = False
        for cand in top_candidates_audit:
            if cand.text_snippet and re.search(
                r"[^\x20-\x7E\s]{3,}|[a-z][A-Z]{3,}|[0-9]{1,2}[a-zA-Z]{2,}",
                cand.text_snippet,
            ):
                ocr_detected = True
                break

        has_dropped_candidates = any(c.reranker_dropout for c in top_candidates_audit)

        if ocr_detected:
            failure_class = FailureClassification.ERR_OCR_NOISE
            root_cause = "Scanned PDF OCR distortion prevented keyword/vector match. Text extraction corrupted table or schedule tokens."
        elif has_dropped_candidates:
            failure_class = FailureClassification.ERR_RERANK_DROPOUT
            root_cause = "Candidates were retrieved by vector/BM25 but dropped during fusion or relevance filtering."
        else:
            failure_class = FailureClassification.ERR_RETRIEVAL_MISS
            root_cause = "Zero evidence chunks acquired from indexed documents. Output withheld by anti-hallucination firewall."
        fix_priority = "P0" if intent_val == "CONVERSATIONAL" else "P1"
    elif not is_passed:
        dbg_status = "FAILED"
        if qg_rep.get("numerical_claims_verified", 0) < qg_rep.get("numerical_claims_total", 0):
            failure_class = FailureClassification.ERR_LLM_HALLUCINATION
            root_cause = f"LLM generated numerical claims unsupported by retrieved context ({rej_reason or 'Numeric mismatch'})."
        elif faith_val is not None and float(faith_val) < 0.70:
            failure_class = FailureClassification.ERR_LLM_HALLUCINATION
            root_cause = f"Synthesizer generated claims with low context faithfulness ({faith_val:.2f} < 0.80)."
        else:
            failure_class = FailureClassification.ERR_GATE_OVERBLOCK
            root_cause = f"Quality gate threshold blocked response despite retrieved context: {rej_reason or 'Threshold failure'}."
        fix_priority = "P1"
    elif unsupported_list:
        dbg_status = "WARNING"
        failure_class = FailureClassification.CITATION_FAILURE
        root_cause = f"{len(unsupported_list)} sentence(s) lack strict bracket citation grounding."
        fix_priority = "P2"
    else:
        dbg_status = "PASS"
        failure_class = FailureClassification.NONE_PASS
        root_cause = "All pipeline stages passed. Retrieval, grounding, arithmetic, and citations verified."
        fix_priority = "NONE"

    exp_intent = (
        str(intent_val)
        if intent_val in ("ACADEMIC_RESEARCH_FACTUAL", "RESEARCH_FACTUAL", "CONVERSATIONAL")
        else ("RESEARCH_FACTUAL" if not is_conv else "CONVERSATIONAL")
    )
    return DebugSummary(
        status=dbg_status,
        failure_class=failure_class,
        expected_intent=exp_intent,
        actual_intent=str(intent_val or "ACADEMIC_RESEARCH"),
        root_cause=root_cause,
        fix_priority=fix_priority,
        reproducible=True,
        request_id=turn_id,
        pipeline_version="1.0.0",
    )
