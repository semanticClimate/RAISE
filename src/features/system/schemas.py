"""
System & Control Center Pydantic Data Models & Schemas
======================================================
Defines payload and request validation models for runtime configuration,
model pulling, and pre-flight neural asset downloads.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field
from src.core.config import models


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
    fallback_order: Optional[List[str]] = None
    disabled_providers: Optional[List[str]] = None
    primary_provider: Optional[str] = None
    routing_policy: Optional[str] = None

    # Neural Retrieval Pipeline Substrates
    embedding_model: Optional[str] = Field(default_factory=lambda: models.EMBEDDING_MODEL_NAME)
    embedding_device: Optional[str] = None
    reranker_model: Optional[str] = Field(default_factory=lambda: models.RERANKER_MODEL_NAME)
    reranker_device: Optional[str] = None
    nli_verifier_model: Optional[str] = Field(default_factory=lambda: models.NLI_MODEL_NAME)
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

    model_name: str = Field(default_factory=lambda: models.EMBEDDING_MODEL_NAME)
    provider: Optional[str] = Field(default="huggingface")
    model_type: Optional[str] = Field(default="embedding")
    huggingface_token: Optional[str] = None


class PreflightDownloadRequest(BaseModel):
    """Payload schema for initiating background neural asset downloads."""
    model_config = {"extra": "ignore"}


class RoutingUpdateRequest(BaseModel):
    """Payload schema for dynamic LLM priority reordering and enabling/disabling."""
    model_config = {"extra": "ignore"}

    fallback_order: Optional[List[str]] = Field(default=None, description="Ordered list of provider keys, e.g. ['vllm', 'gemini', 'groq']")
    disabled_providers: Optional[List[str]] = Field(default=None, description="List of provider keys to deactivate")
    primary_provider: Optional[str] = Field(default=None, description="Primary LLM provider to use first")
    routing_policy: Optional[str] = Field(default=None, description="LOCAL_FIRST, CLOUD_FIRST, etc.")

    asset_ids: Optional[List[str]] = None
