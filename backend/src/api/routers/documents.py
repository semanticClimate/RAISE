"""
Documents & Ingestion Router
Endpoints for uploading PDFs, IBM Docling / PyMuPDF parsing, batch ingestion,
real-time SSE pipeline status tracking, serving raw PDF binaries, and document lifecycle deletion.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse

from src.api.context import (
    DOCUMENTS_DIR,
    DOWNLOAD_DIR,
    MANIFEST_FILE,
    record_ready_document,
)
from src.api.dependencies import get_postgres_manager, get_rag_engine, get_document_service
from src.features.ingestion.pipeline import AcademicPipelineIngestor
from src.api.routers.vault_batch import execute_load_vault_defaults, execute_ingest_download_folder

logger = logging.getLogger("raise.router.documents")
router = APIRouter(tags=["Documents & Ingestion"])

from src.core.config import BACKEND_DIR

BASE_DIR = BACKEND_DIR


@router.post("/api/upload")
@router.post("/api/documents/upload")
@router.post("/api/sources/upload")
async def upload_document_spec(
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    session_id: Optional[str] = Form(None),
    library: Optional[str] = Form(None),
    parser: Optional[str] = Form(None),
    engine: Optional[str] = Form(None),
    parse_mode: Optional[str] = Form(None),
    extract_tables: Optional[str] = Form(None),
    full_potential: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),
    document_service: Any = Depends(get_document_service),
):
    """
    Document Upload endpoint matching shared frontend specification.
    Supports both single 'file' and multi-file 'files' multipart form fields.
    Honors query and form parameters:
      parser='docling', engine='docling', mode='expert', full_potential='true', extract_tables='true'
    Maintains real-time ingestion phase progression:
      uploading (15%) -> parsing (40%) -> chunking (65%) -> embedding (85%) -> ready (100%)
    """
    q_params = request.query_params
    effective_parser = parser or q_params.get("parser") or engine or q_params.get("engine") or "auto"
    effective_mode = mode or q_params.get("mode") or parse_mode or q_params.get("parse_mode") or "fast"
    effective_library = library or q_params.get("library") or "default"
    effective_full_potential = str(full_potential or q_params.get("full_potential") or "false").lower() in ("true", "1", "yes")
    effective_extract_tables = str(extract_tables or q_params.get("extract_tables") or "true").lower() in ("true", "1", "yes")

    use_engine = "docling" if (effective_parser.lower() in ("docling", "deep") or effective_full_potential) else ("auto" if effective_mode.lower() == "expert" else "fast")

    upload_list: List[UploadFile] = []
    seen_filenames = set()
    raw_candidates = ([file] if file else []) + (files or [])
    for candidate in raw_candidates:
        if candidate and candidate.filename:
            fn = Path(candidate.filename).name.strip("\"'")
            if fn and fn not in seen_filenames:
                seen_filenames.add(fn)
                upload_list.append(candidate)

    if not upload_list:
        raise HTTPException(status_code=400, detail="No file selected for upload")

    reports = []
    for up_file in upload_list:
        if not up_file.filename:
            continue
        rep = await document_service.ingest_uploaded_file_async(
            file=up_file,
            session_id=session_id,
            library=effective_library,
            engine=use_engine,
            full_potential=effective_full_potential,
            extract_tables=effective_extract_tables,
        )
        reports.append(rep)

    total_nodes, total_edges = document_service.sync_rag_and_graph()
    first_rep = reports[0] if reports else {}
    failed_count = sum(1 for r in reports if r.get("status") == "failed")
    overall_status = "error" if (reports and failed_count == len(reports)) else "success"

    return {
        "status": overall_status,
        "message": (
            "Document(s) uploaded and processed successfully"
            if overall_status == "success"
            else f"Document ingestion failed: {reports[0].get('error', 'Processing error')}"
        ),
        "uploaded_count": len(reports),
        "document_id": first_rep.get("doc_id"),
        "doc_id": first_rep.get("doc_id"),
        "filename": first_rep.get("filename"),
        "chunks": first_rep.get("chunks_extracted", 0),
        "library": effective_library,
        "reports": reports,
        "documents": [
            {
                "doc_id": r.get("doc_id"),
                "document_id": r.get("doc_id"),
                "filename": r.get("filename"),
                "status": r.get("status", "ready"),
                "chunks": r.get("chunks_extracted", 0),
            }
            for r in reports
        ],
        "total_nodes": total_nodes,
        "total_edges": total_edges,
    }



@router.post("/api/upload-academic-pdfs")
async def upload_academic_pdfs(
    request: Request,
    files: List[UploadFile] = File(...),
    parser: Optional[str] = Form(None),
    engine: Optional[str] = Form(None),
    parse_mode: Optional[str] = Form(None),
    extract_tables: Optional[str] = Form(None),
    full_potential: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),
    rag_engine: Any = Depends(get_rag_engine),
):
    """
    Multi-PDF Ingestion Pipeline:
    1. Upload and save PDFs to Download/
    2. Extract structure-aware text spans & clean OCR with Docling / PyMuPDF
    3. Extract Academic Entities & Relations
    4. Index into ChromaDB & sync into Neo4j
    5. Register in verified ready manifest
    """
    if not files:
        raise HTTPException(status_code=400, detail="No PDF files uploaded.")

    q_params = request.query_params
    effective_parser = parser or q_params.get("parser") or engine or q_params.get("engine") or "docling"
    effective_mode = mode or q_params.get("mode") or parse_mode or q_params.get("parse_mode") or "fast"
    effective_full_potential = str(full_potential or q_params.get("full_potential") or "false").lower() in ("true", "1", "yes")
    effective_extract_tables = str(extract_tables or q_params.get("extract_tables") or "true").lower() in ("true", "1", "yes")

    use_engine = "docling" if (effective_parser.lower() in ("docling", "deep") or effective_mode.lower() == "expert" or effective_full_potential) else "auto"

    ingested_reports = []
    academic_pipeline = AcademicPipelineIngestor(download_dir=DOWNLOAD_DIR)

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for upload_file in files:
        if not upload_file.filename.lower().endswith(".pdf"):
            continue

        dest_name = Path(upload_file.filename).name.strip("\"'")
        dest_path = DOWNLOAD_DIR / dest_name
        try:
            upload_file.file.seek(0)
        except Exception:
            pass
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)

        # Process the newly uploaded PDF without arbitrary page truncations
        res = academic_pipeline.process_pdf(
            dest_path,
            max_pages=None,
            engine=use_engine,
            full_potential=effective_full_potential,
            extract_tables=effective_extract_tables,
        )
        ingested_reports.append(res)

        # Record into ready documents manifest
        size_mb = round(dest_path.stat().st_size / (1024 * 1024), 2)
        record_ready_document(
            filename=dest_path.name,
            pages=res.get("pages_processed", 1),
            size_mb=size_mb,
            chunks_count=res.get("chunks_extracted", 0)
        )

    # Reload graph data
    if rag_engine:
        rag_engine._load_processed_data()

    total_nodes = rag_engine.graph_engine.graph.number_of_nodes() if (rag_engine and hasattr(rag_engine, "graph_engine")) else 0
    total_edges = rag_engine.graph_engine.graph.number_of_edges() if (rag_engine and hasattr(rag_engine, "graph_engine")) else 0

    return {
        "status": "success",
        "uploaded_count": len(ingested_reports),
        "reports": ingested_reports,
        "total_nodes": total_nodes,
        "total_edges": total_edges,
    }


@router.post("/api/vault/load-defaults")
async def load_vault_defaults(rag_engine: Any = Depends(get_rag_engine)):
    """Ingests or loads all available academic reports from DOCUMENTS_DIR directory."""
    return execute_load_vault_defaults(rag_engine)


def _resolve_document_file(doc_identifier: str) -> Optional[Path]:
    """Resolves raw filename, URI-encoded name, stem, or document ID to a physical PDF file path."""
    import urllib.parse

    clean_raw = urllib.parse.unquote(doc_identifier).strip()
    clean = Path(clean_raw).name  # Neutralizes ../ and leading slashes
    if not clean or clean in (".", ".."):
        return None

    # 1. Direct path check in DOCUMENTS_DIR / DOWNLOAD_DIR
    for p in (DOCUMENTS_DIR / clean, DOWNLOAD_DIR / clean):
        if p.exists() and p.is_file():
            return p

    # 2. Check manifest for matching id, filename, or stem
    if MANIFEST_FILE.exists():
        try:
            m_data = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
            for doc in m_data.get("ready_documents", []):
                d_id = str(doc.get("id") or "")
                d_fn = str(doc.get("filename") or "")
                if clean in (d_id, d_fn, Path(d_fn).stem):
                    cand = DOCUMENTS_DIR / Path(d_fn).name
                    if cand.exists() and cand.is_file():
                        return cand
        except Exception:
            pass

    # 3. Case-insensitive search across candidate directories
    for parent in (DOCUMENTS_DIR, DOWNLOAD_DIR):
        if parent.exists():
            for f in parent.glob("*.pdf"):
                if f.name.lower() == clean.lower() or f.stem.lower() == clean.lower() or f.name.lower() == f"{clean.lower()}.pdf":
                    return f

    return None


@router.get("/api/pdf/{filename}")
@router.head("/api/pdf/{filename}")
@router.get("/api/documents/{filename}/file")
@router.head("/api/documents/{filename}/file")
async def get_pdf_file(filename: str):
    """
    Serves physical PDF for deep-linked in-browser viewing with #page=N.
    Enforces HTTP 206 Partial Content byte ranges, inline display, and long-term caching.
    """
    import os
    import urllib.parse

    clean_name = urllib.parse.unquote(filename).strip()

    # Search candidates: DOWNLOAD_DIR, DOCUMENTS_DIR, user Downloads
    candidates = [
        DOWNLOAD_DIR / clean_name,
        DOCUMENTS_DIR / clean_name,
        Path(os.path.expanduser(f"~/Downloads/{clean_name}")),
    ]

    target_path = None
    for cand in candidates:
        if cand.exists() and cand.is_file():
            target_path = cand
            break

    if not target_path:
        target_path = _resolve_document_file(clean_name)

    if not target_path or not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")

    return FileResponse(
        path=str(target_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{target_path.name}"',
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=86400",
        }
    )


@router.get("/api/pdf/{filename}/pages/{page_number}")
@router.get("/api/pdf/{filename}/pages/{page_number}/pdf")
@router.get("/api/pdf/{filename}/pages/{page_number}/image")
@router.get("/api/pdf/{filename}/pages/{page_number}/png")
@router.get("/api/pdf/{filename}/pages/{page_number}/view")
@router.get("/api/documents/{filename}/pages/{page_number}")
@router.get("/api/documents/{filename}/pages/{page_number}/pdf")
@router.get("/api/documents/{filename}/pages/{page_number}/image")
@router.get("/api/documents/{filename}/pages/{page_number}/png")
@router.get("/api/documents/{filename}/pages/{page_number}/view")
@router.get("/api/documents/{filename}/page/{page_number}")
async def get_pdf_single_page(
    filename: str,
    page_number: int,
    request: Request,
    format: Optional[str] = None,
):
    """
    Sub-30ms Single-Page Document Extraction Endpoint.
    Extracts ONLY page_number from the target PDF using PyMuPDF.
    Zero full-PDF downloads: returns a lightweight 1-page PDF (or high-res PNG).
    Supported formats: 'pdf' (default), 'image' / 'png', 'view' (HTML preview).
    """
    import urllib.parse
    import pymupdf

    target_path = _resolve_document_file(filename)
    if not target_path or not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")

    if page_number < 1:
        raise HTTPException(status_code=400, detail="Page number must be >= 1.")

    try:
        doc = pymupdf.open(str(target_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open PDF document: {e}")

    try:
        total_pages = doc.page_count
        if page_number > total_pages:
            raise HTTPException(
                status_code=404,
                detail=f"Page {page_number} exceeds document page count ({total_pages}).",
            )

        p_idx = page_number - 1
        path_lower = request.url.path.lower()
        if path_lower.endswith("/image") or path_lower.endswith("/png"):
            fmt = "image"
        elif path_lower.endswith("/view"):
            fmt = "view"
        elif path_lower.endswith("/pdf"):
            fmt = "pdf"
        else:
            fmt = (format or "pdf").lower().strip()

        if fmt in ("image", "png", "img"):
            page = doc.load_page(p_idx)
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            return Response(
                content=img_bytes,
                media_type="image/png",
                headers={
                    "Content-Disposition": f'inline; filename="{target_path.stem}_p{page_number}.png"',
                    "Cache-Control": "public, max-age=604800",
                },
            )
        elif fmt == "view":
            encoded_name = urllib.parse.quote(target_path.name)
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{target_path.name} — Page {page_number}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      margin: 0;
      background: #090d16;
      color: #f1f5f9;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
    }}
    header {{
      width: 100%;
      background: rgba(15, 23, 42, 0.95);
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      backdrop-filter: blur(8px);
      box-sizing: border-box;
      z-index: 10;
    }}
    .title-box {{
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }}
    .badge {{
      background: #3b82f6;
      color: white;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      white-space: nowrap;
    }}
    .doc-name {{
      font-weight: 600;
      font-size: 14px;
      color: #e2e8f0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 450px;
    }}
    .btn-group {{
      display: flex;
      gap: 10px;
      flex-shrink: 0;
    }}
    a.btn {{
      background: rgba(255, 255, 255, 0.1);
      color: #f8fafc;
      padding: 6px 14px;
      border-radius: 6px;
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      transition: background 0.15s;
    }}
    a.btn:hover {{
      background: rgba(255, 255, 255, 0.2);
    }}
    a.btn-primary {{
      background: #2563eb;
    }}
    a.btn-primary:hover {{
      background: #1d4ed8;
    }}
    .page-container {{
      padding: 24px;
      display: flex;
      justify-content: center;
      width: 100%;
      box-sizing: border-box;
    }}
    .page-img {{
      max-width: 960px;
      width: 100%;
      height: auto;
      border-radius: 8px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
      background: white;
    }}
  </style>
</head>
<body>
  <header>
    <div class="title-box">
      <span class="badge">Page {page_number} / {total_pages}</span>
      <span class="doc-name">{target_path.name}</span>
    </div>
    <div class="btn-group">
      <a class="btn btn-primary" href="/api/pdf/{encoded_name}/pages/{page_number}/pdf" target="_blank">Open Isolated PDF</a>
      <a class="btn" href="/api/pdf/{encoded_name}#page={page_number}" target="_blank">Full Report ({total_pages}p)</a>
    </div>
  </header>
  <main class="page-container">
    <img class="page-img" src="/api/pdf/{encoded_name}/pages/{page_number}/image" alt="Page {page_number} of {target_path.name}">
  </main>
</body>
</html>"""
            return HTMLResponse(content=html_content)
        else:
            # Default: Single-Page PDF stream
            with pymupdf.open() as single_doc:
                single_doc.insert_pdf(doc, from_page=p_idx, to_page=p_idx)
                pdf_bytes = single_doc.tobytes()
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{target_path.stem}_page_{page_number}.pdf"',
                    "Cache-Control": "public, max-age=604800",
                },
            )
    finally:
        doc.close()


