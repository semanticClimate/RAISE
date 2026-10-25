"""
Tests for Corrective RAG (CRAG) Evaluator and Hypothetical Document Embeddings (HyDE).
Validates self-reflective grading, routing actions, entity coverage, and fallback mechanisms.
"""

from unittest.mock import MagicMock
import pytest

from src.retrieval.crag_evaluator import (
    CorrectiveRAGEvaluator,
    CRAGAction,
    CRAGDecision,
    get_crag_evaluator,
)
from src.retrieval.hyde import HyDEGenerator


class TestCRAGEvaluator:
    @pytest.fixture
    def evaluator(self):
        return CorrectiveRAGEvaluator(
            high_threshold=0.70,
            low_threshold=0.40,
            min_chunk_relevance=0.25,
        )

    def test_term_extraction_and_entity_mentions(self, evaluator):
        query = "What is the total research grant received by IIT Kharagpur from DST?"
        terms = evaluator.extract_salient_terms(query)
        assert "total" in terms
        assert "grant" in terms
        assert "what" not in terms
        assert "the" not in terms

        entities = evaluator.extract_entity_mentions(query)
        assert "IIT" in entities or "DST" in entities

    def test_score_chunk_relevance_modalities(self, evaluator):
        # Cross encoder score in logit scale
        chunk_logit = {"cross_encoder_score": 2.5, "text": "sample text"}
        s1 = evaluator.score_chunk_relevance(["sample"], chunk_logit)
        assert 0.8 < s1 < 1.0

        # Direct similarity
        chunk_sim = {"similarity": 0.85, "text": "sample text"}
        s2 = evaluator.score_chunk_relevance(["sample"], chunk_sim)
        assert s2 == 0.85

        # Term overlap
        chunk_lexical = {"text": "annual research expenditure and grant details"}
        s3 = evaluator.score_chunk_relevance(["research", "grant"], chunk_lexical)
        assert s3 == 1.0

    def test_empty_retrieval_routing_policy(self, evaluator):
        # /audit must strictly abstain
        res_audit = evaluator.evaluate(
            query="Audit compliance expenditure for 2024",
            chunks=[],
            command="/audit",
        )
        assert res_audit.decision == CRAGDecision.INCORRECT
        assert res_audit.action == CRAGAction.ABSTAIN_INSUFFICIENT
        assert "INSUFFICIENT_EVIDENCE" in res_audit.reason

        # /compare allows web search fallback
        res_compare = evaluator.evaluate(
            query="Compare patent counts between IIT Delhi and IIT Bombay",
            chunks=[],
            command="/compare",
            allow_web_fallback=True,
        )
        assert res_compare.decision == CRAGDecision.INCORRECT
        assert res_compare.action == CRAGAction.WEB_SEARCH_FALLBACK

    def test_high_confidence_retrieval_proceeds(self, evaluator):
        chunks = [
            {
                "text": "Indian Institute of Technology Madras received total external funding of Rs. 400 Crore.",
                "similarity": 0.95,
            },
            {
                "text": "Madras research park funded initiatives under DST and MeitY.",
                "similarity": 0.85,
            },
        ]
        res = evaluator.evaluate(
            query="Indian Institute funding from external grants",
            chunks=chunks,
        )
        assert res.decision == CRAGDecision.CORRECT
        assert res.action == CRAGAction.PROCEED
        assert res.confidence >= 0.70
        assert len(res.retained_chunks) == 2

    def test_ambiguous_retrieval_routing(self, evaluator):
        # Ambiguous score (0.40 <= confidence < 0.70) with command=/compare triggers web fallback
        chunks_ambiguous = [{"text": "General overview of engineering institutions and yield.", "similarity": 0.55}]
        res_compare = evaluator.evaluate(
            query="Compare publication yield",
            chunks=chunks_ambiguous,
            command="/compare",
        )
        assert res_compare.action == CRAGAction.WEB_SEARCH_FALLBACK

        # Ambiguous score on general query triggers graph expansion
        res_general = evaluator.evaluate(
            query="Inter-departmental collaboration network",
            chunks=chunks_ambiguous,
            command=None,
        )
        assert res_general.action == CRAGAction.EXPAND_GRAPH

    def test_singleton_evaluator(self):
        ev1 = get_crag_evaluator()
        ev2 = get_crag_evaluator()
        assert ev1 is ev2


class TestHyDEGenerator:
    def test_hypothetical_passage_generation(self):
        mock_provider = MagicMock()
        mock_provider.is_available = True
        mock_provider.complete.return_value = (
            "According to the official institutional annual report, research grants "
            "totaled Rs. 350 Crore for the academic year 2023-24."
        )

        mock_router = MagicMock()
        mock_router.providers = {"gemini": mock_provider}

        hyde = HyDEGenerator(provider_router=mock_router)
        res = hyde.generate_hypothetical_document("Total research grant allocation")

        assert "350 Crore" in res
        assert mock_provider.complete.call_count == 1

        # Check caching
        res_cached = hyde.generate_hypothetical_document("Total research grant allocation")
        assert res_cached == res
        assert mock_provider.complete.call_count == 1

    def test_hypothetical_passage_generation_legacy_generate(self):
        mock_provider = MagicMock(spec=["is_available", "generate"])
        mock_provider.is_available = True
        mock_provider.generate.return_value = "Hypothetical academic passage via generate."

        mock_router = MagicMock(spec=["get_provider_by_name"])
        mock_router.get_provider_by_name.return_value = mock_provider

        hyde = HyDEGenerator(provider_router=mock_router)
        res = hyde.generate_hypothetical_document("Test query")
        assert "Hypothetical academic passage" in res

    def test_fallback_when_router_fails(self):
        mock_router = MagicMock()
        mock_router.providers = {}
        mock_router.complete.side_effect = RuntimeError("Service unavailable")

        hyde = HyDEGenerator(provider_router=mock_router)
        res = hyde.generate_hypothetical_document("Query with failing router")

        # Falls back to query itself
        assert res == "Query with failing router"

    def test_embedded_slash_command_in_query(self, evaluator=None):
        ev = CorrectiveRAGEvaluator()
        chunk = {"content": "The annual research budget is Rs 500 Crore.", "similarity": 0.85}
        res_audit = ev.evaluate("/audit What is the budget?", [chunk])
        assert res_audit.decision == CRAGDecision.CORRECT

        res_audit_empty = ev.evaluate("/audit What is the budget?", [])
        assert res_audit_empty.action == CRAGAction.ABSTAIN_INSUFFICIENT

    def test_chunk_content_key_extraction(self):
        ev = CorrectiveRAGEvaluator()
        chunk = {"content": "IIT Madras received 400 Crore in grants.", "similarity": 0.90}
        res = ev.evaluate("What is the grant received by IIT Madras?", [chunk])
        assert res.decision == CRAGDecision.CORRECT
        assert len(res.missing_entities) == 0
