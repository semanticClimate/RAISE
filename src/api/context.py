"""
RAISE API Context & State Utilities
Manifest tracking, active drawer parsing, client IP resolution,
telemetry tracking, and real-time cancellation tokens.
"""

from __future__ import annotations

import json
import logging
import re
import socket
import time
import urllib.parse
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from fastapi import Request

from src.core.config import settings

logger = logging.getLogger("raise.api.context")

# Document Directories and Manifest
DOCUMENTS_DIR = settings.documents_dir
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR = DOCUMENTS_DIR  # Compatibility alias
MANIFEST_FILE = settings.processed_dir / "ingested_manifest.json"
LIBRARY_DIR = getattr(settings, "library_dir", settings.data_dir / "library")
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
CATALOGS_DIR = getattr(settings, "catalogs_dir", settings.data_dir / "catalogs")
CATALOGS_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR = getattr(settings, "chunks_dir", settings.processed_dir / "chunks")
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_DIR = getattr(settings, "graph_dir", settings.processed_dir / "graph_triples")
GRAPH_DIR.mkdir(parents=True, exist_ok=True)

TEST_ARTIFACT_NAMES = {
    "dummy.pdf",
    "test_sample.pdf",
    "test_docling.pdf",
    "real_test.pdf",
    "test.pdf",
}


def is_test_document(filename: str) -> bool:
    """Filter out synthetic test and stub documents from user library views."""
    fn_lower = filename.lower()
    return fn_lower in TEST_ARTIFACT_NAMES or fn_lower.startswith("test_")


_PDF_METADATA_CACHE: Dict[str, Tuple[float, int, float]] = {}  # str(path) -> (mtime, pages, size_mb)


def get_pdf_metadata(pdf_path: Path, cached_pages: int = 1, cached_size_mb: float = 1.0) -> Tuple[int, float]:
    """Retrieves PDF page count and size in MB, caching results by file modification time (mtime)."""
    if not pdf_path.exists():
        return cached_pages, cached_size_mb
    try:
        st = pdf_path.stat()
        mtime = st.st_mtime
        p_str = str(pdf_path)
        if p_str in _PDF_METADATA_CACHE:
            c_mtime, c_pages, c_size = _PDF_METADATA_CACHE[p_str]
            if c_mtime == mtime:
                return c_pages, c_size
        size_mb = round(st.st_size / (1024 * 1024), 2)
        pages = cached_pages
        try:
            import pymupdf
            with pymupdf.open(str(pdf_path)) as pdoc:
                pages = max(1, pdoc.page_count)
        except Exception:
            pages = max(1, cached_pages)
        _PDF_METADATA_CACHE[p_str] = (mtime, pages, size_mb)
        return pages, size_mb
    except Exception:
        return cached_pages, cached_size_mb


def auto_scan_and_reconcile_documents():
    """
    Auto-scans DOCUMENTS_DIR for PDFs and reconciles with ingested chunks/catalogs.
    If a PDF has processed chunks in CHUNKS_DIR or extracted text in LIBRARY_DIR,
    it automatically registers it into ingested_manifest.json if missing.
    """
    if not DOCUMENTS_DIR.exists():
        return
    ready_list = get_ready_documents_list()
    registered_files = {d.get("filename") for d in ready_list if d.get("filename")}

    for pdf_file in DOCUMENTS_DIR.glob("*.pdf"):
        if is_test_document(pdf_file.name):
            continue
        stem = pdf_file.stem
        chunk_file = CHUNKS_DIR / f"{stem}_chunks.json"
        extracted_file = LIBRARY_DIR / f"{stem}_extracted.md"

        real_chunks_count = 0
        if chunk_file.exists():
            try:
                c_data = json.loads(chunk_file.read_text(encoding="utf-8"))
                if isinstance(c_data, list):
                    real_chunks_count = len(c_data)
            except Exception:
                pass

        real_pages, size_mb = get_pdf_metadata(pdf_file)

        if pdf_file.name not in registered_files and (real_chunks_count > 0 or extracted_file.exists()):
            record_ready_document(
                filename=pdf_file.name,
                pages=real_pages,
                size_mb=size_mb,
                chunks_count=real_chunks_count,
                is_protected=False,
                uploaded_by="user",
            )

