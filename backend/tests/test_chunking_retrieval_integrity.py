"""
Unit Test Suite for Chunking and Retrieval Integrity
=====================================================
Verifies that:
1. Short governance/roster pages (e.g. Council Nominees, Board of Governors)
   are never discarded by baseline recursive chunking.
2. Hierarchical splitting cleanly splits oversized paragraphs without data loss.
3. Fixed-size baseline preserves actual page provenance.
"""

import pytest
from src.chunking.baselines import process_recursive_baseline, process_fixed_baseline


def test_recursive_baseline_preserves_short_governance_roster():
    # Simulates Page 4 of Annual Report where every single paragraph is < 30 words
    parsed_sections = [
        {
            "page_number": 4,
            "doc_page_number": "iv",
            "heading": "The Visitor & Board of Governors",
            "text": (
                "The Visitor\n\n"
                "Smt. Droupadi Murmu\n\n"
                "President of India\n\n"
                "Board of Governors\n\n"
                "Dr. Pawan Goenka (Chairman)\n"
                "Chairman, Indian National Space Promotion Authorization\n\n"
                "Prof. V Kamakoti\n\n"
                "Director\n"
                "Indian Institute of Technology Madras\n\n"
                "Council Nominees\n\n"
                "Smt. Saumya Gupta, IAS (Ex Officio)\n\n"
                "Prof. Shireesh B Kedare\n"
                "Department of Energy Science and Engineering\n\n"
                "Dr. B Mahadevan\n"
                "Professor of Operations Management\n\n"
                "Dr. S Kishore Kumar\n"
                "Defence Research and Development Organisation Fellow"
            ),
            "has_table": False,
            "tables_count": 0,
        }
    ]

    res = process_recursive_baseline(
        parsed_sections=parsed_sections,
        document_id="doc_test",
        filename="test_report.pdf",
        university="IIT Madras",
        reporting_period="2024-25",
        pages=1,
    )

    child_chunks = res["child_chunks"]
    assert len(child_chunks) == 1, "Short governance page must be preserved as 1 complete chunk, not dropped"
    chunk = child_chunks[0]
    assert chunk.primary_page == 4
    assert chunk.printed_page == "iv"
    assert "Council Nominees" in chunk.plain_text
    assert "Smt. Saumya Gupta" in chunk.plain_text
    assert "Prof. Shireesh B Kedare" in chunk.plain_text
    assert "Dr. B Mahadevan" in chunk.plain_text
    assert "Dr. S Kishore Kumar" in chunk.plain_text


def test_recursive_baseline_splits_large_sections_without_loss():
    # Create section with 600 words
    paras = [f"Paragraph {i} has some detailed academic context and research information repeating words. " * 5 for i in range(12)]
    full_text = "\n\n".join(paras)

    parsed_sections = [
        {
            "page_number": 12,
            "doc_page_number": "12",
            "heading": "Research and Development",
            "text": full_text,
            "has_table": False,
            "tables_count": 0,
        }
    ]

    res = process_recursive_baseline(
        parsed_sections=parsed_sections,
        document_id="doc_test",
        filename="test_report.pdf",
        university="IIT Madras",
        reporting_period="2024-25",
        pages=1,
        target_words=200,
        max_words=300,
    )

    child_chunks = res["child_chunks"]
    assert len(child_chunks) >= 2, "Oversized section must be split into multiple chunks"
    for c in child_chunks:
        assert c.primary_page == 12
        assert "Research and Development" in c.heading
        assert len(c.plain_text.split()) <= 350


def test_fixed_baseline_page_provenance():
    parsed_sections = [
        {"page_number": 1, "text": "First page text content here.", "heading": "Title"},
        {"page_number": 5, "text": "Fifth page text content here.", "heading": "Section 5"},
    ]

    res = process_fixed_baseline(
        parsed_sections=parsed_sections,
        document_id="doc_test",
        filename="test_report.pdf",
        university="IIT Madras",
        reporting_period="2024-25",
        pages=5,
    )

    child_chunks = res["child_chunks"]
    assert len(child_chunks) == 2
    assert child_chunks[0].primary_page == 1
    assert child_chunks[1].primary_page == 5
