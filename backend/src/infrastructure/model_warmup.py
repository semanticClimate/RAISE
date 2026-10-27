"""
RAISE Neural Model Pre-Warming Engine
=====================================
Asynchronously pre-warms local neural inference models on host GPU/CPU at startup:
1. Dense Vector Embeddings (EMBEDDING_MODEL / EMBEDDING_DEVICE)
2. Contextual Cross-Encoder Reranker (RERANKER_MODEL / RERANKER_DEVICE)
3. NLI Claim Verification Gate (NLI_MODEL / NLI_DEVICE)

Executes a 1-token dummy inference on each to prime PyTorch CUDA kernels
and memory caches, eliminating first-query latency spikes and timeouts.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Dict

logger = logging.getLogger("raise.infrastructure.model_warmup")


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


def warmup_all_neural_models() -> Dict[str, float]:
    """
    Runs background pre-warming for embedding, reranking, and NLI models.
    Returns a dictionary of component latencies in milliseconds.
    """
    latencies: Dict[str, float] = {}
    _safe_print("\033[1;94m" + "=" * 78 + "\033[0m")
    _safe_print(" \033[1;94m[RAISE] PRE-WARMING NEURAL INFERENCE STACK (BACKGROUND GPU/CPU INIT)\033[0m")
    _safe_print(f"  * Embedding Model : \033[93m{os.getenv('EMBEDDING_MODEL', 'BAAI/bge-large-en-v1.5')}\033[0m (Device: \033[96m{os.getenv('EMBEDDING_DEVICE', 'cuda')}\033[0m)")
    _safe_print(f"  * Context Reranker: \033[93m{os.getenv('RERANKER_MODEL', 'BAAI/bge-reranker-large')}\033[0m (Device: \033[96m{os.getenv('RERANKER_DEVICE', 'cuda')}\033[0m)")
    _safe_print(f"  * NLI Verifier    : \033[93m{os.getenv('NLI_MODEL', 'dleemiller/finecat-nli-l')}\033[0m (Device: \033[96m{os.getenv('NLI_DEVICE', 'cuda')}\033[0m)")
    _safe_print("\033[1;94m" + "-" * 78 + "\033[0m")

    # 1. Pre-warm Embedding Model
    try:
        from src.infrastructure.vector.chroma import LocalVectorEngine
        t0 = time.perf_counter()
        ve = LocalVectorEngine()
        model = ve._get_embedding_model()
        if model is not None:
            # Prime PyTorch CUDA kernels with dummy encode
            _ = model.encode(["warmup query for cuda context initialization"], show_progress_bar=False)
            dur = round((time.perf_counter() - t0) * 1000, 1)
            latencies["embedding"] = dur
            logger.info("Local embedding model (%s) pre-warmed in %sms.", ve.model_key, dur)
            _safe_print(f" \033[1;92m[OK]\033[0m \033[97mDense Embeddings Ready\033[0m     : \033[93m{ve.model_key}\033[0m ({dur}ms)")
        else:
            logger.warning("Local embedding model could not be loaded.")
    except Exception as exc:
        logger.warning("Embedding model pre-warming notice: %s", exc)

    # 2. Pre-warm Cross-Encoder Reranker Model
    try:
        from src.retrieval.reranker import CrossEncoderReranker
        t0 = time.perf_counter()
        reranker = CrossEncoderReranker()
        reranker._ensure_model_loaded()
        if reranker.model is not None:
            # Prime PyTorch CUDA kernels with dummy cross-encoder prediction
            _ = reranker.model.predict([("warmup query", "warmup passage")], show_progress_bar=False)
            dur = round((time.perf_counter() - t0) * 1000, 1)
            latencies["reranker"] = dur
            logger.info("Contextual Cross-Encoder reranker (%s) pre-warmed in %sms.", reranker.model_name, dur)
            _safe_print(f" \033[1;92m[OK]\033[0m \033[97mContextual Reranker Ready\033[0m  : \033[93m{reranker.model_name}\033[0m ({dur}ms)")
        else:
            logger.warning("Cross-Encoder reranker could not be loaded; using heuristic fallback.")
    except Exception as exc:
        logger.warning("Reranker pre-warming notice: %s", exc)

    # 3. Pre-warm NLI Verifier Model
    try:
        from src.features.evaluation.nli_verifier import FineCatNLIVerifier
        t0 = time.perf_counter()
        if FineCatNLIVerifier._ensure_loaded():
            verifier = FineCatNLIVerifier()
            # Prime PyTorch CUDA kernels with dummy classification
            _ = verifier.classify_pair("The company reported revenue of 50M.", "The company reported revenue.")
            dur = round((time.perf_counter() - t0) * 1000, 1)
            latencies["nli"] = dur
            logger.info("NLI Claim Verifier (%s) pre-warmed in %sms.", FineCatNLIVerifier.MODEL_ID, dur)
            _safe_print(f" \033[1;92m[OK]\033[0m \033[97mNLI Verifier Gate Ready\033[0m    : \033[93m{verifier.model_id}\033[0m ({dur}ms)")
        else:
            logger.info("NLI verifier offline; deterministic lexical claim verification active.")
    except Exception as exc:
        logger.warning("NLI verifier pre-warming notice: %s", exc)

    _safe_print("\033[1;94m" + "=" * 78 + "\033[0m")
    return latencies
