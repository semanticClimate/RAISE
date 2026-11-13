"""
RAISE Centralized Typed Configuration System — Core Module
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field


# Base canonical paths inside RAG
# Canonical backend directory
_file_path = Path(__file__).resolve()
BACKEND_DIR = _file_path.parents[2] if len(_file_path.parents) > 2 and _file_path.parents[2].name == "backend" else _file_path.parents[1]
PROJECT_ROOT = BACKEND_DIR
REPO_ROOT = BACKEND_DIR

# Canonical data directory inside backend
DATA_DIR = PROJECT_ROOT / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
LIBRARY_DIR = DATA_DIR / "library"
CATALOGS_DIR = DATA_DIR / "catalogs"
PROCESSED_DIR = DATA_DIR / "processed"
CHUNKS_DIR = PROCESSED_DIR / "chunks"
GRAPH_DIR = PROCESSED_DIR / "graph_triples"
RUNTIME_DIR = PROJECT_ROOT / ".runtime"
VECTOR_DB_DIR = RUNTIME_DIR / ".chromadb"
UPLOAD_DIR = DOCUMENTS_DIR
AUDIO_DIR = RUNTIME_DIR / "audio"
LOG_DIR = PROJECT_ROOT / "logs"
TESTS_DIR = PROJECT_ROOT / "tests"
FIXTURES_DIR = TESTS_DIR / "fixtures"

# Ensure canonical directories exist automatically upon import
DATA_DIR.mkdir(parents=True, exist_ok=True)
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
CATALOGS_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

# Ensure ingested_manifest.json exists with valid structure
MANIFEST_FILE = PROCESSED_DIR / "ingested_manifest.json"
if not MANIFEST_FILE.exists():
    try:
        MANIFEST_FILE.write_text('{\n  "ready_documents": [],\n  "timestamp": ""\n}', encoding="utf-8")
    except Exception:
        pass


# Load environment variables from .env if present immediately
def _load_env_file():
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        env_file = PROJECT_ROOT.parent / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=env_file, override=False)
        except Exception:
            pass

_load_env_file()


def resolve_local_model_path(repo_or_path: str) -> str:
    """
    Dynamically checks for locally downloaded weights in workspace model folders (models/...)
    before falling back to remote Hugging Face repository ID.
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
        PROJECT_ROOT.parent / "models",
        PROJECT_ROOT / "models",
        Path.cwd() / "models",
        Path.cwd() / "backend" / "models",
    ])

    norm_slash = cleaned.replace("\\", "/")
    basename = norm_slash.split("/")[-1]
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
            return str(cand)

    return repo_or_path


