"""
RAISE Hybrid Retrieval & Fusion Engine — Layer B: RRF & Reranking
================================================================
Component          : Reciprocal Rank Fusion & Hybrid Retriever (src/retrieval/fusion.py)
Hardware / Process : cuda:0 (auto-detected GPU) / CPU fallback
Dimensions / Specs : RRF + Cross-Attention (BAAI/bge-reranker-large)
Verification       : Real-time cross-attention scores + neighborhood chunk expansion
Status             : VERIFIED / MODULAR ARCHITECTURE

Modular Architecture:
---------------------
- Contextual Reranker Engine: `src.retrieval.reranker`
- Entity & Boundary Filtering: `src.retrieval.entity_filtering`
- Macro-Chunk Parent Hydration: `src.retrieval.macro_hydration`
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from langchain_core.documents import Document
    HAS_LANGCHAIN_DOC = True
except ImportError:
    HAS_LANGCHAIN_DOC = False

    class Document:  # type: ignore
        def __init__(self, page_content: str, metadata: Optional[Dict[str, Any]] = None):
            self.page_content = page_content
            self.metadata = metadata or {}

# Modular re-exports for 100% backward compatibility
from src.retrieval.reranker import (
    CrossEncoderReranker,
    is_table_candidate,
)
from src.retrieval.macro_hydration import (
    hydrate_macro_chunks,
    get_parent_chunks_cache,
)
from src.retrieval.entity_filtering import (
    filter_entity_mismatches,
    filter_subgraph_entity_mismatches,
    get_library_institutions,
)

logger = logging.getLogger("raise.retrieval.fusion")
HAS_CROSS_ENCODER = True


def chunk_to_document(chunk: Dict[str, Any] | Document) -> Document:
    """Converts a raw chunk dictionary into a canonical LangChain Document."""
    if isinstance(chunk, Document):
        return chunk
    text = str(chunk.get("plain_text") or chunk.get("text") or chunk.get("content") or "")
    metadata = dict(chunk.get("metadata") or {})
    for key in [
        "chunk_id", "id", "pdf_filename", "primary_page", "printed_page",
        "heading", "doc_id", "similarity", "score", "cross_encoder_score",
        "rrf_score", "source", "document", "is_table",
    ]:
        if key in chunk and key not in metadata:
            metadata[key] = chunk[key]
    if "chunk_id" not in metadata and "id" in chunk:
        metadata["chunk_id"] = chunk["id"]
    return Document(page_content=text, metadata=metadata)


def document_to_chunk(doc: Document | Dict[str, Any]) -> Dict[str, Any]:
    """Converts a LangChain Document into a standard dictionary chunk."""
    if isinstance(doc, dict):
        return dict(doc)
    chunk = dict(doc.metadata or {})
    chunk["text"] = doc.page_content
    chunk["plain_text"] = doc.page_content
    if "chunk_id" not in chunk and "id" in chunk:
        chunk["chunk_id"] = chunk["id"]
    return chunk


def _extract_id_and_dict(item: Any, id_key: str = "chunk_id") -> Tuple[str, Dict[str, Any]]:
    """Extracts a unique string ID and dictionary from either a dict or a LangChain Document."""
    if isinstance(item, dict):
        d = dict(item)
        doc_id = str(
            d.get(id_key)
            or d.get("id")
            or (d.get("metadata", {}).get(id_key) if isinstance(d.get("metadata"), dict) else None)
            or (d.get("metadata", {}).get("chunk_id") if isinstance(d.get("metadata"), dict) else None)
            or f"doc_{hash(str(d.get('text') or d.get('plain_text') or d)[:100])}"
        )
        return doc_id, d
    elif hasattr(item, "page_content") and hasattr(item, "metadata"):
        meta = dict(item.metadata or {})
        doc_id = str(
            meta.get(id_key)
            or meta.get("id")
            or meta.get("chunk_id")
            or f"doc_{hash(item.page_content[:100])}"
        )
        d = dict(meta)
        d["text"] = item.page_content
        d["plain_text"] = item.page_content
        if "chunk_id" not in d:
            d["chunk_id"] = doc_id
        return doc_id, d
    else:
        doc_id = f"doc_{hash(str(item))}"
        d = {"text": str(item), "plain_text": str(item), "chunk_id": doc_id}
        return doc_id, d


def reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any] | Any]],
    k: int = 60,
    id_key: str = "chunk_id",
    weights: Optional[List[float]] = None,
    table_boost: bool = True,
    min_score_threshold: Optional[float] = None,
    intent: Optional[str] = None,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Computes Reciprocal Rank Fusion (RRF) over multiple ranked retrieval result sets.
    Formula: RRF(d) = sum(w_m / (k + rank_m(d)))

    Supports:
    - Input items as Python dicts or LangChain Documents.
    - Intent-aware modality weights (Dense, Sparse BM25, Knowledge Graph).
    - Hard minimum score threshold pruning (min_score_threshold).
    - Table and schedule structural boosting (1.35x), gated strictly by query intent.
    """
    if not ranked_lists:
        return []

    active_weights = weights
    if active_weights is None and intent:
        from src.retrieval.intent import classify_retrieval_intent
        _, active_weights = classify_retrieval_intent(intent)

    # Determine whether table boost is active based on tabular/numerical/financial query intent
    is_table_boost_active = False
    if table_boost:
        intent_str = (intent or "").lower()
        valid_intents = ("financial", "tabular", "numerical", "comparison", "numerical_or_factual", "table", "stats", "audit")
        if any(vi in intent_str for vi in valid_intents):
            is_table_boost_active = True
        elif query:
            q_lower = query.lower()
            tabular_cues = (
                "table", "schedule", "balance sheet", "revenue", "income", "expenditure",
                "budget", "profit", "loss", "ebitda", "margin", "ratio", "financial",
                "statement", "metric", "allocation", "grant", "crore", "lakh", "inr", "$", "%",
                "figures", "row", "column", "comparison", "compare", "breakdown", "versus", "vs"
            )
            if any(cue in q_lower for cue in tabular_cues) or bool(re.search(r"\b\d+(?:\.\d+)?%?\b", query)):
                is_table_boost_active = True

    scores: Dict[str, float] = {}
    doc_map: Dict[str, Dict[str, Any]] = {}

    for l_idx, r_list in enumerate(ranked_lists):
        w = active_weights[l_idx] if (active_weights and l_idx < len(active_weights)) else 1.0
        for rank, item in enumerate(r_list, start=1):
            doc_id, entry_dict = _extract_id_and_dict(item, id_key=id_key)
            if doc_id not in doc_map:
                doc_map[doc_id] = entry_dict

            score_increment = (1.0 / (k + rank)) * w
            if is_table_boost_active and is_table_candidate(entry_dict):
                score_increment *= 1.35
            scores[doc_id] = scores.get(doc_id, 0.0) + score_increment

    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    results = []
    for rank, doc_id in enumerate(sorted_ids, start=1):
        final_score = round(scores[doc_id], 6)
        if min_score_threshold is not None and final_score < min_score_threshold:
            continue
        entry = dict(doc_map[doc_id])
        entry["rrf_score"] = final_score
        entry["rrf_rank"] = rank
        results.append(entry)

    return results




