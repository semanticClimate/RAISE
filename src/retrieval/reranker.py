"""
RAISE Cross-Encoder Contextual Reranker Engine
==============================================
Component: `src.retrieval.reranker`
Architecture Layer: Retrieval / Cross-Attention Scoring & Multi-Query Max-Pooling

Overview:
---------
Performs high-precision cross-attention relevance scoring between incoming queries
(including decomposed sub-queries) and candidate text chunks.

Key Capabilities:
1. Lazy Singleton Model Loading:
   - Supports `BAAI/bge-reranker-large` (primary) and `cross-encoder/ms-marco-MiniLM-L-6-v2` (fallback).
   - Loads weights lazily into GPU/CPU memory once and caches across queries.
2. Context Window Extraction:
   - Scans text passages for query structural keywords (e.g. `balance sheet`, `schedule 3`, `table 4`)
     and semantic terms to center the 2,500-character CrossEncoder attention window on the densest information region.
3. Multi-Hop Subquery Max-Pooling:
   - Computes: `score(c) = max(CrossEncoder(Q_raw, c), max_i CrossEncoder(Q_sub_i, c))`
   - Prevents score dilution when candidate chunks answer an atomic leg of a complex decomposed question.
4. Institutional Boundary Enforcement:
   - Automatically prunes candidates from conflicting institutions before final ranking.
5. Prior Calibration Guardrails:
   - Preserves high-consensus Reciprocal Rank Fusion (RRF) candidates to maintain retrieval recall.
"""

from __future__ import annotations

import logging
import os
import re
import math
import threading
from typing import Any, Dict, List, Optional, Tuple

from src.retrieval.entity_filtering import filter_entity_mismatches
from src.core.config import models, AVAILABLE_RERANKER_MODELS

logger = logging.getLogger("raise.retrieval.reranker")

_CROSS_ENCODER_MODEL_CACHE: Dict[str, Any] = {}
_RERANKER_LOCK = threading.Lock()
_GLOBAL_FLASHRANKER: Optional[Any] = None


def _get_global_flashranker() -> Optional[Any]:
    global _GLOBAL_FLASHRANKER
    if _GLOBAL_FLASHRANKER is None:
        try:
            from flashrank import Ranker
            _GLOBAL_FLASHRANKER = Ranker()
        except Exception:
            _GLOBAL_FLASHRANKER = False
    return _GLOBAL_FLASHRANKER if _GLOBAL_FLASHRANKER is not False else None


def is_table_candidate(candidate: Dict[str, Any] | Any) -> bool:
    """Detects whether candidate contains tabular, markdown schedule, scientific data, or financial grid structure."""
    if hasattr(candidate, "page_content"):
        txt = str(candidate.page_content or "")
        meta = getattr(candidate, "metadata", {}) or {}
    else:
        txt = str(candidate.get("plain_text") or candidate.get("text") or "")
        meta = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else candidate

    txt_lower = txt.lower()
    structural_keywords = (
        "balance sheet" in txt_lower
        or "income & expenditure" in txt_lower
        or "income and expenditure" in txt_lower
        or "schedule forming part" in txt_lower
        or "receipts and payments" in txt_lower
        or "corpus/capital fund" in txt_lower
        or "earmarked / endowment" in txt_lower
        or "establishment expenses" in txt_lower
        or "figure " in txt_lower
        or "fig. " in txt_lower
        or "appendix" in txt_lower
        or "exhibit" in txt_lower
        or "supplementary" in txt_lower
        or "dataset" in txt_lower
        or "benchmark" in txt_lower
        or "methodology" in txt_lower
        or "equation" in txt_lower
        or "theorem" in txt_lower
        or "algorithm" in txt_lower
    )

    return (
        "| --- |" in txt
        or "|:---" in txt
        or "| ---:" in txt
        or "### Extracted Table" in txt
        or structural_keywords
        or bool(meta.get("has_table"))
        or bool(meta.get("is_table"))
        or int(meta.get("tables_count", 0) or 0) > 0
    )