@dataclass(frozen=True)
class ModelConfig:
    # LLM Synthesis
    LLM_PROVIDER: str = os.getenv("RAISE_LLM_PROVIDER", os.getenv("LLM_PROVIDER", "gemini"))
    LLM_MODEL_NAME: str = os.getenv("RAISE_LLM_MODEL", os.getenv("LLM_MODEL_NAME", "gemini-2.5-flash"))
    GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    GEMINI_FALLBACK_CANDIDATES: tuple[str, ...] = (
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-flash-latest",
    )
    OPENAI_MODEL_NAME: str = os.getenv("OPENAI_MODEL_NAME", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    GROQ_MODEL_NAME: str = os.getenv("GROQ_MODEL", "qwen/qwen-2.5-32b-instruct")
    GROQ_FALLBACK_CANDIDATES: tuple[str, ...] = (
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
    )
    DEEPSEEK_MODEL_NAME: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    NVIDIA_MODEL_NAME: str = os.getenv("NVIDIA_MODEL", "meta/llama-3.2-11b-vision-instruct")
    OPENROUTER_MODEL_NAME: str = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku")
    ANTHROPIC_MODEL_NAME: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet")
    COHERE_MODEL_NAME: str = os.getenv("COHERE_MODEL", "command-r-plus-08-2024")
    MISTRAL_MODEL_NAME: str = os.getenv("MISTRAL_MODEL", "open-mistral-nemo")
    MISTRAL_FALLBACK_CANDIDATES: tuple[str, ...] = (
        "open-mistral-7b",
        "codestral-latest",
        "mistral-small-latest",
    )

    # Retrieval & Reranking
    EMBEDDING_MODEL_NAME: str = os.getenv("RAISE_EMBEDDING_MODEL", os.getenv("EMBEDDING_MODEL", "google/embeddinggemma-2"))
    EMBEDDING_MODEL_KEYWORD: str = "embeddinggemma"
    GEMMA_KEYWORD: str = "gemma"
    EMBEDDING_FALLBACK_MODEL_NAME: str = os.getenv("EMBEDDING_FALLBACK_MODEL", "BAAI/bge-large-en-v1.5")
    EMBEDDING_BASE_MODEL_NAME: str = os.getenv("EMBEDDING_BASE_MODEL", "BAAI/bge-base-en-v1.5")
    EMBEDDING_M3_MODEL_NAME: str = os.getenv("EMBEDDING_M3_MODEL", "BAAI/bge-m3")
    RERANKER_MODEL_NAME: str = os.getenv("RAISE_RERANKER_MODEL", os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"))
    RERANKER_FALLBACK_MODEL_NAME: str = os.getenv("RERANKER_FALLBACK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

    # Ingestion / Entity Extraction
    GLINER_MODEL_NAME: str = os.getenv("RAISE_GLINER_MODEL", os.getenv("GLINER_MODEL", "urchade/gliner_medium-v2.1"))

    # NLI Entailment
    NLI_MODEL_NAME: str = os.getenv("RAISE_NLI_MODEL", os.getenv("NLI_MODEL", "dleemiller/finecat-nli-ultra-l"))


models = ModelConfig()

AVAILABLE_EMBEDDING_MODELS: Dict[str, str] = {
    "embeddinggemma-2": "google/embeddinggemma-2",
    "embeddinggemma": "google/embeddinggemma-2",
    "google/embeddinggemma-2": "google/embeddinggemma-2",
    "bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
    "bge-large": "BAAI/bge-large-en-v1.5",
    "BAAI/bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
    "bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
    "bge-base": "BAAI/bge-base-en-v1.5",
    "BAAI/bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
    "all-mpnet-base-v2": "sentence-transformers/all-mpnet-base-v2",
    "sentence-transformers/all-mpnet-base-v2": "sentence-transformers/all-mpnet-base-v2",
    "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
    "nomic-ai/nomic-embed-text-v1.5": "nomic-ai/nomic-embed-text-v1.5",
    "nomic-embed-text-v1.5": "nomic-ai/nomic-embed-text-v1.5",
    "bge-m3": "BAAI/bge-m3",
    "BAAI/bge-m3": "BAAI/bge-m3",
    "nomic-ai/nomic-embed-vision-v1.5": "nomic-ai/nomic-embed-vision-v1.5",
    "nomic-embed-vision": "nomic-ai/nomic-embed-vision-v1.5",
    "openai/clip-vit-base-patch32": "openai/clip-vit-base-patch32",
    "clip-vit-base": "openai/clip-vit-base-patch32",
    "meta/llama-3.2-11b-vision-instruct": "meta/llama-3.2-11b-vision-instruct",
    "qwen-embedding-4b": "Qwen/Qwen3-Embedding-4B",
}

EMBEDDING_FALLBACKS_768: list[str] = [
    "BAAI/bge-base-en-v1.5",
    "sentence-transformers/all-mpnet-base-v2",
    "nomic-ai/nomic-embed-text-v1.5",
]

EMBEDDING_FALLBACKS_1024: list[str] = [
    "BAAI/bge-large-en-v1.5",
    "BAAI/bge-m3",
]

AVAILABLE_RERANKER_MODELS: Dict[str, str] = {
    "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
    "BAAI/bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
    "bge-reranker-large": "BAAI/bge-reranker-v2-m3",
    "BAAI/bge-reranker-large": "BAAI/bge-reranker-v2-m3",
    "bge-reranker-base": "BAAI/bge-reranker-base",
    "BAAI/bge-reranker-base": "BAAI/bge-reranker-base",
    "ms-marco-MiniLM-L-6-v2": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "cross-encoder/ms-marco-MiniLM-L-6-v2": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "jina-reranker-v3.5": "BAAI/bge-reranker-v2-m3",
    "jinaai/jina-reranker-v3.5": "BAAI/bge-reranker-v2-m3",
    "jina-reranker": "BAAI/bge-reranker-v2-m3",
    "default": "BAAI/bge-reranker-v2-m3",
}

SUPPORTED_FAMILY_KEYWORDS: tuple[str, ...] = ("llama", "qwen", "mistral", "phi", "gemma", "deepseek")
OPENROUTER_FAMILY_KEYWORDS: tuple[str, ...] = ("llama-3", "qwen-2.5", "mistral-7b", "phi-3", "gemma-2")

OFFLINE_CATALOG_FALLBACK: list[dict[str, Any]] = [
    {"id": "meta-llama/Llama-3.2-3B-Instruct", "name": "Llama 3.2 3B Instruct", "download_size_gb": 2.0, "min_ram_gb": 8, "tier": "Fast & Light", "status": "READY", "downloads": "Offline Default", "source": "catalog_fallback"},
    {"id": "Qwen/Qwen2.5-7B-Instruct", "name": "Qwen 2.5 7B Instruct", "download_size_gb": 4.7, "min_ram_gb": 16, "tier": "Balanced Reasoning", "status": "READY", "downloads": "Offline Default", "source": "catalog_fallback"},
    {"id": "meta-llama/Meta-Llama-3.1-8B-Instruct", "name": "Llama 3.1 8B Instruct", "download_size_gb": 4.9, "min_ram_gb": 16, "tier": "High Fidelity", "status": "READY", "downloads": "Offline Default", "source": "catalog_fallback"},
]


class Neo4jConfig(BaseModel):
    """Neo4j Graph Database Configuration."""
    uri: str = Field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    user: str = Field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = Field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password123"))
    database: str = Field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))
    max_connection_lifetime: int = Field(default_factory=lambda: int(os.getenv("NEO4J_MAX_CONNECTION_LIFETIME", "3600")))
    max_connection_pool_size: int = Field(default_factory=lambda: int(os.getenv("NEO4J_MAX_CONNECTION_POOL_SIZE", "50")))
    connection_timeout: float = Field(default_factory=lambda: float(os.getenv("NEO4J_CONNECTION_TIMEOUT", "5.0")))


class VectorConfig(BaseModel):
    persist_directory: Path = Field(
        default_factory=lambda: (
            Path(os.getenv("CHROMA_PERSIST_DIRECTORY"))
            if os.getenv("CHROMA_PERSIST_DIRECTORY") and Path(os.getenv("CHROMA_PERSIST_DIRECTORY")).is_absolute()
            else (
                BACKEND_DIR / ".chromadb_embeddinggemma_2"
                if not os.getenv("CHROMA_PERSIST_DIRECTORY") or os.getenv("CHROMA_PERSIST_DIRECTORY").endswith(".chromadb_embeddinggemma_2")
                else (BACKEND_DIR / os.getenv("CHROMA_PERSIST_DIRECTORY")).resolve()
            )
        )
    )
    collection_name: str = Field(default_factory=lambda: os.getenv("CHROMA_COLLECTION_NAME", "raise_docling_embeddinggemma_2"))
    embedding_model: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", models.EMBEDDING_MODEL_NAME))
    embedding_device: str = Field(default_factory=lambda: os.getenv("EMBEDDING_DEVICE", "cuda"))
    embedding_dimension: int = Field(default_factory=lambda: int(os.getenv("EMBEDDING_DIMENSION", "768")))
    hnsw_space: str = Field(default_factory=lambda: os.getenv("CHROMA_HNSW_SPACE", "cosine"))

    @staticmethod
    def format_collection_name(
        dataset: str,
        parser: str = "docling",
        embedding_model: str = "bge_large",
    ) -> str:
        """
        Enforces canonical tripartite naming standard:
        [dataset]_[parser]_[embedding_model]
        """
        import re

        def _clean(val: str) -> str:
            if not val:
                return ""
            s = str(val).split("/")[-1].split("\\")[-1]
            return re.sub(r"[^a-zA-Z0-9]+", "_", s.strip().lower()).strip("_")

        d = _clean(dataset) or "default"
        p = _clean(parser) or "docling"
        m = _clean(embedding_model) or "embeddinggemma_2"
        if "embeddinggemma" in m or "gemma" in m:
            m = "embeddinggemma_2"
        if "bge_large" in m:
            m = "bge_large"
        elif "bge_m3" in m:
            m = "bge_m3"
        elif "minilm" in m:
            m = "minilm"
        elif "qwen" in m:
            m = "qwen"
        return f"{d}_{p}_{m}"

    @staticmethod
    def parse_collection_name(name: str) -> Dict[str, str]:
        """Deconstructs [dataset]_[parser]_[embedding_model]."""
        if not name:
            return {"dataset": "default", "parser": "docling", "embedding_model": "bge_large"}
        parts = name.split("_")
        if len(parts) >= 3:
            return {"dataset": parts[0], "parser": parts[1], "embedding_model": "_".join(parts[2:])}
        elif len(parts) == 2:
            return {"dataset": parts[0], "parser": parts[1], "embedding_model": "bge_large"}
        return {"dataset": name, "parser": "unknown", "embedding_model": "unknown"}




class RerankerConfig(BaseModel):
    """Contextual Cross-Encoder Reranker Configuration."""
    model_name: str = Field(default_factory=lambda: os.getenv("RERANKER_MODEL", models.RERANKER_MODEL_NAME))
    device: str = Field(default_factory=lambda: os.getenv("RERANKER_DEVICE", "cuda"))
    top_n: int = Field(default_factory=lambda: int(os.getenv("RERANKER_TOP_N", "8")))


class NLIConfig(BaseModel):
    """Natural Language Inference Verification Configuration."""
    model_name: str = Field(default_factory=lambda: os.getenv("NLI_MODEL", models.NLI_MODEL_NAME))
    device: str = Field(default_factory=lambda: os.getenv("NLI_DEVICE", "cuda"))
    max_length: int = Field(default_factory=lambda: int(os.getenv("NLI_MAX_LENGTH", "4096")))

class LLMConfig(BaseModel):
    """Local & Remote Large Language Model Configuration."""
    backend: Literal["ollama", "huggingface", "openai-compatible", "vllm", "cloud"] = Field(
        default_factory=lambda: os.getenv("LLM_BACKEND", "vllm")  # type: ignore
    )
    model_name: str = Field(default_factory=lambda: os.getenv("LLM_MODEL_NAME", models.LLM_MODEL_NAME))
    base_url: str = Field(default_factory=lambda: os.getenv("LLM_BASE_URL", os.getenv("VLLM_BASE_URL", "http://localhost:8002/v1")))
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY")))
    temperature: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.1")))
    max_tokens: int = Field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "1024")))
    top_p: float = Field(default_factory=lambda: float(os.getenv("LLM_TOP_P", "0.9")))
    request_timeout: float = Field(default_factory=lambda: float(os.getenv("LLM_REQUEST_TIMEOUT", "60.0")))