# Active Abort & Cancellation Token Registry (bounded in-memory)
ACTIVE_ABORTS: Set[str] = set()
ACTIVE_REQUEST_ABORTS: Set[str] = set()
SESSION_ABORT_TIMESTAMPS: Dict[str, float] = {}

# System Telemetry & Operational Metrics Tracker
SYSTEM_START_TIME = time.time()
SYSTEM_METRICS: Dict[str, Any] = {
    "total_queries": 0,
    "successful_queries": 0,
    "failed_queries": 0,
    "latencies": deque(maxlen=500),
}


def record_query_metric(latency: float, success: bool = True):
    SYSTEM_METRICS["total_queries"] += 1
    if success:
        SYSTEM_METRICS["successful_queries"] += 1
    else:
        SYSTEM_METRICS["failed_queries"] += 1
    SYSTEM_METRICS["latencies"].append(round(latency, 3))


def is_aborted(
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    started_at: Optional[float] = None,
    redis_client: Any = None,
) -> bool:
    """
    Checks if an in-flight query has been cancelled.
    Supports request-level specificity and timestamp-aware session aborts.
    A new query with started_at > abort_timestamp is NEVER treated as aborted.
    """
    # 1. Direct request ID abort check (request-level specificity)
    if request_id and (request_id in ACTIVE_REQUEST_ABORTS or request_id in ACTIVE_ABORTS):
        return True

    # 2. Session-level abort check with timestamp awareness
    if session_id:
        abort_ts = SESSION_ABORT_TIMESTAMPS.get(session_id)
        if abort_ts is not None:
            if started_at is not None:
                # Query was only aborted if it started BEFORE or AT the abort timestamp
                if started_at <= abort_ts:
                    return True
            else:
                return True

    # 3. Redis cross-process checks
    if redis_client:
        try:
            if request_id:
                if redis_client.get(f"abort:req:{request_id}") or redis_client.get(f"abort:{request_id}"):
                    return True
            if session_id:
                raw_session = redis_client.get(f"abort:session:{session_id}") or redis_client.get(f"abort:{session_id}")
                if raw_session:
                    if started_at is not None:
                        try:
                            s_ts = float(raw_session.decode("utf-8") if isinstance(raw_session, bytes) else raw_session)
                            if started_at <= s_ts:
                                return True
                        except ValueError:
                            return True
                    else:
                        return True
        except Exception:
            pass

    return False


def record_abort(session_id: Optional[str] = None, request_id: Optional[str] = None, redis_mgr: Any = None):
    """
    Records an abort signal for a specific in-flight query or current session.
    """
    # Bound memory set sizes to prevent unbounded memory growth
    if len(ACTIVE_ABORTS) > 1000:
        ACTIVE_ABORTS.clear()
    if len(ACTIVE_REQUEST_ABORTS) > 1000:
        ACTIVE_REQUEST_ABORTS.clear()
    if len(SESSION_ABORT_TIMESTAMPS) > 1000:
        SESSION_ABORT_TIMESTAMPS.clear()

    now = time.time()
    if request_id:
        ACTIVE_ABORTS.add(request_id)
        ACTIVE_REQUEST_ABORTS.add(request_id)
        if redis_mgr and getattr(redis_mgr, "is_connected", False) and getattr(redis_mgr, "_client", None):
            try:
                redis_mgr._client.setex(f"abort:req:{request_id}", 60, "1")
            except Exception:
                pass

    if session_id:
        ACTIVE_ABORTS.add(session_id)
        SESSION_ABORT_TIMESTAMPS[session_id] = now
        if redis_mgr and getattr(redis_mgr, "is_connected", False) and getattr(redis_mgr, "_client", None):
            try:
                redis_mgr._client.setex(f"abort:session:{session_id}", 60, str(now))
            except Exception:
                pass

    if redis_mgr:
        try:
            redis_mgr.publish_abort(session_id, request_id)
        except Exception:
            pass


