"""
RAISE Citation Builder & Bracket Renumbering Sanitizer
======================================================
Purpose:
  Transforms raw chunk metadata into clean citation dictionaries and
  renumbers in-text bracket citations to strictly consecutive [1..N] order,
  filtering unreferenced source citations and stripping meta-commentary.

Author: RAISE Core Architecture Team
Maintainability: Keep under 140 lines with zero regex regressions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def build_evidence_citations(
    ordered_chunks: List[Dict[str, Any]],
    active_doc_list: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Builds clean citation dictionaries from ordered evidence chunks, grouped by unique document page."""
    citations: List[Dict[str, Any]] = []
    seen_pages: Dict[Tuple[str, int], Dict[str, Any]] = {}

    for idx, c in enumerate(ordered_chunks):
        meta = c.get("metadata", {})
        cid = str(meta.get("chunk_id") or c.get("id") or f"chk_{idx+1}")
        raw_t = c.get("text", "")
        cleaned_excerpt = re.sub(r"\[Section Context:[^\]]*\]", "", raw_t, flags=re.IGNORECASE)
        cleaned_excerpt = re.sub(
            r"Institution:.*?\n|Document:.*?\n|Period:.*?\n|Page:.*?\n|Heading:.*?\n|Content:\s*",
            "",
            cleaned_excerpt,
        ).strip()
        cleaned_excerpt = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", cleaned_excerpt)
        cleaned_excerpt = re.sub(r"\s+", " ", cleaned_excerpt).strip()

        p_page = meta.get("primary_page") or meta.get("physical_page") or meta.get("page")
        if not p_page or int(p_page) < 1:
            match = re.search(r"_p0*(\d+)", cid)
            p_page = int(match.group(1)) if match else 1
        p_page = int(p_page)

        pdf_name = (
            meta.get("pdf_filename")
            or meta.get("filename")
            or (active_doc_list[0] if active_doc_list else "Annual Report.pdf")
        )
        d_page = meta.get("printed_page")
        page_key = (pdf_name, p_page)

        if page_key in seen_pages:
            existing = seen_pages[page_key]
            if cid not in existing.get("chunk_ids", []):
                existing.setdefault("chunk_ids", []).append(cid)
            if cleaned_excerpt and cleaned_excerpt not in existing.get("plain_text", ""):
                existing["plain_text"] = (existing.get("plain_text", "") + " " + cleaned_excerpt)[:1000]
            continue

        import urllib.parse
        encoded_name = urllib.parse.quote(pdf_name)
        page_url = f"/api/pdf/{encoded_name}/pages/{p_page}/pdf"
        page_image_url = f"/api/pdf/{encoded_name}/pages/{p_page}/image"
        page_view_url = f"/api/pdf/{encoded_name}/pages/{p_page}/view"

        cit = {
            "citation_index": len(citations) + 1,
            "chunk_id": cid,
            "chunk_ids": [cid],
            "document_id": meta.get("doc_id") or meta.get("document_id") or Path(pdf_name).stem,
            "pdf_filename": pdf_name,
            "primary_page": p_page,
            "printed_page": d_page if (d_page and str(d_page).strip() != "") else None,
            "heading": meta.get("heading") or f"Section (Page {p_page})",
            "plain_text": cleaned_excerpt[:500],
            "university": meta.get("university", "Academic Institution"),
            "similarity": round(float(c.get("similarity", 0.88)), 3),
            "page_url": page_url,
            "page_image_url": page_image_url,
            "page_view_url": page_view_url,
        }
        seen_pages[page_key] = cit
        citations.append(cit)

    return citations


def renumber_and_sanitize_citations(
    raw_answer: str,
    citations: List[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Strips negative meta-commentary, renumbers bracket citations to consecutive 1..N order,
    and returns sanitized answer text and aligned citations list.
    """
    # Strip negative meta-commentary explaining omitted/irrelevant passages
    cleaned_answer = re.sub(
        r'(?:(?:Excerpts?|Passages?|Sources?|References?)\s*(?:\[\d+\][,\s&and–-]*)+[^.\n]*(?:omitted|excluded|not\s+(?:used|relevant)|do\s+not\s+pertain|pertain\s+to|refer\s+to|irrelevant)[^.\n]*[.\n]?)',
        '',
        raw_answer,
        flags=re.IGNORECASE,
    ).strip()

    found_indices: List[int] = []
    for m in re.finditer(r"\[\[?([0-9\s,\-–]+)\]?\]", cleaned_answer):
        for part in re.findall(r"\d+", m.group(1)):
            try:
                p_int = int(part)
                if p_int not in found_indices:
                    found_indices.append(p_int)
            except ValueError:
                pass

    if found_indices:
        index_mapping = {old_idx: new_idx for new_idx, old_idx in enumerate(found_indices, 1)}

        def _replace_cit(match):
            sub_parts = re.findall(r"\d+", match.group(1))
            new_parts = [str(index_mapping.get(int(sp), sp)) for sp in sub_parts if sp.isdigit()]
            seen_p = set()
            unique_parts = [sp for sp in new_parts if not (sp in seen_p or seen_p.add(sp))]
            return f"[{', '.join(unique_parts)}]"

        cleaned_answer = re.sub(r"\[\[?([0-9\s,\-–]+)\]?\]", _replace_cit, cleaned_answer)
        cleaned_answer = re.sub(r"\[(\d+)\](?:\s*\[\1\])+", r"[\1]", cleaned_answer)

        filtered_cits: List[Dict[str, Any]] = []
        seen_new = set()
        for old_idx in found_indices:
            new_idx = index_mapping.get(old_idx)
            if new_idx in seen_new:
                continue
            matching = [c for c in citations if c.get("citation_index") == old_idx]
            if matching:
                seen_new.add(new_idx)
                cit_copy = dict(matching[0])
                cit_copy["citation_index"] = new_idx
                filtered_cits.append(cit_copy)
        final_cits = filtered_cits if filtered_cits else citations
    else:
        final_cits = citations

    if cleaned_answer:
        try:
            from prompts.system_synthesis import sanitize_rag_text
        except ImportError:
            from RAG.prompts.system_synthesis import sanitize_rag_text
        cleaned_answer = sanitize_rag_text(cleaned_answer)

    return cleaned_answer, final_cits