class PostgresConfig(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port: int = Field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    user: str = Field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    password: str = Field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "postgres"))
    database: str = Field(default_factory=lambda: os.getenv("POSTGRES_DB", "raise"))


class RedisConfig(BaseModel):
    url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))


class LangGraphConfig(BaseModel):
    default_hops: int = Field(default_factory=lambda: int(os.getenv("GRAPHRAG_DEFAULT_HOPS", "2")))
    max_hops: int = Field(default_factory=lambda: int(os.getenv("GRAPHRAG_MAX_HOPS", "3")))
    default_top_k: int = Field(default_factory=lambda: int(os.getenv("GRAPHRAG_DEFAULT_TOP_K", "4")))
    max_nodes: int = Field(default_factory=lambda: int(os.getenv("GRAPHRAG_MAX_NODES", "35")))
    max_retries: int = Field(default_factory=lambda: int(os.getenv("LANGGRAPH_MAX_RETRIES", "1")))
    trace_level: str = Field(default_factory=lambda: os.getenv("LANGGRAPH_TRACE_LEVEL", "DEBUG"))


class ServerConfig(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    reload: bool = Field(default_factory=lambda: os.getenv("RELOAD", "false").lower() in ("true", "1"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "info"))


class Settings(BaseModel):
    app_name: str = "RAISE (Research Assessment Intelligence & Semantic Extraction)"
    version: str = "1.0.0"
    project_root: Path = PROJECT_ROOT
    base_dir: Path = PROJECT_ROOT
    rag_dir: Path = PROJECT_ROOT
    data_dir: Path = DATA_DIR
    documents_dir: Path = DOCUMENTS_DIR
    library_dir: Path = LIBRARY_DIR
    catalogs_dir: Path = CATALOGS_DIR
    processed_dir: Path = PROCESSED_DIR
    chunks_dir: Path = CHUNKS_DIR
    graph_dir: Path = GRAPH_DIR
    vector_db_dir: Path = VECTOR_DB_DIR
    upload_dir: Path = UPLOAD_DIR
    audio_dir: Path = AUDIO_DIR
    log_dir: Path = LOG_DIR
    fixtures_dir: Path = FIXTURES_DIR
    download_dir: Path = DOCUMENTS_DIR
    
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    vector: VectorConfig = Field(default_factory=VectorConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    nli: NLIConfig = Field(default_factory=NLIConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    langgraph: LangGraphConfig = Field(default_factory=LangGraphConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)


settings = Settings()
