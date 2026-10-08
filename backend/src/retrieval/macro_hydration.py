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

    cache: Dict[str, Dict[str, Any]] = {}
    base_dirs = [
        Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "chunks",
        Path(__file__).resolve().parent.parent / "data" / "processed" / "chunks",
        Path("backend/data/processed/chunks"),
        Path("data/processed/chunks"),
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
            c_copy["metadata"] = meta
            hydrated.append(c_copy)
        else:
            hydrated.append(c)

    return hydrated