@router.get("/api/documents/{document_id}/status")
async def get_document_ingestion_status(
    document_id: str,
    document_service: Any = Depends(get_document_service),
):
    """
    Tier 1 Critical: Real-time Document Ingestion Pipeline Status Endpoint.
    Pollable every 2-3s by frontend during document upload and indexing.
    Returns current pipeline phase, percent (0-100), and stage message.
    """
    status_info = document_service.get_document_status(document_id)
    if status_info:
        return status_info
    raise HTTPException(status_code=404, detail=f"Document status for '{document_id}' not found")


@router.get("/api/documents/{document_id}/events")
async def get_document_ingestion_events(
    document_id: str,
    document_service: Any = Depends(get_document_service),
):
    """
    Server-Sent Events (SSE) Stream for real-time document upload/ingestion progress.
    Stream terminates automatically when phase=='ready' or status=='failed'.
    """
    async def event_generator():
        last_percent = -1
        while True:
            st = document_service.get_document_status(document_id)
            if st:
                curr_pct = st.get("percent", 0)
                if curr_pct != last_percent:
                    last_percent = curr_pct
                    yield f"data: {json.dumps(st)}\n\n"
                if st.get("phase") == "ready" or st.get("status") in ("ready", "failed"):
                    yield "data: [DONE]\n\n"
                    break
            await asyncio.sleep(0.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@router.get("/api/documents")
@router.get("/api/documents/manifest")
async def get_documents(document_service: Any = Depends(get_document_service)):
    """List only documents whose chunking and embedding are confirmed and ready for Q&A."""
    return await asyncio.to_thread(document_service.list_library_documents)


@router.delete("/api/documents/{document_id}")
async def delete_document_by_id(
    document_id: str,
    document_service: Any = Depends(get_document_service),
):
    """Delete a document by document_id or filename matching shared specification."""
    success, msg_or_fn, err_code = document_service.delete_document(document_id)
    if not success:
        if err_code == "PROTECTED":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg_or_fn)
        raise HTTPException(status_code=500, detail=msg_or_fn)

    updated_docs = (await asyncio.to_thread(document_service.list_library_documents)).get("documents", [])
    logger.info(f"[DELETE] Successfully purged user document '{msg_or_fn}' from Library")
    return {
        "status": "success",
        "filename": msg_or_fn,
        "documents": updated_docs,
        "total_count": len(updated_docs)
    }


