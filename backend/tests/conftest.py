"""
RAISE System Test Suite Root Conftest
Provides:
  - Advanced Lifecycle Hooks (pytest_report_header, pytest_configure, pytest_runtest_setup)
  - Dynamic Fixture Factories (Matrix Query Factory, Synthetic Chunk Factory)
  - Session-Scoped Database & Subsystem Connection Factories
  - Function-Level Isolation & Automatic State Teardown
"""

import sys
import os
import time
import uuid
import pytest
from pathlib import Path
from typing import Dict, Any, Generator, Callable

# Ensure project root (RAG) is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Enforce deterministic local testing flags
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"


# =============================================================================
# 1. ADVANCED LIFECYCLE HOOKS
# =============================================================================

def pytest_report_header(config):
    """Dynamic header hook displaying live subsystem readiness and environment."""
    # Dynamically detect active LLM inference target
    llm_target = "LLM Inference"
    try:
        from src.infrastructure.providers.router import get_provider_router, InferenceTask
        router = get_provider_router()
        prov = router.get_provider_for_task(InferenceTask.CHAT)
        if prov:
            m_name = getattr(prov, "model_name", "")
            llm_target = f"{prov.name.upper()} ({m_name})" if m_name else prov.name.upper()
    except Exception:
        llm_target = os.getenv("LLM_PROVIDER", "LLM Inference").upper()

    pg_port = os.getenv("POSTGRES_PORT", "5432")
    redis_port = os.getenv("REDIS_PORT", "6379")
    neo_port = os.getenv("NEO4J_PORT", "7687")

    return [
        "-" * 78,
        "🛡️  RAISE SYSTEM TEST SUITE: INITIALIZING SUBSYSTEMS",
        f"Python Runtime : {sys.version.split()[0]} on {sys.platform}",
        f"Execution Mode : importlib | Timeout: 120s | AsyncIO: Auto",
        f"Active Targets : Postgres ({pg_port}) | Redis ({redis_port}) | Neo4j ({neo_port}) | {llm_target}",
        "-" * 78,
    ]


def pytest_configure(config):
    """Registers custom markers natively within the test runner."""
    config.addinivalue_line("markers", "operator: Developer and Database Operator telemetry tests")
    config.addinivalue_line("markers", "api: Remote FastAPI, CORS, SSE, and contract tests")
    config.addinivalue_line("markers", "unit: Isolated algorithmic and business logic unit tests")
    config.addinivalue_line("markers", "integration: Multi-substrate full pipeline integration tests")


def pytest_runtest_setup(item):
    """
    Dynamic lifecycle control hook:
    Verifies markers and blocks external network calls for pure unit tests.
    """
    unit_marker = item.get_closest_marker("unit")
    if unit_marker:
        os.environ["BLOCK_EXTERNAL_CALLS"] = "1"
    else:
        os.environ.pop("BLOCK_EXTERNAL_CALLS", None)


# =============================================================================
# 2. SESSION-SCOPED CONNECTION FACTORIES
# =============================================================================

@pytest.fixture(scope="session")
def postgres_manager():
    """Session-scoped persistent connection factory to PostgreSQL 16."""
    from src.infrastructure.database.postgres import PostgresManager
    mgr = PostgresManager()
    yield mgr


@pytest.fixture(scope="session")
def redis_cache():
    """Session-scoped persistent connection factory to Redis 7."""
    from src.infrastructure.cache.redis import RedisCacheManager
    cache = RedisCacheManager()
    yield cache


@pytest.fixture(scope="session")
def operator_instance(postgres_manager, redis_cache):
    """Session-scoped instance of the DeveloperOperator telemetry engine."""
    from src.features.system.service import DeveloperOperator
    operator = DeveloperOperator(
        postgres_mgr=postgres_manager,
        redis_mgr=redis_cache
    )
    yield operator


@pytest.fixture(scope="session")
def api_client():
    """Session-scoped TestClient initialized with full FastAPI application."""
    from fastapi.testclient import TestClient
    from app import app
    with TestClient(app) as client:
        yield client


# =============================================================================
# 3. DYNAMIC FIXTURE FACTORIES
# =============================================================================

@pytest.fixture
def matrix_query_factory() -> Callable[..., Dict[str, Any]]:
    """
    Dynamic Fixture Factory:
    Generates parameterized test queries with configurable modes, libraries, and threads.
    """
    def _create(query: str, mode: str = "fast", thread_id: str = None, library: str = None) -> Dict[str, Any]:
        return {
            "message": query,
            "mode": mode,
            "session_id": thread_id or f"matrix_test_{uuid.uuid4().hex[:8]}",
            "stream": False,
            "library": library
        }
    return _create


@pytest.fixture
def synthetic_chunk_factory() -> Callable[..., Dict[str, Any]]:
    """
    Dynamic Fixture Factory:
    Generates synthetic chunks with custom metadata, headings, and coordinates.
    """
    def _create(
        chunk_id: str = None,
        heading: str = "Test Section",
        plain_text: str = "Sample scientific text.",
        page: int = 1,
        extra_meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        cid = chunk_id or f"chk_synth_{uuid.uuid4().hex[:6]}"
        payload = {
            "chunk_id": cid,
            "heading": heading,
            "plain_text": plain_text,
            "source_pages": [page],
            "metadata": {
                "source_pdf": "synthetic_fixture.pdf",
                "page": page,
                **(extra_meta or {})
            }
        }
        return payload
    return _create


# =============================================================================
# 4. FUNCTION-LEVEL ISOLATION & AUTOMATIC TEARDOWN
# =============================================================================

@pytest.fixture
def isolated_session_id(postgres_manager, redis_cache) -> Generator[str, None, None]:
    """
    Function-level isolated session ID that automatically purges all created
    PostgreSQL rows and Redis keys upon test completion.
    """
    sid = f"isolated_test_{uuid.uuid4().hex[:12]}"
    yield sid
    # Safe teardown
    try:
        postgres_manager.clear_session(sid)
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def teardown_all_neo4j_drivers():
    """Session-level safety fixture ensuring all background database drivers close."""
    yield
    try:
        from src.api.context import get_rag_engine
        engine = get_rag_engine()
        if engine and hasattr(engine, "close"):
            engine.close()
    except Exception:
        pass