def clear_abort(session_id: Optional[str] = None, request_id: Optional[str] = None, redis_mgr: Any = None):
    """
    Clears active abort flags for a session or request when a new query begins.
    Ensures that new incoming queries are never aborted by stale cancellation tokens.
    """
    if session_id:
        ACTIVE_ABORTS.discard(session_id)
        SESSION_ABORT_TIMESTAMPS.pop(session_id, None)
        if redis_mgr and getattr(redis_mgr, "is_connected", False) and getattr(redis_mgr, "_client", None):
            try:
                redis_mgr._client.delete(f"abort:session:{session_id}")
                redis_mgr._client.delete(f"abort:{session_id}")
            except Exception:
                pass

    if request_id:
        ACTIVE_ABORTS.discard(request_id)
        ACTIVE_REQUEST_ABORTS.discard(request_id)
        if redis_mgr and getattr(redis_mgr, "is_connected", False) and getattr(redis_mgr, "_client", None):
            try:
                redis_mgr._client.delete(f"abort:req:{request_id}")
                redis_mgr._client.delete(f"abort:{request_id}")
            except Exception:
                pass


def get_lan_ip() -> str:
    """Discover host machine LAN IPv4 address for remote cross-device communication."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def get_authentic_client_ip(request: Request) -> str:
    """
    Extract authentic remote client IP across Cloudflare tunnels, reverse proxies, and Docker bridges.
    Safely resolves X-Forwarded-For and X-Real-IP headers to prevent proxy rate-limiting bypasses.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        for ip in ips:
            if ip not in ("127.0.0.1", "localhost", "::1"):
                return ip
        if ips:
            return ips[0]
    real_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Real-IP")
    if real_ip and real_ip.strip():
        return real_ip.strip()
    return request.client.host if (request and request.client) else "127.0.0.1"


def get_ready_documents_list() -> List[Dict[str, Any]]:
    """Retrieve list of actively confirmed ready documents from authoritative manifest.
    Does NOT auto-scan or auto-register external PDFs without explicit user upload."""
    if MANIFEST_FILE.exists():
        try:
            data = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
            return data.get("ready_documents", [])
        except Exception:
            return []
    return []


def record_ready_document(
    filename: str,
    pages: int,
    size_mb: float,
    chunks_count: int,
    is_protected: bool = False,
    uploaded_by: str = "user"
):
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"ready_documents": [], "deleted_documents": []}
    if MANIFEST_FILE.exists():
        try:
            manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            manifest = {"ready_documents": [], "deleted_documents": []}

    deleted = [f for f in manifest.get("deleted_documents", []) if f != filename]
    manifest["deleted_documents"] = deleted

    docs = manifest.get("ready_documents", [])
    updated = False
    for d in docs:
        if d.get("filename") == filename:
            d["pages"] = pages
            d["size_mb"] = size_mb
            d["chunks_count"] = chunks_count
            d["status"] = "ready"
            d["is_protected"] = is_protected if is_protected is not None else d.get("is_protected", False)
            d["uploaded_by"] = uploaded_by or d.get("uploaded_by", "user")
            updated = True
            break
    if not updated:
        docs.append({
            "filename": filename,
            "pages": pages,
            "size_mb": size_mb,
            "chunks_count": chunks_count,
            "status": "ready",
            "is_protected": is_protected,
            "uploaded_by": uploaded_by
        })
    manifest["ready_documents"] = docs
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def remove_ready_document(filename: str) -> bool:
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"ready_documents": [], "deleted_documents": []}
    if MANIFEST_FILE.exists():
        try:
            manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            manifest = {"ready_documents": [], "deleted_documents": []}

    deleted = manifest.get("deleted_documents", [])
    if filename not in deleted:
        deleted.append(filename)

    docs = manifest.get("ready_documents", [])
    new_docs = [d for d in docs if d.get("filename") != filename]

    manifest["ready_documents"] = new_docs
    manifest["deleted_documents"] = deleted
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return True


