"""
RAISE Centralized Typed Configuration System — Core Module
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field


# Base canonical paths inside RAG
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../RAG
DATA_DIR = PROJECT_ROOT / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
LIBRARY_DIR = DATA_DIR / "library"
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

# Ensure directories exist
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


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
            Path(os.getenv("CHROMA_PERSIST_DIRECTORY", str(PROJECT_ROOT / ".chromadb_embeddinggemma_2")))
            if Path(os.getenv("CHROMA_PERSIST_DIRECTORY", "")).is_absolute()
            else (PROJECT_ROOT / os.getenv("CHROMA_PERSIST_DIRECTORY", ".chromadb_embeddinggemma_2")).resolve()
        )
    )
    collection_name: str = Field(default_factory=lambda: os.getenv("CHROMA_COLLECTION_NAME", "raise_docling_embeddinggemma_2"))
    embedding_model: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "google/embeddinggemma-2"))
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
    model_name: str = Field(default_factory=lambda: os.getenv("RERANKER_MODEL", "jinaai/jina-reranker-v3.5"))
    device: str = Field(default_factory=lambda: os.getenv("RERANKER_DEVICE", "cuda"))
    top_n: int = Field(default_factory=lambda: int(os.getenv("RERANKER_TOP_N", "8")))


class NLIConfig(BaseModel):
    """Natural Language Inference Verification Configuration."""
    model_name: str = Field(default_factory=lambda: os.getenv("NLI_MODEL", "dleemiller/finecat-nli-ultra-l"))
    device: str = Field(default_factory=lambda: os.getenv("NLI_DEVICE", "cuda"))
    max_length: int = Field(default_factory=lambda: int(os.getenv("NLI_MAX_LENGTH", "4096")))

class LLMConfig(BaseModel):
    """Local & Remote Large Language Model Configuration."""
    backend: Literal["ollama", "huggingface", "openai-compatible", "vllm", "cloud"] = Field(
        default_factory=lambda: os.getenv("LLM_BACKEND", "vllm")  # type: ignore
    )
    model_name: str = Field(default_factory=lambda: os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4"))
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
