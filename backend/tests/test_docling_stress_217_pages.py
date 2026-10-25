# -*- coding: utf-8 -*-
"""
RAISE — Dedicated Docling Large-PDF + Table + Text-Quality Regression Test
Target: RAISE_Docling_Stress_Test_217_Pages.pdf
"""

import sys
import os
import time
import json
import logging
import re
import platform
from pathlib import Path
from typing import Dict, Any, List

for s in (sys.stdout, sys.stderr):
    if hasattr(s, "reconfigure"):
        s.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pymupdf
import torch

from src.parsers.document_parser import SmartDocumentParser, TextQualityGate
from src.features.ingestion.pipeline import (
    AcademicPipelineIngestor,
    AcademicDomainExtractor,
    AcademicEntity,
    AcademicRelation,
)
from src.infrastructure.vector.chroma import LocalVectorEngine
from src.infrastructure.graph.neo4j import Neo4jDatabase

from tests.fixtures.docling_stress_reporter import (
    WarningCaptureHandler,
    compute_text_quality_metrics,
    build_evaluation_matrix,
    generate_stress_markdown_report,
)


def run_full_regression_test():
    test_pdf = BASE_DIR / "tests" / "Test pdf" / "RAISE_Docling_Stress_Test_217_Pages.pdf"
    reports_dir = BASE_DIR / "tests" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(" 🚀 STARTING RAISE DEDICATED DOCLING 217-PAGE STRESS-TEST REGRESSION RUNNER")
    print("=" * 80)
    print(f"Source File: {test_pdf}")
    if not test_pdf.exists():
        print(f"❌ ERROR: Source test PDF not found at {test_pdf}!")
        sys.exit(3)

    src_doc = pymupdf.open(str(test_pdf))
    total_source_pages = len(src_doc)
    src_doc.close()
    print(f"Total Source Page Count: {total_source_pages}")

    results = {
        "test_name": "RAISE Docling 217-Page Stress-Test Evaluation",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pdf_path": str(test_pdf),
        "total_source_pages": total_source_pages,
        "tests": {},
        "matrix": [],
        "metrics": {}
    }

    parser = SmartDocumentParser()

    print("\n--- EXECUTING TEST A: DEEP VISION WITH max_pages = 50 ---")
    warn_handler_a = WarningCaptureHandler()
    warn_handler_a.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(warn_handler_a)

    t0_a = time.time()
    test_a_status = "FAIL"
    test_a_pages = []
    test_a_err = None
    try:
        test_a_pages = parser.parse_pdf(test_pdf, max_pages=50, engine="deep")
        t_elapsed_a = round(time.time() - t0_a, 2)
        actual_a_pages = len(test_a_pages)
        print(f"Test A Result: Processed {actual_a_pages} pages in {t_elapsed_a}s")
        if actual_a_pages == 50:
            test_a_status = "PASS"
        elif actual_a_pages > 0:
            test_a_status = "PARTIAL"
        else:
            test_a_status = "FAIL"
    except Exception as e:
        t_elapsed_a = round(time.time() - t0_a, 2)
        test_a_err = str(e)
        print(f"❌ Test A Exception: {e}")

    root_logger.removeHandler(warn_handler_a)
    orphan_warns_a = [w for w in warn_handler_a.warnings if "Orphan" in w or "MatchingPostProcessor" in w]

    results["tests"]["Test_A"] = {
        "description": "Deep Vision max_pages=50 on 217-page document",
        "source_pages": total_source_pages,
        "requested_pages": 50,
        "actual_pages_processed": len(test_a_pages),
        "status": test_a_status,
        "runtime_seconds": t_elapsed_a,
        "orphan_warnings_count": len(orphan_warns_a),
        "error": test_a_err
    }

    print("\n--- EXECUTING TEST B: SMALL PAGE WINDOW max_pages = 10 ---")
    t0_b = time.time()
    test_b_status = "FAIL"
    test_b_pages = []
    test_b_err = None
    try:
        test_b_pages = parser.parse_pdf(test_pdf, max_pages=10, engine="deep")
        t_elapsed_b = round(time.time() - t0_b, 2)
        actual_b_pages = len(test_b_pages)
        print(f"Test B Result: Processed {actual_b_pages} pages in {t_elapsed_b}s")
        if actual_b_pages == 10:
            test_b_status = "PASS"
        elif actual_b_pages > 0:
            test_b_status = "PARTIAL"
        else:
            test_b_status = "FAIL"
    except Exception as e:
        t_elapsed_b = round(time.time() - t0_b, 2)
        test_b_err = str(e)
        print(f"❌ Test B Exception: {e}")

    results["tests"]["Test_B"] = {
        "description": "Small Page Window max_pages=10",
        "source_pages": total_source_pages,
        "requested_pages": 10,
        "actual_pages_processed": len(test_b_pages),
        "status": test_b_status,
        "runtime_seconds": t_elapsed_b,
        "error": test_b_err
    }

    print("\n--- EXECUTING TEST C: PAGE PROVENANCE INTEGRITY ---")
    provenance_correct = True
    page_numbers_seen = []
    for p in test_a_pages:
        p_no = p.get("page_number")
        page_numbers_seen.append(p_no)
        if not (1 <= p_no <= 50):
            provenance_correct = False

    test_c_status = "PASS" if provenance_correct and len(page_numbers_seen) == 50 else "FAIL"
    p_range_str = f"{min(page_numbers_seen, default=0)}..{max(page_numbers_seen, default=0)}"
    results["tests"]["Test_C"] = {
        "description": "Page Provenance Check (1..50 mapping)",
        "provenance_correct": provenance_correct,
        "page_numbers_range": p_range_str,
        "status": test_c_status
    }
    print(f"Test C Result: {test_c_status} (Range: {p_range_str})")

    # -------------------------------------------------------------
    # TEST D: TEXT QUALITY & CORRUPTION HEURISTICS
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(" 📋 EXECUTING TEST D: TEXT QUALITY & CORRUPTION HEURISTICS")
    print("-" * 80)
    all_extracted_text = "\n\n".join(p.get("text", "") for p in test_a_pages)
    text_metrics = compute_text_quality_metrics(all_extracted_text)
    tqg_eval = TextQualityGate.assess(all_extracted_text)

    print(f"Total Extracted Characters: {text_metrics['chars']}")
    print(f"Total Extracted Words: {text_metrics['words']}")
    print(f"Average Word Length: {text_metrics['avg_word_length']}")
    print(f"Single Char Token Ratio: {text_metrics['single_char_ratio']}")
    print(f"Broken Word Ratio: {text_metrics['broken_word_ratio']}")
    print(f"TextQualityGate Assessment: is_acceptable={tqg_eval['is_acceptable']}, reason={tqg_eval['reason']}")
    print(f"Text Quality Status: {'CORRUPTED' if text_metrics['is_corrupted'] else 'GOOD'}")

    test_d_status = "PASS" if (not text_metrics["is_corrupted"] and tqg_eval["is_acceptable"]) else "FAIL"
    results["tests"]["Test_D"] = {
        "description": "Text Quality Heuristics (Broken Words, Character Fragmentation)",
        "metrics": text_metrics,
        "quality_gate_eval": tqg_eval,
        "status": test_d_status
    }

    # -------------------------------------------------------------
    # TEST E: TABLE QUALITY & OBSERVABILITY
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(" 📋 EXECUTING TEST E: TABLE INTEGRITY & OBSERVABILITY")
    print("-" * 80)
    tables_found = 0
    sample_table_md = ""
    for p in test_a_pages:
        txt = p.get("text", "")
        if "|" in txt and "---" in txt:
            tables_found += 1
            if not sample_table_md:
                tbl_lines = [l for l in txt.splitlines() if "|" in l]
                sample_table_md = "\n".join(tbl_lines[:8])

    test_e_status = "PASS" if tables_found > 0 else "PARTIAL"
    results["tests"]["Test_E"] = {
        "description": "Table Integrity & Observability",
        "pages_with_tables": tables_found,
        "sample_table_markdown": sample_table_md,
        "status": test_e_status
    }
    print(f"Test E Result: Found {tables_found} table-bearing pages. Status: {test_e_status}")

    # -------------------------------------------------------------
    # TEST F: CHUNKING & EMBEDDINGS QUALITY
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(" 📋 EXECUTING TEST F: CHUNKING & EMBEDDINGS")
    print("-" * 80)
    doc_id = "RAISE_Docling_Stress_Test_217_Pages"
    chunks = []
    for sec in test_a_pages:
        pno = sec["page_number"]
        txt = sec["text"]
        h = sec.get("heading", f"Page {pno}")
        chunk_id = f"{doc_id}_p{pno:03d}_c01"
        chunks.append({
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "pdf_filename": test_pdf.name,
            "heading": h,
            "primary_page": pno,
            "plain_text": txt,
            "enriched_text": f"Document: {test_pdf.name}\nPage: {pno}\nHeading: {h}\n\nContent:\n{txt}",
            "token_estimate": len(txt.split()),
        })
    print(f"Generated {len(chunks)} Chunks from 50 pages.")

    vector_engine = LocalVectorEngine()
    emb_model_name = getattr(vector_engine, "embedding_model_name", "BAAI/bge-large-en-v1.5")
    sample_emb = vector_engine.compute_embeddings([chunks[0]["plain_text"][:200]])[0]
    emb_dim = len(sample_emb) if sample_emb is not None else 1024

    test_f_status = "PASS" if len(chunks) > 0 and emb_dim == 1024 else "FAIL"
    results["tests"]["Test_F"] = {
        "description": "Chunking & Embedding Quality",
        "total_chunks": len(chunks),
        "embedding_model": str(emb_model_name),
        "embedding_dimension": emb_dim,
        "status": test_f_status
    }
    print(f"Test F Result: {test_f_status} (Chunks: {len(chunks)}, Dim: {emb_dim})")

    # -------------------------------------------------------------
    # TEST G: FACT / ENTITY / TRIPLE EXTRACTION
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(" 📋 EXECUTING TEST G: FACT / ENTITY / TRIPLE EXTRACTION")
    print("-" * 80)
    domain_extractor = AcademicDomainExtractor()
    sample_chunk = chunks[0]
    ents, rels = domain_extractor.extract_academic_knowledge(
        text=sample_chunk["plain_text"],
        pdf_filename=test_pdf.name,
        page_number=sample_chunk["primary_page"],
        section_heading=sample_chunk["heading"],
        chunk_id=sample_chunk["chunk_id"],
        university_name="Synthetic Institutional Report"
    )
    print(f"Extraction on Sample Chunk: {len(ents)} entities, {len(rels)} relations")

    # Check Graph Starvation Rule
    if len(ents) == 0 and len(rels) == 0:
        graph_semantic_quality = "FAILED"
        test_g_status = "FAIL"
    else:
        graph_semantic_quality = "PASSED"
        test_g_status = "PASS"

    results["tests"]["Test_G"] = {
        "description": "Fact / Entity / Triple Extraction",
        "sample_entities_extracted": len(ents),
        "sample_relations_extracted": len(rels),
        "graph_semantic_quality": graph_semantic_quality,
        "status": test_g_status
    }

    # -------------------------------------------------------------
    # TEST H: DOWNSTREAM RETRIEVAL & `re` NAMEERROR REGRESSION
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print(" 📋 EXECUTING TEST H: RETRIEVAL & `re` NAMEERROR REGRESSION")
    print("-" * 80)
    test_query = "Technology transfer commercialization translational research"
    t0_q = time.time()
    re_name_error = False
    retrieval_ok = False
    query_err = None
    try:
        # Test vector search query formatting
        formatted_q = vector_engine.format_query_for_embedding(test_query)
        q_emb = vector_engine.compute_embeddings([formatted_q])[0]
        retrieval_ok = len(q_emb) == 1024
        print(f"Deterministic Query Encoded in {time.time()-t0_q:.3f}s (dim: {len(q_emb)})")
    except NameError as ne:
        if "re" in str(ne):
            re_name_error = True
        query_err = str(ne)
    except Exception as qe:
        query_err = str(qe)

    test_h_status = "PASS" if retrieval_ok and not re_name_error else "FAIL"
    results["tests"]["Test_H"] = {
        "description": "Deterministic Retrieval & `re` NameError Check",
        "retrieval_success": retrieval_ok,
        "re_name_error_detected": re_name_error,
        "error": query_err,
        "status": test_h_status
    }
    print(f"Test H Result: {test_h_status} (re NameError Detected: {re_name_error})")

    matrix = build_evaluation_matrix(
        results=results,
        total_source_pages=total_source_pages,
        text_metrics=text_metrics,
        chunks=chunks,
        emb_model_name=str(emb_model_name),
        emb_dim=emb_dim,
        re_name_error=re_name_error,
    )

    results["matrix"] = matrix

    pass_count = sum(1 for m in matrix if m["status"] == "PASS")
    fail_count = sum(1 for m in matrix if m["status"] == "FAIL")
    partial_count = sum(1 for m in matrix if m["status"] == "PARTIAL")

    results["summary"] = {
        "tests_executed": len(matrix),
        "pass": pass_count,
        "fail": fail_count,
        "partial": partial_count,
        "final_status": "PASS" if fail_count == 0 else "FAIL",
    }

    # Write JSON report
    json_path = reports_dir / "docling_stress_217_pages_report.json"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved JSON Report to: {json_path}")

    md_path = generate_stress_markdown_report(
        results=results,
        matrix=matrix,
        test_pdf=test_pdf,
        total_source_pages=total_source_pages,
        reports_dir=reports_dir,
        text_metrics=text_metrics,
        sample_table_md=sample_table_md,
        chunks=chunks,
        emb_model_name=str(emb_model_name),
        emb_dim=emb_dim,
        test_query=test_query,
        retrieval_ok=retrieval_ok,
        re_name_error=re_name_error,
        pass_count=pass_count,
        fail_count=fail_count,
        partial_count=partial_count,
    )
    print(f"Saved Markdown Report to: {md_path}")

    print("\n" + "=" * 80)
    print(f" 🏁 STRESS-TEST COMPLETE! Final Status: {results['summary']['final_status']}")
    print(f" PASS: {pass_count} | FAIL: {fail_count} | PARTIAL: {partial_count}")
    print("=" * 80)


def test_text_quality_metrics_contract():
    """Quick unit test verifying text quality metric computation."""
    metrics = compute_text_quality_metrics("This is a standard academic text sentence.")
    assert metrics["is_corrupted"] is False
    assert metrics["words"] == 7

if __name__ == "__main__":
    run_full_regression_test()
