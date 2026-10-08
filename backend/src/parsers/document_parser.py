"""
RAISE Adaptive Document Parser (Docling + PyMuPDF Hybrid)
==========================================================
Purpose:
  Intelligently chooses the best parsing engine based on document complexity:
  - Uses Docling (TableFormer / LayoutFormer) for layout-heavy, multi-column, table-rich documents.
  - Uses PyMuPDF (fitz) for fast text-first streaming and fallback when ML parser is unavailable.

Architecture & Maintenance:
  This module acts as the unified high-level facade. Detailed implementation sub-components:
  - `src.parsers.text_quality.py`: Normalization and TextQualityGate evaluating OCR/parsing health.
  - `src.parsers.pymupdf_engine.py`: Fast geometric block layout parser and table extractor.
  - `src.parsers.docling_engine.py`: Neural table recovery and layout recognition engine.

Backward Compatibility:
  All public classes, methods, and functions (`SmartDocumentParser`, `DoclingLayoutParser`,
  `TextQualityGate`, `normalize_text`, `coalesce_markdown_sections`) remain 100% backward compatible.

Author: RAISE Core Architecture Team
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional

# Re-export text quality and normalization primitives
from src.parsers.text_quality import (
    TextQualityGate,
    normalize_text,
    coalesce_markdown_sections,
)
from src.parsers.pymupdf_engine import PyMuPDFParserEngine
from src.parsers.docling_engine import DoclingParserEngine, HAS_DOCLING


class SmartDocumentParser:
    """
    Dual-engine parser that automatically routes between Docling & PyMuPDF.
    """

    def __init__(self):
        self._docling_engine = DoclingParserEngine()
        self._pymupdf_engine = PyMuPDFParserEngine()

    @property
    def _docling_converter_no_ocr(self):
        return self._docling_engine._docling_converter_no_ocr

    @_docling_converter_no_ocr.setter
    def _docling_converter_no_ocr(self, val):
        self._docling_engine._docling_converter_no_ocr = val

    @property
    def _docling_converter_ocr(self):
        return self._docling_engine._docling_converter_ocr

    @_docling_converter_ocr.setter
    def _docling_converter_ocr(self, val):
        self._docling_engine._docling_converter_ocr = val

    def get_converter(self, do_ocr: bool = False):
        """Delegates to internal Docling converter factory."""
        return self._docling_engine.get_converter(do_ocr=do_ocr)

    def has_scanned_pages(self, pdf_path: Path, max_check: int = 20) -> bool:
        """Checks if a PDF document contains predominantly scanned pages."""
        return self._pymupdf_engine.has_scanned_pages(pdf_path=pdf_path, max_check=max_check)

    def should_use_docling(self, pdf_path: Path, max_check_pages: int = 5) -> bool:
        """
        Always use Docling as the primary layout and table parsing engine whenever available.
        Docling seamlessly handles text, scanned image OCR, multi-column articles, and tables.
        """
        return HAS_DOCLING

    def parse_pdf(
        self,
        pdf_path: Path | str,
        max_pages: Optional[int] = None,
        engine: str = "auto",
        full_potential: bool = False,
        extract_tables: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Extracts structured page/chunk records using the optimal engine.
        - engine: 'auto' | 'fast' (PyMuPDF: ~2s) | 'deep' | 'docling' (Docling TableFormer: neural cell recovery)
        Removes arbitrary max caps to support full-document processing in Deep Vision / Docling mode.
        """
        pdf_path = Path(pdf_path)
        eng_lower = str(engine or "auto").lower()

        use_docling = False
        if eng_lower in ("deep", "docling") or full_potential:
            use_docling = HAS_DOCLING
        elif eng_lower == "fast":
            use_docling = False
        else:  # auto
            use_docling = self.should_use_docling(pdf_path)

        if use_docling:
            pages = self._docling_engine.parse(pdf_path=pdf_path, max_pages=max_pages)
            if pages is not None:
                return pages

        # Fallback to high-speed PyMuPDF parser
        return self._pymupdf_engine.parse(pdf_path=pdf_path, max_pages=max_pages)

    # Expose helper static methods for backward compatibility
    @staticmethod
    def normalize_text(text: str) -> str:
        return normalize_text(text)

    @staticmethod
    def coalesce_markdown_sections(
        sections: List[str],
        target_words: int = 450,
        min_words: int = 120,
        max_words: int = 700,
    ) -> List[str]:
        return coalesce_markdown_sections(
            sections=sections,
            target_words=target_words,
            min_words=min_words,
            max_words=max_words,
        )


# Backward-compatible alias conforming to RAISE Canonical Implementation Map
DoclingLayoutParser = SmartDocumentParser

__all__ = [
    "SmartDocumentParser",
    "DoclingLayoutParser",
    "TextQualityGate",
    "normalize_text",
    "coalesce_markdown_sections",
]
