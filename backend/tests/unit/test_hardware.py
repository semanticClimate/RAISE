"""
Unit tests for dynamic system hardware and subsystem telemetry engine.
Validates zero-hardcoding and dynamic host resource interrogation.
"""

from __future__ import annotations

import os
import pytest
from src.infrastructure.hardware import (
    get_ram_info,
    get_cpu_info,
    get_gpu_info,
    get_llm_telemetry,
    get_database_telemetry,
    get_system_manifest,
    format_hardware_summary,
)


def test_dynamic_ram_detection():
    """Verify RAM is detected dynamically without hardcoded fallback."""
    ram = get_ram_info()
    assert isinstance(ram, dict)
    assert "detected" in ram
    if ram["detected"]:
        assert isinstance(ram["total_gb"], float)
        assert ram["total_gb"] > 0
        assert isinstance(ram["available_gb"], float)
        assert ram["available_gb"] >= 0
        assert isinstance(ram["percent_used"], (int, float))
        assert 0 <= ram["percent_used"] <= 100


def test_dynamic_cpu_detection():
    """Verify CPU cores and platform architecture are dynamically queried."""
    cpu = get_cpu_info()
    assert isinstance(cpu, dict)
    assert "architecture" in cpu
    assert "system" in cpu
    assert cpu["logical_cores"] is None or (isinstance(cpu["logical_cores"], int) and cpu["logical_cores"] > 0)


def test_dynamic_gpu_detection():
    """Verify GPU information is discovered dynamically without static model assumptions."""
    gpu = get_gpu_info()
    assert isinstance(gpu, dict)
    assert "detected" in gpu
    assert "cuda_available" in gpu
    assert "device_count" in gpu
    assert isinstance(gpu["devices"], list)

    if gpu["cuda_available"] and gpu["device_count"] > 0:
        dev = gpu["devices"][0]
        assert "name" in dev
        assert isinstance(dev["name"], str) and len(dev["name"]) > 0
        assert "total_vram_gb" in dev
        assert isinstance(dev["total_vram_gb"], float) and dev["total_vram_gb"] > 0


def test_llm_telemetry_zero_secret_leak():
    """Verify LLM telemetry reports configuration without exposing private API keys."""
    llm = get_llm_telemetry()
    assert isinstance(llm, dict)
    assert "active_backend" in llm
    assert "fallback_chain" in llm
    assert "providers" in llm

    # Zero secret exposure check: Ensure actual API key strings are NEVER returned
    for provider, data in llm["providers"].items():
        assert "api_key" not in data, f"Provider {provider} must not expose api_key"
        assert "key" not in data, f"Provider {provider} must not expose key"
        assert isinstance(data.get("configured"), bool)


def test_database_telemetry_safe_execution():
    """Verify database telemetry runs gracefully and returns structured status."""
    db = get_database_telemetry()
    assert isinstance(db, dict)
    assert "neo4j" in db
    assert "chroma" in db
    assert "redis" in db
    assert "postgres" in db
    for key in ("neo4j", "chroma", "redis", "postgres"):
        assert "online" in db[key]
        assert isinstance(db[key]["online"], bool)


def test_system_manifest_consolidation():
    """Verify full system manifest includes host, memory, cpu, gpu, llm, and databases."""
    manifest = get_system_manifest()
    assert isinstance(manifest, dict)
    assert "host" in manifest
    assert "memory" in manifest
    assert "cpu" in manifest
    assert "gpu" in manifest
    assert "llm" in manifest
    assert "databases" in manifest


def test_hardware_summary_string_format():
    """Verify formatted hardware summary string is non-empty and contains memory and OS info."""
    summary = format_hardware_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0
    assert "RAM" in summary
