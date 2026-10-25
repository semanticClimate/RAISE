"""
Security & Safety Firewall Tests for dev_main.py:
Guarantees that execute_dev_purge_all and '--purge-all' CANNOT be accidentally executed
and strictly rejects unauthorized attempts.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from src.cli.commands import execute_dev_purge_all


@pytest.mark.security
@pytest.mark.cli
def test_purge_all_blocked_when_token_env_unset(capsys):
    """Verifies purge immediately aborts when RAISE_DEV_PURGE_TOKEN is missing."""
    mock_pipeline = MagicMock()
    mock_memory = MagicMock()

    with patch.dict(os.environ, {}, clear=True), \
         patch("pathlib.Path.exists", return_value=False):
        result = execute_dev_purge_all(mock_pipeline, mock_memory)

    assert result is False
    captured = capsys.readouterr().out
    assert "PURGE BLOCKED" in captured
    assert "RAISE_DEV_PURGE_TOKEN" in captured
    mock_pipeline.purge_all_documents.assert_not_called()


@pytest.mark.security
@pytest.mark.cli
def test_purge_all_aborts_on_invalid_token(capsys):
    """Verifies purge aborts when user enters an invalid token."""
    mock_pipeline = MagicMock()
    mock_memory = MagicMock()

    with patch.dict(os.environ, {"RAISE_DEV_PURGE_TOKEN": "SUPER_SECRET_123"}), \
         patch("getpass.getpass", return_value="WRONG_TOKEN"), \
         patch("builtins.input", return_value="WRONG_TOKEN"):
        result = execute_dev_purge_all(mock_pipeline, mock_memory)

    assert result is False
    captured = capsys.readouterr().out
    assert "AUTHENTICATION FAILED" in captured
    mock_pipeline.purge_all_documents.assert_not_called()


@pytest.mark.security
@pytest.mark.cli
def test_purge_all_aborts_if_confirmation_string_mismatched(capsys):
    """Verifies purge aborts if user fails to type exact 'CONFIRM-PURGE' string."""
    mock_pipeline = MagicMock()
    mock_memory = MagicMock()

    with patch.dict(os.environ, {"RAISE_DEV_PURGE_TOKEN": "SUPER_SECRET_123"}), \
         patch("getpass.getpass", return_value="SUPER_SECRET_123"), \
         patch("builtins.input", return_value="no"):
        result = execute_dev_purge_all(mock_pipeline, mock_memory)

    assert result is False
    captured = capsys.readouterr().out
    assert "Operation cancelled by user" in captured
    mock_pipeline.purge_all_documents.assert_not_called()