def purge_all_ready_documents() -> bool:
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"ready_documents": [], "deleted_documents": []}
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return True


clear_ready_documents = purge_all_ready_documents


def _parse_drawer_active_docs(raw_val: Any) -> Optional[List[str]]:
    """
    Parse, normalize, and unquote active drawer documents from:
    1. Repeated query params (?active_docs=doc1.pdf&active_docs=doc2.pdf)
    2. Comma-separated query strings (?active_docs=doc1.pdf,doc2.pdf)
    3. JSON array strings (?active_docs=["doc1.pdf", "doc2.pdf"])
    4. URL-encoded spaces and special characters via urllib.parse.unquote_plus
       (e.g., Annual+Report+2024-25+final+upload.pdf or Annual%20Report%202024.pdf)
    """
    if raw_val is None:
        return None

    raw_list = raw_val if isinstance(raw_val, (list, tuple, set)) else [raw_val]
    items_to_process: List[str] = []

    for entry in raw_list:
        if entry is None:
            continue
        raw_str = str(entry).strip()
        if not raw_str or raw_str.lower() in ("[]", "null", "none"):
            continue
        if raw_str.startswith("[") and raw_str.endswith("]"):
            try:
                parsed = json.loads(raw_str)
                if isinstance(parsed, list):
                    for p in parsed:
                        if p is not None and str(p).strip() and str(p).strip().lower() not in ("[]", "null", "none"):
                            items_to_process.append(str(p).strip())
                    continue
            except Exception:
                pass
        items_to_process.append(raw_str)

    cleaned_docs: List[str] = []
    for item in items_to_process:
        tokens = item.split(",") if "," in item else [item]
        for tok in tokens:
            unquoted = urllib.parse.unquote_plus(tok.strip()).strip("\"'")
            if unquoted and unquoted.lower() not in ("[]", "null", "none") and unquoted not in cleaned_docs:
                cleaned_docs.append(unquoted)

    return cleaned_docs


GREETING_TYPO_REGEX = re.compile(
    r"^(hi+|hello+|helo+|hekko+|hey+|heyy+|heyo|howdy|hola|yo+|sup|hlo|hlw|greetings)(?:\s+there|\s+raise|\s+bot|\s*!|\s*\.|\s*\?)*$",
    re.IGNORECASE
)


def is_conversational_or_memory_query(query: str) -> bool:
    """
    Detects if a query is a greeting, introduction, memory recall, or general assistant dialogue.
    These queries bypass the document drawer check completely.
    """
    q_clean = query.strip()
    if GREETING_TYPO_REGEX.match(q_clean):
        return True

    q_lower = q_clean.lower()
    patterns = [
        r"^(he|hi+|hello+|helo+|hekko+|hey+|heyy+|heyo|greetings|howdy|hola|yo+|sup|hlo|hlw)\b",
        r"^good\s+(morning|afternoon|evening|day)\b",
        r"\b(?:my\s+name\s+is|call\s+me)\b",
        r"\b(?:do\s+you\s+know|what\s+is|what's)\s+my\s+name\b",
        r"\bwho\s+am\s+i\b",
        r"\bdo\s+you\s+remember\b",
        r"\b(?:what\s+is|what's)\s+your\s+name\b",
        r"\bwho\s+are\s+you\b",
        r"\bwhat\s+can\s+you\s+do\b",
        r"\bhow\s+are\s+you\b",
        r"\b(?:thank\s+you|thanks|nice\s+to\s+meet\s+you)\b",
        r"\b(?:what\s+did\s+i\s+(?:just\s+)?(?:say|ask))\b",
        r"^(test|hello\s+test|ping)\b",
    ]
    for pat in patterns:
        if re.search(pat, q_clean, re.IGNORECASE):
            return True
    if len(q_clean.split()) <= 6:
        if any(w in q_lower for w in ["who are you", "who r u", "whats your name", "what is your name", "my name", "your name"]):
            return True
    return False


