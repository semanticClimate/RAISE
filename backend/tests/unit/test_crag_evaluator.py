"""
Unit Tests for Corrective Retrieval-Augmented Generation (CRAG) Evaluator
========================================================================
Validates:
1. High-confidence retrieval yielding CORRECT decision and PROCEED action.
2. Moderate-confidence retrieval yielding AMBIGUOUS decision and appropriate branching.
3. Strict policy enforcement:
   - `/audit` strictly abstains with INSUFFICIENT_EVIDENCE.
   - `/browser` and `/compare` trigger WEB_SEARCH_FALLBACK.
4. Pruning of irrelevant chunks below relevance thresholds.
"""

import pytest
from src.retrieval.crag_evaluator import (
    CorrectiveRAGEvaluator,
    CRAGDecision,
    CRAGAction,
    get_crag_evaluator,
)


@pytest.mark.unit
def test_crag_evaluator_singleton():
    """Verifies singleton accessor returns instance."""
    ev1 = get_crag_evaluator()
    ev2 = get_crag_evaluator()
    assert ev1 is ev2
    assert isinstance(ev1, CorrectiveRAGEvaluator)


@pytest.mark.unit
def test_crag_empty_chunks_audit_abstention():
    """Verifies /audit command strictly abstains when zero chunks are provided."""
    evaluator = CorrectiveRAGEvaluator()
    res = evaluator.evaluate(
        query="Verify compliance of Section 4 grants",
        chunks=[],
        command="/audit",
    )
    assert res.decision == CRAGDecision.INCORRECT
    assert res.action == CRAGAction.ABSTAIN_INSUFFICIENT
    assert "INSUFFICIENT_EVIDENCE" in res.reason


@pytest.mark.unit
def test_crag_empty_chunks_browser_fallback():
    """Verifies /browser command falls back to controlled web search when zero chunks are provided."""
    evaluator = CorrectiveRAGEvaluator()
    res = evaluator.evaluate(
        query="Latest national ranking of the university",
        chunks=[],
        command="/browser",
        allow_web_fallback=True,
    )
    assert res.decision == CRAGDecision.INCORRECT
    assert res.action == CRAGAction.WEB_SEARCH_FALLBACK


@pytest.mark.unit
def test_crag_correct_evaluation():
    """Verifies high-relevance chunks trigger CORRECT decision and PROCEED action."""
    evaluator = CorrectiveRAGEvaluator(high_threshold=0.65)
    query = "What is the endowment fund balance for BRIC Institute?"
    chunks = [
        {
            "id": "c1",
            "text": "The BRIC Institute endowment fund balance closed at Rs 120 crore for FY 2024.",
            "similarity": 0.88,
        },
        {
            "id": "c2",
            "text": "BRIC Institute research grants and endowment funds allocation schedule.",
            "similarity": 0.75,
        },
    ]

    res = evaluator.evaluate(query=query, chunks=chunks, command="/chat")
    assert res.decision == CRAGDecision.CORRECT
    assert res.action == CRAGAction.PROCEED
    assert res.confidence >= 0.65
    assert len(res.retained_chunks) == 2


@pytest.mark.unit
def test_crag_ambiguous_audit_strict_abstention_on_missing_entity():
    """Verifies /audit strictly abstains if required query entities are missing from ambiguous context."""
    evaluator = CorrectiveRAGEvaluator(high_threshold=0.75, low_threshold=0.35)
    query = "Audit expenditure report for NABI Genomics Center"
    # Chunks mention expenditure but miss NABI Genomics Center
    chunks = [
        {
            "id": "c1",
            "text": "General institutional expenditure report covering maintenance and utilities.",
            "similarity": 0.50,
        }
    ]

    res = evaluator.evaluate(query=query, chunks=chunks, command="/audit")
    assert res.action == CRAGAction.ABSTAIN_INSUFFICIENT
    assert "INSUFFICIENT_EVIDENCE" in res.reason


@pytest.mark.unit
def test_crag_ambiguous_compare_triggers_web_search():
    """Verifies /compare command allows controlled web search fallback when evidence is ambiguous."""
    evaluator = CorrectiveRAGEvaluator(high_threshold=0.80, low_threshold=0.30)
    query = "Compare NIRF ranking of Institute A versus Institute B"
    chunks = [
        {
            "id": "c1",
            "text": "Institute A participated in national framework exercises.",
            "similarity": 0.45,
        }
    ]

    res = evaluator.evaluate(query=query, chunks=chunks, command="/compare", allow_web_fallback=True)
    assert res.decision == CRAGDecision.AMBIGUOUS
    assert res.action == CRAGAction.WEB_SEARCH_FALLBACK
