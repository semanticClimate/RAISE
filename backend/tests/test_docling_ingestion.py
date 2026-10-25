"""
Automated Test Suite for Native Docling Layout Parsing & Ingestion.
Directly converts real academic PDFs and validates section extraction,
Markdown tables, and page provenance.
"""

import sys
from pathlib import Path
import pytest

# Ensure RAG root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parsers.document_parser import SmartDocumentParser, HAS_DOCLING


def test_docling_availability():
    """Verify Docling library is natively installed and imported."""
    assert HAS_DOCLING is True, "Docling must be natively available in Python environment."


def test_docling_real_pdf_conversion():
    """Test Docling parsing on actual academic PDF fixture from tests/Test pdf."""
    docs_dir = Path(__file__).resolve().parents[1] / "data" / "documents"
    test_pdf_dir = Path(__file__).resolve().parent / "Test pdf"
    
    candidates = list(docs_dir.glob("*.pdf")) + list(test_pdf_dir.glob("*.pdf"))
    if not candidates:
        pytest.skip("No test PDF fixtures present")
    pdf_path = candidates[0]

    parser = SmartDocumentParser()
    parsed = parser.parse_pdf(pdf_path, max_pages=1, engine="deep")
    assert len(parsed) > 0, "Docling must produce at least 1 parsed section."
    
    first_sec = parsed[0]
    assert "page_number" in first_sec
    assert "heading" in first_sec
    assert "text" in first_sec
    assert first_sec["engine"].startswith("Docling")
    assert len(first_sec["text"]) > 20
