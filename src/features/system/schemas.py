"""
System & Control Center Pydantic Data Models & Schemas
======================================================
Defines payload and request validation models for runtime configuration,
model pulling, and pre-flight neural asset downloads.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from src.core.config import models


class SystemConfigRequest(BaseModel):
    """Payload schema for system configuration updates and connection testing, accepting both camelCase and snake_case."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    llm_backend: Optional[str] = Field(None, validation_alias=AliasChoices("llm_backend", "llmBackend", "backend"))
    llm_mode: Optional[str] = Field(default="cloud_groq", description="cloud_groq, cloud_gemini, or local_ollama", validation_alias=AliasChoices("llm_mode", "llmMode", "mode"))
    groq_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("groq_api_key", "groqApiKey", "groqKey"))
    gemini_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("gemini_api_key", "geminiApiKey", "google_api_key", "googleApiKey"))
    openai_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("openai_api_key", "openaiApiKey"))
    anthropic_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("anthropic_api_key", "anthropicApiKey"))
    nvidia_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("nvidia_api_key", "nvidiaApiKey"))
    cohere_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("cohere_api_key", "cohereApiKey"))
    mistral_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("mistral_api_key", "mistralApiKey"))
    vercel_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("vercel_api_key", "vercelApiKey"))
    deepseek_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("deepseek_api_key", "deepseekApiKey"))
    openrouter_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("openrouter_api_key", "openrouterApiKey"))
    custom_api_key: Optional[str] = Field(None, validation_alias=AliasChoices("custom_api_key", "customApiKey"))
    custom_base_url: Optional[str] = Field(None, validation_alias=AliasChoices("custom_base_url", "customBaseUrl"))
    custom_model_name: Optional[str] = Field(None, validation_alias=AliasChoices("custom_model_name", "customModelName"))
    selected_local_model: Optional[str] = Field("llama3.2:3b", validation_alias=AliasChoices("selected_local_model", "selectedLocalModel", "local_model", "localModel"))
    ollama_model: Optional[str] = Field(None, validation_alias=AliasChoices("ollama_model", "ollamaModel"))
    fallback_order: Optional[List[str]] = Field(None, validation_alias=AliasChoices("fallback_order", "fallbackOrder"))
    disabled_providers: Optional[List[str]] = Field(None, validation_alias=AliasChoices("disabled_providers", "disabledProviders"))
    primary_provider: Optional[str] = Field(None, validation_alias=AliasChoices("primary_provider", "primaryProvider"))
    routing_policy: Optional[str] = Field(None, validation_alias=AliasChoices("routing_policy", "routingPolicy"))

    # Neural Retrieval Pipeline Substrates
    embedding_model: Optional[str] = Field(default_factory=lambda: models.EMBEDDING_MODEL_NAME, validation_alias=AliasChoices("embedding_model", "embeddingModel", "embedder_id", "embedderId"))
    embedding_device: Optional[str] = Field(None, validation_alias=AliasChoices("embedding_device", "embeddingDevice"))
    reranker_model: Optional[str] = Field(default_factory=lambda: models.RERANKER_MODEL_NAME, validation_alias=AliasChoices("reranker_model", "rerankerModel", "reranker_id", "rerankerId"))
    reranker_device: Optional[str] = Field(None, validation_alias=AliasChoices("reranker_device", "rerankerDevice"))
    nli_verifier_model: Optional[str] = Field(default_factory=lambda: models.NLI_MODEL_NAME, validation_alias=AliasChoices("nli_verifier_model", "nliVerifierModel", "verifier_id", "verifierId"))
    nli_model: Optional[str] = Field(None, validation_alias=AliasChoices("nli_model", "nliModel"))
    nli_device: Optional[str] = Field(None, validation_alias=AliasChoices("nli_device", "nliDevice"))
    neural_device: Optional[str] = Field(default="auto", validation_alias=AliasChoices("neural_device", "neuralDevice", "device"))
    huggingface_token: Optional[str] = Field(None, validation_alias=AliasChoices("huggingface_token", "huggingfaceToken", "hf_token", "hfToken"))

    # Database Substrates
    neo4j_mode: Optional[str] = Field(default="in_memory_fallback", description="cloud, local, or in_memory_fallback", validation_alias=AliasChoices("neo4j_mode", "neo4jMode"))
    neo4j_uri: Optional[str] = Field(None, validation_alias=AliasChoices("neo4j_uri", "neo4jUri", "neo4j_url", "neo4jUrl"))
    neo4j_user: Optional[str] = Field(None, validation_alias=AliasChoices("neo4j_user", "neo4jUser"))
    neo4j_password: Optional[str] = Field(None, validation_alias=AliasChoices("neo4j_password", "neo4jPassword"))
    neo4j_database: Optional[str] = Field(None, validation_alias=AliasChoices("neo4j_database", "neo4jDatabase"))
    redis_mode: Optional[str] = Field(default="in_memory_fallback", description="cloud, local, or in_memory_fallback", validation_alias=AliasChoices("redis_mode", "redisMode"))
    redis_url: Optional[str] = Field(None, validation_alias=AliasChoices("redis_url", "redisUrl", "redis_uri", "redisUri"))
    redis_uri: Optional[str] = Field(None, validation_alias=AliasChoices("redis_uri", "redisUri"))
    postgres_mode: Optional[str] = Field(default="in_memory_fallback", description="cloud, local, or in_memory_fallback", validation_alias=AliasChoices("postgres_mode", "postgresMode"))
    postgres_url: Optional[str] = Field(None, validation_alias=AliasChoices("postgres_url", "postgresUrl", "postgres_uri", "postgresUri"))
    postgres_uri: Optional[str] = Field(None, validation_alias=AliasChoices("postgres_uri", "postgresUri"))
    tunnel_url: Optional[str] = Field(None, validation_alias=AliasChoices("tunnel_url", "tunnelUrl"))


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
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    fallback_order: Optional[List[str]] = Field(
        default=None,
        validation_alias=AliasChoices("fallback_order", "fallbackOrder", "fallback_chain", "fallbackChain"),
        description="Ordered list of provider keys, e.g. ['vllm', 'gemini', 'groq']"
    )
    disabled_providers: Optional[List[str]] = Field(
        default=None,
        validation_alias=AliasChoices("disabled_providers", "disabledProviders"),
        description="List of provider keys to deactivate"
    )
    primary_provider: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("primary_provider", "primaryProvider"),
        description="Primary LLM provider to use first"
    )
    routing_policy: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("routing_policy", "routingPolicy"),
        description="LOCAL_FIRST, CLOUD_FIRST, etc."
    )

    asset_ids: Optional[List[str]] = None
