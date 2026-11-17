"""
RAISE Vault Purge & Document Lifecycle Manager
===============================================
Purpose:
  Provides surgical and nuclear deletion mechanisms for ingested documents,
  vector embeddings, graph entities, disk artifacts, and raw PDF files.

Operations:
  1. Single-Document Surgical Purge (`purge_document`):
     - Resolves document identifiers against the ingested manifest.
     - Extracts associated entity IDs from graph triples.
     - Deletes document embeddings from ChromaDB.
     - Deletes nodes and relationships from Neo4j DBMS.
     - Removes nodes from in-memory NetworkX graph.
     - Unlinks JSON chunks, triples, facts, and the physical PDF.
     - Updates manifest and cleans active reasoning memory trajectories.
  2. Full-Vault Reset (`purge_all_documents`):
     - Wipes ChromaDB vector collections.
     - Purges all Neo4j nodes and constraints.
     - Clears in-memory NetworkX graph and reasoning memory.
     - Wipes all processed JSON/Markdown artifacts and resets the manifest.
     - Optionally deletes raw document files from documents/ and downloads/.

Author: RAISE Core Architecture Team
Maintainability: Keep under 250 lines with defensive filesystem error handling.
"""

from __future__ import annotations
import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from src.retrieval.pipeline import StandaloneRAGPipeline

logger = logging.getLogger(__name__)