def _find_file_for_stem(directory: Path, stem: str, suffix: str) -> Optional[Path]:
    """Helper to locate document derivative files handling diverse filename sanitization formats."""
    if not directory.exists():
        return None
    candidates = [
        directory / f"{stem}{suffix}",
        directory / f"{re.sub(r'[^a-zA-Z0-9]', '_', stem)}{suffix}",
        directory / f"{re.sub(r'[^a-zA-Z0-9_-]', '_', stem)}{suffix}",
        directory / f"{re.sub(r'[ -]', '_', stem)}{suffix}",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    clean_prefix = re.sub(r'[^a-zA-Z0-9]', '_', stem).split('_')[0].lower()
    if len(clean_prefix) >= 3:
        for f in directory.iterdir():
            if f.is_file() and f.name.endswith(suffix) and f.name.lower().startswith(clean_prefix):
                return f
    return None


def get_library_documents(postgres_mgr: Any = None, auto_scan: bool = True) -> Dict[str, Any]:
    """
    Consolidated reader for all confirmed ready documents across manifest and PostgreSQL.
    Auto-reconciles real chunk counts from CHUNKS_DIR, page counts from PDFs, and checks
    availability of extracted markdown in LIBRARY_DIR and catalogs in CATALOGS_DIR.
    """
    if auto_scan:
        try:
            auto_scan_and_reconcile_documents()
        except Exception as e:
            logger.debug(f"[Library] Auto-scan notice: {e}")

    ready_docs = get_ready_documents_list()
    pg_docs = postgres_mgr.list_documents() if postgres_mgr and hasattr(postgres_mgr, "list_documents") else []

    result_docs = []
    seen = set()

    for r in ready_docs:
        fn = r.get("filename")
        if not fn or fn in seen or is_test_document(fn):
            continue
        seen.add(fn)
        stem = Path(fn).stem
        clean_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem)[:40]
        is_prot = bool(r.get("is_protected", False))
        can_del = not is_prot
        owner_val = r.get("uploaded_by", "system" if is_prot else "user")

        # Reconcile true chunk count from filesystem
        chunks_cnt = r.get("chunks_count", 0)
        chunk_file = _find_file_for_stem(CHUNKS_DIR, stem, "_chunks.json")
        if chunk_file and chunk_file.exists():
            try:
                c_data = json.loads(chunk_file.read_text(encoding="utf-8"))
                if isinstance(c_data, list) and len(c_data) > 0:
                    chunks_cnt = len(c_data)
            except Exception:
                pass

        # Reconcile true page count & size from physical PDF
        pages_cnt = r.get("pages", 1)
        pdf_path = DOCUMENTS_DIR / fn
        if not pdf_path.exists():
            for c in [DOCUMENTS_DIR / fn, settings.data_dir / "documents" / fn]:
                if c.exists():
                    pdf_path = c
                    break
        size_mb = r.get("size_mb", 1.0)
        if pdf_path.exists():
            pages_cnt, size_mb = get_pdf_metadata(pdf_path, cached_pages=pages_cnt, cached_size_mb=size_mb)

        # Check extracted markdown
        extracted_md_file = _find_file_for_stem(LIBRARY_DIR, stem, "_extracted.md")
        has_extracted_md = bool(extracted_md_file and extracted_md_file.exists())
        extracted_md_url = f"/api/documents/{fn}/extracted-markdown" if has_extracted_md else ""
        extracted_md_size_bytes = extracted_md_file.stat().st_size if has_extracted_md else 0

        # Check OKF catalog
        okf_catalog_file = _find_file_for_stem(CATALOGS_DIR, stem, ".okf.md")
        has_okf_catalog = bool(okf_catalog_file and okf_catalog_file.exists())
        okf_catalog_url = f"/api/documents/{fn}/okf-catalog" if has_okf_catalog else ""
        okf_catalog_size_bytes = okf_catalog_file.stat().st_size if has_okf_catalog else 0

        # Check graph entities/triples
        triples_file = _find_file_for_stem(GRAPH_DIR, stem, "_triples.json")
        graph_triples_cnt = 0
        if triples_file and triples_file.exists():
            try:
                t_data = json.loads(triples_file.read_text(encoding="utf-8"))
                if isinstance(t_data, list):
                    graph_triples_cnt = len(t_data)
            except Exception:
                pass

        result_docs.append({
            "id": f"doc_{clean_stem}",
            "doc_id": f"doc_{clean_stem}",
            "filename": fn,
            "name": fn,
            "title": stem.replace("_", " "),
            "pages": pages_cnt,
            "size_mb": size_mb,
            "chunks_count": chunks_cnt,
            "chunks": chunks_cnt,
            "status": "ready",
            "phase": "ready",
            "is_protected": is_prot,
            "can_delete": can_del,
            "deletable": can_del,
            "owner": owner_val,
            "uploaded_at": r.get("processed_at") or "2026-09-05T00:00:00",
            "library": "default",
            "has_extracted_md": has_extracted_md,
            "extracted_md_url": extracted_md_url or "",
            "extracted_md_size_bytes": extracted_md_size_bytes,
            "has_okf_catalog": has_okf_catalog,
            "okf_catalog_url": okf_catalog_url or "",
            "okf_catalog_size_bytes": okf_catalog_size_bytes,
            "graph_triples_count": graph_triples_cnt,
        })

    for d in pg_docs:
        fn = d.get("filename")
        if not fn or fn in seen or is_test_document(fn):
            continue
        seen.add(fn)
        stem = Path(fn).stem
        clean_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem)[:40]
        is_prot = bool(d.get("is_protected", False))
        can_del = bool(d.get("can_delete", not is_prot))
        owner_val = d.get("owner", "user")

        # Check extracted markdown & okf
        extracted_md_file = _find_file_for_stem(LIBRARY_DIR, stem, "_extracted.md")
        has_extracted_md = bool(extracted_md_file and extracted_md_file.exists())
        extracted_md_url = f"/api/documents/{fn}/extracted-markdown" if has_extracted_md else ""
        extracted_md_size_bytes = extracted_md_file.stat().st_size if has_extracted_md else 0

        okf_catalog_file = _find_file_for_stem(CATALOGS_DIR, stem, ".okf.md")
        has_okf_catalog = bool(okf_catalog_file and okf_catalog_file.exists())
        okf_catalog_url = f"/api/documents/{fn}/okf-catalog" if has_okf_catalog else ""
        okf_catalog_size_bytes = okf_catalog_file.stat().st_size if has_okf_catalog else 0

        result_docs.append({
            "id": d.get("id") or f"doc_{clean_stem}",
            "doc_id": d.get("id") or f"doc_{clean_stem}",
            "filename": fn,
            "name": fn,
            "title": stem.replace("_", " "),
            "pages": d.get("pages_processed", 1),
            "size_mb": round(d.get("file_size_bytes", 1024 * 1024) / (1024 * 1024), 2),
            "chunks_count": d.get("chunks", 0),
            "chunks": d.get("chunks", 0),
            "status": "ready",
            "phase": "ready",
            "is_protected": is_prot,
            "can_delete": can_del,
            "deletable": can_del,
            "owner": owner_val,
            "uploaded_at": d.get("uploaded_at") or "2026-09-05T00:00:00",
            "library": d.get("library", "default"),
            "has_extracted_md": has_extracted_md,
            "extracted_md_url": extracted_md_url or "",
            "extracted_md_size_bytes": extracted_md_size_bytes,
            "has_okf_catalog": has_okf_catalog,
            "okf_catalog_url": okf_catalog_url or "",
            "okf_catalog_size_bytes": okf_catalog_size_bytes,
            "graph_triples_count": 0,
        })

    return {"documents": result_docs, "total_count": len(result_docs)}
