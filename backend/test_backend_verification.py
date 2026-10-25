#!/usr/bin/env python3
"""
Backend Verification Test Suite
===============================
Standard verification tests provided by the Frontend Team to validate:
  1. Syntax & Bytecode Compilation
  2. Frontend Payload Contract & Subgraph Preservation
  3. Citation Provenance & Single-Page PDF URLs
  4. Document Resolver Stem & Case-Insensitive Matching
  5. FastAPI Route Table Integrity

Usage:
  cd backend
  python test_backend_verification.py
  # or
  pytest test_backend_verification.py -v
"""

import compileall
import os
import sys
import unittest
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class Test1_SyntaxAndBytecode(unittest.TestCase):
    """Test 1: Compiles all backend files to guarantee zero syntax or import errors."""

    def test_bytecode_compilation(self):
        targets = [
            BACKEND_DIR / "src",
            BACKEND_DIR / "app.py",
            BACKEND_DIR / "main.py",
            BACKEND_DIR / "server.py",
        ]
        for t in targets:
            if t.is_dir():
                success = compileall.compile_dir(str(t), quiet=1, force=False)
            else:
                success = compileall.compile_file(str(t), quiet=1, force=False)
            self.assertTrue(success, f"Bytecode compilation failed for: {t}")


class Test2_FrontendPayloadContract(unittest.TestCase):
    """Test 2: Tests QueryService._format_frontend_payload()."""

    def setUp(self):
        from src.features.query.service import QueryService
        # Initialize QueryService with dummy rag_engine
        self.service = QueryService.__new__(QueryService)

    def test_subgraph_and_claims_preservation(self):
        raw_result = {
            "grounded_answer": "According to the annual report, research expenditures were 45 crores.",
            "citations": [{"citation_index": 1, "pdf_filename": "Annual Report 2022-23.pdf", "primary_page": 10}],
            "subgraph": {
                "nodes": [{"id": "n1", "label": "Institution", "name": "NIPGR"}],
                "edges": [{"id": "e1", "source": "n1", "target": "n2", "type": "REPORTED"}],
            },
            "verified_claims": [
                {"claim_id": "c1", "text": "Research expenditures were 45 crores.", "status": "VERIFIED"}
            ],
            "top_chunks": [
                {"chunk_id": "chk_1", "text": "Expenditure summary...", "similarity": 0.92}
            ],
            "quality_gate_decision": "accept",
            "execution_time": 1.45,
            "latency_sec": 1.45,
        }

        payload = self.service._format_frontend_payload(raw_result, "What were research expenditures?", "sess_123")

        # 1. Subgraph must not be empty
        self.assertGreater(len(payload["subgraph"]["nodes"]), 0, "Subgraph nodes must not be stripped to empty []")
        self.assertGreater(len(payload["subgraph"]["edges"]), 0, "Subgraph edges must not be stripped to empty []")
        self.assertEqual(payload["subgraph"]["nodes"][0]["name"], "NIPGR")

        # 2. Verified claims & top chunks must be preserved
        self.assertEqual(len(payload["verified_claims"]), 1)
        self.assertEqual(payload["verified_claims"][0]["claim_id"], "c1")
        self.assertEqual(len(payload["top_chunks"]), 1)
        self.assertEqual(payload["top_chunks"][0]["chunk_id"], "chk_1")

        # 3. Quality gate decision must be accepted
        self.assertEqual(payload["quality_gate_decision"], "accept")
        self.assertEqual(payload["status"], "SUCCESS")

    def test_refusal_preservation(self):
        # Query with insufficient evidence
        raw_result = {
            "grounded_answer": "INSUFFICIENT_EVIDENCE: The documents do not specify funding for project X.",
            "citations": [],
            "subgraph": {"nodes": [], "edges": []},
            "verified_claims": [],
            "top_chunks": [],
            "quality_gate_decision": "unable_to_verify",
        }

        payload = self.service._format_frontend_payload(raw_result, "What is funding for project X?", "sess_124")

        # Refusal queries must retain quality_gate_decision: "unable_to_verify"
        self.assertEqual(payload["quality_gate_decision"], "unable_to_verify")
        self.assertNotIn("INSUFFICIENT_EVIDENCE:", payload["grounded_answer"])


