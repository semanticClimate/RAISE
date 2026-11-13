"""
RAISE Query Intake & Reformulation Pipeline
===========================================
Component: `src.features.query.intake`
Architecture Layer: Query Processing / Master Intake Orchestrator

Implements the 4-node preprocessing sequence:
  1. Intent Router & Out-of-Scope Firewall: `src.features.query.intent_router`
  2. Coreference Resolution & Pronoun Disambiguation: `src.features.query.coreference`
  3. Query Decomposer & Splitter: `src.features.query.decomposer`
  4. Pipeline Stage Telemetry Tracker: `src.features.query.telemetry`
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Modular re-exports for 100% backward compatibility
from .telemetry import (
    PipelineTelemetry,
    StageRecord,  # noqa: F401
)
from .intent_router import (
    IntentRouteResult,
    IntentRouterNode,
)
from .coreference import (
    CoreferenceResolverNode,
)
from .decomposer import (
    QueryDecomposerNode,
)

logger = logging.getLogger("raise.query.intake")


@dataclass
class QueryIntakeResult:
    """Consolidated outcome of the query intake, coreference, and decomposition pipeline."""
    original_query: str
    standalone_query: str
    decomposed_queries: List[str]
    intent_route: IntentRouteResult
    resolved_entity: Optional[str]
    telemetry: PipelineTelemetry
    corrected_query: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_query": self.original_query,
            "standalone_query": self.standalone_query,
            "corrected_query": self.corrected_query,
            "decomposed_queries": self.decomposed_queries,
            "intent": self.intent_route.intent,
            "datasource": self.intent_route.datasource,
            "is_safe": self.intent_route.is_safe,
            "bypass_retrieval": self.intent_route.bypass_retrieval,
            "direct_response": self.intent_route.direct_response,
            "resolved_entity": self.resolved_entity,
            "pipeline_stages": self.telemetry.to_list(),
        }


class QueryIntakeEngine:
    """
    Orchestrates the entire Query Intake & Reformulation pipeline:
    1. Telemetry start (RECEIVED)
    2. Spelling & Typo Correction / Normalization
    3. Intent Routing & Firewall (ROUTING)
    4. Coreference Resolution (COREFERENCE_RESOLUTION)
    5. Query Decomposition (QUERY_DECOMPOSITION)
    """

    def __init__(self, session_manager: Optional[Any] = None):
        self.session_manager = session_manager
        self.router = IntentRouterNode()
        self.coref = CoreferenceResolverNode(session_manager=session_manager)
        self.decomposer = QueryDecomposerNode()

    def correct_spelling_and_typos(self, query: str) -> str:
        """
        Normalizes and repairs user typos, misspelled keywords, or phonetic errors
        using fast LLM completion before intent classification and search retrieval.
        Preserves named entities, organizational abbreviations (e.g., BRIC, DBT, NABI), and years.
        """
        clean_q = query.strip()
        if not clean_q or len(clean_q) < 4:
            return clean_q

        lower_q = clean_q.lower()
        if any(lower_q.startswith(g) for g in ["hi", "hello", "hey", "good morning", "good evening", "howdy"]):
            return clean_q

        try:
            from src.infrastructure.providers.router import get_provider_router, InferenceTask
            llm_router = get_provider_router()
            system_prompt = (
                "You are an academic search query spell-checker and normalizer for research organizations and institutional annual reports.\n"
                "Task: Correct any obvious typos, spelling mistakes, or letter omissions in the query.\n"
                "Rules:\n"
                "1. Keep all abbreviations and proper nouns intact (e.g., BRIC, DBT, NABI, THSTI, CIAB, NBRC, RCB, NII, IIT, IITMRP, MoES, DST, CSIR).\n"
                "2. Preserve all numbers, years (e.g., 2023-24, 2024, 2025), and financial units.\n"
                "3. If the query already has correct spelling, return it exactly as is.\n"
                "4. Do NOT answer the question, do NOT explain, and do NOT add punctuation or conversational text.\n"
                "5. Return strictly the single corrected query string."
            )
            corrected = llm_router.complete(
                prompt=f"User Query: {clean_q}",
                task=InferenceTask.QUERY_REWRITE,
                system_prompt=system_prompt,
                max_tokens=60,
                temperature=0.0,
            )
            if corrected:
                cleaned = corrected.strip().strip('"\'')
                if (
                    not any(cleaned.startswith(err) for err in ("Inference execution error", "Error executing", "Cloud LLM", "Ollama error"))
                    and "\n" not in cleaned
                    and len(cleaned) >= 2
                    and len(cleaned) <= len(clean_q) * 2
                ):
                    return cleaned
        except Exception as e:
            logger.warning(f"Spell correction failed, falling back to original query: {e}")

        return clean_q

    def process(
        self,
        query: str,
        thread_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> QueryIntakeResult:
        telemetry = PipelineTelemetry()

        # Step 0: Spelling and Typo Normalization
        clean_query = self.correct_spelling_and_typos(query)

        # Step 1: Intent Routing & Out-of-Scope Firewall
        telemetry.start_stage("ROUTING")
        route_res = self.router.route(clean_query)
        telemetry.complete_stage("ROUTING", f"Classified as {route_res.intent} -> {route_res.datasource}")

        # If Out-of-Scope or General Chat, skip database lookups
        if route_res.bypass_retrieval:
            telemetry.skip_stage("COREFERENCE_RESOLUTION", "Zero-DB bypass for out-of-scope/chat")
            telemetry.skip_stage("QUERY_DECOMPOSITION", "Zero-DB bypass for out-of-scope/chat")
            telemetry.skip_stage("VECTOR_RETRIEVAL", "Bypassed")
            telemetry.skip_stage("BM25_RETRIEVAL", "Bypassed")
            telemetry.skip_stage("GRAPH_RETRIEVAL", "Bypassed")
            telemetry.skip_stage("FUSION", "Bypassed")
            telemetry.skip_stage("RERANKING", "Bypassed")
            telemetry.start_stage("SYNTHESIS")
            telemetry.complete_stage("SYNTHESIS", "Direct general response generated")
            telemetry.complete_stage("COMPLETED", "Bypass flow completed")

            return QueryIntakeResult(
                original_query=query,
                standalone_query=clean_query,
                decomposed_queries=[clean_query],
                intent_route=route_res,
                resolved_entity=None,
                telemetry=telemetry,
                corrected_query=clean_query if clean_query != query else None,
            )

        # Step 2: Coreference Resolution
        telemetry.start_stage("COREFERENCE_RESOLUTION")
        standalone, dominant_ent = self.coref.resolve(clean_query, thread_id=thread_id, chat_history=chat_history)
        telemetry.complete_stage(
            "COREFERENCE_RESOLUTION",
            f"Resolved: '{clean_query}' -> '{standalone}'" if dominant_ent else "No pronoun ambiguity",
        )

        # Step 3: Query Decomposition
        telemetry.start_stage("QUERY_DECOMPOSITION")
        decomposed = self.decomposer.decompose(standalone)
        telemetry.complete_stage(
            "QUERY_DECOMPOSITION",
            f"Split into {len(decomposed)} sub-queries: {decomposed}",
        )

        return QueryIntakeResult(
            original_query=query,
            standalone_query=standalone,
            decomposed_queries=decomposed,
            intent_route=route_res,
            resolved_entity=dominant_ent,
            telemetry=telemetry,
            corrected_query=clean_query if clean_query != query else None,
        )
