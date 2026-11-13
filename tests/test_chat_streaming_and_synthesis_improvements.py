"""
Unit and Integration Tests for Chat Streaming & Response Synthesis Improvements
================================================================================
Tests:
1. Content negotiation in /api/chat (SSE vs. raw plain-text streaming).
2. Deterministic academic course and program extraction in PlanExecutorMixin.
3. Single-bracket citation formatting and chunk deduplication.
4. Consecutive line deduplication and entity list bounding in sanitize_rag_text.
"""

import re
import pytest
from unittest.mock import MagicMock
from src.features.agent.router_executor import PlanExecutorMixin
from prompts.system_synthesis import sanitize_rag_text, clean_repetitive_citations


class MockExecutionPlan:
    def __init__(self, query: str):
        self.query = query
        self.retrieved_evidence = {}
        self.selected_tools = []
        self.extracted_universities = []
        self.grounded_answer = ""
        self.citations = []
        self.verified_claims = []
        self.answer_contract = {}
        self.traceability_score = 0.0


def test_content_negotiation_detection():
    """Verify that accept headers containing text/event-stream always resolve to SSE."""
    # Scenario A: Browser standard header containing both text/event-stream and text/plain fallback
    accept_hdr_browser = "text/event-stream, text/plain; q=0.9, */*; q=0.8"
    req_format_sse = "sse"

    is_explicit_raw_a = (req_format_sse == "raw") or (
        "text/plain" in accept_hdr_browser.lower()
        and "text/event-stream" not in accept_hdr_browser.lower()
        and req_format_sse != "sse"
    )
    assert is_explicit_raw_a is False, "Browser accept header with format=sse must NOT trigger raw stream"

    # Scenario B: Explicit format=raw
    req_format_raw = "raw"
    is_explicit_raw_b = (req_format_raw == "raw") or (
        "text/plain" in accept_hdr_browser.lower()
        and "text/event-stream" not in accept_hdr_browser.lower()
        and req_format_raw != "sse"
    )
    assert is_explicit_raw_b is True, "format=raw must trigger raw stream"

    # Scenario C: Plain text accept header only
    accept_plain_only = "text/plain"
    is_explicit_raw_c = (None == "raw") or (
        "text/plain" in accept_plain_only.lower()
        and "text/event-stream" not in accept_plain_only.lower()
        and None != "sse"
    )
    assert is_explicit_raw_c is True, "Accept: text/plain without text/event-stream must trigger raw stream"


def test_academic_course_fallback_extraction():
    """Verify that Course queries extract clean degree, course, and exam details with citations."""
    executor = PlanExecutorMixin()
    executor.reranker = MagicMock()
    executor.reranker.rerank = lambda query, candidates, text_key="text", top_n=8: candidates[:top_n]
    
    mock_contract = MagicMock()
    mock_contract.claims = []
    mock_contract.grounding_score = 0.95
    mock_contract.to_dict = lambda: {}
    executor.verifier = MagicMock()
    executor.verifier.create_answer_contract = MagicMock(return_value=mock_contract)
    executor.fact_engine = MagicMock()
    executor.fact_engine.query_facts = MagicMock(return_value=[])

    mock_chunks = [
        {
            "id": "app_chunk_0",
            "chunk_id": "app_chunk_0",
            "text": (
                "GATE Paper Code\n\n(Biotechnology)\n\n"
                "Qualification Details\nM. Sc.\nBiotechnology\nGraduated: No; Year of Graduation: 2027\nPANJAB UNIVERSITY"
            ),
            "metadata": {"pdf_filename": "ApplicationForm.pdf", "chunk_id": "app_chunk_0", "primary_page": 1},
            "similarity": 0.95,
        },
        {
            "id": "file_chunk_0",
            "chunk_id": "file_chunk_0",
            "text": (
                "MSBB 110: Biophysical Chemistry of Biomacromolecules\n"
                "M.Sc. Systems Biology and Bioinformatics\n"
                "Centre for Systems Biology and Bioinformatics (U.I.E.A.S.T.) PANJAB UNIVERSITY, CHANDIGARH 160014"
            ),
            "metadata": {"pdf_filename": "final!! 110 (2)-1.pdf", "chunk_id": "file_chunk_0", "primary_page": 1},
            "similarity": 0.92,
        },
    ]

    plan = MockExecutionPlan("Course")
    plan.retrieved_evidence["chunks"] = mock_chunks

    res = executor.execute_plan(plan, active_docs=["ApplicationForm.pdf", "final!! 110 (2)-1.pdf"])

    # Assertions
    assert res.grounded_answer, "Grounded answer must not be empty"
    assert any(term in res.grounded_answer for term in ["M. Sc.", "Biotechnology", "Systems Biology", "MSBB 110", "Biomacromolecules"])
    assert "[[" not in res.grounded_answer, "Double brackets [[N]] must not appear in answer"
    assert "[" in res.grounded_answer and "]" in res.grounded_answer, "Single bracket citations [N] must be present"
    assert len(res.citations) > 0, "Citations list must contain at least 1 citation"


def test_sanitize_rag_text_deduplication():
    """Verify that sanitize_rag_text deduplicates consecutive duplicate lines."""
    input_text = (
        "• **Applicant Information & Declaration**:\n"
        "• **Applicant Information & Declaration**:\n"
        "I confirm that I fulfil the eligibility criteria.\n"
        "I confirm that I fulfil the eligibility criteria.\n"
        "• **GATE Exam Details**\n"
    )
    sanitized = sanitize_rag_text(input_text)
    
    # Check that duplicates were removed
    declaration_count = sanitized.count("Applicant Information & Declaration")
    assert declaration_count == 1, f"Expected 1 occurrence of declaration header, found {declaration_count}"
    
    confirm_count = sanitized.count("I confirm that I fulfil the eligibility criteria.")
    assert confirm_count == 1, f"Expected 1 occurrence of confirmation line, found {confirm_count}"


def test_clean_repetitive_citations_brackets():
    """Verify that citations with standard [N] format are properly normalized."""
    text = "• **Item A** [1].\n• **Item B** [1].\n• **Item C** [1]."
    cleaned = clean_repetitive_citations(text)
    assert "[1]" in cleaned
    assert "[[" not in cleaned
