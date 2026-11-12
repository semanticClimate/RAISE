"""
RAISE — Document Library & Ingestion Manager
============================================
Handles document manifest querying, safe user deletion, RBAC document protection,
and local PDF ingestion via fast (PyMuPDF) and deep vision (IBM Docling) parsers.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.cli.commands import sanitize_path
from src.cli.renderer import C

logger = logging.getLogger("RAISE_DocManager")


def _resolve_base_dir(base_dir: Optional[Path] = None) -> Path:
    """Resolves canonical repository root directory and ensures the data folder hierarchy exists."""
    if base_dir is not None:
        root = Path(base_dir)
    else:
        main_mod = sys.modules.get("main")
        if main_mod and hasattr(main_mod, "BASE_DIR"):
            root = Path(main_mod.BASE_DIR)
        else:
            resolved = Path(__file__).resolve()
            root = resolved.parents[3] if len(resolved.parents) > 3 and resolved.parents[2].name == "backend" else resolved.parents[2]

    # Automatically create the canonical data folder and its subdirectories when user clones the repo
    data_dir = (root / "backend" / "data") if (root / "backend" / "data").exists() or (root / "backend").exists() else (root / "data")
    for sub in ["documents", "library", "catalogs", "processed", "processed/chunks", "processed/graph_triples"]:
        (data_dir / sub).mkdir(parents=True, exist_ok=True)
    manifest_file = data_dir / "processed" / "ingested_manifest.json"
    if not manifest_file.exists():
        try:
            manifest_file.write_text('{\n  "ready_documents": [],\n  "timestamp": ""\n}', encoding="utf-8")
        except Exception:
            pass
    return root


def get_active_documents_list(base_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Returns list of active documents from the ingested manifest."""
    root = _resolve_base_dir(base_dir)
    manifest_file = root / "backend" / "data" / "processed" / "ingested_manifest.json"
    if not manifest_file.exists():
        manifest_file = root / "data" / "processed" / "ingested_manifest.json"
    if not manifest_file.exists():
        return []
    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        return data.get("ready_documents", [])
    except Exception:
        return []


def list_active_documents(focused_document: Optional[str] = None, base_dir: Optional[Path] = None) -> None:
    """Displays formatted table of active documents in the manifest."""
    docs = get_active_documents_list(base_dir=base_dir)
    if not docs:
        print(f"\n{C.WARN}⚠️  No documents found in workspace manifest.{C.RESET}")
        print(f"   {C.MUTED}Use '{C.ACCENT}upload <path>{C.MUTED}' to ingest your first PDF report.{C.RESET}\n")
        return

    print(f"\n{C.SECTION}📚 Active Document Library ({len(docs)} registered reports):{C.RESET}")
    print(f"  {C.MUTED}{'ID':<4} {'FILENAME':<36} {'PAGES':<8} {'CHUNKS':<8} {'SIZE':<8} {'STATUS'}{C.RESET}")
    print(f"  {C.MUTED}{'─'*4} {'─'*36} {'─'*8} {'─'*8} {'─'*8} {'─'*12}{C.RESET}")
    for i, d in enumerate(docs, 1):
        fname = d.get("filename", "")
        pages = str(d.get("pages", "N/A"))
        chunks = str(d.get("chunks_count", "N/A"))
        size = f"{d.get('size_mb', 0):.1f}MB"
        is_focused = focused_document and (fname.lower() == focused_document.lower())
        focus_badge = f" {C.SUCCESS}👉 [ATTACHED]{C.RESET}" if is_focused else ""
        disp_name = (fname[:33] + "...") if len(fname) > 36 else fname
        print(
            f"  {C.NUM}{i:<4}{C.RESET} {C.WHITE}{disp_name:<36}{C.RESET} "
            f"{C.ACCENT}{pages:<8}{C.RESET} {C.CYAN}{chunks:<8}{C.RESET} "
            f"{C.MUTED}{size:<8}{C.RESET}{focus_badge}"
        )

    print()
    if focused_document:
        print(f"  🎯 {C.MUTED}Current Target Scope:{C.RESET} {C.SECTION}'{focused_document}' ATTACHED{C.RESET}")
    else:
        print(
            f"  🌐 {C.MUTED}Current Target Scope:{C.RESET} {C.ACCENT}ALL DOCUMENTS ATTACHED{C.RESET} "
            "(Library-Wide Drawer Grounding)"
        )
    print(
        f"  💡 {C.INFO}Tip:{C.RESET} Type '{C.ACCENT}attach <number|name>{C.RESET}' to focus, "
        f"or '{C.ACCENT}attach all{C.RESET}' to search all.\n"
    )


