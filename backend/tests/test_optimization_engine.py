import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.features.system.optimization import ContextBudgetManager, TieredQueryResultCache

def test_optimization_suite():
    # 1. Test Context Budget Manager
    print("=== 1. TESTING CONTEXT BUDGET MANAGER ===")
    budget_mgr = ContextBudgetManager(total_window=8192)

    sample_triples = [f"(:Institution {{name: 'IITM'}})-[:HAS_DEPARTMENT]->(:Department {{name: 'Dept_{i}'}})" for i in range(50)]
    sample_chunks = [{"chunk_id": f"chk_{i}", "plain_text": "This is a detailed paragraph describing research grants and patent metrics." * 10} for i in range(20)]
    sample_history = [{"user_query": f"Query {i}", "assistant_answer": f"Answer {i}"} for i in range(15)]

    fitted = budget_mgr.fit_context(
        system_prompt="You are a certified GraphRAG auditor." * 50,
        graph_triples=sample_triples,
        vector_chunks=sample_chunks,
        conversation_turns=sample_history,
    )

    print(f"Total Consumed Tokens:     {fitted['estimated_consumed_tokens']} / 8192")
    print(f"Available Generation Tokens:{fitted['available_generation_tokens']}")
    print(f"Fitted Graph Triples Count: {len(fitted['graph_triples'])} / 50")
    print(f"Fitted Vector Chunks Count: {len(fitted['vector_chunks'])} / 20")
    print(f"Fitted Conversation Turns:  {len(fitted['conversation_history'])} / 15\n")

    assert fitted["estimated_consumed_tokens"] <= 8192
    assert fitted["available_generation_tokens"] >= 1000

    # 2. Test Tiered Query Result Cache
    print("=== 2. TESTING TIERED QUERY RESULT CACHE ===")
    cache = TieredQueryResultCache(max_memory_items=2, cache_dir=".runtime/test_cache")
    query = "What is the total research budget of Panjab University?"
    sample_answer_payload = {
        "grounded_answer": "Panjab University allocated Rs. 650 Crore.",
        "citations": [{"doc": "PU_Report.pdf", "page": 4}],
        "traceability_score": 0.95,
    }

    # Initial Miss
    miss = cache.get(query)
    print(f"Initial Lookup (Expected Miss): {miss}")
    assert miss is None

    # Set Cache
    cache.set(query, sample_answer_payload, ttl_seconds=60)

    # Tier 1 In-Memory Hit
    hit_lru = cache.get(query)
    print(f"Tier 1 (Memory LRU Hit): Cache Tier = {hit_lru.get('cache_tier')}, Answer = {hit_lru.get('grounded_answer')}")
    assert hit_lru is not None
    assert hit_lru["cache_tier"] == "memory_lru"

    # Invalidate memory to test Tier 2 Disk Cache
    cache.memory_cache.clear()
    hit_disk = cache.get(query)
    print(f"Tier 2 (Disk Cache Hit):  Cache Tier = {hit_disk.get('cache_tier')}, Answer = {hit_disk.get('grounded_answer')}")
    assert hit_disk is not None
    assert hit_disk["cache_tier"] == "disk_cache"

    # Cleanup test cache
    cache.invalidate_all()
    print("\n[ALL LATENCY & RESOURCE OPTIMIZATION TESTS PASSED CLEANLY]")

if __name__ == "__main__":
    test_optimization_suite()
