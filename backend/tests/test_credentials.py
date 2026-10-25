"""
Unit Tests for Secure Credential Management (Windows DPAPI / Keyring / Env Resolution)
Verifies zero secret leakage, layered resolution precedence, and credential status masking.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.infrastructure.credentials.manager import (
    CredentialManager,
    KEYRING_SERVICE_NAME,
    PROVIDER_ENV_MAPPING,
)


class MockKeyring:
    """In-memory dictionary mock simulating Windows Credential Locker."""
    def __init__(self):
        self.store = {}

    def get_password(self, service: str, username: str):
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str):
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str):
        if (service, username) in self.store:
            del self.store[(service, username)]
        else:
            raise Exception("Password not found")


@pytest.fixture
def mock_mgr(tmp_path):
    """Fixture providing an isolated CredentialManager with in-memory keyring and isolated .env."""
    mock_env = tmp_path / ".env"
    mock_env.write_text("VLLM_BASE_URL=http://localhost:8002/v1\n", encoding="utf-8")

    mgr = CredentialManager(service_name="test.ai.runtime", env_file_path=mock_env)
    mgr._keyring = MockKeyring()
    return mgr


def test_credential_initial_status_missing(mock_mgr):
    """Verify that unconfigured credentials safely report 'missing'."""
    # Ensure env var is not set
    with patch.dict(os.environ, {}, clear=True):
        assert mock_mgr.get_credential("groq") is None
        assert mock_mgr.get_credential_status("groq") == "missing"
        assert mock_mgr.get_credential_source("groq") == "none"


def test_credential_set_and_get(mock_mgr):
    """Verify setting and retrieving credentials through the secure store."""
    test_secret = "test-secret-value-12345"
    with patch.dict(os.environ, {}, clear=True):
        success = mock_mgr.set_credential("groq", test_secret)
        assert success is True

        # Check retrieval in-memory
        retrieved = mock_mgr.get_credential("groq")
        assert retrieved == test_secret

        # Check masked status never exposes the secret
        status = mock_mgr.get_credential_status("groq")
        assert status == "configured"
        assert test_secret not in status

        source = mock_mgr.get_credential_source("groq")
        assert source in ("environment", "keyring (DPAPI)")


def test_credential_deletion(mock_mgr):
    """Verify clean deletion of credentials from secure locker and environment."""
    with patch.dict(os.environ, {}, clear=True):
        mock_mgr.set_credential("deepseek", "secret_deepseek_key")
        assert mock_mgr.get_credential_status("deepseek") == "configured"

        del_success = mock_mgr.delete_credential("deepseek")
        assert del_success is True
        assert mock_mgr.get_credential("deepseek") is None
        assert mock_mgr.get_credential_status("deepseek") == "missing"


def test_env_precedence_over_keyring(mock_mgr):
    """Verify that process OS environment variables take precedence over the secure store."""
    mock_mgr.set_credential("gemini", "keyring_stored_secret")

    # Override with OS environment variable
    with patch.dict(os.environ, {"GEMINI_API_KEY": "env_override_secret"}):
        assert mock_mgr.get_credential("gemini") == "env_override_secret"
        assert mock_mgr.get_credential_source("gemini") == "environment"


def test_env_example_safety():
    """Verify that .env.example contains only placeholders and zero real secrets."""
    example_path = Path(__file__).resolve().parents[2] / ".env.example"
    if not example_path.exists():
        example_path = Path(__file__).resolve().parents[1] / ".env.example"
    assert example_path.exists(), ".env.example must exist"
    content = example_path.read_text(encoding="utf-8")

    # Check for known secret prefixes
    for bad_prefix in ["AIza", "gsk_", "sk-", "nvapi-"]:
        assert bad_prefix not in content, f"Forbidden secret prefix {bad_prefix} found in .env.example"

    # Confirm key variables are present as placeholders
    assert "GEMINI_API_KEY=" in content
    assert "GROQ_API_KEY=" in content
    assert "DEEPSEEK_API_KEY=" in content
    assert "NVIDIA_API_KEY=" in content
    assert "COHERE_API_KEY=" in content
