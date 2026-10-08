"""
RAISE Telemetry Audit Models & Provenance Records
==================================================
Purpose:
  Provides granular audit containers for candidates, claim-by-claim verification,
  numerical consistency, multi-hop reasoning, and provenance chains.

Data Models:
  - `CandidateAuditItem`: Reranker candidate ranking, score, retriever source, and dropout tracking.
  - `ClaimEvidenceAuditItem`: Sentence-level NLI entailment / contradiction audit record.
  - `NumericalAuditItem`: Arithmetic equation verification and tolerance bounds.
  - `NumericalDiffItem`: Ground truth vs pipeline value extraction comparison.
  - `CitationAuditItem`: Numerical bracket-to-page binding validity.
  - `HopEvidenceItem`: Multi-hop entity bridge and path confidence.
  - `PromptContextTelemetry`: Chunks and character snippets injected into synthesizer memory.
  - `ProvenanceItem` & `ProvenanceData`: Explicit document, page, and chunk citation chains.

Author: RAISE Core Architecture Team
Maintainability: Keep under 250 lines with typed serializability.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.cli.metric_types import MetricValue


@dataclass
class CandidateAuditItem:
    rank: int
    chunk_id: str
    score: float
    retriever: str  # "VECTOR", "BM25", "GRAPH", "HYBRID"
    primary_page: int
    heading: str = ""
    semantic_similarity: Optional[float] = None
    bm25_score: Optional[float] = None
    entity_overlap: Optional[float] = None
    numeric_overlap: Optional[float] = None
    graph_distance: Optional[int] = None
    contains_expected_entity: Optional[bool] = None
    reranker_dropout: bool = False
    text_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "chunk_id": self.chunk_id,
            "score": self.score,
            "retriever": self.retriever,
            "primary_page": self.primary_page,
            "heading": self.heading,
            "semantic_similarity": self.semantic_similarity,
            "bm25_score": self.bm25_score,
            "entity_overlap": self.entity_overlap,
            "numeric_overlap": self.numeric_overlap,
            "graph_distance": self.graph_distance,
            "contains_expected_entity": self.contains_expected_entity,
            "reranker_dropout": self.reranker_dropout,
            "text_snippet": self.text_snippet,
        }


@dataclass
class ClaimEvidenceAuditItem:
    claim_id: str
    text: str
    evidence_chunk_id: Optional[str] = None
    primary_page: Optional[int] = None
    support_status: str = "DIRECT"
    confidence: float = 1.0
    notes: str = ""
    nli_entailment_prob: Optional[float] = None
    nli_contradiction_prob: Optional[float] = None
    retrieval_relevance_score: Optional[float] = None
    verification_tier: str = "TIER2_LEXICAL"
    verification_path: str = "DETERMINISTIC"
    decision_reason: str = ""
    raw_logits: Optional[Dict[str, float]] = None
    softmax_probs: Optional[Dict[str, float]] = None
    calibration_status: str = "UNVALIDATED_RAW_SOFTMAX"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "evidence_chunk_id": self.evidence_chunk_id,
            "primary_page": self.primary_page,
            "support_status": self.support_status,
            "confidence": self.confidence,
            "notes": self.notes,
            "nli_entailment_prob": self.nli_entailment_prob,
            "nli_contradiction_prob": self.nli_contradiction_prob,
            "retrieval_relevance_score": self.retrieval_relevance_score,
            "verification_tier": self.verification_tier,
            "verification_path": self.verification_path,
            "decision_reason": self.decision_reason,
            "raw_logits": self.raw_logits,
            "softmax_probs": self.softmax_probs,
            "calibration_status": self.calibration_status,
        }


@dataclass
class NumericalAuditItem:
    detected_metrics: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    arithmetic_status: str = "PASS"
    numeric_consistency: str = "PASS"
    tolerance: str = "±0.0"
    source_page: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_metrics": self.detected_metrics,
            "relationships": self.relationships,
            "arithmetic_status": self.arithmetic_status,
            "numeric_consistency": self.numeric_consistency,
            "tolerance": self.tolerance,
            "source_page": self.source_page,
        }


@dataclass
class NumericalDiffItem:
    metric_name: str
    ground_truth_value: Optional[str] = None
    pipeline_value: Optional[str] = None
    source_page_expected: Optional[int] = None
    source_page_retrieved: Optional[int] = None
    status: str = "PASS"
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "ground_truth_value": self.ground_truth_value,
            "pipeline_value": self.pipeline_value,
            "source_page_expected": self.source_page_expected,
            "source_page_retrieved": self.source_page_retrieved,
            "status": self.status,
            "details": self.details,
        }


@dataclass
class CitationAuditItem:
    sentence_index: int
    sentence_snippet: str
    cited_indices: List[int]
    resolved_pages: List[int]
    is_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sentence_index": self.sentence_index,
            "sentence_snippet": self.sentence_snippet,
            "cited_indices": self.cited_indices,
            "resolved_pages": self.resolved_pages,
            "is_valid": self.is_valid,
        }


@dataclass
class HopEvidenceItem:
    hop_id: int
    sub_goal: str = ""
    source_entity: str = ""
    relation: str = ""
    target_entity: str = ""
    supporting_chunks: List[str] = field(default_factory=list)
    graph_path: List[Dict[str, str]] = field(default_factory=list)
    temporal_constraints: List[str] = field(default_factory=list)
    confidence: float = 1.0
    status: str = "VERIFIED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hop_id": self.hop_id,
            "sub_goal": self.sub_goal,
            "source_entity": self.source_entity,
            "relation": self.relation,
            "target_entity": self.target_entity,
            "supporting_chunks": self.supporting_chunks,
            "graph_path": self.graph_path,
            "temporal_constraints": self.temporal_constraints,
            "confidence": self.confidence,
            "status": self.status,
        }


@dataclass
class PromptContextTelemetry:
    packed_chunk_ids: List[str] = field(default_factory=list)
    prompt_context_tokens: int = 0
    context_snippets: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packed_chunk_ids": self.packed_chunk_ids,
            "prompt_context_tokens": self.prompt_context_tokens,
            "context_snippets": self.context_snippets,
        }


@dataclass
class ProvenanceItem:
    citation_index: int
    document: str
    primary_page: int
    printed_page: Optional[str] = None
    section_heading: str = ""
    chunk_id: str = ""
    evidence_score: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    excerpt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation_index": self.citation_index,
            "document": self.document,
            "primary_page": self.primary_page,
            "printed_page": self.printed_page,
            "section_heading": self.section_heading,
            "chunk_id": self.chunk_id,
            "evidence_score": self.evidence_score.to_dict(),
            "excerpt": self.excerpt,
        }


@dataclass
class ProvenanceData:
    citations: List[ProvenanceItem] = field(default_factory=list)
    unique_documents: List[str] = field(default_factory=list)
    unique_sections: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citations": [c.to_dict() for c in self.citations],
            "unique_documents": self.unique_documents,
            "unique_sections": self.unique_sections,
        }
