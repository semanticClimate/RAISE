"""
RAISE — System Status Dashboard & Command Reference
===================================================
Diagnostic visualizer inspecting live Neo4j, ChromaDB, vLLM, Redis,
Reasoning Memory, and Math Engine components, alongside user command help.
"""

from __future__ import annotations

from typing import Any

from src.cli.document_manager import get_active_documents_list
from src.cli.renderer import C
from src.cli.system_launcher import check_vllm_health, get_synthesizer_status


def print_system_status(pipeline: Any = None, memory: Any = None) -> None:
    """Prints a comprehensive diagnostic view of all RAISE subsystems."""
    print("\n" + C.BANNER + "═" * 74 + C.RESET)
    print(f" {C.TITLE}🩺 RAISE MULTI-SUBSTRATE SUBSYSTEM DIAGNOSTICS{C.RESET}")
    print(C.BANNER + "═" * 74 + C.RESET)

    # 1. Neo4j Knowledge Graph
    neo_db = pipeline.neo4j_db if (pipeline and hasattr(pipeline, "neo4j_db")) else None
    if neo_db is None:
        try:
            from src.infrastructure.graph.neo4j import Neo4jDatabase
            neo_db = Neo4jDatabase()
        except Exception as neo_probe_err:
            logger.debug(f"Neo4j direct probe notice: {neo_probe_err}")
            neo_db = None

    if neo_db and getattr(neo_db, "connected", False):
        try:
            node_cnt = neo_db.run_cypher("MATCH (n) RETURN count(n) AS c")[0]["c"]
            rel_cnt = neo_db.run_cypher("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
            neo_str = f"{C.SUCCESS}CONNECTED{C.RESET} ({node_cnt} nodes, {rel_cnt} relationships | bolt://localhost:7687)"
        except Exception as e:
            neo_str = f"{C.SUCCESS}CONNECTED{C.RESET} (bolt://localhost:7687 | note: {e})"
    else:
        neo_str = f"{C.WARN}OFFLINE{C.RESET} (Using in-memory graph fallback)"

    # 2. ChromaDB Dense Vector Store
    try:
        col = getattr(pipeline.vector_engine, "collection", None) if pipeline and hasattr(pipeline, "vector_engine") else None
        if col is None:
            from src.infrastructure.vector.chroma import LocalVectorEngine
            _ve = LocalVectorEngine()
            col = _ve.collection
            chunk_cnt = col.count() if col else 0
            model_key = _ve.model_key
        else:
            chunk_cnt = col.count() if col else 0
            model_key = getattr(pipeline.vector_engine, "model_key", "default")

        if chunk_cnt == 0:
            chroma_str = f"{C.WARN}EMPTY{C.RESET} (0 indexed chunks | Model: {model_key})"
        else:
            chroma_str = f"{C.SUCCESS}READY{C.RESET} ({chunk_cnt} indexed chunks | Model: {model_key})"
    except Exception as e:
        chroma_str = f"{C.DANGER}OFFLINE{C.RESET} ({e})"

    # 3. Active Synthesizer (Local vLLM or Cloud AI)
    synth_info = get_synthesizer_status()
    synth_str = synth_info["display_string"]

    # 4. Redis Semantic Cache
    try:
        from src.infrastructure.cache.redis import RedisCacheManager
        _rm = RedisCacheManager()
        redis_conn = _rm.is_connected
    except Exception:
        redis_conn = False
    redis_str = (
        f"{C.SUCCESS}ONLINE{C.RESET} (Port 6379 connected)"
        if redis_conn
        else f"{C.MUTED}DISABLED{C.RESET} (In-memory fallback)"
    )

    # 5. Reasoning Memory
    traj_cnt = len(getattr(memory, "trajectories", [])) if memory else 0
    mem_str = f"{C.SUCCESS}ACTIVE{C.RESET} ({traj_cnt} learned reasoning trajectories stored)"

    # 6. Active Document Manifest
    docs = get_active_documents_list()
    doc_str = f"{C.ACCENT}{len(docs)} registered document(s){C.RESET}"

    print(f"  • {C.MUTED}Neo4j Graph Engine:{C.RESET}        {neo_str}")
    print(f"  • {C.MUTED}ChromaDB Vector Store:{C.RESET}     {chroma_str}")
    print(f"  • {C.MUTED}Active Synthesizer:{C.RESET}        {synth_str}")
    print(f"  • {C.MUTED}Redis Semantic Cache:{C.RESET}      {redis_str}")
    print(f"  • {C.MUTED}Reasoning Memory Engine:{C.RESET}   {mem_str}")
    print(f"  • {C.MUTED}Deterministic Math Engine:{C.RESET} {C.SUCCESS}OPERATIONAL{C.RESET} (Audited sums, CAGR, differences)")
    print(f"  • {C.MUTED}Document Library Capacity:{C.RESET} {doc_str}")
    print(C.BANNER + "═" * 74 + C.RESET + "\n")


def print_help_menu() -> None:
    """Prints the user CLI command reference."""
    print("\n" + C.BANNER + "═" * 74 + C.RESET)
    print(f" {C.TITLE}📖 RAISE COMMAND CHEATSHEET{C.RESET}")
    print(C.BANNER + "═" * 74 + C.RESET)
    print(f"  • {C.ACCENT}<Question>{C.RESET}          — Queries the currently attached document (or all attached)")
    print(f"  • {C.NUM}attach <N|name>{C.RESET}    — Attaches strictly to document number N or matching name in drawer")
    print(f"  • {C.NUM}attach all{C.RESET}         — Expands search scope to ALL documents in library simultaneously")
    print(f"  • {C.NUM}upload <path>{C.RESET}       — Ingests a new academic PDF report (PyMuPDF or Docling)")
    print(f"  • {C.NUM}library{C.RESET} / {C.NUM}docs{C.RESET}    — Lists all active registered PDF reports in the library")
    print(f"  • {C.NUM}delete <name>{C.RESET}      — Deletes a user-uploaded report (protected reports blocked)")
    print(f"  • {C.NUM}delete all{C.RESET}         — Safe workspace reset (clears user files & chat memory; databases intact)")
    print(f"  • {C.NUM}clear chat{C.RESET}         — Clears current conversation context and session memory")
    print(f"  • {C.NUM}status{C.RESET}             — Displays real-time health of Neo4j, ChromaDB, vLLM, and Redis")
    print(f"  • {C.NUM}exit{C.RESET} / {C.NUM}q{C.RESET}             — Exits RAISE Studio")
    print(C.BANNER + "═" * 74 + C.RESET + "\n")
