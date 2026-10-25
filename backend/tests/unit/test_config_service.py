"""
Unit Tests for System Configuration Service & Control Center Persistence
========================================================================
Validates:
1. Masking and unmasking detection (mask_secret, is_masked_secret).
2. First-launch detection gating across cloud, local LLMs, and markers.
3. Multi-provider configuration persistence (Groq, Gemini, OpenAI, vLLM, Ollama).
4. Masked credential protection (prevents overwriting real secrets with telemetry placeholders).
5. Synchronized root and backend .env and .runtime marker persistence with zero secret leakage.
"""

import os
from pathlib import Path
import pytest

from src.features.system.config_service import (
    mask_secret,
    is_masked_secret,
    get_current_configuration,
    save_configuration,
)
from src.features.system.schemas import SystemConfigRequest
from src.infrastructure.credentials.manager import CredentialManager


class MockKeyring:
    """In-memory dictionary mock simulating secure credential storage."""
    def __init__(self):
        self.store = {}

    def get_password(self, service: str, username: str):
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str):
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str):
        self.store.pop((service, username), None)


@pytest.fixture
def isolated_config_env(tmp_path, monkeypatch):
    """Creates an isolated temporary root and backend directory structure for testing config_service."""
    fake_root = tmp_path / "repo_root"
    fake_backend = fake_root / "backend"
    fake_backend.mkdir(parents=True)

    root_env = fake_root / ".env"
    backend_env = fake_backend / ".env"

    initial_content = "CHROMA_PERSIST_DIRECTORY=./chroma_data\nEMBEDDING_MODEL=BAAI/bge-large-en-v1.5\n"
    root_env.write_text(initial_content, encoding="utf-8")
    backend_env.write_text(initial_content, encoding="utf-8")

    monkeypatch.setattr("src.features.system.config_service.ROOT_DIR", fake_root)
    monkeypatch.setattr("src.features.system.config_service.BACKEND_DIR", fake_backend)
    monkeypatch.setattr("src.features.system.config_service.ENV_FILE_PATH", backend_env)
    monkeypatch.setattr("src.features.system.config_service.ROOT_ENV_FILE_PATH", root_env)

    # Use isolated CredentialManager with in-memory keyring
    mock_mgr = CredentialManager(env_file_path=backend_env)
    mock_mgr._keyring = MockKeyring()
    monkeypatch.setattr("src.infrastructure.credentials.manager.get_credential_manager", lambda: mock_mgr)

    # Clear environment variables
    for var in [
        "GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "MISTRAL_API_KEY",
        "NVIDIA_API_KEY", "COHERE_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
        "OPENROUTER_API_KEY", "LLM_BACKEND", "LLM_MODEL_NAME", "SETUP_COMPLETED"
    ]:
        monkeypatch.delenv(var, raising=False)

    yield {
        "root": fake_root,
        "backend": fake_backend,
        "root_env": root_env,
        "backend_env": backend_env,
        "mgr": mock_mgr,
    }


def test_mask_and_masked_secret_detection():
    """Verifies that sensitive keys are masked and masked placeholders are accurately detected."""
    assert mask_secret("") == ""
    assert mask_secret(None) == ""
    assert mask_secret("short") == "********"
    assert mask_secret("gsk_1234567890abcdef") == "gsk_...cdef"

    assert is_masked_secret("gsk_...cdef") is True
    assert is_masked_secret("********") is True
    assert is_masked_secret("gsk_real_secret_key_12345") is False
    assert is_masked_secret("") is False
    assert is_masked_secret(None) is False


def test_first_launch_gating(isolated_config_env, monkeypatch):
    """Verifies first_run_completed requires configured provider or setup completion."""
    # Clean unconfigured state
    cfg = get_current_configuration()
    assert cfg["first_run_completed"] is False

    # Local LLM without marker must NOT bypass first-launch gating
    monkeypatch.setenv("LLM_BACKEND", "vllm")
    cfg = get_current_configuration()
    assert cfg["first_run_completed"] is False

    # Setting setup marker marks it completed
    marker = isolated_config_env["root"] / ".runtime" / "setup_completed"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("true\n", encoding="utf-8")
    cfg = get_current_configuration()
    assert cfg["first_run_completed"] is True


def test_save_configuration_cloud_and_local(isolated_config_env):
    """Verifies saving configuration correctly updates both cloud and local LLM modes."""
    # 1. Configure Cloud Groq & OpenAI
    req_cloud = SystemConfigRequest(
        llm_mode="cloud_groq",
        groq_api_key="gsk_test_groq_key_9999",
        openai_api_key="sk-test-openai-key-8888",
    )
    res1 = save_configuration(req_cloud)
    assert res1["status"] == "success"
    assert res1["active_mode"] == "groq"

    # Verify both .env files updated and preserved initial variables
    for env_file in [isolated_config_env["root_env"], isolated_config_env["backend_env"]]:
        content = env_file.read_text(encoding="utf-8")
        assert "GROQ_API_KEY=gsk_test_groq_key_9999" in content
        assert "OPENAI_API_KEY=sk-test-openai-key-8888" in content
        assert "SETUP_COMPLETED=true" in content
        assert "CHROMA_PERSIST_DIRECTORY=./chroma_data" in content

    # Verify setup marker created
    assert (isolated_config_env["root"] / ".runtime" / "setup_completed").exists()
    assert (isolated_config_env["backend"] / ".runtime" / "setup_completed").exists()

    # 2. Configure Local vLLM
    req_vllm = SystemConfigRequest(
        llm_mode="local_vllm",
        selected_local_model="Qwen/Qwen2.5-7B-Instruct",
    )
    res2 = save_configuration(req_vllm)
    assert res2["status"] == "success"
    assert res2["active_mode"] == "vllm"
    assert res2["active_model"] == "Qwen/Qwen2.5-7B-Instruct"

    content_vllm = isolated_config_env["backend_env"].read_text(encoding="utf-8")
    assert "LLM_BACKEND=vllm" in content_vllm
    assert "LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct" in content_vllm


def test_masked_secret_protection(isolated_config_env):
    """Verifies that submitting masked placeholder strings does NOT clobber real credentials."""
    # First set real keys
    req1 = SystemConfigRequest(
        llm_mode="cloud_gemini",
        gemini_api_key="AIza_real_gemini_key_123456",
        groq_api_key="gsk_real_groq_key_987654",
    )
    save_configuration(req1)

    # Next submit masked keys (as returned in telemetry/UI)
    req2 = SystemConfigRequest(
        llm_mode="cloud_gemini",
        gemini_api_key="AIza...3456",
        groq_api_key="gsk_...7654",
    )
    save_configuration(req2)

    # Verify real keys are intact
    mgr = isolated_config_env["mgr"]
    assert mgr.get_credential("gemini") == "AIza_real_gemini_key_123456"
    assert mgr.get_credential("groq") == "gsk_real_groq_key_987654"
    assert "AIza...3456" not in isolated_config_env["backend_env"].read_text(encoding="utf-8")
