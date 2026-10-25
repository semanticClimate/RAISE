"""
Tests interactive REPL command dispatch: drawer scoping, mode changes, list docs, and history reset.
"""

import re
import pytest
from unittest.mock import patch, MagicMock
from src.cli.renderer import ObsMode
from src.cli.commands import SessionTracker
from dev_main import main


@pytest.mark.unit
@pytest.mark.cli
def test_repl_mode_switch_command(mock_pipeline, mock_memory, capsys):
    """Verifies that typing 'mode 2' or 'mode VERBOSE' dynamically updates session mode."""
    inputs = iter(["mode 2", "exit"])
    
    with patch("dev_main.StandaloneRAGPipeline", return_value=mock_pipeline), \
         patch("dev_main.ReasoningMemory", return_value=mock_memory), \
         patch("dev_main.auto_start_containers"), \
         patch("builtins.input", lambda prompt="": next(inputs)), \
         patch("sys.argv", ["dev_main.py"]):
        main()

    captured = capsys.readouterr().out
    assert "OBSERVABILITY MODE UPDATED" in captured
    assert "VERBOSE" in captured


@pytest.mark.unit
@pytest.mark.cli
def test_repl_scope_attachment_commands(mock_pipeline, mock_memory, capsys):
    """Verifies 'attach all', 'detach', and 'attach <N>' commands."""
    manifest = [
        {"filename": "Report_A.pdf", "pages": 50},
        {"filename": "Report_B.pdf", "pages": 120},
    ]
    inputs = iter([
        "attach all",
        "detach",
        "attach 2",
        "exit"
    ])
    
    with patch("dev_main.StandaloneRAGPipeline", return_value=mock_pipeline), \
         patch("dev_main.ReasoningMemory", return_value=mock_memory), \
         patch("dev_main.auto_start_containers"), \
         patch("dev_main.get_active_documents_list", return_value=manifest), \
         patch("builtins.input", lambda prompt="": next(inputs)), \
         patch("sys.argv", ["dev_main.py"]):
        main()

    captured = capsys.readouterr().out
    clean_out = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", captured)
    assert "Searching across ALL documents" in clean_out
    assert "Drawer Emptied" in clean_out
    assert "Scope attached strictly to 'Report_B.pdf'" in clean_out


@pytest.mark.unit
@pytest.mark.cli
def test_repl_clear_chat_and_memory(mock_pipeline, mock_memory, capsys):
    """Verifies 'clear chat' invokes pipeline.clear_chat_session() and memory.clear()."""
    inputs = iter(["clear chat", "exit"])
    
    with patch("dev_main.StandaloneRAGPipeline", return_value=mock_pipeline), \
         patch("dev_main.ReasoningMemory", return_value=mock_memory), \
         patch("dev_main.auto_start_containers"), \
         patch("builtins.input", lambda prompt="": next(inputs)), \
         patch("sys.argv", ["dev_main.py"]):
        main()

    mock_pipeline.clear_chat_session.assert_called_once()
    mock_memory.clear.assert_called_once()


@pytest.mark.unit
@pytest.mark.cli
def test_repl_list_active_documents(mock_pipeline, mock_memory, capsys):
    """Verifies 'docs' command triggers list_active_documents."""
    inputs = iter(["docs", "exit"])
    
    with patch("dev_main.StandaloneRAGPipeline", return_value=mock_pipeline), \
         patch("dev_main.ReasoningMemory", return_value=mock_memory), \
         patch("dev_main.auto_start_containers"), \
         patch("dev_main.list_active_documents") as mock_list, \
         patch("builtins.input", lambda prompt="": next(inputs)), \
         patch("sys.argv", ["dev_main.py"]):
        main()

    mock_list.assert_called_once()


@pytest.mark.unit
@pytest.mark.cli
def test_repl_exit_on_eof_error(mock_pipeline, mock_memory, capsys):
    """Verifies that EOFError exits the loop gracefully without unhandled exception."""
    def raise_eof(prompt=""):
        raise EOFError()

    with patch("dev_main.StandaloneRAGPipeline", return_value=mock_pipeline), \
         patch("dev_main.ReasoningMemory", return_value=mock_memory), \
         patch("dev_main.auto_start_containers"), \
         patch("builtins.input", raise_eof), \
         patch("sys.argv", ["dev_main.py"]):
        main()

    captured = capsys.readouterr().out
    assert "Exiting RAISE Dev Studio. Goodbye!" in captured