class CrossEncoderReranker:
    """
    Cross-Encoder Contextual Reranking supporting BAAI/bge-reranker-large
    and cross-encoder/ms-marco-MiniLM-L-6-v2 with fallback token-level cross-attention heuristic scoring.
    Loads weights lazily on first rerank() call and caches as singleton in memory for instant reuse.
    """

    AVAILABLE_RERANKERS = AVAILABLE_RERANKER_MODELS

    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        target_name = model_name or os.getenv("RERANKER_MODEL", models.RERANKER_MODEL_NAME)
        self.model_name = self.AVAILABLE_RERANKERS.get(target_name, target_name)
        self.device = device or os.getenv("RERANKER_DEVICE")
        self.model = _CROSS_ENCODER_MODEL_CACHE.get(self.model_name)
        self._loaded = self.model is not None

    def _ensure_model_loaded(self):
        """Thread-safe lazy singleton loader for CrossEncoder / Jina Reranker."""
        if self.model is not None:
            return
        with _RERANKER_LOCK:
            if self.model is not None:
                return
            if self.model_name in _CROSS_ENCODER_MODEL_CACHE:
                self.model = _CROSS_ENCODER_MODEL_CACHE[self.model_name]
                self._loaded = True
                return
            if self._loaded and self.model is None:
                return
            self._loaded = True
        try:
            from sentence_transformers import CrossEncoder
            import torch
            import warnings

            dev = self.device or os.getenv("RERANKER_DEVICE") or os.getenv("NEURAL_DEVICE")
            if dev:
                dev = str(dev).lower()
                if dev in ("auto", "none", "", "default"):
                    dev = "cuda" if torch.cuda.is_available() else "cpu"
                elif "cuda" in dev and not torch.cuda.is_available():
                    logger.warning("CUDA requested for reranker (%s) but torch.cuda.is_available() is False. Using CPU.", self.model_name)
                    dev = "cpu"
            else:
                dev = "cuda" if torch.cuda.is_available() else "cpu"

            token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
            orig_requested_model = self.model_name
            try:
                from src.core.config import resolve_local_model_path
                resolved_name = resolve_local_model_path(self.model_name)
                target_model = resolved_name

                target_dtype = (
                    torch.bfloat16
                    if ("cuda" in dev and torch.cuda.is_bf16_supported())
                    else (torch.float16 if "cuda" in dev else torch.float32)
                )
                try:
                    loaded_model = CrossEncoder(
                        target_model,
                        device=dev,
                        token=token,
                        trust_remote_code=True,
                        model_kwargs={"dtype": target_dtype},
                    )
                except Exception:
                    loaded_model = CrossEncoder(
                        target_model,
                        device=dev,
                        token=token,
                        trust_remote_code=True,
                    )
                self.model = loaded_model
                self.model_name = target_model
                _CROSS_ENCODER_MODEL_CACHE[self.model_name] = loaded_model
                _CROSS_ENCODER_MODEL_CACHE[orig_requested_model] = loaded_model
                _CROSS_ENCODER_MODEL_CACHE[models.RERANKER_MODEL_NAME] = loaded_model
                _CROSS_ENCODER_MODEL_CACHE["default"] = loaded_model
                logger.info("Cross-Attention Reranker (%s) initialized successfully on %s.", target_model, dev)
            except Exception as e:
                logger.warning("Could not load primary reranker (%s): %s. Attempting fallback.", self.model_name, e)
                try:
                    fallback_name = models.RERANKER_FALLBACK_MODEL_NAME
                    if fallback_name in _CROSS_ENCODER_MODEL_CACHE:
                        self.model = _CROSS_ENCODER_MODEL_CACHE[fallback_name]
                        self.model_name = fallback_name
                    else:
                        loaded_model = CrossEncoder(
                            fallback_name,
                            device=dev,
                            token=token,
                        )
                        self.model = loaded_model
                        self.model_name = fallback_name
                        _CROSS_ENCODER_MODEL_CACHE[fallback_name] = loaded_model
                    # Crucial: Cache under the original requested model key so future queries don't retry & reload
                    _CROSS_ENCODER_MODEL_CACHE[orig_requested_model] = self.model
                    _CROSS_ENCODER_MODEL_CACHE["default"] = self.model
                    logger.info("CrossEncoder fallback reranker (%s) loaded.", fallback_name)
                except Exception as fe:
                    logger.warning("Could not load fallback reranker: %s. Using heuristic cross-scoring.", fe)
                    self.model = None
        except Exception as e:
            logger.warning("Reranker initialization exception: %s", e)
            self.model = None

    async def arerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        text_key: str = "plain_text",
        top_n: int = 8,
        subqueries: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Asynchronously dispatches reranking to thread executor to keep event loop free."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.rerank(
                query=query,
                candidates=candidates,
                text_key=text_key,
                top_n=top_n,
                subqueries=subqueries,
            ),
        )

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        text_key: str = "plain_text",
        top_n: int = 8,
        subqueries: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Computes query-candidate cross-attention relevance scores and filters peripheral neighbors.
        Supports multi-hop sub-query max-pooling:
        score(c) = max(CrossEncoder(Q_raw, c), max_i CrossEncoder(Q_sub_i, c))
        This eliminates score collapse for atomic multi-hop facts.
        """
        if not candidates:
            return []

        self._ensure_model_loaded()

        all_queries = [query]
        if subqueries:
            for sq in subqueries:
                sq_clean = sq.strip()
                if sq_clean and sq_clean.lower() != query.strip().lower() and sq_clean not in all_queries:
                    all_queries.append(sq_clean)

        stop_words = {"what", "which", "where", "when", "that", "this", "from", "with", "have", "does", "about", "into"}
        structural_pattern = (
            r"(?:table\s*\d+(?:\.\d+)?|figure\s*\d+|fig\.\s*\d+|appendix\s*[a-z0-9]+|exhibit\s*[a-z0-9]+|"
            r"algorithm\s*\d+|schedule\s*\d+|section\s*\d+|equation\s*\d+|theorem\s*\d+|"
            r"supplementary|dataset|benchmark|methodology|"
            r"balance\s*sheet|income\s*(?:and|&)\s*expenditure|corpus|endowment|grants|signatories|establishment\s*expenses)"
        )
        global_structural_terms = re.findall(
            structural_pattern,
            query,
            re.IGNORECASE,
        )

        all_pairs: List[Tuple[str, str]] = []
        for q in all_queries:
            q_structural = re.findall(
                structural_pattern,
                q,
                re.IGNORECASE,
            )
            q_words = [w for w in re.findall(r"\b[a-zA-Z0-9_\-]{4,}\b", q) if w.lower() not in stop_words]

            for c in candidates:
                if hasattr(c, "page_content"):
                    text = str(c.page_content or "")
                else:
                    text = str(c.get("enriched_text") or c.get(text_key) or c.get("text") or c.get("plain_text") or c.get("heading") or "")
                snippet = text[:3000]

                all_matches = []
                for qt in q_structural:
                    for m in re.finditer(re.escape(qt), text, re.IGNORECASE):
                        all_matches.append((m.start(), 5))
                for qw in q_words:
                    for m in re.finditer(r"\b" + re.escape(qw) + r"\b", text, re.IGNORECASE):
                        all_matches.append((m.start(), 1))

                if all_matches:
                    best_idx = all_matches[0][0]
                    best_score = -1
                    for idx, _ in all_matches:
                        window_score = sum(weight for m_pos, weight in all_matches if idx - 150 <= m_pos <= idx + 650)
                        if window_score > best_score:
                            best_score = window_score
                            best_idx = idx

                    start_idx = max(0, best_idx - 250)
                    snippet = text[start_idx : start_idx + 2500]

                all_pairs.append((q, snippet))

        if self.model is not None:
            try:
                if hasattr(self.model, "rerank"):
                    all_scores = []
                    for q in all_queries:
                        cand_texts = [p[1] for p in all_pairs if p[0] == q]
                        if cand_texts:
                            res = self.model.rerank(q, cand_texts, max_query_length=512, max_length=1024)
                            q_scores = [0.0] * len(cand_texts)
                            for r in res:
                                q_scores[int(r["index"])] = float(r["relevance_score"])
                            all_scores.extend(q_scores)
                        else:
                            all_scores.extend([0.0] * len(candidates))
                elif hasattr(self.model, "predict"):
                    raw_scores = self.model.predict(all_pairs, batch_size=64, show_progress_bar=False)
                    all_scores = [float(s) for s in raw_scores]
                else:
                    all_scores = self._score_with_flashrank_or_heuristic(all_pairs)
            except Exception:
                all_scores = self._score_with_flashrank_or_heuristic(all_pairs)
        else:
            all_scores = self._score_with_flashrank_or_heuristic(all_pairs)

        n_candidates = len(candidates)
        reranked = []
        for idx, c in enumerate(candidates):
            if hasattr(c, "page_content") and hasattr(c, "metadata"):
                entry = dict(c.metadata or {})
                entry["text"] = c.page_content
                entry["plain_text"] = c.page_content
                if "chunk_id" not in entry and "id" in entry:
                    entry["chunk_id"] = entry["id"]
            else:
                entry = dict(c)

            cand_raw = str(entry.get(text_key) or entry.get("text") or entry.get("plain_text") or entry.get("heading") or "")

            best_q_score = -999.0
            best_matched_q = query
            for q_idx, q_str in enumerate(all_queries):
                score_val = all_scores[q_idx * n_candidates + idx]
                if score_val > best_q_score:
                    best_q_score = score_val
                    best_matched_q = q_str

            # Normalize raw logit score to [0.0, 1.0] if model returned uncalibrated logits
            prob_score = (
                1.0 / (1.0 + math.exp(-max(min(best_q_score, 10.0), -10.0)))
                if (best_q_score < 0.0 or best_q_score > 1.0)
                else best_q_score
            )

            # Exact institutional role & modifier boost (e.g. 'nominees', 'appointed', 'positions', 'senate nominees')
            # Prevents generic large membership rosters from displacing targeted governance/administrative sections
            query_words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", query) if w.lower() not in stop_words]
            target_keywords = [
                kw for kw in query_words
                if kw in {"nominee", "nominees", "appointed", "positions", "visitor", "governors",
                          "chairman", "chancellor", "director", "registrar", "scientific", "technical"}
            ]
            cand_lower = cand_raw.lower()
            if target_keywords:
                matched_kw = sum(1 for kw in target_keywords if kw in cand_lower)
                if matched_kw > 0:
                    prob_score = min(1.0, prob_score + 0.10 * (matched_kw / len(target_keywords)))

            # Convex monotonic table boost (preserves strict ordering in [0.0, 1.0])
            has_table_match = (
                any(re.search(re.escape(qt), cand_raw, re.IGNORECASE) for qt in global_structural_terms)
                or (is_table_candidate(entry) and bool(global_structural_terms))
            )
            calibrated_score = prob_score + (0.08 * (1.0 - prob_score) if has_table_match else 0.0)

            entry["cross_encoder_score"] = round(calibrated_score, 6)
            entry["raw_cross_encoder_score"] = round(prob_score, 6)
            entry["matched_subquery"] = best_matched_q
            reranked.append(entry)

        reranked = filter_entity_mismatches(query, reranked)
        reranked.sort(key=lambda x: x["cross_encoder_score"], reverse=True)

        if reranked:
            # All scores are now strictly calibrated in [0.0, 1.0]
            filtered_by_score = [c for c in reranked if c["cross_encoder_score"] >= 0.05]
            top_candidates = (filtered_by_score if filtered_by_score else reranked)[:top_n]

            top_rrf = sorted([c for c in reranked if c.get("rrf_rank", 99) <= 2], key=lambda x: x.get("rrf_rank", 99))
            for rrf_cand in top_rrf:
                cid = rrf_cand.get("chunk_id") or rrf_cand.get("id")
                if not any((tc.get("chunk_id") or tc.get("id")) == cid for tc in top_candidates):
                    if len(top_candidates) >= top_n:
                        top_candidates[-1] = rrf_cand
                    else:
                        top_candidates.append(rrf_cand)
        else:
            top_candidates = []

        expanded_results = []
        seen_ids = set()
        for cand in top_candidates:
            cid = cand.get("chunk_id") or cand.get("id") or (
                cand.get("metadata", {}).get("chunk_id") if isinstance(cand.get("metadata"), dict) else None
            )
            if not cid:
                cid = f"chk_anon_{len(seen_ids)}"
            if cid not in seen_ids:
                seen_ids.add(cid)
                expanded_results.append(cand)

        return expanded_results[:top_n]

    def _score_with_flashrank_or_heuristic(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """
        Ultra-fast CPU transformer reranking using FlashRank (sub-query aware, zero-crash).
        Falls back to lexical cross-attention heuristic only if FlashRank is unavailable.
        """
        if not pairs:
            return []
        try:
            from flashrank import RerankRequest
            ranker = _get_global_flashranker()
            if ranker is not None:
                query_groups: Dict[str, List[Tuple[int, str]]] = {}
                for idx, (q, passage_text) in enumerate(pairs):
                    query_groups.setdefault(q, []).append((idx, passage_text))

                scores = [0.5] * len(pairs)
                for q_text, p_items in query_groups.items():
                    passages = [{"id": orig_idx, "text": txt} for orig_idx, txt in p_items]
                    req = RerankRequest(query=q_text, passages=passages)
                    results = ranker.rerank(req)
                    for item in results:
                        scores[item["id"]] = float(item["score"])
                return scores
        except Exception as e:
            logger.debug("FlashRank unavailable (%s); falling back to lexical heuristics.", e)

        all_scores = []
        for p_q, p_snip in pairs:
            all_scores.extend(self._heuristic_cross_attention_scores(p_q, [(p_q, p_snip)]))
        return all_scores

    def _heuristic_cross_attention_scores(
        self, query: str, pairs: List[Tuple[str, str]]
    ) -> List[float]:
        """High-precision lexical overlap & contextual co-occurrence fallback."""
        q_tokens = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", query.lower()))
        if not q_tokens:
            return [0.5] * len(pairs)

        scores = []
        for _, text in pairs:
            t_tokens = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", text.lower()))
            overlap = len(q_tokens.intersection(t_tokens))
            precision = overlap / len(q_tokens) if q_tokens else 0.0
            num_boost = 0.2 if re.search(r"\b(\d+|crore|lakh|inr|grant|patent)\b", text, re.IGNORECASE) else 0.0
            score = round(min(1.0, precision + num_boost), 4)
            scores.append(score)
        return scores


EvidenceReranker = CrossEncoderReranker


__all__ = ["CrossEncoderReranker", "EvidenceReranker", "is_table_candidate"]
