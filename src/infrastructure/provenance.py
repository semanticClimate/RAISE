"""
RAISE Pipeline Architecture & Provenance Metadata Builder
=========================================================
Component: `src.infrastructure.provenance`
Architecture Layer: Infrastructure / Metadata & Observability

Provides unified provenance metadata discovery for:
  - Storage Substrates (ChromaDB + Neo4j / NetworkX)
  - Active LLM Provider & Model (Gemini, Groq, Ollama, etc.)
  - Dense Embedding Encoder (google/embeddinggemma-2 or BAAI/bge-large-en-v1.5)
  - Cross-Encoder Reranker (BAAI/bge-reranker-large or None (Bypassed) in fast mode)
  - NLI Entailment Verifier (FineCat-NLI or None (Bypassed) in fast mode)

Guarantees:
  - Emits 'None (Bypassed)' or 'N/A' rather than null when components are bypassed.
  - Matches the frontend PipelineInfo Zod schema specification.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def build_pipeline_info(mode: Optional[str] = "expert") -> Dict[str, str]:
    """
    Constructs a validated PipelineInfo dictionary for exports and provenance tracking.
    """
    # 1. LLM Provider & Model Resolution
    actual_llm_prov = os.getenv("LLM_PROVIDER", "gemini").lower()
    if os.getenv("GROQ_API_KEY") and actual_llm_prov == "groq":
        actual_llm_model = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
    else:
        actual_llm_model = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")

    # 2. Storage Substrates Resolution
    neo4j_online = False
    try:
        from src.infrastructure.database.neo4j import Neo4jClient
        neo4j_online = Neo4jClient.is_healthy()
    except Exception:
        pass
    storage_desc = (
        "ChromaDB (Vector) + Neo4j (Graph)"
        if neo4j_online
        else "ChromaDB (Vector) + NetworkX (In-Memory Graph)"
    )

    # 3. Dense Embedding Model
    encoder_model = (
        os.getenv("EMBEDDING_MODEL")
        or os.getenv("EMBEDDER_MODEL_NAME")
        or "google/embeddinggemma-2"
    )

    # 4. Mode-Aware Reranker & NLI Models (Never emit null)
    is_fast_mode = str(mode or "").lower() == "fast"

    if is_fast_mode:
        reranker_model = "None (Bypassed)"
        nli_verifier_model = "None (Bypassed)"
    else:
        reranker_model = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-large")
        nli_verifier_model = (
            os.getenv("NLI_VERIFIER_MODEL")
            or os.getenv("NLI_MODEL")
            or "dleemiller/finecat-nli-ultra-l"
        )

    return {
        "storage_used": storage_desc or "ChromaDB (Vector) + Neo4j (Graph)",
        "llm_provider": actual_llm_prov or "gemini",
        "llm_model": actual_llm_model or "gemini-3.5-flash-lite",
        "encoder_model": encoder_model or "google/embeddinggemma-2",
        "reranker_model": reranker_model or "None (Bypassed)",
        "nli_verifier_model": nli_verifier_model or "None (Bypassed)",
    }
