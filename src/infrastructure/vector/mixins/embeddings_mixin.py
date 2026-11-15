"""

ChromaDB Dense Vector Embeddings & Model Management Mixin

=========================================================

Manages embedding models (BGE-Large, BGE-M3, MiniLM, Qwen), local CUDA/CPU device assignment,

offline fallback vectors, embedding vector validation, and query instruction formatting.



Architectural Role & Guarantees:

--------------------------------

1. Supported Embedding Models:

   - `BAAI/bge-large-en-v1.5` (1024-dim, default SOTA academic dense representation)

   - `BAAI/bge-m3` (1024-dim, multilingual + multi-granularity)

   - `sentence-transformers/all-MiniLM-L6-v2` (384-dim, ultra-fast lightweight CPU benchmark model)

   - `Qwen/Qwen3-Embedding-4B` (4096-dim high-capacity instruction-tuned model)



2. Hardware Selection:

   - Auto-detects CUDA GPU availability with graceful fallback to CPU.

   - Respects `RAISE_EMBEDDING_DEVICE` environment variable override.



3. Asymmetric Query Prefixes:

   - BGE models require: `"Represent this sentence for searching relevant passages: {query}"`

   - E5 models require: `"query: {query}"`

   - Qwen models require: `"Instruct: Retrieve relevant academic passages for research question\nQuery: {query}"`

   - MiniLM requires no prefix.



4. Vector Integrity Validation (`validate_embedding_vector`):

   - Confirms length matches expected dimension (e.g. 1024).

   - Rejects NaN, Inf, nulls, and all-zero degenerate vectors.



How to Extend or Tune:

----------------------

- To add a new embedding model, register its HuggingFace identifier in `AVAILABLE_MODELS`.

- To update query instruction prompts, adjust `format_query_for_embedding()`.

"""



from __future__ import annotations



import os

import math

import warnings

from pathlib import Path

from typing import List, Optional, Dict, Tuple, Any

import threading

from src.core.config import (
    models,
    AVAILABLE_EMBEDDING_MODELS,
    EMBEDDING_FALLBACKS_768,
    EMBEDDING_FALLBACKS_1024,
)

_EMBEDDING_MODEL_CACHE: Dict[Tuple[str, str], Any] = {}
_EMBEDDING_LOCK = threading.Lock()


