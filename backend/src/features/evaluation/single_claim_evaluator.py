"""
RAISE Single Claim Evaluator (4-Tier Verification Hierarchy)
============================================================
Purpose:
  Evaluates an individual atomic factual claim against retrieved evidence,
  bound citation chunk, and neural NLI models across 4 verification tiers:
    - Tier 1: Deterministic numerical, currency, temporal & formula verification.
    - Tier 2: Direct lexical quote & ngram overlap fast-path.
    - Tier 3: Neural FineCat-NLI cross-encoder semantic entailment / contradiction.
    - Tier 4: Soft containment & semantic fallback.

Author: RAISE Core Architecture Team
Maintainability: Keep under 260 lines with verifiable decision provenance.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import ClaimVerificationResult
from .numerical_verifier import NumericalClaimVerifier
from src.features.evaluation.nli_verifier import nli_verifier


def verify_single_claim(
    cid: str,
    c_text: str,
    evidence_text: str,
    evidence_lower: str,
    citations_list: Optional[List[Dict[str, Any]]],
    nli_engine: Optional[Any],
    enable_nli: bool,
    query: str,
    stop_words: Set[str],
) -> Tuple[ClaimVerificationResult, bool, bool, bool]:
    """
    Evaluates a single factual claim across the 4-tier hierarchy.

    Returns:
        (result, is_supported, is_num_mismatch, is_cit_error)
    """
    notes = []

    # Extract citations in this specific claim
    cit_refs = [int(m) for m in re.findall(r"\[(\d+)\]", c_text)]
    clean_claim = re.sub(r"\[\[?\s*\d+(?:\s*[,-–]\s*\d+)*\s*\]?\]", "", c_text).strip()

    # Resolve bound evidence chunk and page
    bound_chunk_id = None
    primary_page = None
    bound_chunk_text = ""
    retrieval_relevance = None

    if citations_list and cit_refs:
        ref_idx = cit_refs[0]
        if 1 <= ref_idx <= len(citations_list):
            c_info = citations_list[ref_idx - 1]
            bound_chunk_id = c_info.get("chunk_id") or c_info.get("id")
            primary_page = int(c_info.get("primary_page", 1)) if c_info.get("primary_page") is not None else None
            bound_chunk_text = str(c_info.get("plain_text") or c_info.get("text") or "")
            retrieval_relevance = c_info.get("cross_encoder_score") or c_info.get("score") or c_info.get("rrf_score")

    premise_text = bound_chunk_text if bound_chunk_text else evidence_text

    # Check for negative assertion / refusal grounded in absence from evidence
    is_negative_assertion = bool(re.search(
        r"(?:do(?:es)?\s+not\s+(?:contain|mention|state|provide|include|discuss|have|list|detail|report)|"
        r"no\s+(?:mention|information|data|details|record|reference|evidence|indication)\s+(?:of|about|regarding|found|exists?)|"
        r"there\s+(?:is|are|was|were)\s+no\b|"
        r"\bno\s+[\w\s\-]+(?:\s+are|\s+is)?\s+mentioned\s+in|"
        r"not\s+(?:found|mentioned|provided|available|present|contained|stated|detailed|reported)\s+in|"
        r"cannot\s+be\s+found\s+in|"
        r"outside\s+(?:the|this)\s+scope|"
        r"neither\s+of\s+the\s+documents\s+contain|"
        r"none\s+of\s+the\s+(?:provided\s+)?documents|"
        r"not\s+contain\s+any\s+information|"
        r"not\s+detail\s+specific|"
        r"is\s+not\s+mentioned)",
        c_text,
        re.IGNORECASE,
    ))

    # Tier 1: Deterministic checks (Numbers & Dates)
    num_valid, matched_nums, unmatched_nums = NumericalClaimVerifier.verify_numbers(c_text, evidence_text, query=query)
    if not num_valid and not is_negative_assertion:
        reason = f"Numerical mismatch: Values {unmatched_nums} not found in evidence."
        notes.append(reason)
        res = ClaimVerificationResult(
            claim_id=cid,
            text=c_text,
            is_supported=False,
            status="NUMERICAL_MISMATCH",
            extracted_numbers=unmatched_nums,
            matched_numbers=matched_nums,
            citations_found=cit_refs,
            notes=notes,
            verification_tier="TIER1_NUMERIC",
            bound_chunk_id=bound_chunk_id,
            primary_page=primary_page,
            retrieval_relevance_score=retrieval_relevance,
            verification_path="DETERMINISTIC",
            decision_reason=reason,
        )
        return res, False, True, False

    # Negative assertion handling
    if is_negative_assertion:
        reason = "Supported negative assertion / refusal grounded in absence from evidence."
        notes.append(reason)
        res = ClaimVerificationResult(
            claim_id=cid,
            text=c_text,
            is_supported=True,
            status="SUPPORTED",
            extracted_numbers=matched_nums,
            matched_numbers=matched_nums,
            citations_found=cit_refs,
            notes=notes,
            verification_tier="TIER1_NUMERIC",
            bound_chunk_id=bound_chunk_id,
            primary_page=primary_page,
            retrieval_relevance_score=retrieval_relevance,
            verification_path="DETERMINISTIC",
            decision_reason=reason,
        )
        return res, True, False, False

    c_words = set(re.findall(r"\b[a-zA-Z0-9_]{3,}\b", clean_claim.lower())) - stop_words
    if not c_words:
        reason = "No substantive non-stopword tokens to invalidate."
        res = ClaimVerificationResult(
            claim_id=cid,
            text=c_text,
            is_supported=True,
            status="SUPPORTED",
            extracted_numbers=matched_nums,
            matched_numbers=matched_nums,
            citations_found=cit_refs,
            notes=[reason],
            verification_tier="TIER1_NUMERIC",
            bound_chunk_id=bound_chunk_id,
            primary_page=primary_page,
            retrieval_relevance_score=retrieval_relevance,
            verification_path="DETERMINISTIC",
            decision_reason=reason,
        )
        return res, True, False, False

    # Lexical overlap with bound premise and full retrieved evidence
    full_match = sum(1 for w in c_words if w in evidence_lower or (len(w) > 4 and w[:4] in evidence_lower))
    overlap_ratio = full_match / len(c_words)

    c_tokens = re.findall(r"\b[a-zA-Z0-9_]{3,}\b", clean_claim.lower())
    ngram_hits = 0
    total_ngrams = max(1, len(c_tokens) - 1)
    if len(c_tokens) >= 2:
        for i in range(len(c_tokens) - 1):
            bigram = f"{c_tokens[i]} {c_tokens[i+1]}"
            if bigram in evidence_lower:
                ngram_hits += 1
    ngram_ratio = ngram_hits / total_ngrams
    grounding_score = (overlap_ratio * 0.6) + (ngram_ratio * 0.4)

    # Tabular / Numeric Fast-Path: If numbers are verified and non-numeric labels match evidence, accept
    non_num_words = {w for w in c_words if not any(c.isdigit() for c in w)}
    non_num_match = sum(1 for w in non_num_words if w in evidence_lower or (len(w) > 4 and w[:4] in evidence_lower))
    non_num_ratio = (non_num_match / len(non_num_words)) if non_num_words else 1.0

    is_math_equation = bool(re.search(r"[-+–/*]\s*.*=", clean_claim) or re.search(r"=\s*.*[-+–/*]", clean_claim))
    if num_valid and len(matched_nums) > 0 and (non_num_ratio >= 0.80 or is_math_equation):
        reason = f"Verified tabular / numeric {'equation' if is_math_equation else 'claim'} ({non_num_ratio*100:.1f}% label grounding, {len(matched_nums)} numbers verified)."
        notes.append(reason)
        res = ClaimVerificationResult(
            claim_id=cid,
            text=c_text,
            is_supported=True,
            status="SUPPORTED",
            extracted_numbers=matched_nums,
            matched_numbers=matched_nums,
            citations_found=cit_refs,
            notes=notes,
            verification_tier="TIER1_NUMERIC",
            bound_chunk_id=bound_chunk_id,
            primary_page=primary_page,
            retrieval_relevance_score=retrieval_relevance,
            verification_path="DETERMINISTIC",
            decision_reason=reason,
        )
        return res, True, False, False

    # Tier 2: Lexical Fast-Path (Exact quote / high overlap >= 0.70)
    if grounding_score >= 0.70 or overlap_ratio >= 0.80:
        reason = f"Direct lexical quote match ({grounding_score*100:.1f}% grounding: {overlap_ratio*100:.1f}% tokens, {ngram_ratio*100:.1f}% ngrams)."
        notes.append(reason)
        res = ClaimVerificationResult(
            claim_id=cid,
            text=c_text,
            is_supported=True,
            status="DIRECT",
            extracted_numbers=matched_nums,
            matched_numbers=matched_nums,
            citations_found=cit_refs,
            notes=notes,
            verification_tier="TIER2_LEXICAL",
            bound_chunk_id=bound_chunk_id,
            primary_page=primary_page,
            retrieval_relevance_score=retrieval_relevance,
            verification_path="DETERMINISTIC",
            decision_reason=reason,
        )
        return res, True, False, False

    # Tier 3: FineCat-NLI Escalation (Ambiguous or Paraphrased Claims)
    active_nli = nli_engine or nli_verifier
    if enable_nli and active_nli is not None:
        nli_eval = active_nli.classify_pair(
            premise=premise_text[:2048] if len(premise_text) > 2048 else premise_text,
            hypothesis=clean_claim,
        )
        ent_prob = nli_eval.get("entailment_prob", 0.0)
        con_prob = nli_eval.get("contradiction_prob", 0.0)
        neu_prob = nli_eval.get("neutral_prob", 0.0)
        is_entailed = nli_eval.get("is_entailed", False)
        is_contradiction = nli_eval.get("is_contradiction", False)
        raw_logits = nli_eval.get("raw_logits")
        softmax_probs = nli_eval.get("softmax_probs")
        calibration_status = nli_eval.get("calibration_status", "UNVALIDATED_RAW_SOFTMAX")
        nli_reason = nli_eval.get("decision_reason", "")
        nli_latency = nli_eval.get("latency_ms", 0.0)
    else:
        ent_prob = 0.0
        con_prob = 0.0
        neu_prob = 0.0
        is_entailed = False
        is_contradiction = False
        raw_logits = None
        softmax_probs = None
        calibration_status = "UNVALIDATED_RAW_SOFTMAX"
        nli_reason = ""
        nli_latency = 0.0

    if is_contradiction or con_prob >= 0.50:
        reason = nli_reason or f"Hard contradiction detected by FineCat-NLI (P(contradiction)={con_prob:.2f} >= 0.50)."
        notes.append(reason)
        res = ClaimVerificationResult(
            claim_id=cid,
            text=c_text,
            is_supported=False,
            status="CONTRADICTION",
            extracted_numbers=unmatched_nums,
            matched_numbers=matched_nums,
            citations_found=cit_refs,
            notes=notes,
            nli_entailment_prob=ent_prob,
            nli_contradiction_prob=con_prob,
            verification_tier="TIER3_NLI",
            bound_chunk_id=bound_chunk_id,
            primary_page=primary_page,
            retrieval_relevance_score=retrieval_relevance,
            verification_path="NLI",
            decision_reason=reason,
            raw_logits=raw_logits,
            softmax_probs=softmax_probs,
            calibration_status=calibration_status,
            latency_ms=nli_latency,
        )
        return res, False, False, False
    elif is_entailed or ent_prob >= 0.55:
        reason = nli_reason or f"Semantically entailed by FineCat-NLI (P(entailment)={ent_prob:.2f} >= 0.55)."
        notes.append(reason)
        res = ClaimVerificationResult(
            claim_id=cid,
            text=c_text,
            is_supported=True,
            status="NLI_ENTAILED",
            extracted_numbers=matched_nums,
            matched_numbers=matched_nums,
            citations_found=cit_refs,
            notes=notes,
            nli_entailment_prob=ent_prob,
            nli_contradiction_prob=con_prob,
            verification_tier="TIER3_NLI",
            bound_chunk_id=bound_chunk_id,
            primary_page=primary_page,
            retrieval_relevance_score=retrieval_relevance,
            verification_path="NLI",
            decision_reason=reason,
            raw_logits=raw_logits,
            softmax_probs=softmax_probs,
            calibration_status=calibration_status,
            latency_ms=nli_latency,
        )
        return res, True, False, False
    elif (
        grounding_score >= 0.30
        or overlap_ratio >= 0.40
        or (matched_nums and not unmatched_nums and overlap_ratio >= 0.15)
        or (con_prob < 0.25 and overlap_ratio >= 0.30)
    ):
        reason = f"Supported via soft containment fallback ({grounding_score*100:.1f}% score)."
        notes.append(reason)
        res = ClaimVerificationResult(
            claim_id=cid,
            text=c_text,
            is_supported=True,
            status="SUPPORTED",
            extracted_numbers=matched_nums,
            matched_numbers=matched_nums,
            citations_found=cit_refs,
            notes=notes,
            nli_entailment_prob=ent_prob,
            nli_contradiction_prob=con_prob,
            verification_tier="TIER4_FALLBACK",
            bound_chunk_id=bound_chunk_id,
            primary_page=primary_page,
            retrieval_relevance_score=retrieval_relevance,
            verification_path="DETERMINISTIC+NLI",
            decision_reason=reason,
            raw_logits=raw_logits,
            softmax_probs=softmax_probs,
            calibration_status=calibration_status,
            latency_ms=nli_latency,
        )
        return res, True, False, False
    else:
        reason = nli_reason or f"Insufficient evidence grounding: NLI neutral/uncertain (P(E)={ent_prob:.2f}, P(N)={neu_prob:.2f}), lexical {grounding_score*100:.1f}%."
        notes.append(reason)
        res = ClaimVerificationResult(
            claim_id=cid,
            text=c_text,
            is_supported=False,
            status="UNSUPPORTED",
            extracted_numbers=unmatched_nums,
            matched_numbers=matched_nums,
            citations_found=cit_refs,
            notes=notes,
            nli_entailment_prob=ent_prob,
            nli_contradiction_prob=con_prob,
            verification_tier="TIER3_NLI",
            bound_chunk_id=bound_chunk_id,
            primary_page=primary_page,
            retrieval_relevance_score=retrieval_relevance,
            verification_path="NLI",
            decision_reason=reason,
            raw_logits=raw_logits,
            softmax_probs=softmax_probs,
            calibration_status=calibration_status,
            latency_ms=nli_latency,
        )
        return res, False, False, False
