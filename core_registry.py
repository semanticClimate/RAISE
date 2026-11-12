"""
RAISE Core Registry & Contract-Locked System Architecture
=========================================================
Implements:
1. Bidirectional Contract Lock (Pydantic v2 populate_by_name=True + AliasChoices for camelCase & snake_case).
2. Zero-Token Live Key Verification (<150ms HTTP checks for Gemini, OpenAI, Anthropic, Groq, OpenRouter, HF).
3. Rust-Accelerated Downloads (HF_HUB_ENABLE_HF_TRANSFER=1) + Hot-Swappable Multi-Backend Registry.
4. Hardware-aware dynamic loading (CUDA bfloat16/float16, Apple Silicon MPS float16, or CPU float32).
5. Default Substrates:
   - Embedder: google/embeddinggemma-2 (+Vision toggle)
   - Reranker: jinaai/jina-reranker-v3.5 (Listwise AutoModel / CrossEncoder)
   - NLI Verifier: dleemiller/finecat-nli-ultra-l (SDPA Attention)
"""

from __future__ import annotations

import gc
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import torch
from fastapi import APIRouter, HTTPException
from huggingface_hub import HfApi, snapshot_download
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

logger = logging.getLogger("raise.core_registry")

# 1. Enable Rust-accelerated parallel downloads (5x-10x faster) if hf_transfer is installed
try:
    import hf_transfer  # noqa: F401
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
except ImportError:
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

router = APIRouter(tags=["System & Models"])


# =====================================================================
# LOCKED CONTRACTS (Accepts both camelCase and snake_case Variants!)
# =====================================================================
class KeyVerificationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    provider: str = Field(
        ...,
        validation_alias=AliasChoices("provider", "llm_provider", "service", "provider_id"),
    )
    api_key: str = Field(
        ...,
        validation_alias=AliasChoices(
            "api_key", "apiKey", "key", "token", "hf_token", "llmApiKey", "secret", "value"
        ),
    )
    target_repo: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("target_repo", "targetRepo", "repo_id", "repoId"),
    )


class ModelConfigRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    embedder_id: str = Field(
        "google/embeddinggemma-2",
        validation_alias=AliasChoices("embedder_id", "embedderId", "encoder", "embedding_model"),
    )
    reranker_id: str = Field(
        "jinaai/jina-reranker-v3.5",
        validation_alias=AliasChoices("reranker_id", "rerankerId", "reranker", "reranker_model"),
    )
    verifier_id: str = Field(
        "dleemiller/finecat-nli-ultra-l",
        validation_alias=AliasChoices(
            "verifier_id", "verifierId", "nli", "verifier", "nli_verifier_model", "nli_model"
        ),
    )
    hf_token: Optional[str] = Field(
        None,
        validation_alias=AliasChoices(
            "hf_token", "hfToken", "huggingface_token", "huggingfaceToken", "token"
        ),
    )
    use_vision: bool = Field(
        False,
        validation_alias=AliasChoices("use_vision", "useVision", "enable_vision"),
    )


