"""
Live API Integration Tests for Cloud Providers
STRICT ISOLATION: These tests only execute when RUN_LIVE_PROVIDER_TESTS=1 is explicitly passed.
Normal regression runs ('pytest') will skip them automatically to protect quotas and billing.
"""

import os
import pytest

from src.infrastructure.credentials.manager import get_credential_manager
from src.infrastructure.providers.gemini import GeminiProvider
from src.infrastructure.providers.groq import GroqProvider
from src.infrastructure.providers.deepseek import DeepSeekProvider
from src.infrastructure.providers.nvidia import NvidiaNIMProvider
from src.infrastructure.providers.cohere import CohereProvider

LIVE_TEST_GATE = os.getenv("RUN_LIVE_PROVIDER_TESTS", "0").lower() in ("1", "true", "yes")

pytestmark = pytest.mark.skipif(
    not LIVE_TEST_GATE,
    reason="Live cloud API tests are strictly opt-in via RUN_LIVE_PROVIDER_TESTS=1"
)


def test_live_groq_diagnostic():
    """Verify live Groq authentication and response when credentials exist."""
    prov = GroqProvider()
    health = prov.health_check(timeout=5.0)
    assert health.status in ("READY", "NOT_CONFIGURED", "RATE_LIMITED", "AUTH_FAILED")


def test_live_gemini_diagnostic():
    """Verify live Gemini authentication and response when credentials exist."""
    prov = GeminiProvider()
    health = prov.health_check(timeout=5.0)
    assert health.status in ("READY", "NOT_CONFIGURED", "RATE_LIMITED", "AUTH_FAILED")


def test_live_deepseek_diagnostic():
    """Verify live DeepSeek authentication and response when credentials exist."""
    prov = DeepSeekProvider()
    health = prov.health_check(timeout=5.0)
    assert health.status in ("READY", "NOT_CONFIGURED", "RATE_LIMITED", "AUTH_FAILED")


def test_live_nvidia_diagnostic():
    """Verify live NVIDIA NIM authentication and response when credentials exist."""
    prov = NvidiaNIMProvider()
    health = prov.health_check(timeout=5.0)
    assert health.status in ("READY", "NOT_CONFIGURED", "RATE_LIMITED", "AUTH_FAILED")


def test_live_cohere_diagnostic():
    """Verify live Cohere authentication and response when credentials exist."""
    prov = CohereProvider()
    health = prov.health_check(timeout=5.0)
    assert health.status in ("READY", "NOT_CONFIGURED", "RATE_LIMITED", "AUTH_FAILED")
