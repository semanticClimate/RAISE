"""
RAISE Telemetry Metric States & Core Value Containers
======================================================
Purpose:
  Provides forensic classification of telemetry data provenance ensuring
  developer consoles never silently fabricate or replace missing measurements
  with realistic-looking synthetic numbers.

Components:
  - `MetricState`: Verifiable classification enum (MEASURED, DERIVED, ESTIMATED, UNAVAILABLE, etc.).
  - `MetricValue[T]`: Generic container enforcing strict state/value integrity invariants.
  - `FailureClassification`: Standardized taxonomy of RAG failure modes.

Author: RAISE Core Architecture Team
Maintainability: Keep under 130 lines with zero external dependencies.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Generic, Optional, TypeVar

T = TypeVar("T")


class MetricState(str, Enum):
    """
    Forensic classification of telemetry data provenance.
    Ensures developer consoles never silently replace missing measurements
    with realistic-looking numbers.
    """
    MEASURED = "MEASURED"          # Directly queried / recorded by database, engine, or timer
    DERIVED = "DERIVED"            # Mathematically computed from measured raw inputs
    ESTIMATED = "ESTIMATED"        # Deterministic approximation (e.g. word-split tokens)
    UNAVAILABLE = "UNAVAILABLE"    # Metric was not recorded or unsupported by the current backend
    NOT_APPLICABLE = "NOT_APPLICABLE"  # Skipped because the execution path bypassed this component
    NOT_RUN = "NOT_RUN"            # Check was scheduled/applicable but skipped/deferred
    FAILED = "FAILED"              # Metric computation or check threw an unhandled exception


@dataclass
class MetricValue(Generic[T]):
    """Container holding a metric value alongside its verifiable provenance state."""
    value: Optional[T] = None
    state: MetricState = MetricState.UNAVAILABLE
    unit: str = ""
    notes: Optional[str] = None

    def __post_init__(self):
        # Strict Invariant: non-value states must never hold a value
        if self.state in (MetricState.UNAVAILABLE, MetricState.NOT_APPLICABLE, MetricState.NOT_RUN, MetricState.FAILED):
            self.value = None
        # Strict Invariant: value states with None automatically normalize to UNAVAILABLE
        elif self.state in (MetricState.MEASURED, MetricState.DERIVED, MetricState.ESTIMATED) and self.value is None:
            self.state = MetricState.UNAVAILABLE

    @classmethod
    def measured(cls, val: T, unit: str = "", notes: Optional[str] = None) -> MetricValue[T]:
        return cls(value=val, state=MetricState.MEASURED, unit=unit, notes=notes)

    @classmethod
    def derived(cls, val: T, unit: str = "", notes: Optional[str] = None) -> MetricValue[T]:
        return cls(value=val, state=MetricState.DERIVED, unit=unit, notes=notes)

    @classmethod
    def estimated(cls, val: T, unit: str = "", notes: Optional[str] = None) -> MetricValue[T]:
        return cls(value=val, state=MetricState.ESTIMATED, unit=unit, notes=notes)

    @classmethod
    def unavailable(cls, unit: str = "", notes: Optional[str] = None) -> MetricValue[T]:
        return cls(value=None, state=MetricState.UNAVAILABLE, unit=unit, notes=notes)

    @classmethod
    def not_applicable(cls, unit: str = "", notes: Optional[str] = None) -> MetricValue[T]:
        return cls(value=None, state=MetricState.NOT_APPLICABLE, unit=unit, notes=notes)

    @classmethod
    def not_run(cls, unit: str = "", notes: Optional[str] = None) -> MetricValue[T]:
        return cls(value=None, state=MetricState.NOT_RUN, unit=unit, notes=notes)

    @classmethod
    def failed(cls, unit: str = "", notes: Optional[str] = None) -> MetricValue[T]:
        return cls(value=None, state=MetricState.FAILED, unit=unit, notes=notes)

    @property
    def is_available(self) -> bool:
        return self.state in (MetricState.MEASURED, MetricState.DERIVED, MetricState.ESTIMATED) and self.value is not None

    def display(self, format_spec: str = "") -> str:
        """Formatted string representation with provenance indicator."""
        if not self.is_available:
            return f"-- [{self.state.value}]"
        if format_spec and isinstance(self.value, (int, float)):
            val_str = f"{self.value:{format_spec}}"
        else:
            val_str = str(self.value)
        unit_str = f" {self.unit}" if self.unit else ""
        if self.state == MetricState.MEASURED:
            return f"{val_str}{unit_str}"
        return f"{val_str}{unit_str} [{self.state.value}]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "state": self.state.value,
            "unit": self.unit,
            "notes": self.notes,
        }


class FailureClassification(str, Enum):
    NONE_PASS = "NONE (PASS)"
    INTENT_ROUTING_FAILURE = "INTENT_ROUTING_FAILURE"
    QUERY_REWRITE_FAILURE = "QUERY_REWRITE_FAILURE"
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"
    RERANKING_FAILURE = "RERANKING_FAILURE"
    CONTEXT_ASSEMBLY_FAILURE = "CONTEXT_ASSEMBLY_FAILURE"
    GENERATION_FAILURE = "GENERATION_FAILURE"
    CITATION_FAILURE = "CITATION_FAILURE"
    GRAPH_FAILURE = "GRAPH_FAILURE"
    DATA_PROVENANCE_FAILURE = "DATA_PROVENANCE_FAILURE"
    QUALITY_GATE_FAILURE = "QUALITY_GATE_FAILURE"
    ZERO_EVIDENCE_REFUSAL = "ZERO_EVIDENCE_REFUSAL"
    ERR_OCR_NOISE = "ERR_OCR_NOISE"
    ERR_RETRIEVAL_MISS = "ERR_RETRIEVAL_MISS"
    ERR_RERANK_DROPOUT = "ERR_RERANK_DROPOUT"
    ERR_LLM_HALLUCINATION = "ERR_LLM_HALLUCINATION"
    ERR_GATE_OVERBLOCK = "ERR_GATE_OVERBLOCK"
    ERR_UNANSWERABLE_CORRECT = "ERR_UNANSWERABLE_CORRECT"
