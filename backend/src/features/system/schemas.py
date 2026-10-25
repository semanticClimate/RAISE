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
    llm_mode: str = Field(default="cloud_groq", description="cloud_groq, cloud_gemini, or local_ollama")
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
    neo4j_mode: str = Field(default="cloud", description="cloud, local, or in_memory_fallback")
    neo4j_uri: Optional[str] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None
    neo4j_database: Optional[str] = None
    redis_mode: str = Field(default="cloud", description="cloud, local, or in_memory_fallback")
    redis_url: Optional[str] = None
    redis_uri: Optional[str] = None
    postgres_mode: str = Field(default="cloud", description="cloud, local, or in_memory_fallback")
    postgres_url: Optional[str] = None
    postgres_uri: Optional[str] = None
    tunnel_url: Optional[str] = None


class ModelPullRequest(BaseModel):
    """Payload schema for streaming model ingestion requests."""
    model_name: str = Field(default="BAAI/bge-large-en-v1.5")


class PreflightDownloadRequest(BaseModel):
    """Payload schema for initiating background neural asset downloads."""
    asset_ids: Optional[List[str]] = None
