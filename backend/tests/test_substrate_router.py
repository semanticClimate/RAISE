"""
Automated Substrate Router Test Suite
======================================
Validates modular substrate connection routing across FAST (FakeRedis/NetworkX/SQLite),
DOCKER (Production container stack), and CLOUD modes.
"""

import os
import pytest
from src.core.substrate_router import (
    SubstrateMode,
    get_active_substrate_mode,
    get_redis_client,
    get_substrate_telemetry_summary,
)


def test_substrate_mode_resolution(monkeypatch):
    """Verifies that environment variable values properly resolve to SubstrateMode enums."""
    # 1. Default to FAST
    monkeypatch.delenv("RAISE_SUBSTRATE_MODE", raising=False)
    assert get_active_substrate_mode() == SubstrateMode.FAST

    # 2. Explicit FAST
    monkeypatch.setenv("RAISE_SUBSTRATE_MODE", "fast")
    assert get_active_substrate_mode() == SubstrateMode.FAST

    # 3. DOCKER variants
    for val in ("docker", "DOCKER", "prod", "PROD", "production", "Production "):
        monkeypatch.setenv("RAISE_SUBSTRATE_MODE", val)
        assert get_active_substrate_mode() == SubstrateMode.DOCKER

    # 4. CLOUD variants
    for val in ("cloud", "CLOUD", "remote", "aws", "gcp "):
        monkeypatch.setenv("RAISE_SUBSTRATE_MODE", val)
        assert get_active_substrate_mode() == SubstrateMode.CLOUD


def test_get_redis_client_in_fast_mode(monkeypatch):
    """Verifies FakeStrictRedis client creation and caching in FAST mode."""
    monkeypatch.setenv("RAISE_SUBSTRATE_MODE", "fast")
    client = get_redis_client()
    assert client is not None
    # Basic get/set roundtrip
    client.set("raise_test_key", "substrate_ok")
    assert client.get("raise_test_key") == "substrate_ok"


def test_substrate_telemetry_summary_fast_mode(monkeypatch):
    """Verifies telemetry badges in FAST mode contain clean ASCII and zero distorted symbols."""
    monkeypatch.setenv("RAISE_SUBSTRATE_MODE", "fast")
    summary = get_substrate_telemetry_summary(neo4j_open=False, redis_open=False, pg_open=False)

    assert "[FAST MODE]" in summary["mode_badge"]
    assert "[FAST-MEM]" in summary["neo4j"]
    assert "[FAKEREDIS]" in summary["redis"]
    assert "[SQLITE]" in summary["postgres"]
    assert "[LOCAL-FS]" in summary["storage"]

    for k, v in summary.items():
        for bad_char in ("✓", "●", "✖"):
            assert bad_char not in v, f"Found forbidden symbol '{bad_char}' in summary[{k}]"


def test_substrate_telemetry_summary_docker_mode(monkeypatch):
    """Verifies telemetry badges in DOCKER mode accurately report port states."""
    monkeypatch.setenv("RAISE_SUBSTRATE_MODE", "docker")

    # All ports open
    summary_online = get_substrate_telemetry_summary(neo4j_open=True, redis_open=True, pg_open=True)
    assert "[DOCKER PRODUCTION MODE]" in summary_online["mode_badge"]
    assert "[DOCKER-ON] bolt://localhost:7687" in summary_online["neo4j"]
    assert "[DOCKER-ON] localhost:6379" in summary_online["redis"]
    assert "[DOCKER-ON] localhost:5432" in summary_online["postgres"]

    # All ports closed
    summary_offline = get_substrate_telemetry_summary(neo4j_open=False, redis_open=False, pg_open=False)
    assert "[OFFLINE]" in summary_offline["neo4j"]
    assert "[OFFLINE]" in summary_offline["redis"]
    assert "[OFFLINE]" in summary_offline["postgres"]

    for s in (summary_online, summary_offline):
        for k, v in s.items():
            for bad_char in ("✓", "●", "✖"):
                assert bad_char not in v, f"Found forbidden symbol '{bad_char}' in summary[{k}]"


def test_substrate_telemetry_summary_cloud_mode(monkeypatch):
    """Verifies telemetry badges in CLOUD mode format remote URIs."""
    monkeypatch.setenv("RAISE_SUBSTRATE_MODE", "cloud")
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://custom.aura.databases.neo4j.io")
    monkeypatch.setenv("CLOUD_STORAGE_BUCKET", "s3://test-vault")

    summary = get_substrate_telemetry_summary(neo4j_open=False, redis_open=False, pg_open=False)
    assert "[CLOUD MODE]" in summary["mode_badge"]
    assert "custom.aura.databases.neo4j.io" in summary["neo4j"]
    assert "[CLOUD-REDIS]" in summary["redis"]
    assert "[CLOUD-PG]" in summary["postgres"]
    assert "s3://test-vault" in summary["storage"]


def test_repl_dispatch_substrate_switch(monkeypatch):
    """Verifies that the interactive REPL substrate switch command updates the active runtime profile."""
    from src.cli.service_runner import dispatch_repl_command

    class MockSupervisor:
        log_lock = None

    # Test switching to docker
    should_exit, _ = dispatch_repl_command("substrate docker", None, MockSupervisor())
    assert should_exit is False
    assert get_active_substrate_mode() == SubstrateMode.DOCKER
    assert os.getenv("USE_FAKEREDIS") == "false"

    # Test switching to fast
    should_exit, _ = dispatch_repl_command("substrate fast", None, MockSupervisor())
    assert should_exit is False
    assert get_active_substrate_mode() == SubstrateMode.FAST
    assert os.getenv("USE_FAKEREDIS") == "true"

    # Test switching to cloud
    should_exit, _ = dispatch_repl_command("substrate cloud", None, MockSupervisor())
    assert should_exit is False
    assert get_active_substrate_mode() == SubstrateMode.CLOUD

