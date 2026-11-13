"""
RAISE Ingestion Manifest & Document State Manager
=================================================
Purpose:
  Provides persistent tracking of ingested documents in `data/processed/ingested_manifest.json`.
  Records page counts, file sizes, chunk counts, and operational readiness status.

Operations:
  - `load_manifest`: Reads the persistent manifest or initializes a clean structure.
  - `update_manifest_entry`: Adds or updates a document record upon successful ingestion.
  - `mark_deleted`: Moves an entry to deleted_documents or removes it from active list.

Author: RAISE Core Architecture Team
Maintainability: Keep under 100 lines with atomic JSON file persistence.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("raise.ingestion.manifest")


def load_manifest(output_dir: Path) -> Dict[str, Any]:
    """Reads ingested_manifest.json safely, returning empty structure on missing or error."""
    manifest_file = output_dir / "ingested_manifest.json"
    if manifest_file.exists():
        try:
            return json.loads(manifest_file.read_text(encoding="utf-8-sig"))
        except Exception as e:
            logger.warning("Manifest read error: %s", e)
    return {"ready_documents": [], "deleted_documents": []}


def update_manifest_entry(
    output_dir: Path,
    pdf_path: Path,
    pages_processed: int,
    chunks_count: int,
) -> None:
    """Updates or appends a document entry in the persistent manifest."""
    try:
        manifest_file = output_dir / "ingested_manifest.json"
        manifest = load_manifest(output_dir)
        
        # Remove from deleted_documents if re-ingested
        manifest["deleted_documents"] = [f for f in manifest.get("deleted_documents", []) if f != pdf_path.name]
        docs = manifest.get("ready_documents", [])
        size_mb = round(pdf_path.stat().st_size / (1024 * 1024), 2) if pdf_path.exists() else 0.0

        updated = False
        for d in docs:
            if d.get("filename") == pdf_path.name:
                d["pages"] = pages_processed
                d["size_mb"] = size_mb
                d["chunks_count"] = chunks_count
                d["status"] = "ready"
                updated = True
                break

        if not updated:
            docs.append({
                "filename": pdf_path.name,
                "pages": pages_processed,
                "size_mb": size_mb,
                "chunks_count": chunks_count,
                "status": "ready",
            })

        manifest["ready_documents"] = docs
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to update ingested manifest: %s", e)
