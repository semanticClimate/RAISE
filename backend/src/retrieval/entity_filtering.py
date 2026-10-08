"""
RAISE Institutional & Entity Boundary Filtering
===============================================
Component: `src.retrieval.entity_filtering`
Architecture Layer: Retrieval / Entity Isolation & Guardrails

Overview:
---------
Enforces strict institutional and domain boundary filtering to prevent cross-document
hallucinations and benchmark leakage.

Key Capabilities:
1. Dynamic Institution Registry:
   - Reads registered institutions and aliases from the processed library manifest.
   - Eliminates hardcoded institutional acronyms or names from Python source code.
2. Candidate Pruning:
   - `filter_entity_mismatches`: If the user's query specifically targets an institution,
     prunes candidate chunks that explicitly belong to a conflicting institution not mentioned in the query.
3. Subgraph Pruning:
   - `filter_subgraph_entity_mismatches`: Filters Neo4j subgraph nodes and edges to prune entities
     belonging to conflicting institutions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger("raise.retrieval.entity_filtering")


def get_library_institutions() -> Dict[str, List[str]]:
    """
    Dynamically loads registered institutions and their aliases from the library manifest.
    Zero hardcoded institution names in Python code.
    """
    try:
        from src.core.config import settings
        manifest_path = settings.processed_dir / "ingested_manifest.json"
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            inst_map: Dict[str, List[str]] = {}
            for doc in data.get("ready_documents", []):
                short_name = (doc.get("short_name") or doc.get("institution") or "").lower().strip()
                inst_full = (doc.get("institution") or "").lower().strip()
                aliases = [a.lower().strip() for a in doc.get("aliases", []) if a]
                if short_name:
                    if short_name not in inst_map:
                        inst_map[short_name] = []
                    for a in aliases:
                        if a not in inst_map[short_name]:
                            inst_map[short_name].append(a)
                    if inst_full and inst_full not in inst_map[short_name]:
                        inst_map[short_name].append(inst_full)
            if inst_map:
                return inst_map
    except Exception:
        pass
    return {}


def filter_entity_mismatches(
    query: str,
    candidates: List[Dict[str, Any] | Any],
) -> List[Dict[str, Any] | Any]:
    """
    Enforces strict institutional/entity boundary filtering.
    If the user's query specifically targets an institution, prunes candidate chunks
    that explicitly belong to a conflicting institution not mentioned in the query.
    Institutions are dynamically resolved from the active Library manifest.
    """
    if not candidates or not query:
        return candidates

    q_lower = query.lower()
    institutions = get_library_institutions()
    if not institutions:
        return candidates

    # Detect which institutions are targeted by the query
    targeted = set()
    for inst_key, aliases in institutions.items():
        if any(alias in q_lower for alias in aliases):
            targeted.add(inst_key)

    # If no specific institution is targeted, or multiple conflicting ones are requested, preserve all
    if not targeted:
        return candidates

    filtered = []
    for c in candidates:
        if hasattr(c, "metadata"):
            meta = c.metadata or {}
            c_text = str(getattr(c, "page_content", "")).lower()
        else:
            meta = c.get("metadata") or {} if isinstance(c, dict) else {}
            c_text = (c.get("text") or c.get("plain_text") or meta.get("contextualized_content") or "").lower()

        pdf_name = (meta.get("pdf_filename") or (c.get("pdf_filename") if isinstance(c, dict) else "") or "").lower()
        doc_id = (meta.get("document_id") or (c.get("document_id") if isinstance(c, dict) else "") or "").lower()

        # Check for conflict with an institution NOT in targeted
        is_conflict = False
        for inst_key, aliases in institutions.items():
            if inst_key not in targeted:
                if any(alias in pdf_name for alias in aliases) or any(alias in doc_id for alias in aliases):
                    is_conflict = True
                    break
                if any(f"institution: {alias}" in c_text for alias in aliases):
                    is_conflict = True
                    break

        if not is_conflict:
            filtered.append(c)

    # Fallback to candidates if filtering would leave zero candidates
    return filtered if filtered else candidates


def filter_subgraph_entity_mismatches(
    query: str,
    subgraph: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Filters Neo4j subgraph nodes and edges to prune entities belonging to conflicting institutions.
    Dynamically loads institutional aliases from the library manifest.
    """
    if not subgraph or not query or not isinstance(subgraph, dict):
        return subgraph

    q_lower = query.lower()
    institutions = get_library_institutions()
    if not institutions:
        return subgraph

    targeted = set()
    for inst_key, aliases in institutions.items():
        if any(alias in q_lower for alias in aliases):
            targeted.add(inst_key)

    if not targeted:
        return subgraph

    conflict_aliases = []
    for inst_key, aliases in institutions.items():
        if inst_key not in targeted:
            conflict_aliases.extend(aliases)

    nodes = subgraph.get("nodes", [])
    valid_nodes = []
    for n in nodes:
        name = str(n.get("name", "")).lower()
        nid = str(n.get("id", "")).lower()
        lbl = str(n.get("label", "")).lower()
        if any(alias in name or alias in nid or alias in lbl for alias in conflict_aliases):
            continue
        valid_nodes.append(n)

    edges = subgraph.get("edges", [])
    valid_edges = []
    for e in edges:
        src = str(e.get("source", "")).lower()
        tgt = str(e.get("target", "")).lower()
        if any(alias in src or alias in tgt for alias in conflict_aliases):
            continue
        valid_edges.append(e)

    return {"nodes": valid_nodes, "edges": valid_edges}
