"""
Asynchronous Parallel Multi-Substrate Retriever for RAISE.
Concurrently executes:
  1. Dense Vector Search (ChromaDB using BGE-Large / all-MiniLM)
  2. Sparse Lexical Search (BM25 keyword/entity matching)
  3. Graph Traversal / Cypher Queries (Neo4j / NetworkX property graph)
Merges candidates using Reciprocal Rank Fusion (RRF, k=60) and applies BGE-Reranker-Large.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.retrieval.fusion import reciprocal_rank_fusion, CrossEncoderReranker
from .bm25 import SelfContainedBM25
from .intent import classify_retrieval_intent, redistribute_channel_weights
from .graph_channel import traverse_graph_channel

__all__ = [
    "AsyncParallelRetriever",
    "ParallelRetriever",
    "SelfContainedBM25",
    "classify_retrieval_intent",
    "redistribute_channel_weights",
]

BASE_DIR = Path(__file__).parent.parent.resolve()
_bin_dir = BASE_DIR / "bin"
if _bin_dir.exists() and str(_bin_dir) not in sys.path:
    sys.path.insert(0, str(_bin_dir))

# Check for compiled Rust acceleration engine
try:
    import raise_engine  # type: ignore
    HAS_RUST_ENGINE = True
except ImportError:
    HAS_RUST_ENGINE = False


class AsyncParallelRetriever:
    """
    Executes dense, sparse, and graph retrieval paths concurrently using asyncio.gather.
    """

    # Retain static method alias for backward compatibility
    classify_retrieval_intent = staticmethod(classify_retrieval_intent)

    def __init__(
        self,
        rag_pipeline: Any,
        reranker_model: Optional[str] = None,
        reranker: Optional[CrossEncoderReranker] = None,
    ):
        self.pipeline = rag_pipeline
        self.reranker = reranker or getattr(rag_pipeline, "reranker", None) or CrossEncoderReranker(model_name=reranker_model)
        from src.reasoning.query_planner import QueryPlanner
        self.query_planner = QueryPlanner()

    async def _search_dense_vector(
        self,
        query: str,
        top_k: int = 6,
        doc_filter: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Run dense vector search in non-blocking threadpool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.pipeline.vector_engine.search(
                query=query,
                top_k=top_k,
                doc_filter=doc_filter,
                active_docs=active_docs,
            )
        )

    async def _search_sparse_lexical(
        self,
        query: str,
        top_k: int = 12,
        active_docs: Optional[List[str]] = None,
        doc_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run sparse BM25 search independently across the entire document chunk corpus."""
        loop = asyncio.get_running_loop()

        def _bm25_search():
            cached_index = getattr(self, "_cached_bm25", None)
            cached_sig = getattr(self, "_cached_bm25_sig", None)

            from src.core.config import CHUNKS_DIR
            base_candidates = [
                CHUNKS_DIR,
                Path(__file__).resolve().parents[2] / "data" / "processed" / "chunks",
            ]
            active_dir = next((b for b in base_candidates if b.exists()), None)
            chunk_files = list(active_dir.glob("*_chunks.json")) if active_dir else []

            # Fast O(1) metadata signature (file count + max mtime) — zero JSON parsing if unchanged!
            current_sig = (
                len(chunk_files),
                max((f.stat().st_mtime for f in chunk_files), default=0.0),
            )

            if cached_index is not None and cached_sig == current_sig and chunk_files:
                return cached_index.search(query, top_k=top_k, active_docs=active_docs, doc_filter=doc_filter)

            corpus_chunks = []
            for cf in chunk_files:
                try:
                    c_list = json.loads(cf.read_text(encoding="utf-8"))
                    if isinstance(c_list, list):
                        corpus_chunks.extend(c_list)
                except Exception:
                    pass

            if not corpus_chunks and hasattr(self.pipeline, "vector_engine") and self.pipeline.vector_engine.collection:
                try:
                    cdata = self.pipeline.vector_engine.collection.get()
                    for idx, cid in enumerate(cdata.get("ids", [])):
                        corpus_chunks.append({
                            "chunk_id": cid,
                            "plain_text": cdata["documents"][idx] if idx < len(cdata["documents"]) else "",
                            "metadata": cdata["metadatas"][idx] if idx < len(cdata["metadatas"]) else {},
                        })
                except Exception:
                    pass

            if not corpus_chunks:
                clean_q = re.sub(r"[^a-zA-Z0-9\s]", "", query.lower())
                query_tokens = [t for t in clean_q.split() if len(t) > 2]
                return self.pipeline.vector_engine.search(
                    query=" ".join(query_tokens) if query_tokens else query,
                    top_k=top_k,
                    doc_filter=doc_filter,
                    active_docs=active_docs,
                )

            cached_index = SelfContainedBM25(corpus_chunks)
            self._cached_bm25 = cached_index
            self._cached_bm25_sig = current_sig
            return cached_index.search(query, top_k=top_k, active_docs=active_docs, doc_filter=doc_filter)

        return await loop.run_in_executor(None, _bm25_search)

    async def _traverse_graph_entities(
        self,
        query: str,
        hops: int = 2,
        active_docs: Optional[List[str]] = None,
        chunk_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Run dynamic graph traversal across Neo4j knowledge graph using chunk neighborhoods or token fallback."""
        return await traverse_graph_channel(
            neo4j_db=getattr(self.pipeline, "neo4j_db", None),
            graph_engine=getattr(self.pipeline, "graph_engine", None),
            query=query,
            hops=hops,
            active_docs=active_docs,
            chunk_ids=chunk_ids,
        )



    async def retrieve_parallel_and_fuse(
        self,
        query: str,
        top_k: int = 16,
        hops: int = 2,
        doc_filter: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
        rerank_top_n: int = 10,
        subqueries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Triggers Dense, Sparse, and Graph retrievers in parallel with asyncio.gather,
        applies Reciprocal Rank Fusion, and contextually reranks candidates with BGE-Reranker-Large.
        """
        dense_task = self._search_dense_vector(query, top_k=top_k, doc_filter=doc_filter, active_docs=active_docs)
        sparse_task = self._search_sparse_lexical(query, top_k=top_k, active_docs=active_docs, doc_filter=doc_filter)
        graph_task = self._traverse_graph_entities(query, hops=hops, active_docs=active_docs, chunk_ids=None)

        # 1. Execute Dense, Sparse, and Graph retrieval concurrently
        dense_res, sparse_res, graph_res = await asyncio.gather(dense_task, sparse_task, graph_task)

        # 2. If graph results are sparse, expand with candidate chunk IDs from interleaved dense/sparse hits
        if len(graph_res) < 5:
            candidate_chunk_ids: List[str] = []
            interleaved_candidates = []
            for d_item, s_item in itertools.zip_longest(dense_res or [], sparse_res or []):
                if d_item is not None:
                    interleaved_candidates.append(d_item)
                if s_item is not None:
                    interleaved_candidates.append(s_item)

            for item in interleaved_candidates:
                cid = item.get("chunk_id") or item.get("id") or (item.get("metadata") or {}).get("chunk_id")
                if cid and str(cid) not in candidate_chunk_ids:
                    candidate_chunk_ids.append(str(cid))

            if candidate_chunk_ids:
                dyn_res = await self._traverse_graph_entities(
                    query,
                    hops=hops,
                    active_docs=active_docs,
                    chunk_ids=candidate_chunk_ids[:15],
                )
                if dyn_res:
                    graph_res = (graph_res or []) + dyn_res

        # 3. Classify query intent to dynamically weight modalities
        intent_type, raw_intent_weights = self.classify_retrieval_intent(query)
        adapted_weights = redistribute_channel_weights(
            raw_intent_weights=raw_intent_weights,
            dense_res=dense_res or [],
            sparse_res=sparse_res or [],
            graph_res=graph_res or [],
        )

        # 4. Reciprocal Rank Fusion with Adaptive Intent Weights & Intent-gated Table Boost
        ranked_candidates_list = [dense_res or [], sparse_res or [], graph_res or []]
        active_lists = []
        active_weights = []
        for l_res, w in zip(ranked_candidates_list, adapted_weights):
            if l_res and w > 0.0:
                active_lists.append(l_res)
                active_weights.append(w)

        fused_candidates = reciprocal_rank_fusion(
            active_lists,
            k=60,
            weights=active_weights if active_weights else None,
            id_key="chunk_id",
            table_boost=True,
            intent=intent_type,
            query=query,
        )

        # 5. Contextual Reranking with BGE-Reranker-Large and Decomposed Subqueries Max-Pooling
        if subqueries is None and hasattr(self, "query_planner") and self.query_planner:
            subqueries = self.query_planner.decompose_to_subqueries(query)

        reranked_chunks = await self.reranker.arerank(
            query=query,
            candidates=fused_candidates,
            text_key="plain_text",
            top_n=rerank_top_n,
            subqueries=subqueries,
        )

        return {
            "reranked_chunks": reranked_chunks,
            "dense_count": len(dense_res),
            "sparse_count": len(sparse_res),
            "graph_count": len(graph_res),
            "fused_count": len(fused_candidates),
            "intent_type": intent_type,
            "intent_weights": raw_intent_weights,
        }

    def retrieve_sync(
        self,
        query: str,
        top_k: int = 16,
        hops: int = 2,
        doc_filter: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
        rerank_top_n: int = 10,
        subqueries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for integration into standard pipeline interfaces."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Inside existing event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(
                        asyncio.run,
                        self.retrieve_parallel_and_fuse(
                            query=query,
                            top_k=top_k,
                            hops=hops,
                            doc_filter=doc_filter,
                            active_docs=active_docs,
                            rerank_top_n=rerank_top_n,
                            subqueries=subqueries,
                        )
                    ).result()
            else:
                return asyncio.run(
                    self.retrieve_parallel_and_fuse(
                        query=query,
                        top_k=top_k,
                        hops=hops,
                        doc_filter=doc_filter,
                        active_docs=active_docs,
                        rerank_top_n=rerank_top_n,
                        subqueries=subqueries,
                    )
                )
        except Exception:
            return asyncio.run(
                self.retrieve_parallel_and_fuse(
                    query=query,
                    top_k=top_k,
                    hops=hops,
                    doc_filter=doc_filter,
                    active_docs=active_docs,
                    rerank_top_n=rerank_top_n,
                    subqueries=subqueries,
                )
            )


# Compatibility alias
ParallelRetriever = AsyncParallelRetriever