class VectorEmbeddingsMixin:
    """Provides dense embedding computation, model loading, and vector validation."""

    AVAILABLE_MODELS = AVAILABLE_EMBEDDING_MODELS



    @property

    def dimension(self) -> int:

        """Returns embedding vector dimension, detected dynamically from model or config."""

        if getattr(self, "embed_model", None) is not None:

            try:

                dim = getattr(self.embed_model, "get_embedding_dimension", getattr(self.embed_model, "get_sentence_embedding_dimension", None))()

                if dim and int(dim) > 0:

                    return int(dim)

            except Exception:

                pass

        env_dim = os.getenv("EMBEDDING_DIMENSION")

        if env_dim:

            try:

                return int(env_dim)

            except ValueError:

                pass

        model_name = getattr(self, "model_key", "").lower()

        if "minilm" in model_name:

            return 384

        if models.EMBEDDING_MODEL_KEYWORD in model_name or models.GEMMA_KEYWORD in model_name or "bge-base" in model_name or "mpnet" in model_name:

            return 768

        if "qwen" in model_name and "4b" in model_name:

            return 4096

        return 1024



    def _get_embedding_model(self):

        """

        Thread-safe singleton loader for SentenceTransformer embedding model into target device.

        Guarantees exact singleton caching across all threads and instances.

        """

        if getattr(self, "embed_model", None) is not None:

            return self.embed_model



        with _EMBEDDING_LOCK:

            if getattr(self, "embed_model", None) is not None:
                return self.embed_model

            # 1. Initialize identifiers outside the try block to avoid UnboundLocalError
            model_id = getattr(self, "model_path", None) or os.getenv("EMBEDDING_MODEL", models.EMBEDDING_MODEL_NAME)
            raw_id = getattr(self, "AVAILABLE_MODELS", {}).get(model_id, model_id) if hasattr(self, "AVAILABLE_MODELS") else model_id
            resolved_id = str(raw_id)
            dev = "cpu"
            cache_key = None

            try:
                import torch
                from sentence_transformers import SentenceTransformer
                from src.core.config import resolve_local_model_path

                cache_folder = os.getenv("HF_HOME", str(Path.home() / ".cache" / "huggingface" / "hub"))
                if getattr(self, "device_override", None):
                    dev = str(self.device_override).lower()
                else:
                    env_dev = os.getenv("EMBEDDING_DEVICE") or os.getenv("RAISE_EMBEDDING_DEVICE") or os.getenv("NEURAL_DEVICE")
                    dev = env_dev.lower() if env_dev else ("cuda" if torch.cuda.is_available() else "cpu")
                if dev in ("auto", "none", "", "default") or ("cuda" in dev and not torch.cuda.is_available()):
                    dev = "cuda" if torch.cuda.is_available() else "cpu"

                resolved_id = resolve_local_model_path(raw_id)
                cache_key = (str(resolved_id), str(dev))

                if cache_key in _EMBEDDING_MODEL_CACHE:
                    self.embed_model = _EMBEDDING_MODEL_CACHE[cache_key]
                    return self.embed_model

                token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
                embed_cfg = {"audio_config": None, "vision_config": None} if models.EMBEDDING_MODEL_KEYWORD in str(raw_id).lower() else None
                dtype_val = (
                    torch.bfloat16
                    if (torch.cuda.is_available() and torch.cuda.is_bf16_supported())
                    else (torch.float16 if torch.cuda.is_available() else torch.float32)
                )

                for local_only in (True, False):
                    try:
                        self.embed_model = SentenceTransformer(
                            resolved_id,
                            cache_folder=cache_folder,
                            local_files_only=local_only,
                            device=dev,
                            token=token,
                            trust_remote_code=True,
                            config_kwargs=embed_cfg,
                            model_kwargs={"dtype": dtype_val},
                        )
                        break
                    except Exception:
                        if not local_only:
                            raise

                if self.embed_model is not None:
                    _EMBEDDING_MODEL_CACHE[cache_key] = self.embed_model

            except Exception as e:
                target_dim = getattr(self, "dimension", 768)
                raw_id_str = str(raw_id).lower() if raw_id else ""
                gemma_kw = str(models.GEMMA_KEYWORD).lower()
                if target_dim == 768 or gemma_kw in raw_id_str:
                    fallback_candidates = list(EMBEDDING_FALLBACKS_768)
                elif target_dim == 1024:
                    fallback_candidates = list(EMBEDDING_FALLBACKS_1024)
                else:
                    fallback_candidates = list(EMBEDDING_FALLBACKS_768)

                print(f"SentenceTransformer load error ({raw_id}): {e}. Attempting dimension-compatible fallback ({target_dim}-dim) to {fallback_candidates[0]}.")

                fallback_loaded = False
                for fb_id in fallback_candidates:
                    try:
                        from sentence_transformers import SentenceTransformer
                        self.embed_model = SentenceTransformer(fb_id, device=dev)
                        _EMBEDDING_MODEL_CACHE[(str(fb_id), str(dev))] = self.embed_model
                        if cache_key is not None:
                            _EMBEDDING_MODEL_CACHE[cache_key] = self.embed_model
                        if raw_id:
                            _EMBEDDING_MODEL_CACHE[(str(raw_id), str(dev))] = self.embed_model
                        fallback_loaded = True
                        print(f"Embedding fallback ({fb_id}) loaded successfully ({target_dim}-dim compatible with ChromaDB).")
                        break
                    except Exception as fb_err:
                        print(f"Fallback {fb_id} failed: {fb_err}")

                if not fallback_loaded:
                    self.embed_model = None



        return getattr(self, "embed_model", None)



    def validate_embedding_vector(self, vec: List[float], expected_dim: Optional[int] = None) -> bool:

        """

        Validates embedding vector integrity:

          - Non-empty list/array of floats

          - Exact expected dimension match (e.g. 1024 or 384)

          - No NaN, Inf, or null values

          - Non-degenerate (not all zeros)

        """

        if not vec or not isinstance(vec, (list, tuple)):

            return False

        dim = expected_dim or self.dimension

        if len(vec) != dim:

            return False

        has_nonzero = False

        for val in vec:

            if val is None or math.isnan(val) or math.isinf(val):

                return False

            if abs(val) > 1e-9:

                has_nonzero = True

        return has_nonzero



    def compute_embeddings(self, texts: List[str], is_query: bool = False) -> List[List[float]]:

        """

        Computes normalized dense vector embeddings under torch.inference_mode().

        Uses native task prompt templates for EmbeddingGemma-2 if available.

        Never falls back to random noise: raises on failure to protect database integrity.

        """

        if not texts:

            return []

        dim = self.dimension

        model = self._get_embedding_model()

        if model is None:

            raise RuntimeError(f"Embedding model '{getattr(self, 'model_key', 'embedding')}' is not available.")



        import torch

        encode_kwargs: Dict[str, Any] = {

            "convert_to_numpy": True,

            "normalize_embeddings": True,

            "batch_size": 64,

            "show_progress_bar": False,

        }

        # Use native SentenceTransformers prompt templates for EmbeddingGemma-2 if registered

        prompts = getattr(model, "prompts", {}) or {}

        if is_query and "Retrieval-query" in prompts:

            encode_kwargs["prompt_name"] = "Retrieval-query"

        elif (not is_query) and "Retrieval-document" in prompts:

            encode_kwargs["prompt_name"] = "Retrieval-document"



        with torch.inference_mode():

            embeddings = model.encode(texts, **encode_kwargs)

        vec_list = embeddings.tolist()

        if vec_list and all(self.validate_embedding_vector(v, dim) for v in vec_list):

            return vec_list

        raise ValueError("Generated embeddings failed dimension or NaN/zero validation.")



    def format_query_for_embedding(self, query: str) -> str:

        """

        Applies asymmetric task instruction prefixes for modern SOTA retrieval models (BGE, E5, Qwen).

        Leaves SBERT (all-MiniLM-L6-v2) unmodified.

        """

        model_name = self.model_key.lower()

        if "bge" in model_name:

            return f"Represent this sentence for searching relevant passages: {query}"

        elif "e5" in model_name:

            return f"query: {query}"

        elif "qwen" in model_name:

            return f"Instruct: Retrieve relevant academic passages for research question\nQuery: {query}"

        return query

