"""
Hard Structural Constraints Engine for Document Chunking
========================================================
Component: `src.chunking.hard_constraints`
Architecture Layer: Document Processing / Deterministic Structural Guardrails

Overview:
---------
Evaluates immutable layout, pagination, and token-budget constraints that strictly
precede soft multi-signal graph optimization.

Deterministic Enforcements:
1. Tables: First-class isolated units. Never merged with running narrative text (`PRESERVE`).
2. Figures: First-class isolated units. Preserved as standalone visual objects (`PRESERVE`).
3. Cross-Page Continuations: Continuous narratives broken across physical PDF pages are forced to merge (`MERGE`).
4. Max Parent Token Limits: Hard token limits to prevent model context window overflow (`SPLIT`).
"""

from __future__ import annotations

import logging

from .models import (
    BoundaryDecision,
    CandidateUnit,
    HardConstraintResult,
)

logger = logging.getLogger("raise.chunking.hard_constraints")


class HardConstraintEngine:
    """
    Evaluates immutable layout and structural constraints that strictly precede
    soft graph signal evaluation.
    Enforces deterministic boundaries for:
      - Tables (first-class isolated units)
      - Figures (first-class isolated units)
      - Cross-page continuation headers (must merge)
      - Max parent token limits (must split)
    """

    @staticmethod
    def evaluate(
        unit_a: CandidateUnit,
        unit_b: CandidateUnit,
        max_parent_tokens: int,
        enable_cross_page_continuity: bool = True,
    ) -> HardConstraintResult:
        """Evaluates adjacent CandidateUnits against strict deterministic rules."""
        # 1. Table boundaries
        if unit_a.is_table or unit_b.is_table:
            return HardConstraintResult(
                triggered=True,
                constraint_type="TABLE_BOUNDARY",
                forced_action=BoundaryDecision.PRESERVE,
                reason_code="HARD_TABLE_BOUNDARY",
                evidence={
                    "unit_a_id": unit_a.candidate_id,
                    "unit_b_id": unit_b.candidate_id,
                    "unit_a_is_table": unit_a.is_table,
                    "unit_b_is_table": unit_b.is_table,
                },
            )

        # 2. Figure boundaries
        if unit_a.is_figure or unit_b.is_figure:
            return HardConstraintResult(
                triggered=True,
                constraint_type="FIGURE_BOUNDARY",
                forced_action=BoundaryDecision.PRESERVE,
                reason_code="HARD_FIGURE_BOUNDARY",
                evidence={
                    "unit_a_id": unit_a.candidate_id,
                    "unit_b_id": unit_b.candidate_id,
                    "unit_a_is_figure": unit_a.is_figure,
                    "unit_b_is_figure": unit_b.is_figure,
                },
            )

        # 3. Cross-page continuation
        if enable_cross_page_continuity:
            if unit_b.is_continued or (unit_b.continuation_of_id and unit_b.continuation_of_id == unit_a.candidate_id):
                return HardConstraintResult(
                    triggered=True,
                    constraint_type="CONTINUATION_HEADER",
                    forced_action=BoundaryDecision.MERGE,
                    reason_code="HARD_CROSS_PAGE_CONTINUATION",
                    evidence={
                        "unit_a_id": unit_a.candidate_id,
                        "unit_b_id": unit_b.candidate_id,
                        "continuation_of_id": unit_b.continuation_of_id,
                        "page_a": unit_a.page_start,
                        "page_b": unit_b.page_start,
                    },
                )

        # 4. Token limit guardrail
        combined_tokens = unit_a.token_estimate + unit_b.token_estimate
        if combined_tokens > max_parent_tokens:
            return HardConstraintResult(
                triggered=True,
                constraint_type="MAX_TOKENS_EXCEEDED",
                forced_action=BoundaryDecision.SPLIT,
                reason_code="HARD_MAX_PARENT_TOKENS_EXCEEDED",
                evidence={
                    "combined_tokens": combined_tokens,
                    "max_parent_tokens": max_parent_tokens,
                    "tokens_a": unit_a.token_estimate,
                    "tokens_b": unit_b.token_estimate,
                },
            )

        return HardConstraintResult(triggered=False)
