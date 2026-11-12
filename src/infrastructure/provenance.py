"""
RAISE Pipeline Architecture & Provenance Metadata Builder
=========================================================
Component: `src.infrastructure.provenance`
Architecture Layer: Infrastructure / Metadata & Observability

Provides unified, real-time provenance metadata discovery for:
  - Storage Substrates (ChromaDB + Neo4j + Redis + PostgreSQL / SQLite)
  - Active LLM Provider & Model (Gemini, Groq, Ollama, etc.)
  - Dense Embedding Encoder (google/embeddinggemma-2 or BAAI/bge-large-en-v1.5)
  - Cross-Encoder Reranker (BAAI/bge-reranker-large or None (Bypassed) in fast mode)
  - NLI Entailment Verifier (FineCat-NLI or None (Bypassed) in fast mode)

Guarantees:
  - Real-time probe of live databases (Neo4j, Redis, PostgreSQL, ChromaDB).
  - Emits 'None (Bypassed in Fast Mode)' rather than null when components are bypassed.
  - Matches the frontend PipelineInfo Zod schema specification.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any, Dict, Optional


def _is_port_online(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def build_pipeline_info(mode: Optional[str] = "expert") -> Dict[str, str]:
    """
    Constructs a validated PipelineInfo dictionary for exports and provenance tracking.
    Accurately discovers all active storage substrates (ChromaDB, Neo4j, Redis, PostgreSQL)
    and AI neural models (Dense Embeddings, BGE Reranker, FineCat NLI, Synthesis LLM).
    """
    # 1. LLM Provider & Model Resolution
    try:
        from src.infrastructure.providers.router import get_provider_router
        prov_router = get_provider_router()
        compl_info = prov_router.get_last_completion_info()
        actual_llm_prov = compl_info.get("provider") or os.getenv("LLM_PROVIDER") or os.getenv("LLM_BACKEND") or "gemini"
        actual_llm_model = compl_info.get("model") or os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")
    except Exception:
        actual_llm_prov = os.getenv("LLM_PROVIDER") or os.getenv("LLM_BACKEND") or "gemini"
        actual_llm_model = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")

    # 2. Storage Substrates Resolution
    # A. ChromaDB Vector Store
    chroma_count = 0
    chroma_model = "google/embeddinggemma-2"
    try:
        import chromadb
        base_dir = Path(__file__).resolve().parent.parent.parent
        candidates = [
            base_dir / ".chromadb_embeddinggemma_2",
            base_dir / "backend" / ".chromadb_embeddinggemma_2",
            base_dir.parent / "backend" / ".chromadb_embeddinggemma_2",
            base_dir / ".chromadb_bge_large",
            base_dir / "backend" / ".chromadb_bge_large",
        ]
        target_chroma = next((p for p in candidates if p.exists()), None)
        if target_chroma:
            client = chromadb.PersistentClient(path=str(target_chroma))
            cols = client.list_collections()
            chroma_count = sum(c.count() for c in cols)
            chroma_model = "google/embeddinggemma-2" if "embeddinggemma" in target_chroma.name else "BAAI/bge-large-en-v1.5"
    except Exception:
        pass

    vector_desc = f"ChromaDB ({chroma_count} chunks | {chroma_model})" if chroma_count > 0 else f"ChromaDB ({chroma_model})"

    # B. Neo4j Graph Database
    neo4j_port = int(os.getenv("NEO4J_PORT", "7687"))
    neo4j_online = _is_port_online("127.0.0.1", neo4j_port)
    graph_desc = f"Neo4j (bolt://localhost:{neo4j_port})" if neo4j_online else "NetworkX (In-Memory Fallback)"

    # C. Redis Cache & Token Bucket
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_online = _is_port_online("127.0.0.1", redis_port)
    cache_desc = f"Redis (localhost:{redis_port})" if redis_online else "In-Memory Semantic Cache"

    # D. PostgreSQL / SQLite Relational Database
    pg_port = int(os.getenv("POSTGRES_PORT", "5432"))
    pg_online = _is_port_online("127.0.0.1", pg_port)
    db_desc = f"PostgreSQL (localhost:{pg_port})" if pg_online else "SQLite (Local Persistence)"

    # Comprehensive Substrates Descriptor
    substrates_list = ["ChromaDB (Vector)"]
    if neo4j_online:
        substrates_list.append("Neo4j (Graph)")
    else:
        substrates_list.append("NetworkX (Graph)")
    if redis_online:
        substrates_list.append("Redis (Cache)")
    if pg_online:
        substrates_list.append("PostgreSQL (Relational)")
    else:
        substrates_list.append("SQLite (Relational)")

    storage_desc = " + ".join(substrates_list)

    # 3. Dense Embedding Model
    encoder_model = (
        os.getenv("EMBEDDING_MODEL")
        or os.getenv("EMBEDDER_MODEL_NAME")
        or chroma_model
        or "google/embeddinggemma-2"
    )

    # 4. Mode-Aware Reranker & NLI Models (Never emit null)
    is_fast_mode = str(mode or "").lower() == "fast"

    if is_fast_mode:
        reranker_model = "None (Bypassed in Fast Mode)"
        nli_verifier_model = "None (Bypassed in Fast Mode)"
    else:
        raw_rerank = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-large")
        try:
            from src.retrieval.reranker import CrossEncoderReranker
            reranker_model = CrossEncoderReranker.AVAILABLE_RERANKERS.get(raw_rerank, raw_rerank)
        except Exception:
            reranker_model = "BAAI/bge-reranker-large"
        nli_verifier_model = (
            os.getenv("NLI_VERIFIER_MODEL")
            or os.getenv("NLI_MODEL")
            or "dleemiller/finecat-nli-ultra-l"
        )

    return {
        "storage_used": storage_desc,
        "llm_provider": actual_llm_prov,
        "llm_model": actual_llm_model,
        "encoder_model": encoder_model,
        "reranker_model": reranker_model,
        "nli_verifier_model": nli_verifier_model,
        "vector_store": vector_desc,
        "graph_database": graph_desc,
        "cache_database": cache_desc,
        "relational_database": db_desc,
    }