def check_document_is_protected(doc_id_or_name: str, base_dir: Optional[Path] = None) -> bool:
    """Checks if a document is marked as protected institutional report in ingested_manifest.json."""
    root = _resolve_base_dir(base_dir)
    manifest_file = root / "data" / "processed" / "ingested_manifest.json"
    if not manifest_file.exists():
        return False
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        target = doc_id_or_name.strip().lower()
        for d in manifest.get("ready_documents", []):
            fname = d.get("filename", "").strip().lower()
            if fname == target or target in fname:
                return bool(d.get("is_protected", False))
    except Exception:
        pass
    return False


def remove_document_from_library(
    doc_id_or_name: str, pipeline: Any, base_dir: Optional[Path] = None
) -> Optional[str]:
    """Purges a document, its ChromaDB vectors, Neo4j nodes, chunks, and manifest entry (standard user: unprotected only)."""
    if check_document_is_protected(doc_id_or_name, base_dir=base_dir):
        print(f"\n{C.DANGER}⛔ [Permission Denied]: '{doc_id_or_name}' is a pre-burned system document.{C.RESET}")
        print(f"   {C.MUTED}Protected institutional reports cannot be removed by standard users.{C.RESET}\n")
        return None

    try:
        res = pipeline.purge_document(doc_id_or_name)
        target_name = res.get("document")
        if res.get("status") == "success" and target_name:
            print(f"\n{C.WARN}🗑️  [PURGED REPORT]:{C.RESET} '{C.WHITE}{target_name}{C.RESET}'")
            print(f"   • {C.MUTED}ChromaDB vectors deleted:{C.RESET} {C.NUM}{res.get('vectors_deleted', 0)}{C.RESET}")
            print(f"   • {C.MUTED}Neo4j nodes detached:{C.RESET}    {C.NUM}{res.get('nodes_deleted', 0)}{C.RESET}")
            print(f"   • {C.MUTED}Files removed from disk:{C.RESET}  {C.WHITE}{sanitize_path(', '.join(res.get('files_removed', [])) or 'None')}{C.RESET}")
            print(f"   • {C.MUTED}Trajectories cleared:{C.RESET}    {C.NUM}{res.get('trajectories_purged', 0)}{C.RESET}\n")
            return target_name
        else:
            print(f"{C.DANGER}❌ Failed to purge document '{doc_id_or_name}'.{C.RESET}")
            return None
    except Exception as e:
        print(f"{C.DANGER}❌ Error purging document: {e}{C.RESET}")
        return None


# Backward-compatibility alias
remove_document_from_vault = remove_document_from_library


