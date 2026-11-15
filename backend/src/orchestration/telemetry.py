"""
RAISE Proof-Level Telemetry Schema
Captures comprehensive forensic traces across query planning, candidate generation,
evidence reranking, relation resolution, proof graph traversal, deterministic operations,
answer derivation, and calibrated abstention gating.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

ProofStatus = Literal["PENDING", "RESOLVED", "FAILED"]


@dataclass
class ProofHopTelemetry:
    hop_id: int
    query_text: str
    target_entity: str
    expected_relation: str
    candidate_count: int
    accepted_evidence_ids: List[str] = field(default_factory=list)
    rejected_evidence_ids: List[str] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    proof_status: ProofStatus = "PENDING"
    cypher_query: Optional[str] = None
    repair_attempts: int = 0
    expanded_1hop: bool = False
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProofLevelLedger:
    query_plan: Dict[str, Any] = field(default_factory=dict)
    retrieval_candidates: List[Dict[str, Any]] = field(default_factory=list)
    reranked_chunks: List[Dict[str, Any]] = field(default_factory=list)
    hop_evidence: List[ProofHopTelemetry] = field(default_factory=list)
    entity_resolutions: List[Dict[str, Any]] = field(default_factory=list)
    relation_checks: List[Dict[str, Any]] = field(default_factory=list)
    proof_graph: Dict[str, Any] = field(default_factory=dict)
    deterministic_operations: List[Dict[str, Any]] = field(default_factory=list)
    answer_derivation: Dict[str, Any] = field(default_factory=dict)
    abstention_gate: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def add_hop(
        self,
        query_text: str,
        target_entity: str,
        expected_relation: str,
        candidate_count: int = 0,
        **kwargs: Any,
    ) -> ProofHopTelemetry:
        """Creates, appends, and returns a new ProofHopTelemetry entry."""
        hop = ProofHopTelemetry(
            hop_id=len(self.hop_evidence) + 1,
            query_text=query_text,
            target_entity=target_entity,
            expected_relation=expected_relation,
            candidate_count=candidate_count,
            **kwargs,
        )
        self.hop_evidence.append(hop)
        return hop

    def record_deterministic_op(
        self, op_type: str, inputs: Dict[str, Any], result: Any, verified: bool = True
    ) -> None:
        """Logs a deterministic arithmetic, citation, or AST check operation."""
        self.deterministic_operations.append(
            {
                "op_type": op_type,
                "inputs": inputs,
                "result": result,
                "verified": verified,
                "timestamp": time.time(),
            }
        )

    def record_abstention_gate(
        self,
        passed: bool,
        faithfulness_score: float,
        retries_used: int,
        failure_reason: Optional[str] = None,
        threshold: float = 0.80,
    ) -> None:
        """Records the RuntimeFaithfulnessQualityGate decision."""
        self.abstention_gate = {
            "passed": passed,
            "faithfulness_score": round(faithfulness_score, 4),
            "threshold": threshold,
            "retries_used": retries_used,
            "abstained": not passed,
            "failure_reason": failure_reason,
        }

    def to_dict(self, include_full_chunks: bool = False) -> Dict[str, Any]:
        """
        Serializes ledger to a dictionary. Preserves chunk IDs and scores by default
        without dumping multi-kilobyte raw text unless include_full_chunks=True.
        """
        def _compact_chunk(c: Dict[str, Any]) -> Dict[str, Any]:
            if include_full_chunks:
                return c
            return {
                k: c[k]
                for k in ("chunk_id", "id", "page_number", "score", "rerank_score", "section_type")
                if k in c
            }

        return {
            "query_plan": self.query_plan,
            "retrieval_candidates_count": len(self.retrieval_candidates),
            "retrieval_candidates": [_compact_chunk(c) for c in self.retrieval_candidates],
            "reranked_chunks_count": len(self.reranked_chunks),
            "reranked_chunks": [_compact_chunk(c) for c in self.reranked_chunks],
            "hop_evidence": [h.to_dict() for h in self.hop_evidence],
            "entity_resolutions": self.entity_resolutions,
            "relation_checks": self.relation_checks,
            "proof_graph": self.proof_graph,
            "deterministic_operations": self.deterministic_operations,
            "answer_derivation": self.answer_derivation,
            "abstention_gate": self.abstention_gate,
            "timestamp": self.timestamp,
        }
