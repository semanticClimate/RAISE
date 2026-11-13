"""
Rigorous Grounding, Completeness, and Anti-Fabrication Quality Gate.
Enforces precision, recall (leaf-node entity completeness), and blocks
ungrounded boundary/section hallucinations as defined in the RAISE pipeline blueprint.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class RigorousQualityGate:
    """
    Validates both Precision (Faithfulness) and Recall (Completeness).
    Prevents the LLM from fabricating structural boundaries or excuses.
    """

    def __init__(self, faithfulness_threshold: float = 0.70):
        self.threshold = faithfulness_threshold

    def verify_completeness_and_grounding(
        self,
        query: str,
        response: str,
        retrieved_contexts: List[str],
    ) -> Dict[str, Any]:
        """
        Validates both Precision (Faithfulness) and Recall (Completeness).
        """
        # 1. Structural Completeness Check: Ensure entity lookup is matched
        is_count_or_math = any(w in query.lower() for w in ["how many", "count", "percentage", "times larger", "growth rate", "difference", "calculate", "sum", "total", "ratio"])
        requires_multiple_entities = not is_count_or_math and any(term in query.lower() for term in ["startups", "companies", "names", "ventures"])
        requires_any_entity = not is_count_or_math and any(term in query.lower() for term in ["startup", "company", "who", "institution", "organization", "university", "faculty", "director"])
        extracted_entities = re.findall(r"\b[A-Z][a-zA-Z0-9]{2,}\b", response)  # Capture Capitalized Entity Names

        # Strip out formatting artifacts to verify concrete domain entity recovery (preserve valid institutional entities)
        system_nodes = {
            "Annual", "Report", "The", "This", "That",
            "These", "Those", "There", "Here", "Based", "Section", "References", "Doc", "Page", "Table",
            "Figure", "Appendix", "According", "Document", "Source", "However", "Therefore", "Moreover",
            "Furthermore", "Please", "Note", "Total", "Number", "Name", "Date", "Details"
        }
        leaf_entities = [entity for entity in extracted_entities if entity not in system_nodes]

        # Check what candidate domain entities were actually present in the retrieved context
        context_blob = " ".join(retrieved_contexts) if retrieved_contexts else ""
        context_entities = {
            e for e in re.findall(r"\b[A-Z][a-zA-Z0-9]{2,}\b", context_blob)
            if e not in system_nodes and len(e) > 2
        }
        answer_entities_set = set(leaf_entities)
        omitted_context_entities = context_entities - answer_entities_set

        min_required = 2 if requires_multiple_entities else (1 if requires_any_entity else 0)
        # Only trigger completeness rejection if the retrieved contexts themselves actually contain >= 2 named entities that the answer omitted
        if min_required > 0 and len(leaf_entities) < min_required and len(omitted_context_entities) >= 2 and len(response.split()) > 35:
            return {
                "decision": "REJECT",
                "reason": f"Completeness Failure: The query requested entities/organizations, but fewer than {min_required} concrete leaf-node entities were identified in the response despite being present in evidence.",
                "retry_action": "BM25_ENTITY_FALLBACK",
            }

        # 2. Grounding & Anti-Fabrication Boundary Verification
        # Check if the LLM generated pseudo-boundaries to justify lack of retrieval
        suspicious_patterns = [
            r"records are restricted",
            r"not detailed in this section",
            r"not included in current records",
            r"Section \d+ and Section \d+ records are missing",
            r"bounded by Section .* unavailable",
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                # Verify if this specific section or restriction is present in retrieved chunks
                has_grounding = any(re.search(pattern, context, re.IGNORECASE) for context in retrieved_contexts)
                if not has_grounding:
                    return {
                        "decision": "REJECT",
                        "reason": f"Anti-Fabrication Failure: Detected ungrounded structural boundary claim ('{pattern}') in response.",
                        "retry_action": "RE-GENERATE_WITH_STRICT_NO_COMMENTARY",
                    }

        # 3. Visual Figure Credibility & Traceability Assessment
        has_fig_ref = bool(re.search(r"(?i)\b(?:Figure|Fig\.?|Table|Chart|Plot)\s*\d+", response))
        fig_grounded = True
        if has_fig_ref:
            fig_grounded = any(
                re.search(r"(?i)\b(?:Figure|Fig\.?|Table|Chart|Plot)\s*\d+", ctx) or "figure" in ctx.lower()
                for ctx in retrieved_contexts
            )
        visual_score = 0.98 if (has_fig_ref and fig_grounded) else (0.95 if not has_fig_ref else 0.85)

        return {
            "decision": "ACCEPT",
            "visual_credibility_score": visual_score,
            "figure_grounded": fig_grounded,
            "reason": "Passed grounding, completeness, and anti-fabrication gates.",
        }

    def validate_with_guardrails(
        self,
        response: str,
        retrieved_contexts: List[str],
    ) -> Dict[str, Any]:
        """
        Validates response grounding against core RAG verification gates.
        Provides backward-compatible diagnostics for guardrails integrations.
        """
        resp_clean = response.strip()
        if len(resp_clean) < 15:
            return {
                "valid": False,
                "method": "core-quality-gate",
                "reason": "Response too short (< 15 characters).",
            }

        if retrieved_contexts:
            resp_words = set(re.findall(r"\b\w{4,}\b", resp_clean.lower()))
            has_overlap = any(
                len(resp_words.intersection(set(re.findall(r"\b\w{4,}\b", ctx.lower())))) >= 2
                for ctx in retrieved_contexts
            )
            if not has_overlap:
                return {
                    "valid": False,
                    "method": "core-quality-gate",
                    "reason": "Response lacks grounded lexical overlap with retrieved passages.",
                }

        return {
            "valid": True,
            "method": "core-quality-gate",
            "diagnostics": "Response passed structural grounding and length validation.",
        }


QualityGateValidator = RigorousQualityGate
quality_gate_validator = RigorousQualityGate()