# =====================================================================
# RUNTIME KEYSTORE & HARDWARE-AWARE MODEL REGISTRY
# =====================================================================
class RuntimeState:
    def __init__(self):
        self.keys: Dict[str, str] = {
            "huggingface": os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or "",
            "openai": os.getenv("OPENAI_API_KEY", ""),
            "gemini": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "",
            "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
            "groq": os.getenv("GROQ_API_KEY", ""),
            "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
            "mistral": os.getenv("MISTRAL_API_KEY", ""),
            "nvidia": os.getenv("NVIDIA_API_KEY", ""),
            "cohere": os.getenv("COHERE_API_KEY", ""),
            "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
        }

        # Auto-detect best hardware accelerator
        # NEVER use float16 with EmbeddingGemma-2 (causes NaN overflow)
        if torch.cuda.is_available():
            self.device = "cuda"
            self.dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
            self.dtype = torch.bfloat16
        else:
            self.device = "cpu"
            self.dtype = torch.float32

        self.embedder: Any = None
        self.reranker: Any = None
        self.reranker_type: str = "cross_encoder"  # "listwise" or "cross_encoder"
        self.verifier: Any = None
        self.active_config: Dict[str, Any] = {
            "embedder_id": "google/embeddinggemma-2",
            "reranker_id": "jinaai/jina-reranker-v3.5",
            "verifier_id": "dleemiller/finecat-nli-ultra-l",
            "use_vision": False,
        }

    def sanitize_key(self, raw_key: Optional[str]) -> str:
        """Strips quotes, newlines, spaces, and accidental 'Bearer ' prefixes."""
        cleaned = (raw_key or "").strip().strip('"').strip("'")
        if cleaned.lower().startswith("bearer "):
            cleaned = cleaned[7:].strip()
        return cleaned

    def get_memory_telemetry(self) -> Dict[str, Any]:
        """
        Dynamically detects live memory allocation across CUDA, Apple Silicon MPS, or CPU.
        Never hardcoded: accurately reflects current host resources and GPU limits.
        """
        telemetry: Dict[str, Any] = {
            "device": self.device,
            "dtype": str(self.dtype),
            "vram_mb": 0.0,
            "total_vram_mb": None,
            "free_vram_mb": None,
            "system_ram_used_mb": 0.0,
            "system_ram_total_mb": 0.0,
        }
        try:
            import psutil
            vm = psutil.virtual_memory()
            telemetry["system_ram_used_mb"] = round(vm.used / (1024 ** 2), 1)
            telemetry["system_ram_total_mb"] = round(vm.total / (1024 ** 2), 1)
        except Exception:
            pass

        if self.device == "cuda" and torch.cuda.is_available():
            try:
                allocated = torch.cuda.memory_allocated()
                telemetry["vram_mb"] = round(allocated / (1024 ** 2), 1)
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                telemetry["total_vram_mb"] = round(total_bytes / (1024 ** 2), 1)
                telemetry["free_vram_mb"] = round(free_bytes / (1024 ** 2), 1)
            except Exception:
                pass
        elif self.device == "mps":
            try:
                if hasattr(torch, "mps") and hasattr(torch.mps, "current_allocated_memory"):
                    allocated = torch.mps.current_allocated_memory()
                    telemetry["vram_mb"] = round(allocated / (1024 ** 2), 1)
                telemetry["total_vram_mb"] = telemetry.get("system_ram_total_mb")
            except Exception:
                pass

        return telemetry

    def unload_all(self):
        """Safely evicts model weights and purges VRAM allocations."""
        for attr in ("embedder", "reranker", "verifier"):
            if getattr(self, attr) is not None:
                delattr(self, attr)
                setattr(self, attr, None)
        gc.collect()
        if self.device == "cuda":
            torch.cuda.empty_cache()
        elif self.device == "mps" and hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
            try:
                torch.mps.empty_cache()
            except Exception:
                pass

    def get_configured_providers(self) -> List[str]:
        """Returns list of providers with actively configured keys."""
        configured = []
        for prov, key in self.keys.items():
            if key and len(key.strip()) > 3:
                configured.append(prov)
        return configured


state = RuntimeState()


def _persist_key_to_env(key_name: str, key_val: str):
    """Safely updates process environment and both backend/.env and root .env files."""
    os.environ[key_name] = key_val
    for env_path in [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]:
        if env_path.exists():
            try:
                lines = env_path.read_text(encoding="utf-8").splitlines()
                updated = False
                new_lines = []
                for line in lines:
                    line_str = line.strip()
                    if line_str.startswith(f"{key_name}=") or line_str.startswith(f"export {key_name}="):
                        new_lines.append(f"{key_name}={key_val}")
                        updated = True
                    else:
                        new_lines.append(line)
                if not updated:
                    new_lines.append(f"{key_name}={key_val}")
                env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to persist {key_name} to {env_path}: {e}")