def purge_document(pipeline: "StandaloneRAGPipeline", doc_identifier: str, postgres_manager: Optional[Any] = None) -> Dict[str, Any]:
    """
    Completely deletes an ingested document and all its associated artifacts:
    1. Deletes embeddings & context chunks from ChromaDB vector store
    2. Deletes nodes and relationships from Neo4j Graph Database
    3. Deletes nodes and edges from in-memory NetworkX Graph
    4. Deletes chunk JSON, graph triples JSON, and fact JSON files from disk
    5. Removes document from active manifest (tracks in deleted_documents)
    6. Cleans reasoning memory trajectories referencing the document
    """
    from src.core.config import settings
    manifest_file = settings.processed_dir / "ingested_manifest.json"
    
    target_filename = None
    
    # 1. Resolve document from manifest
    if manifest_file.exists():
        try:
            mdata = json.loads(manifest_file.read_text(encoding="utf-8"))
            docs = mdata.get("ready_documents", [])
            if doc_identifier.isdigit():
                idx = int(doc_identifier) - 1
                if 0 <= idx < len(docs):
                    target_filename = docs[idx].get("filename")
            else:
                for d in docs:
                    fn = d.get("filename", "")
                    if doc_identifier.lower() in fn.lower():
                        target_filename = fn
                        break
        except Exception as e:
            logger.warning("Failed to parse manifest during document purge: %s", e)

    if not target_filename:
        target_filename = doc_identifier

    target_doc_id = re.sub(r"[^a-zA-Z0-9]", "_", Path(target_filename).stem)[:40]

    # 2. Extract entity IDs from graph triples before deletion
    entity_ids = []
    triple_file = settings.processed_dir / "graph_triples" / f"{target_doc_id}_triples.json"
    if triple_file.exists():
        try:
            tdata = json.loads(triple_file.read_text(encoding="utf-8"))
            for ent in tdata.get("entities", []):
                if "entity_id" in ent:
                    entity_ids.append(ent["entity_id"])
        except Exception as e:
            logger.warning("Failed to extract entity IDs from triples: %s", e)

    # 3. Delete from ChromaDB Vector Store
    deleted_vectors = pipeline.vector_engine.delete_document(pdf_filename=target_filename, doc_id=target_doc_id)

    # 4. Delete from Neo4j Database
    neo4j_res = pipeline.neo4j_db.delete_document_nodes(doc_id=target_doc_id, entity_ids=entity_ids)
    deleted_nodes = neo4j_res.get("nodes_deleted", 0)

    # 5. Delete from In-Memory NetworkX Graph
    nx_deleted = pipeline.graph_engine.remove_document_nodes(doc_id=target_doc_id, entity_ids=entity_ids)

    # 6. Delete disk JSON artifacts
    removed_files = []
    for sub in ["chunks", "graph_triples", "facts", "neo4j"]:
        sdir = settings.processed_dir / sub
        if sdir.exists():
            for f in sdir.glob(f"{target_doc_id}*"):
                try:
                    f.unlink()
                    removed_files.append(f.name)
                except Exception:
                    pass

    # 6b. Delete physical PDF / source document from documents folder if requested
    for cand_name in [target_filename, f"{target_filename}.pdf", f"{target_doc_id}.pdf"]:
        cand_path = settings.documents_dir / cand_name
        if cand_path.exists():
            try:
                cand_path.unlink()
                removed_files.append(cand_path.name)
            except Exception:
                pass

    # Also check for any file in documents_dir whose stem matches target_doc_id
    if settings.documents_dir.exists():
        for p in settings.documents_dir.glob("*"):
            if p.is_file() and (p.name.lower() == target_filename.lower() or p.stem.lower() == target_doc_id.lower()):
                try:
                    p.unlink()
                    if p.name not in removed_files:
                        removed_files.append(p.name)
                except Exception:
                    pass

    # 7. Update Manifest
    if manifest_file.exists():
        try:
            mdata = json.loads(manifest_file.read_text(encoding="utf-8"))
            mdata["ready_documents"] = [d for d in mdata.get("ready_documents", []) if d.get("filename") != target_filename]
            if target_filename not in mdata.get("deleted_documents", []):
                mdata.setdefault("deleted_documents", []).append(target_filename)
            manifest_file.write_text(json.dumps(mdata, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to update manifest during purge: %s", e)

    # 7b. Delete from PostgreSQL (reusing pooled singleton)
    try:
        pm = postgres_manager or getattr(pipeline, "postgres_manager", None)
        if pm is None:
            from src.infrastructure.database.postgres import PostgresManager
            pm = PostgresManager()
        pm.delete_document(target_doc_id)
        pm.delete_document(target_filename)
    except Exception as e:
        logger.warning("Failed to delete PostgreSQL document during purge: %s", e)

    # 7c. Remove OKF Catalog Profile
    catalogs_purged = []
    try:
        from src.features.catalog.knowledge_catalog import KnowledgeCatalogRegistry
        reg = KnowledgeCatalogRegistry.get_instance()
        catalogs_purged = reg.remove_profile(target_filename)
        removed_files.extend(catalogs_purged)
    except Exception as e:
        logger.warning("Failed to remove OKF catalog profile: %s", e)

    # 8. Clean reasoning memory trajectories
    trajs_removed = pipeline.reasoning_memory.remove_document_trajectories(target_filename)

    return {
        "status": "success",
        "document": target_filename,
        "doc_id": target_doc_id,
        "vectors_deleted": deleted_vectors,
        "nodes_deleted": deleted_nodes,
        "nx_nodes_deleted": nx_deleted,
        "files_removed": removed_files,
        "trajectories_purged": trajs_removed,
    }


def purge_all_documents(
    pipeline: "StandaloneRAGPipeline",
    delete_raw_files: bool = True,
    preserved_filenames: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Completely resets and wipes the entire research vault:
    1. Clears ChromaDB vector collection
    2. Clears Neo4j graph nodes and relationships
    3. Clears NetworkX in-memory graph
    4. Clears all processed chunk, fact, and triple files
    5. Clears PostgreSQL documents and status tables
    6. Resets ingested manifest
    7. Clears reasoning memory
    8. Clears library directory and stray data caches
    9. Optionally deletes non-core raw document files
    """
    import shutil
    from src.core.config import settings
    
    # 1. Reset Vector Store
    pipeline.vector_engine.reset_collection()

    # 2. Reset Neo4j
    pipeline.neo4j_db.purge_all_nodes()

    # 3. Reset In-Memory Graph
    pipeline.graph_engine.clear()

    # 4. Clear Reasoning Memory
    pipeline.reasoning_memory.clear()

    # 5. Clear PostgreSQL Documents
    try:
        from src.infrastructure.database.postgres import PostgresManager
        pm = PostgresManager()
        pm.clear_all_documents()
    except Exception as e:
        logger.warning("Failed to clear PostgreSQL documents during vault purge: %s", e)

    # 6. Remove processed files
    removed_count = 0
    for sub in ["chunks", "graph_triples", "facts", "neo4j"]:
        sdir = settings.processed_dir / sub
        if sdir.exists():
            for f in sdir.glob("*.json"):
                try:
                    f.unlink()
                    removed_count += 1
                except Exception:
                    pass

    # Also remove processed markdown files or audit files in processed_dir
    if settings.processed_dir.exists():
        for f in settings.processed_dir.glob("*.md"):
            try:
                f.unlink()
                removed_count += 1
            except Exception:
                pass
        for f in settings.processed_dir.glob("*.json"):
            if f.name != "ingested_manifest.json":
                try:
                    f.unlink()
                    removed_count += 1
                except Exception:
                    pass

    # Clean stray features/data folder if present
    stray_data = Path(__file__).resolve().parent.parent / "features" / "data"
    if stray_data.exists():
        try:
            shutil.rmtree(stray_data, ignore_errors=True)
            removed_count += 1
        except Exception:
            pass

    # Clean library cache folder
    lib_dir = settings.data_dir / "library"
    if lib_dir.exists():
        for f in lib_dir.glob("*"):
            if f.is_file():
                try:
                    f.unlink()
                except Exception:
                    pass

    # 7. Reset manifest
    manifest_file = settings.processed_dir / "ingested_manifest.json"
    if manifest_file.exists():
        try:
            manifest_file.write_text(json.dumps({"ready_documents": [], "deleted_documents": []}, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to reset manifest: %s", e)

    # 7b. Clear all OKF Knowledge Catalogs
    catalogs_purged = 0
    try:
        from src.features.catalog.knowledge_catalog import KnowledgeCatalogRegistry
        reg = KnowledgeCatalogRegistry.get_instance()
        catalogs_purged = reg.clear_all_catalogs()
        removed_count += catalogs_purged
    except Exception as e:
        logger.warning("Failed to clear OKF catalogs: %s", e)

    # 8. Delete non-core raw document files if requested
    raw_files_deleted = 0
    core_docs = {f.lower() for f in (preserved_filenames or [])}
    env_preserved = os.getenv("VAULT_PRESERVED_DOCUMENTS", "")
    if env_preserved:
        core_docs.update(f.strip().lower() for f in env_preserved.split(",") if f.strip())

    if delete_raw_files:
        docs_dir = settings.documents_dir
        if docs_dir.exists():
            for f in docs_dir.glob("*"):
                if f.is_file() and (not core_docs or f.name.lower() not in core_docs):
                    try:
                        f.unlink()
                        raw_files_deleted += 1
                    except Exception:
                        pass
        
        downloads_dir = getattr(settings, "downloads_dir", None) or (settings.data_dir / "downloads")
        if downloads_dir.exists():
            for f in downloads_dir.glob("*"):
                if f.is_file() and f.name.lower() not in core_docs:
                    try:
                        f.unlink()
                        raw_files_deleted += 1
                    except Exception:
                        pass

    return {
        "status": "success",
        "message": f"Complete vault purge successful. Wiped all vectors, graph nodes, chunks, postgres records, {catalogs_purged} OKF catalogs, and {raw_files_deleted} non-core raw files.",
        "files_removed": removed_count,
        "catalogs_purged": catalogs_purged,
        "raw_documents_deleted": raw_files_deleted,
    }
