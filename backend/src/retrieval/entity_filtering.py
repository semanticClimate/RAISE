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
from typing import Any, Dict, List, Optional

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


def _norm_entity(text: str) -> str:
    import re
    return re.sub(r"[\W_]+", " ", text).lower().strip()


def filter_entity_mismatches(
    query: str,
    candidates: List[Dict[str, Any] | Any],
    institutions: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any] | Any]:
    """
    Enforces strict institutional/entity boundary filtering.
    If the user's query specifically targets an institution, prunes candidate chunks
    that explicitly belong to a conflicting institution not mentioned in the query.
    Institutions are dynamically resolved from the active Library manifest or optional argument.
    Zero hardcoded institution names.
    """
    if not candidates or not query:
        return candidates

    q_lower = query.lower()
    if institutions is None:
        institutions = get_library_institutions()
    if not institutions:
        return candidates

    # Detect which institutions are targeted by the query
    targeted = set()
    for inst_key, aliases in institutions.items():
        if any(_norm_entity(alias) in _norm_entity(q_lower) for alias in aliases if alias):
            targeted.add(inst_key)

    # If no specific institution is targeted, or multiple conflicting ones are requested, preserve all
    if not targeted:
        return candidates

    filtered = []
    for c in candidates:
        if hasattr(c, "metadata"):
            meta = c.metadata or {}
            c_text = str(getattr(c, "page_content", ""))
        else:
            meta = c.get("metadata") or {} if isinstance(c, dict) else {}
            c_text = c.get("text") or c.get("plain_text") or meta.get("contextualized_content") or ""

        pdf_name = meta.get("pdf_filename") or (c.get("pdf_filename") if isinstance(c, dict) else "") or ""
        doc_id = meta.get("document_id") or (c.get("document_id") if isinstance(c, dict) else "") or ""

        norm_pdf = _norm_entity(pdf_name)
        norm_doc = _norm_entity(doc_id)
        norm_text = _norm_entity(c_text)

        # Check for conflict with an institution NOT in targeted
        is_conflict = False
        for inst_key, aliases in institutions.items():
            if inst_key not in targeted:
                for alias in aliases:
                    n_alias = _norm_entity(alias)
                    if not n_alias:
                        continue
                    if n_alias in norm_pdf or n_alias in norm_doc:
                        is_conflict = True
                        break
                    if n_alias in norm_text:
                        is_conflict = True
                        break
                if is_conflict:
                    break

        if not is_conflict:
            filtered.append(c)

    # Fallback to candidates if filtering would leave zero candidates
    return filtered if filtered else candidates


def filter_subgraph_entity_mismatches(
    query: str,
    subgraph: Dict[str, Any],
    institutions: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """
    Filters Neo4j subgraph nodes and edges to prune entities belonging to conflicting institutions.
    Dynamically loads institutional aliases from the library manifest, caller arguments, or node labels.
    """
    import re
    if not subgraph or not query or not isinstance(subgraph, dict):
        return subgraph

    q_lower = query.lower()
    if institutions is None:
        institutions = dict(get_library_institutions())
    else:
        institutions = dict(institutions)

    # Dynamically discover any institutions present directly in subgraph nodes
    if subgraph and isinstance(subgraph, dict):
        for n in subgraph.get("nodes", []):
            if str(n.get("label", "")).lower() in ("institution", "organization", "university"):
                name = str(n.get("name", "")).strip()
                if name:
                    n_key = name.lower()
                    if n_key not in institutions:
                        parts = [p.lower() for p in re.findall(r"\b[A-Za-z0-9]+\b", name) if len(p) >= 3]
                        institutions[n_key] = list(set([n_key] + parts))

    if not institutions:
        return subgraph

    targeted = set()
    for inst_key, aliases in institutions.items():
        if any(_norm_entity(alias) in _norm_entity(q_lower) for alias in aliases if alias):
            targeted.add(inst_key)

    if not targeted:
        return subgraph

    conflict_aliases = []
    for inst_key, aliases in institutions.items():
        if inst_key not in targeted:
            for alias in aliases:
                n_alias = _norm_entity(alias)
                if n_alias:
                    conflict_aliases.append(n_alias)

    nodes = subgraph.get("nodes", [])
    valid_nodes = []
    for n in nodes:
        name = _norm_entity(str(n.get("name", "")))
        nid = _norm_entity(str(n.get("id", "")))
        lbl = _norm_entity(str(n.get("label", "")))
        if any(alias in name or alias in nid or alias in lbl for alias in conflict_aliases):
            continue
        valid_nodes.append(n)

    edges = subgraph.get("edges", [])
    valid_edges = []
    for e in edges:
        src = _norm_entity(str(e.get("source", "")))
        tgt = _norm_entity(str(e.get("target", "")))
        if any(alias in src or alias in tgt for alias in conflict_aliases):
            continue
        valid_edges.append(e)

    return {"nodes": valid_nodes, "edges": valid_edges}