# =====================================================================
# ENDPOINT 1: REAL-TIME ZERO-TOKEN KEY VERIFIER (Cloud LLMs + HF)
# =====================================================================
@router.post("/api/v1/system/keys/verify", operation_id="core_verify_api_keys_v1", include_in_schema=False)
@router.post("/api/system/keys/verify", operation_id="core_verify_api_keys_system", include_in_schema=False)
@router.post("/keys/verify", operation_id="core_verify_api_keys")
async def verify_and_save_key(req: KeyVerificationRequest):
    provider = req.provider.lower().strip()
    clean_key = state.sanitize_key(req.api_key)

    if not clean_key:
        raise HTTPException(status_code=400, detail="API key is empty after stripping whitespace.")

    default_headers = {"User-Agent": "RAISE-Academic-Studio/1.0"}
    async with httpx.AsyncClient(timeout=10.0, headers=default_headers) as client:
        try:
            if provider in ("huggingface", "hf"):
                api = HfApi(token=clean_key)
                user_info = api.whoami()
                # Optional: Check if user has access to a gated repo like google/embeddinggemma-2
                if req.target_repo:
                    api.model_info(req.target_repo, token=clean_key)
                state.keys["huggingface"] = clean_key
                _persist_key_to_env("HUGGINGFACE_TOKEN", clean_key)
                _persist_key_to_env("HF_TOKEN", clean_key)
                return {
                    "valid": True,
                    "provider": "huggingface",
                    "account": user_info.get("name") or user_info.get("fullname", "verified"),
                    "masked_key": f"{clean_key[:4]}...{clean_key[-4:]}",
                }

            elif provider == "openai":
                r = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {clean_key}"},
                )
                r.raise_for_status()
                state.keys["openai"] = clean_key
                os.environ["OPENAI_API_KEY"] = clean_key
                _persist_key_to_env("OPENAI_API_KEY", clean_key)
                os.environ["LLM_BACKEND"] = "openai"
                _persist_key_to_env("LLM_BACKEND", "openai")

            elif provider in ("gemini", "google"):
                r = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    headers={"x-goog-api-key": clean_key},
                )
                r.raise_for_status()
                state.keys["gemini"] = clean_key
                os.environ["GEMINI_API_KEY"] = clean_key
                os.environ["GOOGLE_API_KEY"] = clean_key
                _persist_key_to_env("GEMINI_API_KEY", clean_key)
                _persist_key_to_env("GOOGLE_API_KEY", clean_key)
                os.environ["LLM_BACKEND"] = "gemini"
                _persist_key_to_env("LLM_BACKEND", "gemini")

            elif provider == "anthropic":
                r = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": clean_key, "anthropic-version": "2023-06-01"},
                )
                r.raise_for_status()
                state.keys["anthropic"] = clean_key
                os.environ["ANTHROPIC_API_KEY"] = clean_key
                _persist_key_to_env("ANTHROPIC_API_KEY", clean_key)
                os.environ["LLM_BACKEND"] = "anthropic"
                _persist_key_to_env("LLM_BACKEND", "anthropic")

            elif provider == "groq":
                r = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {clean_key}"},
                )
                r.raise_for_status()
                state.keys["groq"] = clean_key
                os.environ["GROQ_API_KEY"] = clean_key
                _persist_key_to_env("GROQ_API_KEY", clean_key)
                os.environ["LLM_BACKEND"] = "groq"
                _persist_key_to_env("LLM_BACKEND", "groq")

            elif provider == "openrouter":
                r = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {clean_key}"},
                )
                r.raise_for_status()
                state.keys["openrouter"] = clean_key
                os.environ["OPENROUTER_API_KEY"] = clean_key
                _persist_key_to_env("OPENROUTER_API_KEY", clean_key)
                os.environ["LLM_BACKEND"] = "openrouter"
                _persist_key_to_env("LLM_BACKEND", "openrouter")

            elif provider == "mistral":
                r = await client.get(
                    "https://api.mistral.ai/v1/models",
                    headers={"Authorization": f"Bearer {clean_key}"},
                )
                r.raise_for_status()
                state.keys["mistral"] = clean_key
                os.environ["MISTRAL_API_KEY"] = clean_key
                _persist_key_to_env("MISTRAL_API_KEY", clean_key)
                os.environ["LLM_BACKEND"] = "mistral"
                _persist_key_to_env("LLM_BACKEND", "mistral")

            else:
                raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

            # Sync with CredentialManager singleton if available
            try:
                from src.infrastructure.credentials.manager import get_credential_manager
                cm = get_credential_manager()
                cm.set_credential(provider, clean_key)
            except Exception:
                pass

            return {
                "valid": True,
                "provider": provider,
                "masked_key": f"{clean_key[:4]}...{clean_key[-4:]}",
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail=f"Key verification failed for {provider}: {str(e)}",
            )


