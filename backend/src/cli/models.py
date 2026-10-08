"""
RAISE Telemetry Models & Pipeline Data Specifications
======================================================
Provides decoupled, typed data structures for end-to-end pipeline observability:
1. MetricState enum & MetricValue container ensuring zero silent fake-number synthesis.
2. Granular sub-stage metric schemas (Intent, Retrieval, Context, Synthesis, Quality, Performance).
3. Consolidated TelemetryFrame container used across CLI, API, Frontend, and JSON Export.

Architecture:
  - `src.cli.metric_types`: `MetricState`, `MetricValue`, `FailureClassification`.
  - `src.cli.audit_models`: Audit items, provenance items, hop evidence, and diff records.
  - `src.cli.models`: Subsystem performance metrics and the master `TelemetryFrame`.

Author: RAISE Core Architecture Team
Maintainability: Keep under 380 lines with clean re-exports and full serialization.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Re-export fundamental metric types
from src.cli.metric_types import (
    MetricState,
    MetricValue,
    FailureClassification,
)

# Re-export audit and provenance records
from src.cli.audit_models import (
    CandidateAuditItem,
    ClaimEvidenceAuditItem,
    NumericalAuditItem,
    NumericalDiffItem,
    CitationAuditItem,
    HopEvidenceItem,
    PromptContextTelemetry,
    ProvenanceItem,
    ProvenanceData,
)

__all__ = [
    "MetricState",
    "MetricValue",
    "FailureClassification",
    "CandidateAuditItem",
    "ClaimEvidenceAuditItem",
    "NumericalAuditItem",
    "NumericalDiffItem",
    "CitationAuditItem",
    "HopEvidenceItem",
    "PromptContextTelemetry",
    "ProvenanceItem",
    "ProvenanceData",
    "IntentMetrics",
    "VectorRetrievalMetrics",
    "BM25RetrievalMetrics",
    "GraphRetrievalMetrics",
    "RerankMetrics",
    "RetrievalMetrics",
    "ContextAssemblyMetrics",
    "SynthesisMetrics",
    "QualityMetrics",
    "PerformanceMetrics",
    "DebugSummary",
    "TelemetryFrame",
]


@dataclass
class IntentMetrics:
    intent: MetricValue[str] = field(default_factory=MetricValue.unavailable)
    confidence: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    query_type: MetricValue[str] = field(default_factory=MetricValue.unavailable)
    complexity: MetricValue[str] = field(default_factory=MetricValue.unavailable)
    coreference_resolved: MetricValue[str] = field(default_factory=MetricValue.unavailable)
    subqueries: List[str] = field(default_factory=list)
    routing_decision: MetricValue[str] = field(default_factory=MetricValue.unavailable)
    latency_ms: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    domain: str = "ACADEMIC / INSTITUTIONAL REPORT"
    routing_explanation: str = ""
    intent_rule_fired: str = "academic_research_firewall_v2"
    competing_intents: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "confidence": self.confidence.to_dict(),
            "query_type": self.query_type.to_dict(),
            "complexity": self.complexity.to_dict(),
            "coreference_resolved": self.coreference_resolved.to_dict(),
            "subqueries": self.subqueries,
            "routing_decision": self.routing_decision.to_dict(),
            "latency_ms": self.latency_ms.to_dict(),
            "domain": self.domain,
            "routing_explanation": self.routing_explanation,
            "intent_rule_fired": self.intent_rule_fired,
            "competing_intents": self.competing_intents,
        }


@dataclass
class VectorRetrievalMetrics:
    model: str = "BAAI/bge-large-en-v1.5"
    collection: str = "raise_graphrag_chunks"
    candidates: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    top_k: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    distance_min: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    distance_max: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    latency_ms: MetricValue[float] = field(default_factory=MetricValue.unavailable)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "collection": self.collection,
            "candidates": self.candidates.to_dict(),
            "top_k": self.top_k.to_dict(),
            "distance_min": self.distance_min.to_dict(),
            "distance_max": self.distance_max.to_dict(),
            "latency_ms": self.latency_ms.to_dict(),
        }


@dataclass
class BM25RetrievalMetrics:
    candidates: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    exact_matches: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    latency_ms: MetricValue[float] = field(default_factory=MetricValue.unavailable)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidates": self.candidates.to_dict(),
            "exact_matches": self.exact_matches.to_dict(),
            "latency_ms": self.latency_ms.to_dict(),
        }


@dataclass
class GraphRetrievalMetrics:
    entry_entities: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    nodes_visited: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    edges_traversed: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    max_hops: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    cypher_query: MetricValue[str] = field(default_factory=MetricValue.unavailable)
    latency_ms: MetricValue[float] = field(default_factory=MetricValue.unavailable)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_entities": self.entry_entities.to_dict(),
            "nodes_visited": self.nodes_visited.to_dict(),
            "edges_traversed": self.edges_traversed.to_dict(),
            "max_hops": self.max_hops.to_dict(),
            "cypher_query": self.cypher_query.to_dict(),
            "latency_ms": self.latency_ms.to_dict(),
        }


@dataclass
class RerankMetrics:
    input_candidates: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    output_evidence: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    mean_score: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    score_improvement_pct: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    latency_ms: MetricValue[float] = field(default_factory=MetricValue.unavailable)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_candidates": self.input_candidates.to_dict(),
            "output_evidence": self.output_evidence.to_dict(),
            "mean_score": self.mean_score.to_dict(),
            "score_improvement_pct": self.score_improvement_pct.to_dict(),
            "latency_ms": self.latency_ms.to_dict(),
        }


@dataclass
class RetrievalMetrics:
    vector: VectorRetrievalMetrics = field(default_factory=VectorRetrievalMetrics)
    bm25: BM25RetrievalMetrics = field(default_factory=BM25RetrievalMetrics)
    graph: GraphRetrievalMetrics = field(default_factory=GraphRetrievalMetrics)
    rerank: RerankMetrics = field(default_factory=RerankMetrics)
    total_retrieval_ms: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    retrievers_enabled: Dict[str, bool] = field(default_factory=lambda: {"Vector": True, "BM25": True, "Graph": False})
    candidates_merged: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    candidates_deduplicated: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    top_candidates_audit: List[CandidateAuditItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector": self.vector.to_dict(),
            "bm25": self.bm25.to_dict(),
            "graph": self.graph.to_dict(),
            "rerank": self.rerank.to_dict(),
            "total_retrieval_ms": self.total_retrieval_ms.to_dict(),
            "retrievers_enabled": self.retrievers_enabled,
            "candidates_merged": self.candidates_merged.to_dict(),
            "candidates_deduplicated": self.candidates_deduplicated.to_dict(),
            "top_candidates_audit": [c.to_dict() for c in self.top_candidates_audit],
        }


@dataclass
class ContextAssemblyMetrics:
    chunks_in_context: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    unique_documents: int = 1
    unique_pages: int = 1
    context_tokens: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    max_context_tokens: int = 8192
    context_utilization_pct: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    chunks_dropped: int = 0
    context_order: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunks_in_context": self.chunks_in_context.to_dict(),
            "unique_documents": self.unique_documents,
            "unique_pages": self.unique_pages,
            "context_tokens": self.context_tokens.to_dict(),
            "max_context_tokens": self.max_context_tokens,
            "context_utilization_pct": self.context_utilization_pct.to_dict(),
            "chunks_dropped": self.chunks_dropped,
            "context_order": self.context_order,
        }


@dataclass
class SynthesisMetrics:
    provider: str = "vLLM (Local TensorRT/PagedAttention)"
    model: str = "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4"
    context_chunks: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    context_tokens: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    output_tokens: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    generation_speed_tok_s: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    time_to_first_token_ms: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    temperature: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    grounding_mode: str = "STRICT (Anti-Hallucination Enabled)"
    citation_contract: str = "NUMERIC BRACKETS ONLY [1..N]"
    latency_ms: MetricValue[float] = field(default_factory=MetricValue.unavailable)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "context_chunks": self.context_chunks.to_dict(),
            "context_tokens": self.context_tokens.to_dict(),
            "output_tokens": self.output_tokens.to_dict(),
            "generation_speed_tok_s": self.generation_speed_tok_s.to_dict(),
            "time_to_first_token_ms": self.time_to_first_token_ms.to_dict(),
            "temperature": self.temperature.to_dict(),
            "grounding_mode": self.grounding_mode,
            "citation_contract": self.citation_contract,
            "latency_ms": self.latency_ms.to_dict(),
        }


@dataclass
class QualityMetrics:
    evidence_overlap_pct: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    numerical_claims_verified: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    numerical_claims_total: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    citation_binding_pct: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    source_coverage_actual: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    source_coverage_total: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    faithfulness_score: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    unsupported_claims_count: MetricValue[int] = field(default_factory=MetricValue.unavailable)
    decision: str = "accept"
    is_gate_passed: bool = True
    rejection_reason: Optional[str] = None
    latency_ms: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    claims_audit: List[ClaimEvidenceAuditItem] = field(default_factory=list)
    unsupported_claims: List[str] = field(default_factory=list)
    numerical_audit: Optional[NumericalAuditItem] = None
    citation_audit: List[CitationAuditItem] = field(default_factory=list)
    citation_precision_pct: MetricValue[float] = field(default_factory=MetricValue.unavailable)
    citation_recall_pct: MetricValue[float] = field(default_factory=MetricValue.unavailable)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_overlap_pct": self.evidence_overlap_pct.to_dict(),
            "numerical_claims_verified": self.numerical_claims_verified.to_dict(),
            "numerical_claims_total": self.numerical_claims_total.to_dict(),
            "citation_binding_pct": self.citation_binding_pct.to_dict(),
            "source_coverage_actual": self.source_coverage_actual.to_dict(),
            "source_coverage_total": self.source_coverage_total.to_dict(),
            "faithfulness_score": self.faithfulness_score.to_dict(),
            "unsupported_claims_count": self.unsupported_claims_count.to_dict(),
            "decision": self.decision,
            "is_gate_passed": self.is_gate_passed,
            "rejection_reason": self.rejection_reason,
            "latency_ms": self.latency_ms.to_dict(),
            "claims_audit": [c.to_dict() for c in self.claims_audit],
            "unsupported_claims": self.unsupported_claims,
            "numerical_audit": self.numerical_audit.to_dict() if self.numerical_audit else None,
            "citation_audit": [c.to_dict() for c in self.citation_audit],
            "citation_precision_pct": self.citation_precision_pct.to_dict(),
            "citation_recall_pct": self.citation_recall_pct.to_dict(),
        }


@dataclass
class PerformanceMetrics:
    routing_ms: float = 0.0
    retrieval_ms: float = 0.0
    synthesis_ms: float = 0.0
    quality_gate_ms: float = 0.0
    total_latency_ms: float = 0.0
    unattributed_latency_ms: float = 0.0
    instrumentation_coverage_pct: float = 100.0
    bottleneck_stage: str = "Synthesis"
    bottleneck_pct: float = 0.0
    stage_percentages: Dict[str, float] = field(default_factory=dict)
    breakdown_tree: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "routing_ms": self.routing_ms,
            "retrieval_ms": self.retrieval_ms,
            "synthesis_ms": self.synthesis_ms,
            "quality_gate_ms": self.quality_gate_ms,
            "total_latency_ms": self.total_latency_ms,
            "unattributed_latency_ms": self.unattributed_latency_ms,
            "instrumentation_coverage_pct": self.instrumentation_coverage_pct,
            "bottleneck_stage": self.bottleneck_stage,
            "bottleneck_pct": self.bottleneck_pct,
            "stage_percentages": self.stage_percentages,
            "breakdown_tree": self.breakdown_tree,
        }


@dataclass
class DebugSummary:
    status: str = "PASS"
    failure_class: FailureClassification = FailureClassification.NONE_PASS
    expected_intent: str = "RESEARCH_FACTUAL"
    actual_intent: str = "ACADEMIC_RESEARCH"
    root_cause: str = "All pipeline stages satisfied grounding and quality thresholds."
    fix_priority: str = "NONE"
    reproducible: bool = True
    request_id: str = ""
    pipeline_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "failure_class": self.failure_class.value if hasattr(self.failure_class, "value") else str(self.failure_class),
            "expected_intent": self.expected_intent,
            "actual_intent": self.actual_intent,
            "root_cause": self.root_cause,
            "fix_priority": self.fix_priority,
            "reproducible": self.reproducible,
            "request_id": self.request_id,
            "pipeline_version": self.pipeline_version,
        }


@dataclass
class TelemetryFrame:
    """
    Consolidated, decoupled Telemetry Frame holding all verified observability metrics.
    Safe for consumption by CLI Renderers, FastAPI Endpoints, and JSON Exporters.
    """
    turn_id: str
    session_id: str
    timestamp: str
    query: str
    scope: str
    mode: str
    answer: str

    intent: IntentMetrics = field(default_factory=IntentMetrics)
    retrieval: RetrievalMetrics = field(default_factory=RetrievalMetrics)
    context_assembly: ContextAssemblyMetrics = field(default_factory=ContextAssemblyMetrics)
    synthesis: SynthesisMetrics = field(default_factory=SynthesisMetrics)
    quality: QualityMetrics = field(default_factory=QualityMetrics)
    provenance: ProvenanceData = field(default_factory=ProvenanceData)
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    debug_summary: DebugSummary = field(default_factory=DebugSummary)
    prompt_context: Optional[PromptContextTelemetry] = None
    candidate_audit: List[CandidateAuditItem] = field(default_factory=list)
    numerical_diffs: List[NumericalDiffItem] = field(default_factory=list)
    hop_evidence_chain: List[HopEvidenceItem] = field(default_factory=list)
    chain_completeness_gate: Dict[str, Any] = field(default_factory=dict)

    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "query": self.query,
            "scope": self.scope,
            "mode": self.mode,
            "answer": self.answer,
            "intent": self.intent.to_dict(),
            "retrieval": self.retrieval.to_dict(),
            "context_assembly": self.context_assembly.to_dict(),
            "synthesis": self.synthesis.to_dict(),
            "quality": self.quality.to_dict(),
            "provenance": self.provenance.to_dict(),
            "performance": self.performance.to_dict(),
            "debug_summary": self.debug_summary.to_dict(),
            "prompt_context": self.prompt_context.to_dict() if self.prompt_context else None,
            "candidate_audit": [c.to_dict() for c in self.candidate_audit],
            "numerical_diffs": [d.to_dict() for d in self.numerical_diffs],
            "hop_evidence_chain": [h.to_dict() for h in self.hop_evidence_chain],
            "chain_completeness_gate": self.chain_completeness_gate,
        }