@router.post("/api/documents/delete")
async def delete_document(
    request: Request,
    document_service: Any = Depends(get_document_service),
):
    """Completely purge a document, its chunks, vectors, Neo4j nodes, and manifest."""
    try:
        body = await request.json()
        filename = body.get("filename", "").strip() or body.get("document_id", "").strip()
        if not filename:
            return JSONResponse(status_code=400, content={"status": "error", "error": "Filename is required"})

        success, msg_or_fn, err_code = document_service.delete_document(filename)
        if not success:
            if err_code == "PROTECTED":
                return JSONResponse(status_code=403, content={"status": "error", "error": msg_or_fn})
            return JSONResponse(status_code=500, content={"status": "error", "error": msg_or_fn})

        updated_docs = (await asyncio.to_thread(document_service.list_library_documents)).get("documents", [])
        logger.info(f"[DELETE] Successfully purged user document '{msg_or_fn}' from Library")
        return {
            "status": "success",
            "filename": msg_or_fn,
            "documents": updated_docs,
            "total_count": len(updated_docs)
        }
    except Exception as e:
        logger.error(f"[DELETE] Failed to delete document: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "error": "Document could not be deleted. Please try again."})



@router.post("/api/documents/delete_all")
@router.post("/api/vault/reset")
async def delete_all_documents(rag_engine: Any = Depends(get_rag_engine)):
    """Completely purge all documents, vectors, graph nodes, chunks, and reset vault."""
    try:
        purge_res = rag_engine.purge_all_documents() if rag_engine else {}
        return {
            "status": "success",
            "details": purge_res,
            "documents": [],
            "total_count": 0
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/api/ingest-download-folder")
async def ingest_download_folder(
    postgres_manager: Any = Depends(get_postgres_manager),
    rag_engine: Any = Depends(get_rag_engine),
):
    """Batch-ingest all PDF reports from Download/ directory and record ready manifest and PostgreSQL metadata."""
    return execute_ingest_download_folder(postgres_manager, rag_engine)

@router.get("/api/documents/scan")
@router.post("/api/documents/scan")
async def scan_documents_folder(document_service: Any = Depends(get_document_service)):
    """
    On-demand scan of data/documents/ directory.
    Automatically registers any processed PDFs into the library and returns updated documents list.
    """
    docs_result = document_service.list_library_documents()
    return {
        "status": "success",
        "message": "Scanned document directory and reconciled library artifacts.",
        "documents": docs_result.get("documents", []),
        "total_count": docs_result.get("total_count", 0),
    }


@router.get("/api/documents/{doc_identifier}/extracted-markdown")
@router.get("/api/library/{doc_identifier}/markdown")
async def get_extracted_markdown(
    doc_identifier: str,
    format: Optional[str] = None,
    request: Request = None,
):
    """
    Exposes full prAISED / extracted markdown for a document (data/library/{stem}_extracted.md).
    Supports raw markdown streaming or structured JSON output.
    """
    import urllib.parse
    clean_id = urllib.parse.unquote(doc_identifier).strip()
    clean_stem = Path(clean_id).stem.replace("doc_", "")
    
    from src.core.config import DATA_DIR
    lib_dir = DATA_DIR / "library"
    
    target_md = None
    # 1. Multi-candidate stem match (supporting alphanumeric and hyphen/space sanitization)
    for cand_name in [
        f"{clean_stem}_extracted.md",
        f"{re.sub(r'[^a-zA-Z0-9]', '_', clean_stem)}_extracted.md",
        f"{re.sub(r'[^a-zA-Z0-9_-]', '_', clean_stem)}_extracted.md",
        f"{re.sub(r'[ -]', '_', clean_stem)}_extracted.md",
        f"{clean_id}_extracted.md",
        f"{Path(clean_id).name}_extracted.md",
    ]:
        for d in [lib_dir, lib_dir.parent.parent / "backend" / "data" / "library"]:
            cand = d / cand_name
            if cand.exists() and cand.is_file():
                target_md = cand
                break
        if target_md:
            break
            
    # 2. Case-insensitive search
    if not target_md and lib_dir.exists():
        for f in lib_dir.glob("*_extracted.md"):
            if f.stem.lower() == f"{clean_stem.lower()}_extracted" or f.stem.lower().startswith(clean_stem.lower()):
                target_md = f
                break

    if not target_md or not target_md.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Extracted markdown for document '{doc_identifier}' not found in library.",
        )

    content = target_md.read_text(encoding="utf-8")
    
    accept_header = request.headers.get("accept", "").lower() if request else ""
    if format == "json" or "application/json" in accept_header:
        return {
            "status": "success",
            "document_id": doc_identifier,
            "filename": f"{target_md.stem.replace('_extracted', '')}.pdf",
            "artifact_type": "extracted_markdown",
            "path": str(target_md),
            "size_bytes": len(content.encode("utf-8")),
            "content": content,
        }

    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="{target_md.name}"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get("/api/documents/{doc_identifier}/okf-catalog")
@router.get("/api/catalogs/{doc_identifier}")
async def get_okf_catalog(
    doc_identifier: str,
    format: Optional[str] = None,
    request: Request = None,
):
    """
    Exposes OKF (Open Knowledge Formulation) catalog markdown for a document (data/catalogs/{stem}.okf.md).
    Supports raw markdown streaming or structured JSON output.
    """
    import urllib.parse
    clean_id = urllib.parse.unquote(doc_identifier).strip()
    clean_stem = Path(clean_id).stem.replace("doc_", "")
    
    from src.core.config import DATA_DIR
    cat_dir = DATA_DIR / "catalogs"
    
    target_okf = None
    for cand_name in [
        f"{clean_stem}.okf.md",
        f"{re.sub(r'[^a-zA-Z0-9]', '_', clean_stem)}.okf.md",
        f"{re.sub(r'[^a-zA-Z0-9_-]', '_', clean_stem)}.okf.md",
        f"{re.sub(r'[ -]', '_', clean_stem)}.okf.md",
        f"{clean_id}.okf.md",
    ]:
        for d in [cat_dir, cat_dir.parent.parent / "backend" / "data" / "catalogs"]:
            cand = d / cand_name
            if cand.exists() and cand.is_file():
                target_okf = cand
                break
        if target_okf:
            break

    if not target_okf and cat_dir.exists():
        for f in cat_dir.glob("*.okf.md"):
            if f.name.lower().startswith(clean_stem.lower()):
                target_okf = f
                break

    if not target_okf or not target_okf.exists():
        raise HTTPException(
            status_code=404,
            detail=f"OKF catalog for document '{doc_identifier}' not found in catalogs.",
        )

    content = target_okf.read_text(encoding="utf-8")
    
    accept_header = request.headers.get("accept", "").lower() if request else ""
    if format == "json" or "application/json" in accept_header:
        return {
            "status": "success",
            "document_id": doc_identifier,
            "filename": f"{target_okf.name.replace('.okf.md', '')}.pdf",
            "artifact_type": "okf_catalog",
            "path": str(target_okf),
            "size_bytes": len(content.encode("utf-8")),
            "content": content,
        }

    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="{target_okf.name}"',
            "Cache-Control": "public, max-age=3600",
        },
    )
