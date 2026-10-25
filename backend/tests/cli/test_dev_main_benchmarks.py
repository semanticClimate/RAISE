"""
Tests automated benchmark suite execution inside dev_main.py.
"""

import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from src.cli.benchmark_runner import run_dev_benchmark
from src.cli.commands import SessionTracker
from src.cli.renderer import ObsMode


@pytest.mark.integration
@pytest.mark.cli
def test_benchmark_runner_executes_suite_and_records_turn(tmp_path, capsys):
    """Verifies that run_dev_benchmark loads benchmark JSON and records scorecards."""
    test_qa_data = {
        "questions": [
            {
                "q_id": "TEST_Q001",
                "tier": 1,
                "question": "What was the total research funding in 2024-25?",
                "ground_truth_answer": "340.5 Rs. Crore",
                "required_keywords": ["340.5", "Crore"],
                "page_citations": ["Page 3"],
            }
        ]
    }
    dataset_file = tmp_path / "benchmark_qa.json"
    dataset_file.write_text(json.dumps(test_qa_data), encoding="utf-8")

    mock_pipeline = MagicMock()
    mock_pipeline.query_subgraph_graphrag.return_value = {
        "grounded_answer": "The total research outlay was 340.5 Rs. Crore [1].",
        "citations": [{"citation_index": 1, "document": "Report.pdf", "primary_page": 3, "similarity": 0.95}],
        "quality_gate_decision": "accept",
    }
    mock_memory = MagicMock()
    session = SessionTracker(mode=ObsMode.NORMAL)

    with patch("src.cli.benchmark_runner.execute_iterative_recovery_query", return_value=(
        mock_pipeline.query_subgraph_graphrag.return_value, {"loop_executed": False}
    )):
        run_dev_benchmark(
            pipeline=mock_pipeline,
            memory=mock_memory,
            session=session,
            benchmark_type=str(dataset_file),
            limit=1,
        )

    captured = capsys.readouterr().out
    assert "BENCHMARK PROVENANCE & FACTUAL VERIFICATION SCORECARD" in captured
    assert "TEST_Q001" in captured
    assert "Strict Correctness" in captured


@pytest.mark.unit
@pytest.mark.cli
def test_benchmark_runner_handles_missing_dataset(capsys):
    """Verifies that non-existent dataset paths abort with clean error."""
    mock_pipeline = MagicMock()
    mock_memory = MagicMock()
    session = SessionTracker(mode=ObsMode.NORMAL)

    run_dev_benchmark(
        pipeline=mock_pipeline,
        memory=mock_memory,
        session=session,
        benchmark_type="non_existent_dataset.json",
    )

    captured = capsys.readouterr().out
    assert "Unknown benchmark suite" in captured or "not found" in captured


@pytest.mark.unit
@pytest.mark.cli
def test_dev_main_frames_benchmark_drawer_isolation(capsys):
    """Verifies that '--benchmark frames' attaches documents to Drawer, excludes institutional PDFs, and prints scorecards."""
    mock_pipeline = MagicMock()
    mock_memory = MagicMock()
    session = SessionTracker(mode=ObsMode.NORMAL)

    mock_question = MagicMock()
    mock_question.question_id = "0"
    mock_question.prompt = "Who was the director of the lab?"
    mock_question.reference_answer = "Dr. Alice"
    mock_question.reasoning_types = ["Multi-hop"]
    mock_question.wiki_links = ["https://en.wikipedia.org/wiki/Alice_Smith", "https://en.wikipedia.org/wiki/Lab"]

    mock_trace = {
        "question_id": "0",
        "generated_answer": "Dr. Alice",
        "retrieval_trace": {
            "retrieved_chunks": [
                {"chunk_id": "chk_1", "text": "Dr. Alice was appointed director.", "source": "https://en.wikipedia.org/wiki/Alice_Smith", "title": "Alice Smith"}
            ],
            "graph_data": {"subgraph_nodes": ["Alice Smith", "Lab"], "subgraph_edges": []},
        },
        "stage_latencies": {"retrieval_ms": 20.0, "generation_ms": 100.0},
        "total_latency_ms": 130.0,
        "multihop_plan": MagicMock(required_hops=2, resolved_hops=2, missing_hops=[]),
    }

    mock_fact = MagicMock(reference_correctness_score=1.0, answer_status="correct")
    mock_reas = MagicMock()
    mock_ret = MagicMock(evidence_coverage=1.0, context_precision=1.0)
    mock_diag = MagicMock()

    with patch("evaluation.benchmarks.frames.data.loader.FramesDatasetLoader.get_questions", return_value=[mock_question]), \
         patch("evaluation.benchmarks.frames.isolation.harness.IsolatedFramesHarness.execute_question", return_value=mock_trace), \
         patch("evaluation.benchmarks.frames.isolation.harness.IsolatedFramesHarness.teardown"), \
         patch("evaluation.benchmarks.frames.runners.runner.FramesBenchmarkRunner.prepare_evaluation_corpus", return_value=12), \
         patch("evaluation.benchmarks.frames.evaluators.factuality.FactualityEvaluator.evaluate", return_value=mock_fact), \
         patch("evaluation.benchmarks.frames.evaluators.reasoning.ReasoningEvaluator.evaluate", return_value=mock_reas), \
         patch("evaluation.benchmarks.frames.evaluators.retrieval.RetrievalEvaluator.evaluate", return_value=mock_ret), \
         patch("evaluation.benchmarks.frames.evaluators.diagnostician.FailureDiagnostician.diagnose", return_value=mock_diag):
        run_dev_benchmark(
            pipeline=mock_pipeline,
            memory=mock_memory,
            session=session,
            benchmark_type="frames",
            limit=1,
        )

    import re
    clean = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    assert "STRICT DRAWER ISOLATION PROTOCOL" in clean
    assert "Drawer Active Scope" in clean
    assert "Alice Smith" in clean
    assert "Institutional PDF Reports QUARANTINED" in clean
    assert "FRAMES PROVENANCE & FACTUAL VERIFICATION SCORECARD" in clean
    assert "Factuality Score" in clean
    assert "100.0%" in clean
    assert "Document Library Status   : UNTOUCHED & PRISTINE" in clean

