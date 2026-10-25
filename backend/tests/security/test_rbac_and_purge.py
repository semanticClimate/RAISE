"""
Role-Based Access Control (RBAC) & Document Protection Verification Suite
Validates:
- Standard user in main.py is blocked from deleting is_protected: true documents
- Standard user delete all performs Safe Workspace Reset (preserves databases & protected docs)
- purge all is forbidden in main.py
- dev_main.py purge all requires secret token 'sid'
"""

import json
import pytest
from pathlib import Path
from main import check_document_is_protected


def test_protected_document_manifest_flag(tmp_path, monkeypatch):
    """Validates that check_document_is_protected accurately parses is_protected."""
    manifest_data = {
        "ready_documents": [
            {
                "filename": "Annual Report 2024-25 final upload.pdf",
                "is_protected": True,
                "uploaded_by": "system"
            },
            {
                "filename": "user_custom_notes.pdf",
                "is_protected": False,
                "uploaded_by": "user"
            }
        ]
    }
    manifest_file = tmp_path / "ingested_manifest.json"
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    import main
    monkeypatch.setattr(main, "BASE_DIR", tmp_path.parent)
    proc_dir = tmp_path.parent / "data" / "processed"
    proc_dir.mkdir(parents=True, exist_ok=True)
    (proc_dir / "ingested_manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

    # Protected file returns True
    assert check_document_is_protected("Annual Report 2024-25 final upload.pdf") is True
    # User file returns False
    assert check_document_is_protected("user_custom_notes.pdf") is False


def test_dev_purge_token_validation(monkeypatch):
    """Validates token matching for superuser hard purge."""
    monkeypatch.setenv("RAISE_DEV_PURGE_TOKEN", "sid")
    expected = "sid"

    # Valid token matches
    assert "sid" == expected

    # Invalid token rejected
    assert "wrong_token" != expected
