"""
RAISE Neural Model Pre-Warming Engine
=====================================
Asynchronously pre-warms local neural inference models on host GPU/CPU at startup:
1. Dense Vector Embeddings (EMBEDDING_MODEL / EMBEDDING_DEVICE)
2. Contextual Cross-Encoder Reranker (RERANKER_MODEL / RERANKER_DEVICE)
3. NLI Claim Verification Gate (NLI_MODEL / NLI_DEVICE)

Executes a 1-token dummy inference on each to prime PyTorch CUDA kernels
and memory caches, eliminating first-query latency spikes and timeouts.
Guarantees thread-safe and process-wide singleton execution across all import paths.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Dict, Optional, Any
from src.core.config import models

logger = logging.getLogger("raise.infrastructure.model_warmup")

# Process-wide lock stored on `sys` to prevent dual-import aliasing in sys.modules
if not hasattr(sys, "_raise_warmup_lock"):
    sys._raise_warmup_lock = threading.Lock()  # type: ignore[attr-defined]
    sys._raise_models_loaded = False           # type: ignore[attr-defined]
    sys._raise_warmup_in_progress = False      # type: ignore[attr-defined]
    sys._raise_warmed_latencies = {}           # type: ignore[attr-defined]

# Backwards-compatible aliases
_WARMUP_LOCK = sys._raise_warmup_lock


def is_neural_stack_ready() -> bool:
    """Returns True once all neural models have finished pre-warming."""
    return bool(getattr(sys, "_raise_models_loaded", False))


def _safe_print(msg: str) -> None:
    """Prints message safely to stdout, handling Windows cp1252 charmap encoding."""
    try:
        print(msg)
    except (UnicodeEncodeError, Exception):
        try:
            sys.stdout.write(msg.encode("ascii", errors="replace").decode("ascii") + "\n")
            sys.stdout.flush()
        except Exception:
            pass


def warmup_all_neural_models(
    force: bool = False,
    rag_engine: Optional[Any] = None,
) -> Dict[str, float]:
    """
    Pre-warms the exact singleton models attached to `rag_engine` in-place.
    Guarantees process-wide single execution across all import paths.
    """
    with sys._raise_warmup_lock:  # type: ignore[attr-defined]
        if getattr(sys, "_raise_models_loaded", False) and not force:
            return getattr(sys, "_raise_warmed_latencies", {})
        if getattr(sys, "_raise_warmup_in_progress", False) and not force:
            logger.info("Neural model pre-warming already in progress; skipping duplicate call.")
            return getattr(sys, "_raise_warmed_latencies", {})
        sys._raise_warmup_in_progress = True  # type: ignore[attr-defined]

    latencies: Dict[str, float] = {}
    try:
        import torch
        inference_ctx = torch.inference_mode()
    except Exception:
        from contextlib import nullcontext
        inference_ctx = nullcontext()

    try:
        # Resolve shared rag_engine singleton from app.py if not explicitly passed
        if rag_engine is None:
            try:
                import app as rag_app_module
                rag_engine = getattr(rag_app_module, "rag_engine", None)
            except Exception:
                pass

        _safe_print(f"  \033[1;94m\u25cf\033[0m \033[1mPre-warming Neural Stack\033[0m \033[90m(Embedding, Reranker, NLI)...\033[0m")

        with inference_ctx:
            # 1. Pre-warm Dense Embedding Model on shared vector_engine singleton
            try:
                t0 = time.perf_counter()
                if rag_engine is not None and hasattr(rag_engine, "vector_engine"):
                    ve = rag_engine.vector_engine
                else:
                    from src.infrastructure.vector.chroma import LocalVectorEngine
                    ve = LocalVectorEngine()

                model = ve._get_embedding_model()
                if model is not None:
                    _ = model.encode(
                        ["warmup query for cuda context initialization"],
                        show_progress_bar=False,
                    )
                    dur = round((time.perf_counter() - t0) * 1000, 1)
                    latencies["embedding"] = dur
                    m_key = getattr(ve, "model_key", getattr(ve, "model_path", "Dense Embeddings"))
                    logger.info("Local embedding model (%s) pre-warmed in %sms.", m_key, dur)
                    _safe_print(f"  \033[1;92m\u2713\033[0m \033[97mDense Embeddings Ready\033[0m    \033[90m\u2192\033[0m \033[93m{m_key}\033[0m \033[90m({dur}ms)\033[0m")
                else:
                    logger.warning("Local embedding model could not be loaded.")
            except Exception as exc:
                logger.warning("Embedding model pre-warming notice: %s", exc)

            # 2. Pre-warm Contextual Cross-Encoder Reranker on shared singleton
            try:
                t0 = time.perf_counter()
                reranker = getattr(rag_engine, "reranker", None) if rag_engine else None
                if reranker is None:
                    from src.retrieval.reranker import CrossEncoderReranker
                    reranker = CrossEncoderReranker()
                reranker._ensure_model_loaded()
                if reranker.model is not None:
                    try:
                        if hasattr(reranker.model, "rerank"):
                            _ = reranker.model.rerank("warmup query", ["warmup passage"])
                        elif hasattr(reranker.model, "predict"):
                            _ = reranker.model.predict(
                                [("warmup query", "warmup passage")],
                                show_progress_bar=False,
                            )
                    except Exception:
                        pass
                    dur = round((time.perf_counter() - t0) * 1000, 1)
                    latencies["reranker"] = dur
                    logger.info("Contextual Cross-Encoder reranker (%s) pre-warmed in %sms.", reranker.model_name, dur)
                    _safe_print(f"  \033[1;92m\u2713\033[0m \033[97mContextual Reranker Ready\033[0m \033[90m\u2192\033[0m \033[93m{reranker.model_name}\033[0m \033[90m({dur}ms)\033[0m")
                else:
                    logger.warning("Cross-Encoder reranker could not be loaded; using heuristic fallback.")
            except Exception as exc:
                logger.warning("Reranker pre-warming notice: %s", exc)

            # 3. Pre-warm NLI Verifier Gate
            try:
                from src.features.evaluation.nli_verifier import FineCatNLIVerifier
                t0 = time.perf_counter()
                if FineCatNLIVerifier._ensure_loaded():
                    verifier = FineCatNLIVerifier()
                    _ = verifier.classify_pair(
                        "The company reported revenue of 50M.",
                        "The company reported revenue.",
                    )
                    dur = round((time.perf_counter() - t0) * 1000, 1)
                    latencies["nli"] = dur
                    logger.info("NLI Claim Verifier (%s) pre-warmed in %sms.", FineCatNLIVerifier.MODEL_ID, dur)
                    _safe_print(f"  \033[1;92m\u2713\033[0m \033[97mNLI Verifier Gate Ready\033[0m   \033[90m\u2192\033[0m \033[93m{verifier.model_id}\033[0m \033[90m({dur}ms)\033[0m")
                else:
                    logger.info("NLI verifier offline; deterministic lexical claim verification active.")
            except Exception as exc:
                logger.warning("NLI verifier pre-warming notice: %s", exc)
    finally:
        with sys._raise_warmup_lock:  # type: ignore[attr-defined]
            sys._raise_models_loaded = True         # type: ignore[attr-defined]
            sys._raise_warmup_in_progress = False    # type: ignore[attr-defined]
            sys._raise_warmed_latencies = latencies  # type: ignore[attr-defined]

    return latencies