def resolve_local_model_path(repo_or_path: str) -> str:
    """
    Checks for locally downloaded weights in specific model folders (models/...)
    before falling back to remote Hugging Face repo ID.
    Supports nested paths (models/google/embeddinggemma-2), flat paths, and direct paths.
    """
    if not repo_or_path:
        return repo_or_path
    cleaned = repo_or_path.strip().strip('"').strip("'")
    if os.path.isdir(cleaned):
        return cleaned

    base_dirs = []
    if os.environ.get("MODELS_DIR"):
        base_dirs.append(Path(os.environ["MODELS_DIR"]))
    base_dirs.extend([
        Path.cwd() / "models",
        Path.cwd() / "backend" / "models",
        Path(__file__).resolve().parent / "models",
        Path(__file__).resolve().parent.parent / "models",
    ])

    basename = cleaned.split("/")[-1]
    norm_slash = cleaned.replace("\\", "/")
    dash_name = norm_slash.replace("/", "--")
    under_name = norm_slash.replace("/", "_")

    candidates = []
    for b in base_dirs:
        candidates.extend([
            b / norm_slash,
            b / basename,
            b / dash_name,
            b / under_name,
        ])

    for cand in candidates:
        if cand.is_dir() and any(cand.iterdir()):
            logger.info(f"Resolved model '{repo_or_path}' to local model folder: {cand}")
            return str(cand)

    return repo_or_path


