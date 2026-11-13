"""
RAISE GraphRAG Macro-Chunk Hydration Engine
===========================================
Component: `src.retrieval.macro_hydration`
Architecture Layer: Retrieval / Context Expansion & Hierarchical Chunking

Overview:
---------
Hydrates fine-grained child chunk passages with complete macro parent sections,
ensuring tabular schedules, financial grids, and multi-paragraph discussions are
supplied to LLM synthesis without contextual truncation.

Key Capabilities:
1. Macro Parent Chunk Cache:
   - Discovers and loads `*_parent_chunks.json` files generated during document ingestion.
   - Caches section hierarchies in memory for sub-millisecond retrieval.
2. Parent Section Hydration:
   - Maps child chunks (`parent_chunk_id`) to their full parent sections.
   - Preserves original retrieval order while deduplicating siblings that reference
     the same parent section.
"""

from __future__ import annotations

import re
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("raise.retrieval.macro_hydration")

_PARENT_CHUNKS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def get_parent_chunks_cache() -> Dict[str, Dict[str, Any]]:
    """Loads and caches all pre-computed macro parent chunks across reports."""
    global _PARENT_CHUNKS_CACHE
    if _PARENT_CHUNKS_CACHE is not None:
        return _PARENT_CHUNKS_CACHE

    from src.core.config import CHUNKS_DIR
    cache: Dict[str, Dict[str, Any]] = {}
    base_dirs = [
        CHUNKS_DIR,
        Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "chunks",
    ]
    for bdir in base_dirs:
        if bdir.exists():
            for pfile in bdir.glob("*_parent_chunks.json"):
                try:
                    pdata = json.loads(pfile.read_text(encoding="utf-8"))
                    if isinstance(pdata, list):
                        for item in pdata:
                            cid = item.get("chunk_id")
                            if cid:
                                cache[cid] = item
                except Exception:
                    pass
    _PARENT_CHUNKS_CACHE = cache
    return _PARENT_CHUNKS_CACHE


def hydrate_macro_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    GraphRAG Macro-Chunk Hydration:
    Replaces fragmented child chunk snippets with the full macro-chunk parent section,
    preserving full tabular grids, section context, and financial schedules without truncation.
    Deduplicates chunks that share the same parent while preserving order.
    """
    if not chunks:
        return []
    parents_map = get_parent_chunks_cache()
    if not parents_map:
        return chunks

    hydrated = []
    seen_parent_ids = set()

    for c in chunks:
        meta = dict(c.get("metadata") or {})
        parent_id = c.get("parent_chunk_id") or meta.get("parent_chunk_id")

        if parent_id and parent_id in parents_map:
            if parent_id in seen_parent_ids:
                continue
            seen_parent_ids.add(parent_id)
            p_obj = parents_map[parent_id]
            parent_text = (
                p_obj.get("plain_text")
                or p_obj.get("contextualized_content")
                or p_obj.get("text")
                or ""
            )

            c_copy = dict(c)
            # If the parent chunk text ends mid-sentence across a page boundary (e.g. trailing fragment or sentence cut off by page break),
            # stitch the next consecutive parent chunk to prevent metric/patent truncation.
            m_pid = re.search(r"^(.*_parent_)(\d+)$", parent_id)
            if m_pid and (not parent_text.rstrip().endswith((".", "!", "?", '"', "'", ";")) or "preamble" in str(meta.get("heading", "")).lower()):
                p_prefix = m_pid.group(1)
                p_idx = int(m_pid.group(2))
                next_pid = f"{p_prefix}{p_idx+1:03d}"
                if next_pid in parents_map:
                    next_p = parents_map[next_pid]
                    next_txt = next_p.get("plain_text") or next_p.get("text") or ""
                    parent_text = parent_text.rstrip() + " " + next_txt.lstrip()
                    next_pages = next_p.get("source_pages") or ([next_p.get("primary_page")] if next_p.get("primary_page") else [])
                    if next_pages:
                        cur_pages = meta.get("source_pages") or ([meta.get("primary_page")] if meta.get("primary_page") else [])
                        meta["source_pages"] = sorted(list(set(cur_pages + next_pages)))

            c_copy["text"] = parent_text
            c_copy["plain_text"] = parent_text
            meta["parent_chunk_id"] = parent_id
            meta["is_macro_hydrated"] = True
            if "heading" not in meta and p_obj.get("heading"):
                meta["heading"] = p_obj["heading"]
            if "primary_page" not in meta and p_obj.get("primary_page"):
                meta["primary_page"] = p_obj["primary_page"]
            if "printed_page" not in meta and p_obj.get("printed_page"):
                meta["printed_page"] = p_obj["printed_page"]

            # Ensure source_pages is preserved from the parent section
            if p_obj.get("source_pages"):
                meta["source_pages"] = list(p_obj["source_pages"])
                c_copy["source_pages"] = meta["source_pages"]

            # Also check for embedded folio headers on non-table header lines (skip TOC and markdown table grids)
            is_toc = any(kw in str(meta.get("heading", "")).lower() for kw in ("contents", "index", "table of contents"))
            if not is_toc and "### Table:" not in parent_text:
                non_table_lines = [l for l in parent_text.splitlines() if not l.strip().startswith("|") and l.count("|") == 1]
                if non_table_lines:
                    folio_matches = re.findall(
                        r"(?:^[A-Za-z0-9\s\-–]{2,40}\s*\|\s*(\d{1,4})$|^(\d{1,4})\s*\|\s*[A-Za-z0-9\s\-–]{2,40}$)",
                        "\n".join(non_table_lines),
                        re.IGNORECASE | re.MULTILINE,
                    )
                    if folio_matches:
                        cur_pages = list(meta.get("source_pages") or ([meta.get("primary_page")] if meta.get("primary_page") else []))
                        for fm in folio_matches:
                            for g in fm:
                                if g and g.isdigit():
                                    p_val = int(g)
                                    if 1 <= p_val <= 400:
                                        cur_pages.append(p_val)
                        meta["source_pages"] = sorted(list(set(cur_pages)))
                        c_copy["source_pages"] = meta["source_pages"]

            c_copy["metadata"] = meta
            hydrated.append(c_copy)
        else:
            hydrated.append(c)

    return hydrated
