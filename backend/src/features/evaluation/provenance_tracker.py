"""
Claim-Level Provenance & Citation Verification Engine
=====================================================
Establishes an unbroken provenance chain:
    Claim -> Evidence Span -> Chunk ID -> Page Number -> Document ID

Ensures:
1. Citations point to valid retrieved chunks.
2. Page numbers originate strictly from chunk metadata (not LLM fabrication).
3. Evaluates citation precision, recall, and page grounding against gold references.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ClaimProvenanceRecord:
    """Provenance record for a single atomic claim."""
    claim_id: str
    claim_text: str
    cited_indices: List[int]
    resolved_chunk_ids: List[str]
    resolved_pages: List[int]
    resolved_documents: List[str]
    is_grounded_in_gold: bool
    hallucinated_pages: List[int] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class QueryProvenanceResult:
    """Provenance & citation evaluation result for a single query."""
    query_id: str
    query: str
    gold_document: str
    gold_pages: List[int]
    retrieved_chunk_count: int
    claims: List[ClaimProvenanceRecord]
    cited_pages: List[int]
    cited_documents: List[str]
    citation_precision: float
    citation_recall: float
    citation_f1: float
    page_grounded: bool
    citation_hallucination_detected: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "gold_document": self.gold_document,
            "gold_pages": self.gold_pages,
            "retrieved_chunk_count": self.retrieved_chunk_count,
            "cited_pages": self.cited_pages,
            "cited_documents": self.cited_documents,
            "citation_precision": round(self.citation_precision, 4),
            "citation_recall": round(self.citation_recall, 4),
            "citation_f1": round(self.citation_f1, 4),
            "page_grounded": self.page_grounded,
            "citation_hallucination_detected": self.citation_hallucination_detected,
            "claims": [asdict(c) for c in self.claims],
            "metadata": self.metadata,
        }


class ProvenanceTracker:
    """
    Validates and traces the provenance of generated answers and individual claims.
    """

    BRACKET_PATTERN = re.compile(r"\[\[?([0-9\s,\-–]+)\]?\]")
    EXPLICIT_PAGE_PATTERN = re.compile(r"\b(?:page|pg\.?|p\.)\s*([0-9]{1,4})\b", re.IGNORECASE)

    @classmethod
    def extract_bracket_citations(cls, text: str) -> List[int]:
        """Extracts numerical indices from bracketed citations [1], [2, 3], etc."""
        indices = []
        for m in cls.BRACKET_PATTERN.finditer(text):
            for part in re.findall(r"\d+", m.group(1)):
                try:
                    idx = int(part)
                    if idx not in indices:
                        indices.append(idx)
                except ValueError:
                    continue
        return indices

    @classmethod
    def extract_explicit_page_mentions(cls, text: str) -> List[int]:
        """Extracts direct page numbers mentioned in text (e.g. 'page 45', 'p. 12')."""
        pages = []
        for m in cls.EXPLICIT_PAGE_PATTERN.finditer(text):
            try:
                p = int(m.group(1))
                if p not in pages:
                    pages.append(p)
            except ValueError:
                continue
        return pages

    @classmethod
    def resolve_chunk_provenance(
        cls,
        citation_index: int,
        context_chunks: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Resolves a 1-based citation index to its chunk metadata: chunk_id, pages, document.
        """
        # 1-based index into context_chunks
        idx_0 = citation_index - 1
        if 0 <= idx_0 < len(context_chunks):
            chunk = context_chunks[idx_0]
        else:
            # Check if any chunk explicitly has "citation_index" == citation_index
            matched = [c for c in context_chunks if c.get("citation_index") == citation_index]
            if matched:
                chunk = matched[0]
            else:
                return None

        # Extract primary page and source pages
        pages: List[int] = []
        p_prim = (
            chunk.get("primary_page")
            or chunk.get("page_number")
            or chunk.get("page")
            or chunk.get("pdf_page")
        )
        if p_prim is not None:
            try:
                pages.append(int(p_prim))
            except (ValueError, TypeError):
                pass

        src_pages = chunk.get("source_pages") or chunk.get("pages") or []
        for sp in src_pages:
            try:
                isp = int(sp)
                if isp not in pages:
                    pages.append(isp)
            except (ValueError, TypeError):
                pass

        doc_name = (
            chunk.get("pdf_filename")
            or chunk.get("document_id")
            or chunk.get("source")
            or chunk.get("doc_id")
            or chunk.get("document")
            or ""
        )

        return {
            "chunk_id": str(chunk.get("chunk_id") or chunk.get("id") or f"chunk_{citation_index}"),
            "pages": pages,
            "document": str(doc_name),
            "text": str(chunk.get("plain_text") or chunk.get("text") or "")[:200],
        }

    @classmethod
    def evaluate_query(
        cls,
        query_id: str,
        query: str,
        answer: str,
        claims: List[str],
        context_chunks: List[Dict[str, Any]],
        gold_document: str = "",
        gold_pages: Optional[List[int]] = None,
        is_negative_probe: bool = False,
    ) -> QueryProvenanceResult:
        """
        Evaluates provenance for an entire answer and its constituent claims.
        """
        gold_pages = gold_pages or []
        gold_pages_set = set(gold_pages)

        # 1. Answer-level bracket citations
        answer_citations = cls.extract_bracket_citations(answer)
        explicit_pages = cls.extract_explicit_page_mentions(answer)

        # Collect all valid pages and documents across context_chunks
        available_pages: Set[int] = set()
        available_docs: Set[str] = set()
        chunk_map: Dict[int, Dict[str, Any]] = {}

        for i in range(1, len(context_chunks) + 1):
            info = cls.resolve_chunk_provenance(i, context_chunks)
            if info:
                chunk_map[i] = info
                available_pages.update(info["pages"])
                if info["document"]:
                    available_docs.add(info["document"].lower())

        # Check for explicit page hallucinations: pages mentioned in text that are not in retrieved chunks
        hallucinated_pages = [p for p in explicit_pages if p not in available_pages]

        # 2. Claim-level provenance mapping
        claim_records: List[ClaimProvenanceRecord] = []
        all_cited_pages: List[int] = []
        all_cited_docs: List[str] = []

        for idx, c_text in enumerate(claims, start=1):
            c_id = f"c_{idx:02d}"
            c_citations = cls.extract_bracket_citations(c_text)
            # If claim text didn't contain brackets, fall back to answer citations if there's only 1 claim
            if not c_citations and len(claims) == 1:
                c_citations = answer_citations

            c_chunk_ids: List[str] = []
            c_pages: List[int] = []
            c_docs: List[str] = []
            c_notes: List[str] = []

            for cit in c_citations:
                info = chunk_map.get(cit)
                if info:
                    c_chunk_ids.append(info["chunk_id"])
                    for p in info["pages"]:
                        if p not in c_pages:
                            c_pages.append(p)
                    if info["document"] and info["document"] not in c_docs:
                        c_docs.append(info["document"])
                else:
                    c_notes.append(f"Citation [{cit}] is out of bounds (max {len(context_chunks)})")

            # Check if this claim's pages touch gold
            is_gold_grounded = False
            if is_negative_probe:
                is_gold_grounded = True  # Negatives are grounded if abstaining
            elif gold_pages_set and any(p in gold_pages_set for p in c_pages):
                is_gold_grounded = True
            elif not gold_pages_set and c_docs and gold_document:
                is_gold_grounded = any(gold_document.lower() in d.lower() or d.lower() in gold_document.lower() for d in c_docs)

            claim_records.append(
                ClaimProvenanceRecord(
                    claim_id=c_id,
                    claim_text=c_text,
                    cited_indices=c_citations,
                    resolved_chunk_ids=c_chunk_ids,
                    resolved_pages=c_pages,
                    resolved_documents=c_docs,
                    is_grounded_in_gold=is_gold_grounded,
                    notes=c_notes,
                )
            )

            for p in c_pages:
                if p not in all_cited_pages:
                    all_cited_pages.append(p)
            for d in c_docs:
                if d not in all_cited_docs:
                    all_cited_docs.append(d)

        # Also incorporate any answer-level citations not captured in individual claims
        for cit in answer_citations:
            info = chunk_map.get(cit)
            if info:
                for p in info["pages"]:
                    if p not in all_cited_pages:
                        all_cited_pages.append(p)
                if info["document"] and info["document"] not in all_cited_docs:
                    all_cited_docs.append(info["document"])

        # Compute Citation Precision and Recall
        if is_negative_probe:
            # Negative probe: if no false citations are made, precision = 1.0, recall = 1.0
            citation_prec = 1.0 if len(answer_citations) == 0 else 0.0
            citation_rec = 1.0
            citation_f1 = 1.0 if len(answer_citations) == 0 else 0.0
            page_grounded = len(answer_citations) == 0
        else:
            if not all_cited_pages:
                citation_prec = 0.0
                citation_rec = 0.0
                citation_f1 = 0.0
                page_grounded = False
            else:
                correct_pages = [p for p in all_cited_pages if p in gold_pages_set]
                citation_prec = len(correct_pages) / len(all_cited_pages) if all_cited_pages else 0.0
                citation_rec = len(correct_pages) / len(gold_pages_set) if gold_pages_set else 0.0
                if (citation_prec + citation_rec) > 0:
                    citation_f1 = (2 * citation_prec * citation_rec) / (citation_prec + citation_rec)
                else:
                    citation_f1 = 0.0
                page_grounded = len(correct_pages) > 0

        citation_hallucination = len(hallucinated_pages) > 0 or any(
            cit > len(context_chunks) for cit in answer_citations
        )

        return QueryProvenanceResult(
            query_id=query_id,
            query=query,
            gold_document=gold_document,
            gold_pages=gold_pages,
            retrieved_chunk_count=len(context_chunks),
            claims=claim_records,
            cited_pages=all_cited_pages,
            cited_documents=all_cited_docs,
            citation_precision=citation_prec,
            citation_recall=citation_rec,
            citation_f1=citation_f1,
            page_grounded=page_grounded,
            citation_hallucination_detected=citation_hallucination,
            metadata={"explicit_hallucinated_pages": hallucinated_pages},
        )

    @classmethod
    def aggregate_results(
        cls, results: List[QueryProvenanceResult]
    ) -> Dict[str, Any]:
        """Aggregates provenance metrics across a test set."""
        if not results:
            return {
                "total_queries": 0,
                "mean_citation_precision": 0.0,
                "mean_citation_recall": 0.0,
                "mean_citation_f1": 0.0,
                "page_grounding_rate": 0.0,
                "citation_hallucination_rate": 0.0,
            }

        total = len(results)
        m_prec = sum(r.citation_precision for r in results) / total
        m_rec = sum(r.citation_recall for r in results) / total
        m_f1 = sum(r.citation_f1 for r in results) / total
        grounded_count = sum(1 for r in results if r.page_grounded)
        hallucination_count = sum(1 for r in results if r.citation_hallucination_detected)

        return {
            "total_queries": total,
            "mean_citation_precision": round(m_prec, 4),
            "mean_citation_recall": round(m_rec, 4),
            "mean_citation_f1": round(m_f1, 4),
            "page_grounding_rate": round(grounded_count / total, 4),
            "citation_hallucination_rate": round(hallucination_count / total, 4),
            "queries": [r.to_dict() for r in results],
        }
