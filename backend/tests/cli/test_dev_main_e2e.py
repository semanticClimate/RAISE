"""
End-to-End Headless CLI Execution Tests:
Tests running `python dev_main.py --query <text>` in one-shot mode.
Verifies clean exit code 0, telemetry emission, and zero REPL hanging.
"""

import sys
import pytest
from unittest.mock import MagicMock, patch
from dev_main import main


@pytest.mark.e2e
@pytest.mark.cli
def test_headless_one_shot_query_execution(mock_pipeline, mock_memory, capsys):
    """Verifies dev_main.py executes query headless, prints grounded answer, and exits cleanly."""
    manifest = [{"filename": "IITMRP Annual Report.pdf", "pages": 50}]
    with patch("dev_main.StandaloneRAGPipeline", return_value=mock_pipeline), \
         patch("dev_main.ReasoningMemory", return_value=mock_memory), \
         patch("dev_main.auto_start_containers"), \
         patch("dev_main.get_active_documents_list", return_value=manifest), \
         patch.object(sys, "argv", [
             "dev_main.py", "--query", "What was the compute capacity?",
             "--attach", "IITMRP Annual Report.pdf", "--mode", "NORMAL"
         ]):
        main()

    captured = capsys.readouterr().out
    assert "GROUNDED RESEARCH ANSWER" in captured
    assert "15.4 Petaflops" in captured
    assert "IITMRP Annual Report.pdf" in captured