class Test3_CitationProvenance(unittest.TestCase):
    """Test 3: Tests citation_sanitizer.py."""

    def test_citation_normalization_and_urls(self):
        from src.features.agent.citation_sanitizer import build_evidence_citations

        ordered_chunks = [
            {
                "id": "chk_p014_0",
                "text": "The institute published 85 high-impact papers in FY 2023.",
                "similarity": 0.94,
                "metadata": {
                    "pdf_filename": "/var/app/data/documents/Annual Report 2022-23.pdf",
                    "primary_page": 14,
                    "doc_id": "Annual Report 2022-23",
                    "heading": "Publications Summary",
                },
            }
        ]

        citations = build_evidence_citations(ordered_chunks)
        self.assertEqual(len(citations), 1)
        cit = citations[0]

        # 1. Basename normalization (no directory prefix)
        self.assertEqual(cit["pdf_filename"], "Annual Report 2022-23.pdf")

        # 2. Accurate single-page URL generation
        self.assertIn("/api/pdf/", cit["page_url"])
        self.assertIn("/pages/14/pdf", cit["page_url"])
        self.assertIn("/api/pdf/", cit["page_view_url"])
        self.assertIn("/pages/14/view", cit["page_view_url"])
        self.assertEqual(cit["primary_page"], 14)


class Test4_DocumentResolver(unittest.TestCase):
    """Test 4: Verifies _resolve_document_file() in documents.py."""

    def test_stem_and_case_insensitive_matching(self):
        from src.api.routers.documents import _resolve_document_file

        # Check resolution against physical files present in data/documents
        target_name = "Annual Report 2022-23.pdf"
        doc_dir = BACKEND_DIR / "data" / "documents"
        target_file = doc_dir / target_name

        if not target_file.exists():
            self.skipTest(f"Physical file {target_name} not found in {doc_dir}")

        # 1. Exact match
        res_exact = _resolve_document_file(target_name)
        self.assertIsNotNone(res_exact)
        self.assertEqual(res_exact.name, target_name)

        # 2. Stem match (no .pdf extension)
        res_stem = _resolve_document_file("Annual Report 2022-23")
        self.assertIsNotNone(res_stem)
        self.assertEqual(res_stem.name, target_name)

        # 3. URI-encoded match (%20)
        res_encoded = _resolve_document_file("Annual%20Report%202022-23.pdf")
        self.assertIsNotNone(res_encoded)
        self.assertEqual(res_encoded.name, target_name)

        # 4. Case-insensitive match
        res_lower = _resolve_document_file("annual report 2022-23.pdf")
        self.assertIsNotNone(res_lower)
        self.assertEqual(res_lower.name.lower(), target_name.lower())


class Test5_FastAPIRouteTableIntegrity(unittest.TestCase):
    """Test 5: Checks that all endpoints expected by the frontend are registered."""

    def test_required_routes_registered(self):
        from app import app

        registered_routes = []
        for r in app.routes:
            if hasattr(r, "path") and r.path:
                registered_routes.append((r.path, getattr(r, "methods", None)))
            elif hasattr(r, "original_router") and hasattr(r.original_router, "routes"):
                for sub_r in r.original_router.routes:
                    if hasattr(sub_r, "path") and sub_r.path:
                        registered_routes.append((sub_r.path, getattr(sub_r, "methods", None)))

        expected_endpoints = [
            ("GET", "/api/health"),
            ("GET", "/api/pdf/{filename}"),
            ("GET", "/api/pdf/{filename}/pages/{page_number}/view"),
            ("GET", "/api/pdf/{filename}/pages/{page_number}/pdf"),
            ("GET", "/api/documents"),
            ("POST", "/api/chat"),
            ("POST", "/api/chat/stream"),
        ]

        for method, expected_path in expected_endpoints:
            match = False
            for route_path, methods in registered_routes:
                if route_path == expected_path:
                    if methods is None or method in methods:
                        match = True
                        break
            self.assertTrue(
                match,
                f"Required endpoint [{method} {expected_path}] is NOT registered in app.routes!",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