def ingest_pdf_from_path(
    pdf_path_str: str,
    pipeline: Any,
    engine: Optional[str] = None,
    max_pages: Optional[int] = None,
    base_dir: Optional[Path] = None,
) -> Optional[str]:
    """
    Ingests any local PDF report provided by the user:
    1. Validates local filesystem path and file extension
    2. Sanitizes displayed paths to protect username privacy
    3. Enforces benchmark test isolation to protect ChromaDB & Neo4j
    4. Handles flexible page range selection ('1-40', '40', 'all')
    5. Executes chosen parsing engine (PyMuPDF Layout-Aware or Docling TableFormer)
    6. Registers document in data/processed/ingested_manifest.json
    7. Refreshes pipeline in-memory indices and sets active document focus
    """
    clean_path = pdf_path_str.strip().strip("'\"")
    if not clean_path:
        print(f"{C.DANGER}❌ Error: Path cannot be empty.{C.RESET}")
        return None

    src_path = Path(clean_path).expanduser().resolve()
    if not src_path.exists() or not src_path.is_file():
        print(f"{C.DANGER}❌ Error: File not found at '{sanitize_path(src_path)}'. Please verify the path and try again.{C.RESET}")
        return None

    if src_path.suffix.lower() != ".pdf":
        print(f"{C.DANGER}❌ Error: File '{src_path.name}' is not a PDF report. Only PDF documents are supported.{C.RESET}")
        return None

    # Benchmark test isolation guardrail
    path_str = str(src_path).lower().replace("\\", "/")
    excluded_patterns = ["evaluation", "benchmark", "question_suite", "question suite", "raise-bench", "gemini-notebook"]
    if any(pattern in path_str for pattern in excluded_patterns):
        print(f"\n{C.DANGER}⛔ [Database Isolation Guard] Ingestion Blocked:{C.RESET}")
        print(f"   '{src_path.name}' matches excluded benchmark patterns.")
        print("   Evaluation datasets must NEVER be ingested into production ChromaDB or Neo4j to prevent test contamination.\n")
        return None

    root = _resolve_base_dir(base_dir)
    docs_dir = root / "data" / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    dest_path = docs_dir / src_path.name

    print("\n" + C.BANNER + "═" * 74 + C.RESET)
    print(f" {C.TITLE}📥 INGESTING USER REPORT:{C.RESET} {C.WHITE}{src_path.name}{C.RESET}")
    print(C.BANNER + "═" * 74 + C.RESET)

    try:
        total_pdf_pages = 0
        try:
            import pymupdf
            with pymupdf.open(str(src_path)) as _doc:
                total_pdf_pages = len(_doc)
        except Exception:
            pass

        if engine is None:
            print(f"\n  {C.SECTION}⚙️  Select Ingestion Speed & Parsing Mode:{C.RESET}")
            print(f"     [{C.NUM}1{C.RESET}] {C.ACCENT}⚡ Fast Mode{C.RESET}   — PyMuPDF Layout-Aware (~2-5s, extracts text, tables & entities) {C.MUTED}[DEFAULT]{C.RESET}")
            print(f"     [{C.NUM}2{C.RESET}] {C.MAGENTA}🔬 Deep Vision{C.RESET}  — IBM Docling TableFormer (neural cell recovery, no page cap)")
            try:
                mode_pick = input(f"     {C.SECTION}Choose mode [1 or 2, default=1]:{C.RESET} ").strip()
            except (EOFError, Exception):
                mode_pick = "1"
            selected_engine = "deep" if mode_pick == "2" else "fast"
        else:
            selected_engine = engine

        if max_pages is not None:
            pages_to_process = total_pdf_pages if int(max_pages) <= 0 else min(int(max_pages), total_pdf_pages)
        elif total_pdf_pages > 0 and total_pdf_pages <= 50:
            pages_to_process = total_pdf_pages
            print(f"  {C.INFO}📄 Document has {total_pdf_pages} page(s) (<= 50) — auto-processing all pages.{C.RESET}")
        else:
            prompt_str = (
                f"     Document has {total_pdf_pages} pages. Pages to process "
                f"[{C.SECTION}Press Enter for ALL {total_pdf_pages} pages{C.RESET}, or enter number / range like 1-40]: "
            )
            try:
                pages_inp = input(prompt_str).strip()
                numbers = [int(n) for n in re.findall(r"\b\d+\b", pages_inp) if int(n) > 0]
                pages_to_process = min(max(numbers), total_pdf_pages) if numbers else total_pdf_pages
            except Exception:
                pages_to_process = total_pdf_pages

        if src_path.resolve() != dest_path.resolve():
            print(f"  {C.MUTED}📂 Staging document to:{C.RESET} {C.CYAN}{sanitize_path(dest_path)}{C.RESET}")
            shutil.copy2(src_path, dest_path)
        else:
            print(f"  {C.MUTED}📂 Document already staged in library:{C.RESET} {C.CYAN}{sanitize_path(dest_path)}{C.RESET}")

        cap_desc = (
            f"all {pages_to_process} pages"
            if (total_pdf_pages and pages_to_process == total_pdf_pages)
            else f"{pages_to_process} pages"
        )
        print(f"  {C.SECTION}⚙️  Extracting ({selected_engine.upper()} mode, {cap_desc}) & indexing dense vectors...{C.RESET}")

        t0 = time.time()
        from src.features.ingestion.pipeline import AcademicPipelineIngestor
        academic_pipeline = AcademicPipelineIngestor(download_dir=docs_dir)
        res = academic_pipeline.process_pdf(dest_path, max_pages=pages_to_process, engine=selected_engine)
        elapsed = round(time.time() - t0, 2)

        manifest_file = root / "data" / "processed" / "ingested_manifest.json"
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        manifest: Dict[str, Any] = {"ready_documents": [], "deleted_documents": []}
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                manifest = {"ready_documents": [], "deleted_documents": []}

        pages_proc = res.get("pages_processed", 1)
        chunks_count = res.get("chunks_count", 0)
        size_mb = round(dest_path.stat().st_size / (1024 * 1024), 2)

        manifest["deleted_documents"] = [f for f in manifest.get("deleted_documents", []) if f != dest_path.name]
        docs = manifest.get("ready_documents", [])
        updated = False
        for d in docs:
            if d.get("filename") == dest_path.name:
                d["pages"] = pages_proc
                d["size_mb"] = size_mb
                d["chunks_count"] = chunks_count
                d["status"] = "ready"
                if "is_protected" not in d:
                    d["is_protected"] = False
                    d["uploaded_by"] = "user"
                updated = True
                break
        if not updated:
            docs.append({
                "filename": dest_path.name,
                "is_protected": False,
                "uploaded_by": "user",
                "pages": pages_proc,
                "size_mb": size_mb,
                "chunks_count": chunks_count,
                "status": "ready",
            })
        manifest["ready_documents"] = docs
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        if hasattr(pipeline, "_load_processed_data"):
            pipeline._load_processed_data()

        facts_cnt = res.get("facts_extracted", res.get("entities_count", 0))
        triples_cnt = res.get("triples_extracted", res.get("relations_count", 0))

        print(f"\n{C.SUCCESS}✅ [INGESTION COMPLETE IN {elapsed}s]{C.RESET}")
        print(f"  • {C.MUTED}Document:{C.RESET}         {C.BOLD}{dest_path.name}{C.RESET}")
        print(f"  • {C.MUTED}Pages Processed:{C.RESET}  {C.NUM}{pages_proc}{C.RESET}")
        print(f"  • {C.MUTED}Chunks Indexed:{C.RESET}   {C.NUM}{chunks_count}{C.RESET}")
        print(f"  • {C.MUTED}Facts Extracted:{C.RESET}  {C.NUM}{facts_cnt}{C.RESET}")
        print(f"  • {C.MUTED}Neo4j Triples:{C.RESET}    {C.NUM}{triples_cnt}{C.RESET}")
        print(f"  • {C.MUTED}Total Library Size:{C.RESET} {C.ACCENT}{len(manifest['ready_documents'])} report(s){C.RESET}")
        print(f"  🎯 [{C.SUCCESS}Active Scope Set To:{C.RESET} '{C.ACCENT}{dest_path.name}{C.RESET}'] ({C.MUTED}Attached to drawer!{C.RESET})\n")
        return dest_path.name

    except Exception as e:
        print(f"\n{C.DANGER}❌ [Ingestion Error]: {e}{C.RESET}")
        return None
