"""
System & Control Center Pydantic Data Models & Schemas
======================================================
Defines payload and request validation models for runtime configuration,
model pulling, and pre-flight neural asset downloads.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class SystemConfigRequest(BaseModel):
    """Payload schema for system configuration updates and connection testing."""
    model_config = {"extra": "ignore"}

    llm_backend: Optional[str] = None
    llm_mode: Optional[str] = Field(default="cloud_groq", description="cloud_groq, cloud_gemini, or local_ollama")
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    vercel_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    custom_api_key: Optional[str] = None
    custom_base_url: Optional[str] = None
    custom_model_name: Optional[str] = None
    selected_local_model: Optional[str] = "llama3.2:3b"
    ollama_model: Optional[str] = None

    # Neural Retrieval Pipeline Substrates
    embedding_model: Optional[str] = Field(default="google/embeddinggemma-2")
    embedding_device: Optional[str] = None
    reranker_model: Optional[str] = Field(default="jinaai/jina-reranker-v3.5")
    reranker_device: Optional[str] = None
    nli_verifier_model: Optional[str] = Field(default="dleemiller/finecat-nli-ultra-l")
    nli_model: Optional[str] = None
    nli_device: Optional[str] = None
    neural_device: Optional[str] = Field(default="auto")
    huggingface_token: Optional[str] = None

    # Database Substrates
    neo4j_mode: Optional[str] = Field(default="in_memory_fallback", description="cloud, local, or in_memory_fallback")
    neo4j_uri: Optional[str] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None
    neo4j_database: Optional[str] = None
    redis_mode: Optional[str] = Field(default="in_memory_fallback", description="cloud, local, or in_memory_fallback")
    redis_url: Optional[str] = None
    redis_uri: Optional[str] = None
    postgres_mode: Optional[str] = Field(default="in_memory_fallback", description="cloud, local, or in_memory_fallback")
    postgres_url: Optional[str] = None
    postgres_uri: Optional[str] = None
    tunnel_url: Optional[str] = None


class ModelPullRequest(BaseModel):
    """Payload schema for streaming model ingestion requests."""
    model_config = {"extra": "ignore"}

    model_name: str = Field(default="google/embeddinggemma-2")
    provider: Optional[str] = Field(default="huggingface")
    model_type: Optional[str] = Field(default="embedding")
    huggingface_token: Optional[str] = None


class PreflightDownloadRequest(BaseModel):
    """Payload schema for initiating background neural asset downloads."""
    model_config = {"extra": "ignore"}

    asset_ids: Optional[List[str]] = None
