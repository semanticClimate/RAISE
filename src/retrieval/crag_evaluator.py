"""
RAISE Corrective Retrieval-Augmented Generation (CRAG) Evaluator
================================================================
Component: `src.retrieval.crag_evaluator`
Architecture Layer: Retrieval Verification / Self-Reflective Filtering
Design Standard: Enterprise-tier, low-latency, modular architecture (<= 400 lines)

Overview:
---------
Evaluates retrieval relevance and entity coverage before response generation.
Categorizes retrieval results into CORRECT, AMBIGUOUS, or INCORRECT states and
enforces verified routing policies:
- `/audit` strictly abstains with INSUFFICIENT_EVIDENCE when confidence is lacking.
- `/browser` and `/compare` permit controlled web search fallbacks to supplement gaps.
- General queries trigger neighborhood graph expansion or deterministic abstention.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("raise.retrieval.crag")


class CRAGDecision(str, Enum):
    CORRECT = "CORRECT"
    AMBIGUOUS = "AMBIGUOUS"
    INCORRECT = "INCORRECT"


class CRAGAction(str, Enum):
    PROCEED = "PROCEED"
    EXPAND_GRAPH = "EXPAND_GRAPH"
    WEB_SEARCH_FALLBACK = "WEB_SEARCH_FALLBACK"
    ABSTAIN_INSUFFICIENT = "ABSTAIN_INSUFFICIENT"


@dataclass
class CRAGEvaluationResult:
    decision: CRAGDecision
    action: CRAGAction
    confidence: float
    reason: str
    retained_chunks: List[Dict[str, Any]] = field(default_factory=list)
    filtered_out_chunks: List[Dict[str, Any]] = field(default_factory=list)
    missing_entities: List[str] = field(default_factory=list)
    suggested_query: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "action": self.action.value,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "retained_chunks_count": len(self.retained_chunks),
            "filtered_out_chunks_count": len(self.filtered_out_chunks),
            "missing_entities": self.missing_entities,
            "suggested_query": self.suggested_query,
        }


class CorrectiveRAGEvaluator:
    """
    Evaluates retrieved document quality and selects corrective self-reflective actions.
    """

    STOPWORDS: Set[str] = {
        "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "is", "are", "was", "were", "what", "which", "who", "whom",
        "how", "why", "when", "where", "does", "did", "do", "can", "could", "would",
        "should", "report", "annual", "details", "give", "show", "tell", "about",
    }

    ENTITY_EXCLUDED_WORDS: Set[str] = {
        "audit", "compare", "browser", "synthesize", "explain", "find",
        "search", "list", "check", "verify", "show", "give", "tell",
        "total", "grand", "details", "report", "annual", "academic",
    }

    def __init__(
        self,
        high_threshold: float = 0.70,
        low_threshold: float = 0.40,
        min_chunk_relevance: float = 0.25,
    ):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.min_chunk_relevance = min_chunk_relevance

    def extract_salient_terms(self, text: str) -> List[str]:
        """Extracts informative query terms excluding standard stopwords."""
        words = re.findall(r"\b[A-Za-z0-9_\-\.]{3,}\b", text)
        return [w.lower() for w in words if w.lower() not in self.STOPWORDS]

    def extract_entity_mentions(self, text: str) -> List[str]:
        """Identifies capitalized multi-word entity candidates or acronyms."""
        acronyms = re.findall(r"\b[A-Z]{2,}\b", text)
        proper_nouns = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        candidates = list(dict.fromkeys(acronyms + proper_nouns))
        excluded = self.STOPWORDS | self.ENTITY_EXCLUDED_WORDS
        return [c for c in candidates if c.lower() not in excluded]

    def score_chunk_relevance(self, query_terms: List[str], chunk: Dict[str, Any]) -> float:
        """
        Computes a normalized relevance score in [0.0, 1.0] for a chunk.
        Prefers reranker/similarity metrics if available; falls back to term overlap.
        """
        # If cross-encoder score is present
        if "cross_encoder_score" in chunk and chunk["cross_encoder_score"] is not None:
            raw_score = float(chunk["cross_encoder_score"])
            # Sigmoid normalization if logit scale (-10 to 10)
            if raw_score < 0.0 or raw_score > 1.0:
                import math
                return 1.0 / (1.0 + math.exp(-max(min(raw_score, 10.0), -10.0)))
            return max(0.0, min(1.0, raw_score))

        # If similarity or score is present
        if "similarity" in chunk and chunk["similarity"] is not None:
            return max(0.0, min(1.0, float(chunk["similarity"])))
        if "score" in chunk and chunk["score"] is not None:
            s = float(chunk["score"])
            return max(0.0, min(1.0, s))

        # Lexical term overlap fallback
        content = str(chunk.get("text") or chunk.get("plain_text") or chunk.get("content") or "").lower()
        if not content or not query_terms:
            return 0.0

        matches = sum(1 for term in query_terms if term in content)
        return min(1.0, matches / max(1, len(query_terms)))

    def evaluate(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        command: Optional[str] = None,
        allow_web_fallback: bool = True,
    ) -> CRAGEvaluationResult:
        """
        Grades retrieval quality and enforces routing decisions.
        Policy:
        - For /audit: strictly abstain with INSUFFICIENT_EVIDENCE if evidence is inadequate.
        - For /browser or /compare: allow controlled web search fallback if internal evidence is inadequate.
        """
        clean_query = query.strip()
        cmd = (command or "").strip().lower()
        if not cmd and clean_query.startswith("/"):
            cmd = clean_query.split()[0].lower()

        if not chunks or not clean_query:
            if cmd in ["/audit", "audit"]:
                return CRAGEvaluationResult(
                    decision=CRAGDecision.INCORRECT,
                    action=CRAGAction.ABSTAIN_INSUFFICIENT,
                    confidence=0.0,
                    reason="INSUFFICIENT_EVIDENCE: No grounded institutional evidence retrieved for audit inspection.",
                    retained_chunks=[],
                    filtered_out_chunks=[],
                )
            elif cmd in ["/browser", "/compare", "browser", "compare"] and allow_web_fallback:
                return CRAGEvaluationResult(
                    decision=CRAGDecision.INCORRECT,
                    action=CRAGAction.WEB_SEARCH_FALLBACK,
                    confidence=0.0,
                    reason="No local documents retrieved; routing to controlled external web search.",
                    retained_chunks=[],
                    filtered_out_chunks=[],
                )
            else:
                return CRAGEvaluationResult(
                    decision=CRAGDecision.INCORRECT,
                    action=CRAGAction.ABSTAIN_INSUFFICIENT,
                    confidence=0.0,
                    reason="INSUFFICIENT_EVIDENCE: Zero candidate documents retrieved for query.",
                    retained_chunks=[],
                    filtered_out_chunks=[],
                )

        core_query = clean_query
        if clean_query.startswith("/"):
            parts = clean_query.split(maxsplit=1)
            core_query = parts[1].strip() if len(parts) > 1 else ""

        query_terms = self.extract_salient_terms(core_query or clean_query)
        entities = self.extract_entity_mentions(core_query or clean_query)

        scored_chunks: List[tuple[float, Dict[str, Any]]] = []
        for c in chunks:
            chunk_dict = dict(c.metadata if hasattr(c, "metadata") else c)
            if hasattr(c, "page_content"):
                chunk_dict["text"] = c.page_content
            elif "content" in chunk_dict and "text" not in chunk_dict:
                chunk_dict["text"] = chunk_dict["content"]
            score = self.score_chunk_relevance(query_terms, chunk_dict)
            scored_chunks.append((score, chunk_dict))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        retained: List[Dict[str, Any]] = []
        filtered: List[Dict[str, Any]] = []
        for s, c in scored_chunks:
            c_copy = dict(c)
            c_copy["crag_relevance_score"] = round(s, 4)
            if s >= self.min_chunk_relevance:
                retained.append(c_copy)
            else:
                filtered.append(c_copy)

        # Entity coverage analysis
        combined_text = " ".join(
            str(c.get("text") or c.get("plain_text") or c.get("content") or c.get("page_content") or "") for c in retained
        ).lower()

        missing_entities = [e for e in entities if e.lower() not in combined_text]
        entity_coverage = 1.0
        if entities:
            entity_coverage = (len(entities) - len(missing_entities)) / len(entities)

        # Calculate composite confidence
        if retained:
            top_scores = [c["crag_relevance_score"] for c in retained[:3]]
            mean_top = sum(top_scores) / len(top_scores)
            max_score = top_scores[0]
            confidence = (0.50 * max_score) + (0.30 * mean_top) + (0.20 * entity_coverage)
        else:
            confidence = 0.0

        confidence = max(0.0, min(1.0, confidence))

        # Corrective Action Routing
        if confidence >= self.high_threshold and len(missing_entities) == 0:
            return CRAGEvaluationResult(
                decision=CRAGDecision.CORRECT,
                action=CRAGAction.PROCEED,
                confidence=confidence,
                reason="Retrieved evidence demonstrates strong semantic alignment and complete entity grounding.",
                retained_chunks=retained,
                filtered_out_chunks=filtered,
                missing_entities=[],
            )

        elif confidence >= self.low_threshold:
            # AMBIGUOUS
            if cmd in ["/audit", "audit"]:
                if missing_entities or confidence < 0.55:
                    return CRAGEvaluationResult(
                        decision=CRAGDecision.AMBIGUOUS,
                        action=CRAGAction.ABSTAIN_INSUFFICIENT,
                        confidence=confidence,
                        reason=(
                            f"INSUFFICIENT_EVIDENCE: Audit requirement missing key entities {missing_entities} "
                            f"or below deterministic threshold (confidence={confidence:.2f})."
                        ),
                        retained_chunks=retained,
                        filtered_out_chunks=filtered,
                        missing_entities=missing_entities,
                    )
                return CRAGEvaluationResult(
                    decision=CRAGDecision.AMBIGUOUS,
                    action=CRAGAction.PROCEED,
                    confidence=confidence,
                    reason="Audit evidence partially complete; proceeding with strict uncertainty disclosures.",
                    retained_chunks=retained,
                    filtered_out_chunks=filtered,
                    missing_entities=[],
                )
            elif cmd in ["/browser", "/compare", "browser", "compare"] and allow_web_fallback:
                return CRAGEvaluationResult(
                    decision=CRAGDecision.AMBIGUOUS,
                    action=CRAGAction.WEB_SEARCH_FALLBACK,
                    confidence=confidence,
                    reason="Evidence ambiguous; triggering controlled web search to corroborate comparison targets.",
                    retained_chunks=retained,
                    filtered_out_chunks=filtered,
                    missing_entities=missing_entities,
                    suggested_query=f"{clean_query} {' '.join(missing_entities)}".strip(),
                )
            else:
                return CRAGEvaluationResult(
                    decision=CRAGDecision.AMBIGUOUS,
                    action=CRAGAction.EXPAND_GRAPH,
                    confidence=confidence,
                    reason="Evidence ambiguous; triggering relational graph traversal to discover missing bridge nodes.",
                    retained_chunks=retained,
                    filtered_out_chunks=filtered,
                    missing_entities=missing_entities,
                )

        else:
            # INCORRECT / LOW CONFIDENCE
            if cmd in ["/audit", "audit"]:
                return CRAGEvaluationResult(
                    decision=CRAGDecision.INCORRECT,
                    action=CRAGAction.ABSTAIN_INSUFFICIENT,
                    confidence=confidence,
                    reason=(
                        f"INSUFFICIENT_EVIDENCE: Confidence ({confidence:.2f}) falls below required threshold "
                        f"for institutional compliance audit."
                    ),
                    retained_chunks=retained,
                    filtered_out_chunks=filtered,
                    missing_entities=missing_entities,
                )
            elif cmd in ["/browser", "/compare", "browser", "compare"] and allow_web_fallback:
                return CRAGEvaluationResult(
                    decision=CRAGDecision.INCORRECT,
                    action=CRAGAction.WEB_SEARCH_FALLBACK,
                    confidence=confidence,
                    reason="Internal context ungrounded; activating controlled web search fallback.",
                    retained_chunks=retained,
                    filtered_out_chunks=filtered,
                    missing_entities=missing_entities,
                    suggested_query=clean_query,
                )
            else:
                return CRAGEvaluationResult(
                    decision=CRAGDecision.INCORRECT,
                    action=CRAGAction.ABSTAIN_INSUFFICIENT,
                    confidence=confidence,
                    reason="Retrieved passages lack required factual relevance; honest abstention initiated.",
                    retained_chunks=retained,
                    filtered_out_chunks=filtered,
                    missing_entities=missing_entities,
                )


_global_crag_evaluator: Optional[CorrectiveRAGEvaluator] = None


def get_crag_evaluator() -> CorrectiveRAGEvaluator:
    """Returns singleton instance of CorrectiveRAGEvaluator."""
    global _global_crag_evaluator
    if _global_crag_evaluator is None:
        _global_crag_evaluator = CorrectiveRAGEvaluator()
    return _global_crag_evaluator
