"""
Baseline Chunking Strategies (Fixed-Size & Recursive)
=====================================================
Component: `src.chunking.baselines`
Architecture Layer: Document Processing / Baseline Comparative Strategies

Overview:
---------
Provides standard baseline chunking implementations used for ablation studies
and diagnostic performance comparisons against Graph-Guided Adaptive Hierarchical Chunking (GGAHC):
- Fixed-Size Chunking (400 words per chunk with 50-word overlap)
- Recursive Character Chunking (hierarchical paragraph and whitespace splitting)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .models import (
    AdaptiveChunk,
    ChunkLevel,
    ChunkingDiagnosticReport,
)

logger = logging.getLogger("raise.chunking.baselines")


def process_fixed_baseline(
    parsed_sections: List[Dict[str, Any]],
    document_id: str,
    filename: str,
    university: str,
    reporting_period: str,
    pages: int,
) -> Dict[str, Any]:
    """Fixed-size chunking baseline (350 words per chunk with 50-word overlap) with accurate page provenance."""
    child_chunks: List[AdaptiveChunk] = []
    c_idx = 0
    chunk_size = 350
    overlap = 50
    step = chunk_size - overlap

    for s_idx, sec in enumerate(parsed_sections, start=1):
        text = (sec.get("text") or sec.get("plain_text") or "").strip()
        if not text:
            continue
        words = text.split()
        if len(words) < 3:
            continue
        pno = int(sec.get("page_number") or 1)
        doc_pno = str(sec.get("doc_page_number") or "") if sec.get("doc_page_number") is not None else None
        heading = str(sec.get("heading") or f"Section {s_idx}").strip()
        is_tbl = bool(sec.get("has_table") or sec.get("is_table") or "| --- |" in text)
        tbl_cnt = int(sec.get("tables_count", 1 if is_tbl else 0))

        if len(words) <= chunk_size:
            c_idx += 1
            cid = f"{document_id}_fixed_{c_idx:04d}"
            child_chunks.append(
                AdaptiveChunk(
                    chunk_id=cid,
                    document_id=document_id,
                    chunk_level=ChunkLevel.CHILD.value,
                    plain_text=text,
                    contextualized_content=text,
                    heading=heading,
                    primary_page=pno,
                    printed_page=doc_pno,
                    source_pages=[pno],
                    token_estimate=len(words),
                    chunking_strategy="fixed",
                    is_table=is_tbl,
                    tables_count=tbl_cnt,
                    metadata={"document_id": document_id, "university": university, "pdf_filename": filename, "page": pno},
                )
            )
            continue

        part_idx = 0
        for start in range(0, len(words), step):
            part_idx += 1
            c_idx += 1
            chunk_words = words[start : start + chunk_size]
            if not chunk_words:
                break
            chunk_str = " ".join(chunk_words)
            cid = f"{document_id}_fixed_{c_idx:04d}"
            sub_h = f"{heading} (Block {part_idx})"
            child_chunks.append(
                AdaptiveChunk(
                    chunk_id=cid,
                    document_id=document_id,
                    chunk_level=ChunkLevel.CHILD.value,
                    plain_text=chunk_str,
                    contextualized_content=chunk_str,
                    heading=sub_h,
                    primary_page=pno,
                    printed_page=doc_pno,
                    source_pages=[pno],
                    token_estimate=len(chunk_words),
                    chunking_strategy="fixed",
                    is_table=is_tbl,
                    tables_count=tbl_cnt,
                    metadata={"document_id": document_id, "university": university, "pdf_filename": filename, "page": pno},
                )
            )

    report = ChunkingDiagnosticReport(
        document_id=document_id,
        filename=filename,
        strategy="fixed",
        pages=pages,
        structural_units_count=len(parsed_sections),
        candidate_semantic_units_count=len(child_chunks),
        final_parent_chunks_count=0,
        final_child_chunks_count=len(child_chunks),
        average_child_tokens=round(sum(c.token_estimate for c in child_chunks) / max(1, len(child_chunks)), 1),
    )

    return {
        "child_chunks": child_chunks,
        "parent_chunks": [],
        "propositions": [],
        "diagnostic_report": report,
        "ascii_trace": f"Fixed chunking baseline: {len(child_chunks)} chunks across {pages} pages",
        "legacy_chunks": [c.to_dict() for c in child_chunks],
    }


def process_recursive_baseline(
    parsed_sections: List[Dict[str, Any]],
    document_id: str,
    filename: str,
    university: str,
    reporting_period: str,
    pages: int,
    target_words: int = 320,
    max_words: int = 480,
    min_words: int = 30,
) -> Dict[str, Any]:
    """
    High-fidelity hierarchical recursive chunking baseline.
    Splits document sections hierarchically (section -> paragraph -> line)
    while preserving compact governance rosters, administrative appointments,
    tables, and short-item structures without discarding critical preliminary or
    tabular pages.
    """
    child_chunks: List[AdaptiveChunk] = []
    c_idx = 0

    for s_idx, sec in enumerate(parsed_sections, start=1):
        raw_text = (sec.get("text") or sec.get("plain_text") or "").strip()
        if not raw_text:
            continue

        # Skip pure blank graphic placeholders that contain zero semantic content
        if (
            raw_text.startswith("[Page")
            and ("Graphic / Blank]" in raw_text or "Graphic / Form]" in raw_text)
            and len(raw_text) < 35
        ):
            continue

        words = raw_text.split()
        if len(words) < 3:
            continue

        pno = int(sec.get("page_number") or 1)
        doc_pno = str(sec.get("doc_page_number") or "") if sec.get("doc_page_number") is not None else None
        base_heading = str(sec.get("heading") or f"Section {s_idx}").strip()
        is_tbl = bool(sec.get("has_table") or sec.get("is_table") or "| --- |" in raw_text)
        tbl_cnt = int(sec.get("tables_count", 1 if is_tbl else 0))

        # Case 1: Entire section fits within max_words (e.g. Page 4 Board of Governors / Council Nominees, 238 words)
        if len(words) <= max_words:
            c_idx += 1
            cid = f"{document_id}_rec_{c_idx:04d}"
            child_chunks.append(
                AdaptiveChunk(
                    chunk_id=cid,
                    document_id=document_id,
                    chunk_level=ChunkLevel.CHILD.value,
                    plain_text=raw_text,
                    contextualized_content=raw_text,
                    heading=base_heading,
                    primary_page=pno,
                    printed_page=doc_pno,
                    source_pages=[pno],
                    token_estimate=len(words),
                    chunking_strategy="recursive",
                    is_table=is_tbl,
                    tables_count=tbl_cnt,
                    metadata={
                        "document_id": document_id,
                        "university": university,
                        "pdf_filename": filename,
                        "page": pno,
                        "heading": base_heading,
                    },
                )
            )
            continue

        # Case 2: Section exceeds max_words -> split hierarchically on paragraphs (\n\n) then lines (\n)
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        curr_paras: List[str] = []
        curr_words = 0
        part_counter = 0

        for p in paragraphs:
            p_len = len(p.split())
            if p_len > max_words:
                # Flush pending accumulated paragraphs first
                if curr_paras:
                    part_counter += 1
                    c_idx += 1
                    c_text = "\n\n".join(curr_paras)
                    cid = f"{document_id}_rec_{c_idx:04d}"
                    sub_h = f"{base_heading} (Part {part_counter})"
                    child_chunks.append(
                        AdaptiveChunk(
                            chunk_id=cid,
                            document_id=document_id,
                            chunk_level=ChunkLevel.CHILD.value,
                            plain_text=c_text,
                            contextualized_content=c_text,
                            heading=sub_h,
                            primary_page=pno,
                            printed_page=doc_pno,
                            source_pages=[pno],
                            token_estimate=len(c_text.split()),
                            chunking_strategy="recursive",
                            is_table=is_tbl,
                            tables_count=tbl_cnt,
                            metadata={
                                "document_id": document_id,
                                "university": university,
                                "pdf_filename": filename,
                                "page": pno,
                                "heading": sub_h,
                            },
                        )
                    )
                    curr_paras = []
                    curr_words = 0

                # Split oversized paragraph by single line breaks
                lines = [l.strip() for l in p.split("\n") if l.strip()]
                sub_lines: List[str] = []
                sub_l_words = 0
                for l in lines:
                    l_len = len(l.split())
                    if sub_l_words + l_len > target_words and sub_l_words >= min_words:
                        part_counter += 1
                        c_idx += 1
                        c_text = "\n".join(sub_lines)
                        cid = f"{document_id}_rec_{c_idx:04d}"
                        sub_h = f"{base_heading} (Part {part_counter})"
                        child_chunks.append(
                            AdaptiveChunk(
                                chunk_id=cid,
                                document_id=document_id,
                                chunk_level=ChunkLevel.CHILD.value,
                                plain_text=c_text,
                                contextualized_content=c_text,
                                heading=sub_h,
                                primary_page=pno,
                                printed_page=doc_pno,
                                source_pages=[pno],
                                token_estimate=len(c_text.split()),
                                chunking_strategy="recursive",
                                is_table=is_tbl,
                                tables_count=tbl_cnt,
                                metadata={
                                    "document_id": document_id,
                                    "university": university,
                                    "pdf_filename": filename,
                                    "page": pno,
                                    "heading": sub_h,
                                },
                            )
                        )
                        sub_lines = [l]
                        sub_l_words = l_len
                    else:
                        sub_lines.append(l)
                        sub_l_words += l_len

                if sub_lines:
                    curr_paras = ["\n".join(sub_lines)]
                    curr_words = sub_l_words
                continue

            if curr_words + p_len > target_words and curr_words >= min_words:
                part_counter += 1
                c_idx += 1
                c_text = "\n\n".join(curr_paras)
                cid = f"{document_id}_rec_{c_idx:04d}"
                sub_h = f"{base_heading} (Part {part_counter})"
                child_chunks.append(
                    AdaptiveChunk(
                        chunk_id=cid,
                        document_id=document_id,
                        chunk_level=ChunkLevel.CHILD.value,
                        plain_text=c_text,
                        contextualized_content=c_text,
                        heading=sub_h,
                        primary_page=pno,
                        printed_page=doc_pno,
                        source_pages=[pno],
                        token_estimate=len(c_text.split()),
                        chunking_strategy="recursive",
                        is_table=is_tbl,
                        tables_count=tbl_cnt,
                        metadata={
                            "document_id": document_id,
                            "university": university,
                            "pdf_filename": filename,
                            "page": pno,
                            "heading": sub_h,
                        },
                    )
                )
                curr_paras = [p]
                curr_words = p_len
            else:
                curr_paras.append(p)
                curr_words += p_len

        # Flush any trailing accumulated content for the section
        if curr_paras:
            c_text = "\n\n".join(curr_paras)
            w_count = len(c_text.split())
            # If tiny remainder (< 45 words) and previous chunk was from the same page, merge to avoid fragmenting
            if (
                w_count < 45
                and part_counter > 0
                and child_chunks
                and child_chunks[-1].primary_page == pno
                and (child_chunks[-1].token_estimate + w_count <= max_words)
            ):
                child_chunks[-1].plain_text += "\n\n" + c_text
                child_chunks[-1].contextualized_content += "\n\n" + c_text
                child_chunks[-1].token_estimate += w_count
            elif w_count >= 3:
                part_counter += 1
                c_idx += 1
                cid = f"{document_id}_rec_{c_idx:04d}"
                sub_h = f"{base_heading} (Part {part_counter})" if part_counter > 1 else base_heading
                child_chunks.append(
                    AdaptiveChunk(
                        chunk_id=cid,
                        document_id=document_id,
                        chunk_level=ChunkLevel.CHILD.value,
                        plain_text=c_text,
                        contextualized_content=c_text,
                        heading=sub_h,
                        primary_page=pno,
                        printed_page=doc_pno,
                        source_pages=[pno],
                        token_estimate=w_count,
                        chunking_strategy="recursive",
                        is_table=is_tbl,
                        tables_count=tbl_cnt,
                        metadata={
                            "document_id": document_id,
                            "university": university,
                            "pdf_filename": filename,
                            "page": pno,
                            "heading": sub_h,
                        },
                    )
                )

    report = ChunkingDiagnosticReport(
        document_id=document_id,
        filename=filename,
        strategy="recursive",
        pages=pages,
        structural_units_count=len(parsed_sections),
        candidate_semantic_units_count=len(child_chunks),
        final_parent_chunks_count=0,
        final_child_chunks_count=len(child_chunks),
        average_child_tokens=round(sum(c.token_estimate for c in child_chunks) / max(1, len(child_chunks)), 1),
    )

    return {
        "child_chunks": child_chunks,
        "parent_chunks": [],
        "propositions": [],
        "diagnostic_report": report,
        "ascii_trace": f"Recursive chunking: {len(child_chunks)} chunks across {pages} pages",
        "legacy_chunks": [c.to_dict() for c in child_chunks],
    }
