"""
Sub-suite conftest for Developer & Database Operator Dashboard testing.
"""
import pytest

@pytest.fixture
def expected_subsystem_keys():
    return ["postgres", "redis", "neo4j", "chromadb", "vllm", "cloudflare"]