"""
Independent Retrieval Ablation & IR Benchmark Engine
====================================================
Evaluates heterogeneous retrieval modalities independently and in all combinatoric ablations:
1. BM25 (Sparse lexical)
2. Dense Vector (BAAI/bge-large-en-v1.5)
3. Graph (Neo4j / NetworkX entity-neighborhood traversal)
4. BM25 + Dense
5. BM25 + Graph
6. Dense + Graph
7. BM25 + Dense + Graph (RRF k=60)
8. BM25 + Dense + Graph + Cross-Encoder Reranker (BAAI/bge-reranker-large)

Computes standard BEIR/MTEB IR metrics:
- Recall@1, Recall@5, Recall@10, Recall@20
- MRR@10
- nDCG@10
- MAP@10

Exports structured traces to:
- evaluation/reports/retrieval_ablation.json
- evaluation/reports/retrieval_ablation.csv
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.features.evaluation.ir_metrics import (
    aggregate_query_metrics,
    compute_retrieval_metrics_battery,
)
from src.retrieval.fusion import reciprocal_rank_fusion

logger = logging.getLogger("raise.features.evaluation.retrieval_ablation")


def _extract_page_numbers_from_chunk(chunk: Dict[str, Any]) -> List[int]:
    """Extracts all physical/printed page numbers associated with a retrieved chunk."""
    pages: List[int] = []
    meta = chunk.get("metadata") or {}

    # 1. Direct metadata fields
    for k in ("primary_page", "page", "physical_page"):
        val = meta.get(k) or chunk.get(k)
        if val is not None:
            try:
                pages.append(int(val))
            except (ValueError, TypeError):
                pass

    # 2. Multi-page lists
    src_pages = meta.get("source_pages") or chunk.get("source_pages") or []
    if isinstance(src_pages, list):
        for p in src_pages:
            try:
                pages.append(int(p))
            except (ValueError, TypeError):
                pass

    # 3. Regex from chunk id (e.g., Doc_p043_c12)
    cid = str(meta.get("chunk_id") or chunk.get("id") or chunk.get("chunk_id") or "")
    m = re.search(r"_p0*(\d+)", cid)
    if m:
        try:
            pages.append(int(m.group(1)))
        except (ValueError, TypeError):
            pass

    return sorted(list(set(pages))) if pages else [1]


class RetrievalAblationRunner:
    """
    Executes modular retrieval ablations across individual and combined channels.
    """

    CONFIGURATIONS = [
        "BM25",
        "Dense",
        "Graph",
        "BM25+Dense",
        "BM25+Graph",
        "Dense+Graph",
        "BM25+Dense+Graph",
        "BM25+Dense+Graph+Reranker",
    ]

    def __init__(self, pipeline: Optional[Any] = None):
        if pipeline is None:
            from src.retrieval.pipeline import StandaloneRAGPipeline
            self.pipeline = StandaloneRAGPipeline()
        else:
            self.pipeline = pipeline
        self.vector_engine = getattr(self.pipeline, "vector_engine", None)
        self.parallel_retriever = getattr(self.pipeline, "parallel_retriever", None)
        self.reranker = getattr(self.pipeline, "reranker", None)
        if not self.reranker and hasattr(self.pipeline, "agent_router") and hasattr(self.pipeline.agent_router, "reranker"):
            self.reranker = self.pipeline.agent_router.reranker

    def run_query_modality(
        self,
        query: str,
        modality: str,
        top_k: int = 20,
        doc_filter: Optional[str] = None,
        active_docs: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves candidates for a single isolated or combined modality.
        """
        # 1. Single channel retrieval
        dense_hits: List[Dict[str, Any]] = []
        bm25_hits: List[Dict[str, Any]] = []
        graph_hits: List[Dict[str, Any]] = []

        needs_dense = "Dense" in modality
        needs_bm25 = "BM25" in modality
        needs_graph = "Graph" in modality

        if needs_dense and self.vector_engine:
            dense_hits = self.vector_engine.search(
                query=query,
                top_k=top_k,
                doc_filter=doc_filter,
                active_docs=active_docs,
            )

        if needs_bm25 and self.parallel_retriever:
            bm25_hits = self.parallel_retriever.retrieve_sync(
                query=query,
                top_k=top_k,
                doc_filter=doc_filter,
                active_docs=active_docs,
                rerank_top_n=top_k,
            ).get("reranked_chunks", [])
            # If using retrieve_sync returns fused, directly use _search_sparse_lexical if possible
            if hasattr(self.parallel_retriever, "_cached_bm25") and self.parallel_retriever._cached_bm25:
                raw_bm = self.parallel_retriever._cached_bm25.search(
                    query, top_k=top_k, active_docs=active_docs, doc_filter=doc_filter
                )
                if raw_bm:
                    bm25_hits = raw_bm

        if needs_graph and hasattr(self.pipeline, "neo4j_db") and self.pipeline.neo4j_db:
            try:
                # Graph entity traversal
                clean_q = re.sub(r"[^a-zA-Z0-9\s]", "", query.lower())
                tokens = [t for t in clean_q.split() if len(t) > 3][:6]
                cypher = """
                    MATCH (n)
                    WHERE (n:Entity OR any(l IN labels(n) WHERE NOT l IN ['Chunk', 'Section']))
                      AND (size($tokens) = 0 OR any(tok IN $tokens WHERE toLower(coalesce(n.label, n.name, n.id, '')) CONTAINS tok))
                    OPTIONAL MATCH (n)-[:HAS_FACT|REPORTED_METRIC|MENTIONS|CONTAINS_CHUNK]-(c:Chunk)
                    RETURN coalesce(n.id, elementId(n)) AS id,
                           coalesce(n.label, n.name, n.id) AS name,
                           coalesce(n.page, c.page, 1) AS page,
                           coalesce(n.document_id, c.document_id, 'doc') AS doc_id
                    LIMIT $top_k
                """
                recs = self.pipeline.neo4j_db.run_cypher(cypher, {"tokens": tokens, "top_k": top_k})
                for r in recs:
                    graph_hits.append({
                        "id": str(r.get("id")),
                        "chunk_id": str(r.get("id")),
                        "plain_text": f"Graph Entity: {r.get('name')}",
                        "metadata": {
                            "primary_page": r.get("page", 1),
                            "pdf_filename": r.get("doc_id"),
                        }
                    })
            except Exception:
                pass

        # 2. Modality Dispatch
        if modality == "BM25":
            return bm25_hits[:top_k]
        elif modality == "Dense":
            return dense_hits[:top_k]
        elif modality == "Graph":
            return graph_hits[:top_k]
        elif modality == "BM25+Dense":
            return reciprocal_rank_fusion([bm25_hits, dense_hits], k=60)[:top_k]
        elif modality == "BM25+Graph":
            return reciprocal_rank_fusion([bm25_hits, graph_hits], k=60)[:top_k]
        elif modality == "Dense+Graph":
            return reciprocal_rank_fusion([dense_hits, graph_hits], k=60)[:top_k]
        elif modality in ("BM25+Dense+Graph", "BM25+Dense+Graph+Reranker"):
            fused = reciprocal_rank_fusion([dense_hits, bm25_hits, graph_hits], k=60)[:top_k]
            if "Reranker" in modality and self.reranker:
                return self.reranker.rerank(
                    query=query,
                    candidates=fused,
                    text_key="plain_text",
                    top_n=top_k,
                )
            return fused

        return dense_hits[:top_k]

    def evaluate_ablation_suite(
        self,
        questions: List[Dict[str, Any]],
        top_k: int = 20,
    ) -> Dict[str, Any]:
        """
        Runs all 8 configurations across the provided questions and aggregates IR metrics.
        """
        results_by_config: Dict[str, List[Dict[str, float]]] = {cfg: [] for cfg in self.CONFIGURATIONS}
        query_level_traces: List[Dict[str, Any]] = []

        total_q = len(questions)
        logger.info(f"Starting retrieval ablation across {total_q} questions...")

        for q_idx, q_item in enumerate(questions, start=1):
            q_id = q_item.get("question_id") or q_item.get("q_id") or f"Q{q_idx:03d}"
            query_text = q_item.get("question") or q_item.get("query") or ""
            gold_doc = q_item.get("target_document") or q_item.get("document") or q_item.get("gold_document") or ""

            # Extract gold pages
            raw_cits = q_item.get("page_citations") or q_item.get("evidence_pages") or q_item.get("gold_pages") or []
            gold_pages: List[int] = []
            for c in raw_cits:
                if isinstance(c, int):
                    gold_pages.append(c)
                elif str(c).isdigit():
                    gold_pages.append(int(c))
            gold_pages = sorted(list(set(gold_pages)))

            # If no gold pages given (e.g. negative control probe), skip IR page rank evaluation
            if not gold_pages:
                continue

            query_record: Dict[str, Any] = {
                "question_id": q_id,
                "query": query_text,
                "gold_document": gold_doc,
                "gold_pages": gold_pages,
                "configurations": {},
            }

            for config_name in self.CONFIGURATIONS:
                candidates = self.run_query_modality(
                    query=query_text,
                    modality=config_name,
                    top_k=top_k,
                    doc_filter=gold_doc if gold_doc else None,
                )

                # Extract retrieved page sequence in ranking order
                retrieved_pages: List[int] = []
                retrieved_cids: List[str] = []
                for cand in candidates:
                    c_pages = _extract_page_numbers_from_chunk(cand)
                    for cp in c_pages:
                        if cp not in retrieved_pages:
                            retrieved_pages.append(cp)
                    cid = cand.get("chunk_id") or cand.get("id") or ""
                    if cid:
                        retrieved_cids.append(str(cid))

                # Compute standard IR metrics battery
                metrics = compute_retrieval_metrics_battery(
                    retrieved_items=retrieved_pages,
                    gold_items=gold_pages,
                    k_thresholds=(1, 5, 10, 20),
                )
                results_by_config[config_name].append(metrics)

                # Find first rank of relevant page
                first_hit_rank = None
                for r_idx, rp in enumerate(retrieved_pages, start=1):
                    if rp in gold_pages:
                        first_hit_rank = r_idx
                        break

                query_record["configurations"][config_name] = {
                    "retrieved_pages": retrieved_pages[:10],
                    "retrieved_chunk_ids": retrieved_cids[:5],
                    "first_gold_page_rank": first_hit_rank,
                    "metrics": metrics,
                }

            query_level_traces.append(query_record)

        # Aggregate metrics across questions
        summary_table: Dict[str, Dict[str, float]] = {}
        for config_name in self.CONFIGURATIONS:
            summary_table[config_name] = aggregate_query_metrics(results_by_config[config_name])

        return {
            "total_questions_evaluated": len(query_level_traces),
            "summary_table": summary_table,
            "query_level_traces": query_level_traces,
        }

    def export_reports(
        self,
        ablation_results: Dict[str, Any],
        output_dir: Path,
    ) -> Tuple[Path, Path]:
        """
        Exports retrieval_ablation.json and retrieval_ablation.csv.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "retrieval_ablation.json"
        csv_path = output_dir / "retrieval_ablation.csv"

        # 1. Export JSON
        json_path.write_text(json.dumps(ablation_results, indent=2), encoding="utf-8")

        # 2. Export CSV
        summary = ablation_results.get("summary_table", {})
        headers = ["Retriever Configuration", "Recall@1", "Recall@5", "Recall@10", "Recall@20", "MRR@10", "nDCG@10", "MAP@10"]
        rows = []
        for cfg in self.CONFIGURATIONS:
            metrics = summary.get(cfg, {})
            rows.append([
                cfg,
                metrics.get("recall@1", 0.0),
                metrics.get("recall@5", 0.0),
                metrics.get("recall@10", 0.0),
                metrics.get("recall@20", 0.0),
                metrics.get("mrr@10", 0.0),
                metrics.get("ndcg@10", 0.0),
                metrics.get("map@10", 0.0),
            ])

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        return json_path, csv_path
