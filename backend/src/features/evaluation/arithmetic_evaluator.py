"""
Deterministic Arithmetic & Numeric Reasoning Evaluator
======================================================
Evaluates the mathematical derivation and arithmetic accuracy of RAG responses:
1. Detects arithmetic queries (sums, differences, growth rates, ratios, percentages).
2. Extracts numerical operands and ground-truth target calculations.
3. Verifies generated results against verified mathematical derivations with configurable tolerance.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class QueryArithmeticResult:
    """Arithmetic verification result for a single query."""
    query_id: str
    query: str
    is_arithmetic: bool
    operation_type: str  # "DIFFERENCE", "SUM", "RATIO", "PERCENTAGE", "GROWTH", "EXACT_NUMERIC", "NONE"
    expected_values: List[float]
    generated_values: List[float]
    is_mathematically_correct: bool
    relative_error: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "is_arithmetic": self.is_arithmetic,
            "operation_type": self.operation_type,
            "expected_values": self.expected_values,
            "generated_values": self.generated_values,
            "is_mathematically_correct": self.is_mathematically_correct,
            "relative_error": round(self.relative_error, 4) if self.relative_error is not None else None,
            "notes": self.notes,
        }


class ArithmeticEvaluator:
    """
    Evaluates arithmetic precision and mathematical reasoning in generated responses.
    """

    DIFF_KEYWORDS = re.compile(r"\b(difference|change|increase|decrease|variance|drop|growth|rose|declined)\b", re.IGNORECASE)
    SUM_KEYWORDS = re.compile(r"\b(total|sum|combined|aggregate|overall|together)\b", re.IGNORECASE)
    RATIO_KEYWORDS = re.compile(r"\b(ratio|proportion|fraction|per\s+capita|rate)\b", re.IGNORECASE)
    PERCENT_KEYWORDS = re.compile(r"\b(percent|percentage|%)\b", re.IGNORECASE)

    NUMBER_CLEANER = re.compile(r"[₹$,\s]")

    @classmethod
    def extract_floats(cls, text: str) -> List[float]:
        """Extracts all floating point and integer numbers from text, ignoring citations."""
        # Strip bracketed citations [1], [2, 3]
        cleaned = re.sub(r"\[\[?\s*\d+(?:\s*[,-–]\s*\d+)*\s*\]?\]", "", text)
        # Strip filenames and page indicators
        cleaned = re.sub(r"\b[\w\-\.]+\.(?:pdf|docx?|txt|csv|json)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(?:p\.|page|pg\.)\s*\d+\b", "", cleaned, flags=re.IGNORECASE)

        # Match numbers with optional decimal point
        matches = re.finditer(r"(?<![a-zA-Z0-9_])[-+]?\d+(?:,\d+)*(?:\.\d+)?(?![a-zA-Z0-9_])", cleaned)
        floats = []
        for m in matches:
            raw = m.group(0).replace(",", "").strip()
            # Ignore standalone years between 1950 and 2050 if they look like calendar years
            try:
                val = float(raw)
                floats.append(val)
            except ValueError:
                continue
        return floats

    @classmethod
    def classify_operation(cls, query: str, gold_answer: str) -> str:
        """Classifies the arithmetic operation type required."""
        combined = f"{query} {gold_answer}"
        if cls.DIFF_KEYWORDS.search(combined):
            return "DIFFERENCE"
        if cls.SUM_KEYWORDS.search(combined):
            return "SUM"
        if cls.PERCENT_KEYWORDS.search(combined):
            return "PERCENTAGE"
        if cls.RATIO_KEYWORDS.search(combined):
            return "RATIO"
        # If no explicit arithmetic keyword but numbers are prominent in gold
        if len(cls.extract_floats(gold_answer)) > 0:
            return "EXACT_NUMERIC"
        return "NONE"

    @classmethod
    def evaluate_query(
        cls,
        query_id: str,
        query: str,
        gold_answer: str,
        generated_answer: str,
        tolerance_rel: float = 0.02,  # 2% relative tolerance
        tolerance_abs: float = 0.1,   # 0.1 absolute tolerance
    ) -> QueryArithmeticResult:
        """
        Evaluates whether generated answer correctly solves the arithmetic/numeric problem.
        """
        op_type = cls.classify_operation(query, gold_answer)
        is_arith = op_type in {"DIFFERENCE", "SUM", "PERCENTAGE", "RATIO"}

        gold_nums = cls.extract_floats(gold_answer)
        gen_nums = cls.extract_floats(generated_answer)

        if not gold_nums:
            return QueryArithmeticResult(
                query_id=query_id,
                query=query,
                is_arithmetic=is_arith,
                operation_type=op_type,
                expected_values=[],
                generated_values=gen_nums,
                is_mathematically_correct=True,
                notes=["No numeric values expected in gold answer."],
            )

        # Check if expected values appear in generated numbers within tolerance
        matched_expected = 0
        min_error = float("inf")
        notes = []

        for exp in gold_nums:
            found = False
            for gen in gen_nums:
                abs_err = abs(exp - gen)
                rel_err = abs_err / (abs(exp) + 1e-9)
                if abs_err <= tolerance_abs or rel_err <= tolerance_rel:
                    found = True
                    min_error = min(min_error, rel_err)
                    break
            if found:
                matched_expected += 1
            else:
                notes.append(f"Expected number {exp} not found within tolerance in generated response.")

        is_correct = matched_expected == len(gold_nums)
        if min_error == float("inf"):
            min_error = 1.0 if not is_correct else 0.0

        return QueryArithmeticResult(
            query_id=query_id,
            query=query,
            is_arithmetic=is_arith,
            operation_type=op_type,
            expected_values=gold_nums,
            generated_values=gen_nums,
            is_mathematically_correct=is_correct,
            relative_error=min_error if is_correct else 1.0,
            notes=notes,
        )

    @classmethod
    def aggregate_results(
        cls, results: List[QueryArithmeticResult]
    ) -> Dict[str, Any]:
        """Aggregates arithmetic and numeric metrics across the test set."""
        if not results:
            return {
                "total_queries": 0,
                "arithmetic_queries_count": 0,
                "arithmetic_accuracy": 0.0,
                "overall_numeric_accuracy": 0.0,
            }

        arithmetic_results = [r for r in results if r.is_arithmetic]
        all_numeric_results = [r for r in results if r.operation_type != "NONE"]

        arith_acc = (
            sum(1 for r in arithmetic_results if r.is_mathematically_correct) / len(arithmetic_results)
            if arithmetic_results
            else 1.0
        )
        overall_num_acc = (
            sum(1 for r in all_numeric_results if r.is_mathematically_correct) / len(all_numeric_results)
            if all_numeric_results
            else 1.0
        )

        return {
            "total_queries": len(results),
            "arithmetic_queries_count": len(arithmetic_results),
            "arithmetic_accuracy": round(arith_acc, 4),
            "all_numeric_queries_count": len(all_numeric_results),
            "overall_numeric_accuracy": round(overall_num_acc, 4),
            "queries": [r.to_dict() for r in results],
        }
