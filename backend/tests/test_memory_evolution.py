import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.features.memory.engine import SessionMemoryManager, LongTermGraphEvolutionManager

def test_memory_and_evolution():
    print("=== 1. SHORT-TERM MEMORY: STATEFUL SESSIONS & PRONOUN RESOLUTION ===")
    session_mgr = SessionMemoryManager()
    thread_id = "user_session_42"

    # Turn 1: User asks about Panjab University
    turn1_q = "Tell me about Panjab University's budget and governance."
    session_mgr.record_turn(
        thread_id=thread_id,
        user_query=turn1_q,
        resolved_query=turn1_q,
        active_entities=["Panjab University"],
        citations=[{"doc": "PU_Report.pdf", "page": 1}],
        assistant_answer="Panjab University had a total budget allocation of Rs. 650 Crore."
    )
    print(f"Turn 1 Recorded: Active Entity = ['Panjab University']")

    # Turn 2: Follow-up with pronoun reference ("their")
    turn2_q = "What were their primary liabilities and revenue streams?"
    resolved_q, entity = session_mgr.resolve_coreference(turn2_q, thread_id=thread_id)
    print(f"Turn 2 Input Query: '{turn2_q}'")
    print(f"Turn 2 Resolved Query: '{resolved_q}'")
    print(f"Disambiguated Entity: '{entity}'")

    assert "Panjab University's" in resolved_q

    print("\n=== 2. LONG-TERM MEMORY: GRAPH-BACKED KNOWLEDGE BASE EVOLUTION ===")
    evolution_mgr = LongTermGraphEvolutionManager()

    # Step 1 & 2: Information Extraction & Verification Staging
    extracted_triples = [
        {
            "source": "Panjab University",
            "source_type": "Institution",
            "relationship": "SECURED_GRANT",
            "target": "DST Clean Energy Initiative",
            "target_type": "Grant",
            "confidence": 0.92,
            "provenance": {"document_id": "PU_Report", "page_number": 14}
        },
        {
            "source": "Panjab University",
            "source_type": "Institution",
            "relationship": "OPERATES_INCUBATOR",
            "target": "PU Bio-Nest Hub",
            "target_type": "Incubator",
            "confidence": 0.88,
            "provenance": {"document_id": "PU_Report", "page_number": 22}
        },
        {
            "source": "Unverified Entity",
            "source_type": "Entity",
            "relationship": "MENTIONS",
            "target": "Unknown Rumor",
            "target_type": "Entity",
            "confidence": 0.40,  # Below threshold
            "provenance": {"document_id": "Unknown", "page_number": 99}
        }
    ]

    staged = evolution_mgr.stage_extracted_triples(extracted_triples, confidence_threshold=0.75)
    print(f"Total Staged Triples: {len(staged)}")
    print(f"Verified for Reconciliation: {sum(1 for s in staged if s.verified)} / {len(staged)}")

    # Step 3: Graph Reconciliation
    recon_res = evolution_mgr.reconcile_into_graph()
    print(f"Reconciliation Status: {recon_res['status']}")
    print(f"Reconciled Nodes: {recon_res['reconciled_nodes']}, Reconciled Edges: {recon_res['reconciled_edges']}")
    print(f"Remaining Unverified in Staging Buffer: {recon_res['remaining_unverified_in_staging']}")

    assert recon_res["reconciled_edges"] == 2
    assert recon_res["remaining_unverified_in_staging"] == 1
    print("\n[ALL TESTS PASSED CLEANLY]")

if __name__ == "__main__":
    test_memory_and_evolution()