# LangChain Core BaseRetriever Integration
try:
    from pydantic import ConfigDict
    from langchain_core.retrievers import BaseRetriever
    from langchain_core.callbacks import CallbackManagerForRetrieverRun

    class HybridRetriever(BaseRetriever):
        """
        Commercial-grade LangChain Core BaseRetriever for RAISE GraphRAG.
        Executes Dense Vector + Sparse BM25 + Neo4j Graph traversal in parallel,
        fuses candidates via Reciprocal Rank Fusion, and applies Cross-Encoder reranking.
        """
        model_config = ConfigDict(arbitrary_types_allowed=True)

        rag_pipeline: Any
        top_k: int = 6
        hops: int = 2
        rerank_top_n: int = 4
        doc_filter: Optional[str] = None
        active_docs: Optional[List[str]] = None

        def _get_relevant_documents(
            self, query: str, *, run_manager: Optional[CallbackManagerForRetrieverRun] = None
        ) -> List[Document]:
            retriever = getattr(self.rag_pipeline, "parallel_retriever", None)
            if retriever and hasattr(retriever, "retrieve_sync"):
                res = retriever.retrieve_sync(
                    query=query,
                    top_k=self.top_k,
                    hops=self.hops,
                    doc_filter=self.doc_filter,
                    active_docs=self.active_docs,
                    rerank_top_n=self.rerank_top_n,
                )
                chunks = res.get("reranked_chunks") or []
            else:
                chunks = self.rag_pipeline.vector_engine.search(
                    query=query,
                    top_k=self.top_k,
                    doc_filter=self.doc_filter,
                    active_docs=self.active_docs,
                )
            return [chunk_to_document(c) for c in chunks]

except ImportError:
    pass
