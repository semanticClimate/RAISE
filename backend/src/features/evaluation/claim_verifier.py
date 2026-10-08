"""
Factual Claim Extraction & 4-Tier Verification Engine
======================================================
Decomposes answers into atomic factual claims and evaluates each claim across a 4-tier
verification hierarchy against structured vector chunks, Neo4j graph triples, and NLI.

Architectural Role & 4-Tier Verification Flow:
----------------------------------------------
1. Sentence Decomposition & Abbreviation Protection:
   - Uses regex sentence splitting while shielding academic abbreviations (`Dr.`, `Prof.`, `Rs.`,
     `e.g.`, `i.e.`, `vs.`, `Fig.`, `No.`).
   - Filters markdown table headers, boilerplate declarations ("Based on excerpts..."), and citation lines.

2. Tier 1: Deterministic Numerical & Temporal Verification:
   - Evaluates all currency, dates, percentages, and metrics via `NumericalClaimVerifier`.
   - Fails immediately with `NUMERICAL_MISMATCH` if an unsupported numerical value is claimed.

3. Tier 2: Direct Lexical Fast-Path:
   - Computes token overlap ratio and bigram ngram grounding.
   - If grounding score >= 0.70 (or token overlap >= 0.80), marks claim as `DIRECT` without invoking neural NLI.

4. Tier 3: Neural NLI Escalation (FineCat-NLI):
   - When a claim is paraphrased or ambiguous, calls the active NLI cross-encoder model.
   - Flagged as `CONTRADICTION` if contradiction probability >= 0.50.
   - Flagged as `NLI_ENTAILED` if entailment probability >= 0.55.

5. Tier 4: Soft Containment Fallback:
   - Accepts partially overlapping claims (grounding >= 0.30 or token overlap >= 0.40) where no contradiction
     was detected, ensuring reasonable recall without hallucinating.

How to Update or Tune:
----------------------
- To adjust the NLI entailment threshold, modify `ent_prob >= 0.55` in `verify_claims()`.
- To tighten or loosen lexical fast-path, modify `grounding_score >= 0.70` or `overlap_ratio >= 0.80`.
- To add new protected abbreviations, add to `abbrevs` list in `extract_claims()`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .models import StructuredEvidence, ClaimVerificationResult
from .single_claim_evaluator import verify_single_claim


class ClaimLevelVerifier:
    """
    Decomposes responses into discrete factual claims and evaluates each claim
    against structured vector passages, Neo4j graph triples, and neural NLI models.
    """

    STOP_WORDS = {
        "what", "is", "the", "and", "or", "for", "with", "from", "that", "this",
        "these", "those", "have", "has", "had", "were", "been", "being", "are",
        "was", "their", "they", "its", "into", "during", "which", "about", "also",
        "based", "verified", "excerpts", "uploaded", "reports", "report", "document"
    }

    @classmethod
    def extract_claims(cls, answer: str) -> List[str]:
        """
        Decomposes an answer string into clean, individual factual claims,
        filtering out structural markdown, titles, parenthetical fragments, and boilerplate.
        """
        # Protect common abbreviations from erroneous sentence splitting
        protected = answer
        abbrevs = ["Dr.", "Prof.", "Mr.", "Ms.", "Rs.", "e.g.", "i.e.", "vs.", "Fig.", "No.", "Inc.", "Ltd.", "Dept."]
        for i, abbr in enumerate(abbrevs):
            protected = protected.replace(abbr, f"__ABBR_{i}__")

        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", protected)
        claims = []
        for s in raw_sentences:
            # Restore abbreviations
            restored = s
            for i, abbr in enumerate(abbrevs):
                restored = restored.replace(f"__ABBR_{i}__", abbr)
            s_clean = restored.strip().lstrip("•-*0123456789. ")

            # Ignore header boilerplate, structural markdown headings, raw citation mappings, or citation declarations
            is_structural_header = (
                s.strip().startswith("#")
                or s_clean.startswith("#")
                or bool(re.match(r"^\*{0,2}[A-Za-z\s/&_-]{3,40}:\*{0,2}$", s_clean))
                or bool(re.match(r"^(?:###|\*\*|##|#)?\s*[\*\_\(\[\{]*\s*(?:conclusion|note\s+on|note|notes|summary|calculation\s+of\s+difference|relevant\s+excerpts|comparison\s+with|table|schedule|methodology)\b:?", s_clean, re.IGNORECASE))
                or bool(re.search(r"^\s*[\*\_\(\[\{]*\s*note\b", s_clean, re.IGNORECASE))
            )
            # Ignore parenthetical fragments, numbers in brackets/parentheses, or fragments lacking words
            is_parenthetical_fragment = (
                bool(re.match(r"^[\(\[\{\*\s]*[₹$Rs\d\.,\s\-_/]+[\)\]\}\*\s]*(?:\[\d+\])*$", s_clean))
                or len(re.findall(r"[a-zA-Z]{2,}", s_clean)) < 2
            )
            is_boilerplate = (
                is_structural_header
                or is_parenthetical_fragment
                or s_clean.startswith("Based on the verified excerpts")
                or s_clean.startswith("Notice:")
                or bool(re.match(r"^\[\d+\]\s*\[Doc:", s_clean))
                or bool(re.match(r"^\[?\s*(?:citations?|sources?|references?)\s*[:\]]", s_clean, re.IGNORECASE))
                or bool(re.match(r"^\[\d+\](?:\s*\[\d+\])*$", s_clean))
                or bool(re.match(r"^(?:citations?|sources?|references?)\s*:\s*(\[\d+\]|\d+|,|\s)*$", s_clean, re.IGNORECASE))
            )
            if len(s_clean) > 10 and not is_boilerplate:
                claims.append(s_clean)
        return claims

    @classmethod
    def verify_claims(
        cls,
        answer: str,
        evidence: StructuredEvidence,
        citations_list: Optional[List[Dict[str, Any]]] = None,
        nli_engine: Optional[Any] = None,
        enable_nli: bool = True,
        query: str = "",
    ) -> Tuple[List[ClaimVerificationResult], float, int, int]:
        """
        Executes the 4-tier verification pipeline across all claims in the answer.

        Returns:
            Tuple of:
              - claims_results: List[ClaimVerificationResult]
              - faithfulness_score: float (supported / total)
              - numerical_mismatches: int
              - citation_errors: int
        """
        claims_text = cls.extract_claims(answer)
        if not claims_text:
            return [], 1.0, 0, 0

        evidence_text = evidence.get_full_text()
        evidence_lower = evidence_text.lower()
        results = []
        supported_count = 0
        num_mismatches = 0
        cit_errors = 0

        for idx, c_text in enumerate(claims_text, start=1):
            cid = f"claim_{idx:03d}"
            res, is_supp, is_num, is_cit = verify_single_claim(
                cid=cid,
                c_text=c_text,
                evidence_text=evidence_text,
                evidence_lower=evidence_lower,
                citations_list=citations_list,
                nli_engine=nli_engine,
                enable_nli=enable_nli,
                query=query,
                stop_words=cls.STOP_WORDS,
            )
            results.append(res)
            if is_supp:
                supported_count += 1
            if is_num:
                num_mismatches += 1
            if is_cit:
                cit_errors += 1

        faithfulness = round(supported_count / len(claims_text), 4) if claims_text else 1.0
        return results, faithfulness, num_mismatches, cit_errors
