"""
Tests CLI flag parsing, argument extraction, and command routing in dev_main.py.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock
from dev_main import main


@pytest.mark.unit
@pytest.mark.cli
def test_dev_main_help_flag_prints_menu_and_exits(capsys):
    """Verifies that '--help' prints the command registry and exits immediately."""
    with patch.object(sys, "argv", ["dev_main.py", "--help"]):
        main()
    
    captured = capsys.readouterr().out
    assert "RAISE DEVELOPER OBSERVABILITY CONSOLE — COMMAND REGISTRY" in captured
    assert "Research & Navigation" in captured
    assert "Observability & Diagnostics" in captured


@pytest.mark.unit
@pytest.mark.cli
def test_dev_main_status_flag_prints_dashboard_and_exits(mock_pipeline, mock_memory, capsys):
    """Verifies that '--status' renders the subsystem health dashboard and terminates."""
    with patch("dev_main.StandaloneRAGPipeline", return_value=mock_pipeline), \
         patch("dev_main.ReasoningMemory", return_value=mock_memory), \
         patch("dev_main.auto_start_containers"), \
         patch.object(sys, "argv", ["dev_main.py", "--status"]):
        main()

    captured = capsys.readouterr().out
    assert "RAISE SYSTEM HEALTH & DEEP OBSERVABILITY DASHBOARD" in captured
    assert "Neo4j Graph Engine" in captured
    assert "ChromaDB Vector Store" in captured


@pytest.mark.unit
@pytest.mark.cli
def test_dev_main_ingest_flag_routing():
    """Verifies that '--ingest' parses path, engine, and pages properly."""
    with patch("dev_main.ingest_pdf_from_path", return_value="Sample_Report.pdf") as mock_ingest, \
         patch("dev_main.auto_start_containers"), \
         patch("dev_main.StandaloneRAGPipeline"), \
         patch("dev_main.ReasoningMemory"), \
         patch.object(sys, "argv", [
             "dev_main.py", "--ingest", "data/documents/Sample_Report.pdf",
             "--engine", "fast", "--pages", "5"
         ]):
        main()
    
    mock_ingest.assert_called_once()
    args, kwargs = mock_ingest.call_args
    assert "Sample_Report.pdf" in args[0]
    assert kwargs.get("engine") == "fast"
    assert kwargs.get("max_pages") == 5


@pytest.mark.unit
@pytest.mark.cli
def test_dev_main_benchmark_flag_routing():
    """Verifies that '--benchmark frames --limit 10' triggers benchmark runner."""
    with patch("src.cli.benchmark_runner.run_dev_benchmark") as mock_bench, \
         patch("dev_main.auto_start_containers"), \
         patch("dev_main.StandaloneRAGPipeline"), \
         patch("dev_main.ReasoningMemory"), \
         patch.object(sys, "argv", ["dev_main.py", "--benchmark", "frames", "--limit", "10"]):
        main()

    mock_bench.assert_called_once()
    args, kwargs = mock_bench.call_args
    assert kwargs.get("benchmark_type") == "frames"
    assert kwargs.get("limit") == 10


@pytest.mark.unit
@pytest.mark.cli
def test_dev_main_mode_and_attach_flag_routing(mock_pipeline, mock_memory, capsys):
    """Verifies that '--mode VERBOSE' and '--attach <name>' initialize session and scope."""
    manifest = [{"filename": "IITMRP Annual Report.pdf", "pages": 50}]
    with patch("dev_main.StandaloneRAGPipeline", return_value=mock_pipeline), \
         patch("dev_main.ReasoningMemory", return_value=mock_memory), \
         patch("dev_main.auto_start_containers"), \
         patch("dev_main.get_active_documents_list", return_value=manifest), \
         patch.object(sys, "argv", [
             "dev_main.py", "--mode", "VERBOSE", "--attach", "IITMRP", "--query", "What is the compute capacity?"
         ]):
        main()

    captured = capsys.readouterr().out
    assert "Mode Initialized" in captured or "VERBOSE" in captured
    assert "Active Scope Attached" in captured or "IITMRP" in captured
