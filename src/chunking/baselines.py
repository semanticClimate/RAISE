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
    """Fixed-size chunking baseline (400 words per chunk with 50-word overlap)."""
    full_text = "\n\n".join(s.get("text", "") for s in parsed_sections)
    words = full_text.split()
    chunk_size = 350
    overlap = 50
    step = chunk_size - overlap

    child_chunks: List[AdaptiveChunk] = []
    c_idx = 0
    for start in range(0, len(words), step):
        c_idx += 1
        chunk_words = words[start:start + chunk_size]
        if not chunk_words:
            break
        text = " ".join(chunk_words)
        cid = f"{document_id}_fixed_{c_idx:03d}"
        child_chunks.append(AdaptiveChunk(
            chunk_id=cid,
            document_id=document_id,
            chunk_level=ChunkLevel.CHILD.value,
            plain_text=text,
            contextualized_content=text,
            heading=f"Fixed Block {c_idx}",
            primary_page=1,
            source_pages=[1],
            token_estimate=len(chunk_words),
            chunking_strategy="fixed",
            metadata={"document_id": document_id, "university": university, "pdf_filename": filename},
        ))

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
        "ascii_trace": "Fixed chunking baseline (no graph optimization)",
        "legacy_chunks": [c.to_dict() for c in child_chunks],
    }


def process_recursive_baseline(
    parsed_sections: List[Dict[str, Any]],
    document_id: str,
    filename: str,
    university: str,
    reporting_period: str,
    pages: int,
) -> Dict[str, Any]:
    """Recursive character chunking baseline (splits hierarchically on \\n\\n, \\n, and space)."""
    child_chunks: List[AdaptiveChunk] = []
    c_idx = 0
    for s_idx, sec in enumerate(parsed_sections, start=1):
        text = sec.get("text", "")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for p in paragraphs:
            if len(p.split()) < 30:
                continue
            c_idx += 1
            cid = f"{document_id}_rec_{c_idx:03d}"
            child_chunks.append(AdaptiveChunk(
                chunk_id=cid,
                document_id=document_id,
                chunk_level=ChunkLevel.CHILD.value,
                plain_text=p,
                contextualized_content=p,
                heading=sec.get("heading", f"Section {s_idx}"),
                primary_page=sec.get("page_number", 1),
                source_pages=[sec.get("page_number", 1)],
                token_estimate=len(p.split()),
                chunking_strategy="recursive",
                metadata={"document_id": document_id, "university": university, "pdf_filename": filename},
            ))

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
        "ascii_trace": "Recursive chunking baseline (no graph optimization)",
        "legacy_chunks": [c.to_dict() for c in child_chunks],
    }
