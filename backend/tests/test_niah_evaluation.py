"""
RAISE Test Suite — Needle-in-a-Haystack (NIAH) Automated Test Suite
Validates:
  1. Strict Database Isolation (Production ChromaDB and Neo4j remain untouched)
  2. Deterministic Corpus & Haystack Assembly across fractional depths
  3. Chunking sensitivity (chunk sizes and overlaps)
  4. Embedding representation probe (needle vs distractor margin)
  5. ChromaDB vector retrieval probe (top-k recall)
  6. CrossEncoder reranker probe
  7. Knowledge graph multi-hop traversal probe
  8. Scientific failure attribution decision tree
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings
from src.infrastructure.vector.chroma import LocalVectorEngine
from src.infrastructure.graph.neo4j import Neo4jDatabase

from evaluation.benchmarks.niah.needle_catalog import (
    NeedleCase,
    NeedleType,
    get_needle,
    list_available_needles,
)
from evaluation.benchmarks.niah.haystack_generator import HaystackGenerator
from evaluation.benchmarks.niah.corpus_builder import CorpusBuilder
from evaluation.benchmarks.niah.chunking_simulator import ChunkingSimulator
from evaluation.benchmarks.niah.isolation_harness import (
    NIAHIsolationHarness,
    IsolatedVectorHarness,
    IsolatedGraphHarness,
)
from evaluation.benchmarks.niah.component_probes import (
    EmbeddingProbe,
    ChromaDBProbe,
    RerankerProbe,
    GraphTraversalProbe,
    LLMGenerationProbe,
)
from evaluation.benchmarks.niah.failure_attributor import FailureAttributor, FailureStage


# =============================================================================
# 1. STRICT DATABASE ISOLATION GUARANTEE
# =============================================================================
def test_isolation_guarantee():
    """
    Verifies that running NIAH evaluation tests does NOT write to, delete from,
    or modify the production ChromaDB collection or production data directory.
    """
    prod_vector = LocalVectorEngine()
    initial_prod_count = prod_vector.count()

    # Run isolated NIAH experiment
    needle = get_needle("fact_quantum_crypt")
    builder = CorpusBuilder(HaystackGenerator(seed=100))
    corpus = builder.build_corpus(needle=needle, target_words=1000, depth=0.50)
    chunked = ChunkingSimulator.chunk_corpus(corpus=corpus, chunk_size=300)

    with NIAHIsolationHarness() as harness:
        # Ingest into isolated harness
        ingested = harness.vector_harness.ingest_simulated_chunks(chunked)
        assert ingested > 0
        assert harness.vector_harness.collection.count() == chunked.total_chunks

        # Query isolated harness
        hits = harness.vector_harness.query(query=needle.query, top_k=5)
        assert len(hits) > 0

    # Verify production collection was NEVER modified
    final_prod_count = prod_vector.count()
    assert initial_prod_count == final_prod_count, (
        f"CRITICAL ISOLATION VIOLATION: Production collection count changed from {initial_prod_count} to {final_prod_count}!"
    )


# =============================================================================
# 2. NEEDLE CATALOG & CORPUS BUILDER
# =============================================================================
def test_needle_catalog_and_validation():
    """Verify all standard needles have valid queries and answer validation logic."""
    available = list_available_needles()
    assert len(available) >= 4

    fact_needle = get_needle("fact_quantum_crypt")
    assert fact_needle.is_answer_in_text("The secret code is DELTA-9842-OMEGA.")
    assert not fact_needle.is_answer_in_text("The secret code is ALPHA-1234-BETA.")

    quant_needle = get_needle("quant_photonic_grant")
    assert quant_needle.is_answer_in_text("The grant was ₹42.75 Crore.")
    assert not quant_needle.is_answer_in_text("The grant was 10 Crore.")


def test_haystack_generator_and_corpus_depths():
    """Verify deterministic corpus assembly and needle depth positioning."""
    gen = HaystackGenerator(seed=42)
    paras = gen.generate_haystack(target_words=1000)
    total_words = sum(len(p.split()) for p in paras)
    assert total_words >= 1000

    builder = CorpusBuilder(generator=gen)
    needle = get_needle("fact_quantum_crypt")

    # Test insertion at beginning (0%), middle (50%), and end (100%)
    for depth in [0.0, 0.50, 1.00]:
        corpus = builder.build_corpus(needle=needle, target_words=1500, depth=depth)
        assert needle.needle_text in corpus.full_text
        assert corpus.needle_char_start >= 0

        if depth == 0.0:
            assert corpus.needle_paragraph_idx == 0
            assert corpus.depth_actual <= 0.05
        elif depth == 1.00:
            assert corpus.needle_paragraph_idx == len(corpus.paragraphs) - 1
            assert corpus.depth_actual >= 0.90
        else:
            assert 0.40 <= corpus.depth_actual <= 0.60


# =============================================================================
# 3. CHUNKING SENSITIVITY & OVERLAP
# =============================================================================
def test_chunking_sensitivity():
    """Verify chunking simulator tracking and overlap handling."""
    needle = get_needle("fact_quantum_crypt")
    builder = CorpusBuilder(HaystackGenerator(seed=42))
    corpus = builder.build_corpus(needle=needle, target_words=2000, depth=0.50)

    # 1. 450 words chunk, 0 overlap
    chunked_450 = ChunkingSimulator.chunk_corpus(corpus=corpus, chunk_size=450, chunk_overlap=0.0)
    assert chunked_450.total_chunks > 0
    assert len(chunked_450.gold_chunk_ids) >= 1
    assert chunked_450.primary_gold_chunk_id in chunked_450.gold_chunk_ids

    # 2. 150 words chunk, 20% overlap
    chunked_150 = ChunkingSimulator.chunk_corpus(corpus=corpus, chunk_size=150, chunk_overlap=0.20)
    assert chunked_150.total_chunks > chunked_450.total_chunks
    assert len(chunked_150.gold_chunk_ids) >= 1


# =============================================================================
# 4. COMPONENT PROBE: EMBEDDING REPRESENTATION
# =============================================================================
def test_embedding_representation_probe():
    """Verify embedding probe correctly calculates cosine similarity margin."""
    with NIAHIsolationHarness() as harness:
        needle = get_needle("fact_quantum_crypt")
        distractors = HaystackGenerator(seed=42).generate_haystack(target_words=1000)

        result = EmbeddingProbe.evaluate(
            vector_harness=harness.vector_harness,
            needle_case=needle,
            distractor_paragraphs=distractors,
        )

        assert result.needle_rank == 1
        assert result.similarity_margin > 0.0
        assert result.representation_success is True


# =============================================================================
# 5. COMPONENT PROBE: CHROMADB RETRIEVAL
# =============================================================================
def test_chromadb_retrieval_probe():
    """Verify ChromaDB probe returns top-k recall and gold rank."""
    needle = get_needle("fact_quantum_crypt")
    builder = CorpusBuilder(HaystackGenerator(seed=42))
    corpus = builder.build_corpus(needle=needle, target_words=2000, depth=0.50)
    chunked = ChunkingSimulator.chunk_corpus(corpus=corpus, chunk_size=450)

    with NIAHIsolationHarness() as harness:
        result = ChromaDBProbe.evaluate(
            vector_harness=harness.vector_harness,
            chunked_corpus=chunked,
            needle_case=needle,
            top_k=5,
        )

        assert result.top_k_recall is True
        assert result.gold_rank == 1
        assert result.gold_similarity is not None and result.gold_similarity > 0.70


# =============================================================================
# 6. COMPONENT PROBE: CROSS-ENCODER RERANKER
# =============================================================================
def test_reranker_probe():
    """Verify Cross-Encoder reranker probe promotes or retains the gold chunk."""
    needle = get_needle("fact_quantum_crypt")
    gold_cid = "chunk_gold_001"
    distractor_cid = "chunk_dist_002"

    candidates = [
        {"chunk_id": distractor_cid, "text": "General academic regulation on campus parking credits."},
        {"chunk_id": gold_cid, "text": needle.needle_text},
    ]

    result = RerankerProbe.evaluate(
        candidates=candidates,
        needle_case=needle,
        gold_chunk_ids=[gold_cid],
        top_n=2,
    )

    assert result.reranker_retained is True
    assert result.post_rerank_rank == 1


# =============================================================================
# 7. COMPONENT PROBE: GRAPH TRAVERSAL
# =============================================================================
def test_graph_traversal_probe():
    """Verify multi-hop relational path finding for graph needles."""
    needle = get_needle("graph_multihop_carbon")
    with NIAHIsolationHarness() as harness:
        result = GraphTraversalProbe.evaluate(
            graph_harness=harness.graph_harness,
            needle_case=needle,
            max_hops=2,
        )

        assert result.seed_found is True
        assert result.target_found is True
        assert result.traversal_success is True


# =============================================================================
# 8. SCIENTIFIC FAILURE ATTRIBUTION
# =============================================================================
def test_failure_attributor_diagnosis():
    """Verify failure attribution decision tree correctly categorizes pipeline faults."""
    from evaluation.benchmarks.niah.component_probes import (
        ChromaDBProbeResult,
        EmbeddingProbeResult,
        RerankerProbeResult,
    )

    # Scenario 1: ChromaDB missed the needle
    missed_chroma = ChromaDBProbeResult(
        needle_id="fact_quantum_crypt",
        top_k=5,
        top_k_recall=False,
        gold_rank=15,
        gold_similarity=0.45,
        reciprocal_rank=1/15,
        total_indexed_chunks=50,
        retrieved_hits_count=5,
    )
    diag1 = FailureAttributor.diagnose(retrieval_res=missed_chroma)
    assert diag1.stage == FailureStage.RETRIEVAL_FAILURE

    # Scenario 2: Embedding collision
    collided_emb = EmbeddingProbeResult(
        needle_id="fact_quantum_crypt",
        query_text="query",
        query_needle_sim=0.60,
        max_distractor_sim=0.75,
        mean_distractor_sim=0.50,
        similarity_margin=-0.15,
        needle_rank=5,
        total_candidates=20,
        representation_success=False,
    )
    diag2 = FailureAttributor.diagnose(embedding_res=collided_emb)
    assert diag2.stage == FailureStage.EMBEDDING_REPRESENTATION_FAILURE

    # Scenario 3: All passed
    passed_chroma = ChromaDBProbeResult(
        needle_id="fact_quantum_crypt",
        top_k=5,
        top_k_recall=True,
        gold_rank=1,
        gold_similarity=0.92,
        reciprocal_rank=1.0,
        total_indexed_chunks=20,
        retrieved_hits_count=5,
    )
    diag3 = FailureAttributor.diagnose(retrieval_res=passed_chroma)
    assert diag3.stage == FailureStage.SUCCESS
