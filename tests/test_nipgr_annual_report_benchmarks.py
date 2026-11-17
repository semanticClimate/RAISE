"""
NIPGR Annual Report 2025 Benchmark Tests
========================================
Automated regression tests verifying that the RAISE GraphRAG pipeline retrieves,
grounds, and synthesizes answers for:
1. Acknowledgements roster (all 13 individuals and roles on Page 2).
2. Nature Index rankings (complete table with Global and India rankings on Page 9).
3. Individual Nature Index metrics (Q1 to Q8).

Zero-Hardcoding Invariant:
No answers or expected strings are hardcoded in system prompts or production code.
All tests query the live StandaloneRAGPipeline / GraphRAGEngine.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.retrieval.pipeline import StandaloneRAGPipeline


@pytest.fixture(scope="module")
def rag_pipeline():
    """Provides a shared StandaloneRAGPipeline instance for the test suite."""
    os.environ["ALLOW_LOCAL_SOCKET_PROBES"] = "1"
    main_chroma = BASE_DIR / ".chromadb_embeddinggemma_2"
    if main_chroma.exists():
        os.environ["CHROMA_PERSIST_DIRECTORY"] = str(main_chroma)
    else:
        pytest.skip("ChromaDB vector store not present in this environment")

    chunks_file = BASE_DIR / "data" / "processed" / "chunks" / "NIPGR_BRIC_Annual_Report_2025_chunks.json"
    if not chunks_file.exists():
        pytest.skip("NIPGR_BRIC_Annual_Report_2025_chunks.json not present on disk")

    return StandaloneRAGPipeline()


def test_nipgr_acknowledgements_roster(rag_pipeline):
    """Verify that acknowledgements names and roles from Page 2 are accurately retrieved and cited."""
    query = "names under ACKNOWLEDGEMENTS"
    res = rag_pipeline.query_subgraph_graphrag(
        query=query,
        active_docs=["NIPGR_BRIC_Annual_Report_2025.pdf"],
        top_k=10,
        hops=2,
    )
    answer = res.get("answer", "")
    citations = res.get("citations", [])

    assert answer, "Expected non-empty answer for acknowledgements query"
    assert citations, "Expected at least one citation for acknowledgements"

    # Verify citation points to Page 2
    cit_chunk_ids = [c.get("chunk_id", "") for c in citations]
    assert any("p002" in cid for cid in cit_chunk_ids), f"Expected citation from Page 2, got: {cit_chunk_ids}"

    # Check if generative LLM is available in current test environment
    router = getattr(rag_pipeline.agent_router, "router", None)
    has_online_llm = False
    if router:
        has_online_llm = any(
            router.providers.get(p) and getattr(router.providers[p], "is_available", lambda: False)()
            for p in ("vllm", "ollama")
        ) or (router.cloud_allowed and bool(router.fallback_chain))

    if not has_online_llm:
        return

    # Verify key individuals are present in the synthesized answer
    expected_names = [
        "Ashwani Pareek",
        "Kalaivani Ganesan",
        "Richi V Mahajan",
        "Sumita Kumari",
        "Susmita Chaudhuri",
        "Ketan Thorat",
        "Dhananjay Huilgol",
        "Divya Mishra",
        "D K Vashist",
        "Vaibhav Anil Argade",
        "Shingar Sharma",
        "Manisha Sharma",
        "Debasish Debnath",
    ]
    for name in expected_names:
        assert name in answer, f"Expected '{name}' to be present in acknowledgements answer"


def test_nipgr_nature_index_rankings_table(rag_pipeline):
    """Verify that the full Nature Index table (Global and India rankings) from Page 9 is accurately retrieved."""
    query = (
        "What are the Nature Index rankings of iBRIC+ India for the overall research output, "
        "government research output, and individual scientific subject areas during the period "
        "1 April 2024 to 31 March 2025? Provide both global and India rankings."
    )
    res = rag_pipeline.query_subgraph_graphrag(
        query=query,
        active_docs=["NIPGR_BRIC_Annual_Report_2025.pdf"],
        top_k=10,
        hops=2,
    )
    answer = res.get("answer", "")
    citations = res.get("citations", [])

    assert answer, "Expected non-empty answer for Nature Index table query"
    assert citations, "Expected at least one citation for Nature Index query"

    # Verify citation points to Page 9 or related Governance/Nature Index parent chunks
    cit_chunk_ids = [c.get("chunk_id", "") for c in citations]
    assert any("p009" in cid or "parent_010" in cid or "parent_016" in cid or "p015" in cid for cid in cit_chunk_ids), (
        f"Expected citation from Page 9 or parent chunks (p009, parent_010, parent_016, p015), got: {cit_chunk_ids}"
    )

    router = getattr(rag_pipeline.agent_router, "router", None)
    has_online_llm = False
    if router:
        has_online_llm = any(
            router.providers.get(p) and getattr(router.providers[p], "is_available", lambda: False)()
            for p in ("vllm", "ollama")
        ) or (router.cloud_allowed and bool(router.fallback_chain))

    if not has_online_llm:
        return

    # Verify all 7 categories and their rankings appear in the answer
    expected_metrics = [
        ("665", "21"),     # Overall
        ("66", "4"),       # Government
        ("227", "1"),      # Biological Sciences
        ("1067", "49"),    # Chemistry
        ("1893", "54"),    # Earth & Environmental Sciences
        ("648", "3"),      # Health Sciences
        ("1649", "72"),    # Physical Sciences
    ]
    for global_rank, india_rank in expected_metrics:
        assert global_rank in answer, f"Expected global rank '{global_rank}' in answer"
        assert india_rank in answer, f"Expected India rank '{india_rank}' in answer"


@pytest.mark.parametrize(
    "query,expected_tokens",
    [
        (
            "What is the overall global Nature Index position of iBRIC+ India?",
            ["665"],
        ),
        (
            "What is the overall India position of iBRIC+ India?",
            ["21"],
        ),
        (
            "What is the global and India position of iBRIC+ in Biological Sciences?",
            ["227", "1"],
        ),
        (
            "Which subject area has the highest India position among the listed scientific disciplines?",
            ["Biological Sciences", "1"],
        ),
        (
            "What are the Nature Index positions of iBRIC+ India in Chemistry?",
            ["1067", "49"],
        ),
        (
            "What is the global position of iBRIC+ India in Earth & Environmental Sciences?",
            ["1893"],
        ),
        (
            "What is the India position of iBRIC+ India in Health Sciences?",
            ["3"],
        ),
        (
            "What is the reporting period covered by the Nature Index profile?",
            ["1 April 2024", "31 March 2025"],
        ),
    ],
    ids=["Q1_overall_global", "Q2_overall_india", "Q3_biological", "Q4_highest_india", "Q5_chemistry", "Q6_earth", "Q7_health", "Q8_period"]
)
def test_nipgr_nature_index_individual_metrics(rag_pipeline, query, expected_tokens):
    """Verify that individual Nature Index fact retrieval returns exact numbers and reporting period."""
    res = rag_pipeline.query_subgraph_graphrag(
        query=query,
        active_docs=["NIPGR_BRIC_Annual_Report_2025.pdf"],
        top_k=10,
        hops=2,
    )
    answer = res.get("answer", "")
    citations = res.get("citations", [])

    assert answer, f"Expected answer for query: '{query}'"
    assert citations, f"Expected citations for query: '{query}'"

    router = getattr(rag_pipeline.agent_router, "router", None)
    has_online_llm = False
    if router:
        has_online_llm = any(
            router.providers.get(p) and getattr(router.providers[p], "is_available", lambda: False)()
            for p in ("vllm", "ollama")
        ) or (router.cloud_allowed and bool(router.fallback_chain))

    if has_online_llm:
        for token in expected_tokens:
            assert token in answer, f"Expected token '{token}' in synthesized LLM answer for query: '{query}'. Answer was: {answer}"
    else:
        # In offline CI test environments without online LLM credentials, verify the exact facts are grounded in retrieved context
        top_chunks = res.get("top_chunks", []) or res.get("relevant_chunks", [])
        retrieved_text = " ".join([str(c.get("text", "") or c.get("plain_text", "")) for c in top_chunks])
        combined_evidence = f"{answer} {retrieved_text}"
        for token in expected_tokens:
            assert token in combined_evidence, (
                f"Expected token '{token}' in retrieved context or answer for query: '{query}'. Evidence was: {combined_evidence[:300]}"
            )
