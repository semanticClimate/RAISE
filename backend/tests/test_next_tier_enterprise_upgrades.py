"""
Verification Suite: Next-Tier Enterprise Upgrades
=================================================
Validates the 5 newly integrated enterprise open-source libraries:
  1. Stanford DSPy: Declarative Signatures & Chain-of-Thought Modules
  2. Outlines: FSM Grammar Compilers & Structured Schema Decoders
  3. Polars: High-Performance Rust Columnar DataFrame Operations
  4. LiteLLM: Unified Multi-Provider Proxy Router
  5. Structlog: Structured Telemetry & Trace Context Logger
"""

import os
import sys
import time
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# =========================================================================
# 1. STANFORD DSPY: Declarative Prompting & Signatures
# =========================================================================
def test_dspy_declarative_signatures_and_module():
    from src.features.agent.dspy_modules import (
        RAGSynthesisSignature,
        QueryDecompositionSignature,
        DSPyRAGModule,
        get_dspy_rag_module,
    )

    # 1.1 Verify DSPy signatures are loaded and valid
    assert RAGSynthesisSignature is not None
    assert QueryDecompositionSignature is not None

    # 1.2 Verify module instance and decomposition
    module = get_dspy_rag_module()
    assert module is not None
    assert module.has_dspy is True

    # 1.3 Test query decomposition via DSPy module
    compound_query = "What were the research publications and how many patents were granted in 2024?"
    sub_queries = module.decompose(compound_query)
    assert isinstance(sub_queries, list)
    assert len(sub_queries) >= 1


# =========================================================================
# 2. OUTLINES: FSM Grammar Compilers & Schema Decoders
# =========================================================================
def test_outlines_fsm_schema_generation_and_validation():
    from src.features.agent.outlines_engine import (
        OutlinesAcademicFact,
        OutlinesGroundedReport,
        get_outlines_engine,
    )

    engine = get_outlines_engine()
    assert engine.has_outlines is True

    # 2.1 Compile schema JSON for FSM logit masking
    schema_json = engine.compile_schema_json(OutlinesGroundedReport)
    assert "executive_summary" in schema_json
    assert "extracted_facts" in schema_json

    # 2.2 Verify structured decoding and validation
    raw_response = """
    {
        "executive_summary": "NIPGR published 147 research papers and was granted 4 patents during FY 2022-23.",
        "extracted_facts": [
            {"metric_name": "Research Papers", "value": "147", "source_page": 12, "confidence": 1.0},
            {"metric_name": "Patents Granted", "value": "4", "source_page": 12, "confidence": 1.0}
        ],
        "unanswerable": false
    }
    """
    report = engine.validate_and_parse(raw_response, OutlinesGroundedReport)
    assert report is not None
    assert isinstance(report, OutlinesGroundedReport)
    assert len(report.extracted_facts) == 2
    assert report.extracted_facts[0].metric_name == "Research Papers"
    assert report.extracted_facts[0].value == "147"
    assert report.extracted_facts[1].source_page == 12


# =========================================================================
# 3. POLARS: High-Performance Rust Columnar DataFrame Operations
# =========================================================================
def test_polars_columnar_dataframe_operations():
    from src.features.verification.polars_engine import get_polars_engine

    engine = get_polars_engine()
    assert engine.has_polars is True

    headers = ["Department", "Budget_Crores", "Expenditure_Crores", "Year"]
    rows = [
        ["Biotechnology", "120.50", "110.20", "2024"],
        ["Computer Science", "185.00", "180.50", "2024"],
        ["Civil Engineering", "65.40", "60.10", "2024"],
        ["Electrical Engineering", "140.20", "135.00", "2024"],
    ]

    # 3.1 Create strongly typed Polars DataFrame
    df = engine.create_dataframe_from_matrix(headers, rows)
    assert df is not None
    assert df.height == 4
    assert "Budget_Crores" in df.columns

    # 3.2 Compute columnar aggregations in microseconds
    stats = engine.compute_column_aggregations(df, "Budget_Crores")
    assert stats["count"] == 4
    assert stats["sum"] == pytest.approx(511.10, rel=1e-3)
    assert stats["mean"] == pytest.approx(127.775, rel=1e-3)
    assert stats["max"] == 185.00
    assert stats["min"] == 65.40

    # 3.3 Test parallel row filtering
    filtered_rows = engine.filter_rows(df, "Budget_Crores", threshold=130.0, operator="gt")
    assert len(filtered_rows) == 2
    depts = [r["Department"] for r in filtered_rows]
    assert "Computer Science" in depts
    assert "Electrical Engineering" in depts

    # 3.4 Zero-copy Apache Arrow export
    arrow_batch = engine.export_to_arrow(df)
    assert arrow_batch is not None


# =========================================================================
# 4. LITELLM: Unified Multi-Provider Proxy Router
# =========================================================================
def test_litellm_unified_router_architecture():
    from src.infrastructure.llm.litellm_router import get_litellm_router

    router = get_litellm_router()
    assert router.has_litellm is True
    assert router.default_model is not None
    assert len(router.DEFAULT_FALLBACK_ORDER) >= 3

    # Verify model fallback chain includes high-throughput providers
    fallback_models = [f["model"] for f in router.DEFAULT_FALLBACK_ORDER]
    assert any("groq" in m for m in fallback_models)
    assert any("cohere" in m for m in fallback_models)


# =========================================================================
# 5. STRUCTLOG: High-Performance Structured Context Logger
# =========================================================================
def test_structlog_structured_logging_and_tracer():
    from src.infrastructure.logging.structured_logger import (
        get_pipeline_logger,
        ContextTracer,
        HAS_STRUCTLOG,
    )

    assert HAS_STRUCTLOG is True
    logger = get_pipeline_logger("test.module")
    assert logger is not None

    # Test ContextTracer timing and contextual metadata
    with ContextTracer(logger, operation="vector_retrieval", query_id="Q101", top_k=8) as tracer:
        time.sleep(0.01)  # 10ms execution

    assert tracer.start_time > 0
