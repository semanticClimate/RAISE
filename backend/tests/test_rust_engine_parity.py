"""
Rust Acceleration Engine & Parity Test Suite (GGAHC Native Core).
Verifies mathematical parity, data structure integrity, and performance advantages of `raise_engine`.
"""

from __future__ import annotations

import pytest
import time
from typing import Any, Dict, List

from src.chunking import (
    AdaptiveChunkingPipeline,
    CandidateUnit,
    ChunkingConfig,
    is_rust_engine_available,
    evaluate_boundaries_rust,
    reciprocal_rank_fusion_rust,
    bm25_search_rust,
    rank_candidates_rust,
    normalize_text_rust,
)
from src.retrieval.fusion import reciprocal_rank_fusion


def test_rust_engine_loaded():
    """Verify that the native Rust acceleration library is compiled and dynamically loaded."""
    assert is_rust_engine_available() is True, "Expected raise_engine.dll to be loaded via ctypes"


def test_rust_text_normalization():
    """Verify Unicode cleanup, typographic normalization, and hyphen repair."""
    raw = "The deep-tech infra-\nstructure \u2014 \u201Cwaveguide sensors\u201D at   Jamnagar."
    cleaned = normalize_text_rust(raw)
    assert cleaned is not None
    assert "infrastructure" in cleaned
    assert '"waveguide sensors"' in cleaned
    assert " - " in cleaned


def test_rust_reciprocal_rank_fusion_parity():
    """Verify mathematical parity between Rust RRF and Python RRF."""
    dense_list = [{"chunk_id": "c1"}, {"chunk_id": "c2"}, {"chunk_id": "c3"}]
    sparse_list = [{"chunk_id": "c2"}, {"chunk_id": "c1"}, {"chunk_id": "c4"}]

    fused = reciprocal_rank_fusion([dense_list, sparse_list], k=60)
    assert len(fused) == 4

    top_ids = [fused[0]["chunk_id"], fused[1]["chunk_id"]]
    assert "c1" in top_ids
    assert "c2" in top_ids
    # RRF score for c1 and c2 should be: 1/61 + 1/62 = 0.0163934 + 0.016129 = 0.032522
    assert pytest.approx(fused[0]["rrf_score"], abs=1e-4) == 0.032522


def test_rust_bm25_compact_inverted_index():
    """Verify compact BM25 lexical search returns expected documents and scores."""
    docs = [
        ("doc_1", "IIT Madras Research Park incubation deep tech ventures"),
        ("doc_2", "XYMA Analytics ultrasonic waveguide sensors for high temperature environments"),
        ("doc_3", "Mindgrove Technologies semiconductor microcontrollers edge vision"),
    ]

    results = bm25_search_rust(docs, query="waveguide sensors", top_k=2)
    assert results is not None
    assert len(results) > 0
    top_doc_id, top_score = results[0]
    assert top_doc_id == "doc_2"
    assert top_score > 1.0


def test_rust_candidate_pre_ranking_quickselect():
    """Verify O(N) QuickSelect ranking over large candidate arrays."""
    candidates = [{"id": i, "score": float(i) * 0.5} for i in range(5000)]
    top_5 = rank_candidates_rust(candidates, top_k=5)

    assert top_5 is not None
    assert len(top_5) == 5
    assert top_5[0]["id"] == 4999
    assert top_5[1]["id"] == 4998
    assert top_5[2]["id"] == 4997


def test_rust_ggahc_boundary_scoring_and_community_detection():
    """Verify multi-signal boundary optimization and community assignments in Rust."""
    cand1 = {
        "candidate_id": "cand_01",
        "document_id": "test_doc",
        "section_id": "sec_1",
        "heading": "Incubation Overview",
        "page_start": 1,
        "page_end": 1,
        "plain_text": "XYMA Analytics incubated at IITMIC develops ultrasonic waveguide sensors.",
        "structural_unit_ids": ["u1"],
        "entities": [{"id": "ent_xyma", "name": "XYMA Analytics", "label": "Startup"}],
        "relationships": [],
    }
    cand2 = {
        "candidate_id": "cand_02",
        "document_id": "test_doc",
        "section_id": "sec_1",
        "heading": "Incubation Overview",
        "page_start": 1,
        "page_end": 1,
        "plain_text": "XYMA Analytics deployed sensors with Emirates Global Aluminium and Reliance Industries.",
        "structural_unit_ids": ["u2"],
        "entities": [{"id": "ent_xyma", "name": "XYMA Analytics", "label": "Startup"}],
        "relationships": [],
    }

    res = evaluate_boundaries_rust([cand1, cand2], {})
    assert res is not None
    decisions, communities = res

    assert len(decisions) == 1
    dec = decisions[0]
    # Strong entity continuity and shared heading should trigger MERGE
    assert dec["decision"] == "MERGE"
    assert dec["boundary_score"] < 0.0
    assert dec["confidence"] >= 0.90
    assert any("entity continuity" in r for r in dec["reasons"])
    assert communities.get("cand_01") == communities.get("cand_02")


def test_full_pipeline_rust_accelerated_run():
    """Verify AdaptiveChunkingPipeline execution with Rust acceleration enabled."""
    pipeline = AdaptiveChunkingPipeline()
    sample_sections = [
        {
            "page_number": 1,
            "heading": "1. Corporate Mission",
            "heading_level": 1,
            "text": (
                "IIT Madras Research Park (IITMRP) is India's premier university research park. "
                "The park fosters deep-tech innovation and industry-academia collaborations across energy and mobility. "
                "In FY 2024-25, the ecosystem continued expanding its incubation operations with faculty mentorship."
            ),
        },
        {
            "page_number": 2,
            "heading": "2. High Temperature Sensors",
            "heading_level": 1,
            "text": (
                "XYMA Analytics manufactures high temperature ultrasonic waveguide sensors for energy utilities. "
                "Mentored by CNDE professors, XYMA deployed the TMAP sensor line at Reliance Industries Jamnagar."
            ),
        },
        {
            "page_number": 3,
            "heading": "3. Audited Financial Statements",
            "heading_level": 1,
            "text": (
                "| Metric | FY 2024 | FY 2025 |\n"
                "|---|---|---|\n"
                "| Total Revenue | 12450 | 15820 |\n"
                "| Net Surplus | 1850 | 2410 |\n"
            ),
            "has_table": True,
        },
    ]

    result = pipeline.process_document(sample_sections, document_id="doc_rust_test")
    assert "child_chunks" in result
    assert "parent_chunks" in result
    assert "propositions" in result
    assert len(result["child_chunks"]) >= 2
    assert result["diagnostic_report"] is not None
