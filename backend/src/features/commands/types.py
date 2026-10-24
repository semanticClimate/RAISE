"""
Command Types & Data Contracts
==============================
Component: `src.features.commands.types`
Architecture: Modular Slash Command System for RAISE
Max Lines: Strictly < 400 lines
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ComparabilityStatus(str, Enum):
    """Explicit comparability state defined in University Comparison Framework."""
    FULLY_COMPARABLE = "FULLY_COMPARABLE"
    CONDITIONALLY_COMPARABLE = "CONDITIONALLY_COMPARABLE"
    CONTEXT_ADJUSTED = "CONTEXT_ADJUSTED"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EXTERNAL_SUPPLEMENTED = "EXTERNAL_SUPPLEMENTED"


@dataclass
class CriterionComparison:
    """Individual criterion comparison between two institutional entities."""
    dimension: str
    criterion: str
    val_a: str
    val_b: str
    comparability: ComparabilityStatus = ComparabilityStatus.FULLY_COMPARABLE
    delta: Optional[str] = None
    citation_a: Optional[str] = None
    citation_b: Optional[str] = None
    notes: Optional[str] = None
    is_external_a: bool = False
    is_external_b: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "criterion": self.criterion,
            "val_a": self.val_a,
            "val_b": self.val_b,
            "comparability": self.comparability.value,
            "delta": self.delta,
            "citation_a": self.citation_a,
            "citation_b": self.citation_b,
            "notes": self.notes,
            "is_external_a": self.is_external_a,
            "is_external_b": self.is_external_b,
        }


@dataclass
class CommandContext:
    """Runtime context passed into a slash command handler."""
    query: str
    command_name: str
    raw_args: str
    args: List[str] = field(default_factory=list)
    active_docs: Optional[List[str]] = None
    session_id: str = "default"
    request_id: str = ""
    mode: str = "fast"
    stream: bool = False
    allow_web_fetch: bool = True
    rag_engine: Any = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandResult:
    """Execution output returned by a slash command handler."""
    status: str = "SUCCESS"
    command: str = ""
    answer: str = ""
    citations: List[Dict[str, Any]] = field(default_factory=list)
    subgraph: Dict[str, Any] = field(default_factory=lambda: {"nodes": [], "edges": []})
    verified_claims: List[Dict[str, Any]] = field(default_factory=list)
    follow_up_inquiries: List[str] = field(default_factory=list)
    quality_gate_decision: str = "accept"
    traceability_score: float = 0.95
    execution_time: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "command": self.command,
            "answer": self.answer,
            "reply": self.answer,
            "grounded_answer": self.answer,
            "citations": self.citations,
            "subgraph": self.subgraph,
            "verified_claims": self.verified_claims,
            "follow_up_inquiries": self.follow_up_inquiries,
            "suggestions": self.follow_up_inquiries,
            "quality_gate_decision": self.quality_gate_decision,
            "traceability_score": self.traceability_score,
            "execution_time": self.execution_time,
            "meta": self.meta,
        }


@dataclass
class CommandMetadata:
    """Descriptor and help definition for registered slash commands."""
    name: str
    description: str
    syntax: str
    examples: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    category: str = "Research"
    is_dev_only: bool = False