# =====================================================================
# ENDPOINT 2: FAST DOWNLOAD + HOT-SWAP ANY ENCODER, RERANKER & NLI
# =====================================================================
@router.post("/api/v1/system/models/load", operation_id="core_load_neural_model_v1", include_in_schema=False)
@router.post("/api/system/models/load", operation_id="core_load_neural_model_system", include_in_schema=False)
@router.post("/models/load", operation_id="core_load_neural_model")
def load_and_prewarm_models(cfg: ModelConfigRequest):
    from sentence_transformers import CrossEncoder, SentenceTransformer
    from transformers import AutoModel

    hf_token = state.sanitize_key(cfg.hf_token) or state.keys.get("huggingface") or None
    if hf_token:
        state.keys["huggingface"] = hf_token
    state.unload_all()

    models_root = Path.cwd() / "models"
    # 0. Check or pre-download missing weights directly to local model directory
    for repo in (cfg.embedder_id, cfg.reranker_id, cfg.verifier_id):
        resolved = resolve_local_model_path(repo)
        if not os.path.isdir(resolved):
            dest = models_root / repo.replace("\\", "/")
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                snapshot_download(repo_id=repo, local_dir=str(dest), token=hf_token)
            except Exception as e:
                err_msg = str(e)
                if "401" in err_msg or "403" in err_msg or "GatedRepo" in err_msg or "gated" in err_msg.lower():
                    logger.warning(f"Model '{repo}' requires Hugging Face authentication or acceptance of terms. If not configured, ungated fallback will be used.")
                else:
                    logger.warning(f"Pre-download notice for {repo}: {e}")

    embed_path = resolve_local_model_path(cfg.embedder_id)
    rerank_path = resolve_local_model_path(cfg.reranker_id)
    verifier_path = resolve_local_model_path(cfg.verifier_id)

    attn_impl = "sdpa"  # Universally safe across NVIDIA GPUs, Laptops, and Apple Silicon MPS

    # 1. Load ANY Dense Embedder (with automatic selective encoder handling for EmbeddingGemma-2)
    embed_cfg_kwargs = {}
    if "embeddinggemma" in cfg.embedder_id.lower() or "embeddinggemma" in embed_path.lower():
        embed_cfg_kwargs["audio_config"] = None
        if not cfg.use_vision:
            embed_cfg_kwargs["vision_config"] = None

    try:
        state.embedder = SentenceTransformer(
            embed_path,
            device=state.device,
            token=hf_token,
            trust_remote_code=True,
            config_kwargs=embed_cfg_kwargs if embed_cfg_kwargs else None,
            model_kwargs={"torch_dtype": state.dtype, "attn_implementation": attn_impl},
        )
    except Exception as e:
        logger.warning(
            f"Could not load primary embedder '{embed_path}' (likely gated repo without HF_TOKEN: {e}). "
            "Falling back to BAAI/bge-base-en-v1.5 (ungated zero-config)."
        )
        cfg.embedder_id = "BAAI/bge-base-en-v1.5"
        state.embedder = SentenceTransformer(
            "BAAI/bge-base-en-v1.5",
            device=state.device,
            model_kwargs={"torch_dtype": state.dtype},
        )

    # 2. Load ANY Reranker (Auto-detects Listwise Jina v3/v3.5 vs Pointwise CrossEncoder)
    try:
        if "jina-reranker-v3" in cfg.reranker_id.lower() or "jina-reranker-v3" in rerank_path.lower():
            state.reranker_type = "listwise"
            state.reranker = AutoModel.from_pretrained(
                rerank_path,
                torch_dtype=state.dtype,
                token=hf_token,
                trust_remote_code=True,
                attn_implementation=attn_impl,
            ).to(state.device).eval()
        else:
            state.reranker_type = "cross_encoder"
            state.reranker = CrossEncoder(
                rerank_path,
                device=state.device,
                token=hf_token,
                trust_remote_code=True,
                automodel_args={"torch_dtype": state.dtype, "attn_implementation": attn_impl},
            )
    except Exception as e:
        logger.warning(f"Could not load primary reranker '{rerank_path}': {e}. Falling back to ms-marco-MiniLM-L-6-v2.")
        state.reranker_type = "cross_encoder"
        state.reranker = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            device=state.device,
        )

    # 3. Load ANY NLI Claim Verifier
    try:
        state.verifier = CrossEncoder(
            verifier_path,
            device=state.device,
            token=hf_token,
            trust_remote_code=True,
            automodel_args={"torch_dtype": state.dtype, "attn_implementation": attn_impl},
        )
    except Exception as e:
        logger.warning(f"Could not load primary NLI verifier '{verifier_path}': {e}. Using heuristic verification.")
        state.verifier = None

    # 4. Pre-Warm All 3 Models Immediately
    with torch.inference_mode():
        _ = state.embedder.encode(["warmup query"], normalize_embeddings=True)
        if state.reranker_type == "listwise" and hasattr(state.reranker, "rerank"):
            _ = state.reranker.rerank("warmup", ["warmup doc"])
        elif hasattr(state.reranker, "predict"):
            _ = state.reranker.predict([("warmup", "warmup doc")])
        if hasattr(state.verifier, "predict"):
            _ = state.verifier.predict([("warmup premise", "warmup claim")])

    # 5. Direct Singleton Sync with Shared RAG Engine & NLI Verifier
    try:
        import sys
        rag_engine = getattr(sys, "_raise_shared_rag_engine", None)
        if rag_engine is None:
            try:
                import app as rag_app_module
                rag_engine = getattr(rag_app_module, "rag_engine", None)
            except Exception:
                pass
        if rag_engine is not None:
            if hasattr(rag_engine, "vector_engine") and rag_engine.vector_engine is not None:
                rag_engine.vector_engine._model = state.embedder
                rag_engine.vector_engine.model_key = cfg.embedder_id
            if hasattr(rag_engine, "reranker") and rag_engine.reranker is not None:
                rag_engine.reranker.model = state.reranker
                rag_engine.reranker.model_name = cfg.reranker_id
    except Exception as e:
        logger.debug(f"Notice syncing core_registry with rag_engine: {e}")

    try:
        from src.features.evaluation.nli_verifier import FineCatNLIVerifier
        if state.verifier is not None:
            FineCatNLIVerifier._shared_model = state.verifier
    except Exception:
        pass

    state.active_config = cfg.model_dump()
    mem_info = state.get_memory_telemetry()
    return {
        "status": "ready",
        "device": state.device,
        "dtype": str(state.dtype),
        "vram_mb": mem_info["vram_mb"],
        "total_vram_mb": mem_info.get("total_vram_mb"),
        "free_vram_mb": mem_info.get("free_vram_mb"),
        "system_ram_used_mb": mem_info.get("system_ram_used_mb"),
        "system_ram_total_mb": mem_info.get("system_ram_total_mb"),
        "active": state.active_config,
    }


# =====================================================================
# ENDPOINT 3: LIVE SYSTEM STATUS
# =====================================================================
@router.get("/api/v1/system/status", operation_id="core_system_status_v1", include_in_schema=False)
@router.get("/api/system/status", operation_id="core_system_status_api", include_in_schema=False)
@router.get("/status", operation_id="core_system_status")
def get_system_status():
    mem_info = state.get_memory_telemetry()
    return {
        "device": state.device,
        "dtype": str(state.dtype),
        "vram_mb": mem_info["vram_mb"],
        "total_vram_mb": mem_info.get("total_vram_mb"),
        "free_vram_mb": mem_info.get("free_vram_mb"),
        "system_ram_used_mb": mem_info.get("system_ram_used_mb"),
        "system_ram_total_mb": mem_info.get("system_ram_total_mb"),
        "active_models": {
            "embedder_id": state.active_config.get("embedder_id", "google/embeddinggemma-2"),
            "reranker_id": state.active_config.get("reranker_id", "jinaai/jina-reranker-v3.5"),
            "verifier_id": state.active_config.get("verifier_id", "dleemiller/finecat-nli-ultra-l"),
            "use_vision": state.active_config.get("use_vision", False),
        },
        "configured_providers": state.get_configured_providers(),
    }
