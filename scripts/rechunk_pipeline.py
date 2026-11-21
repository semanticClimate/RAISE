"""
RAISE Re-Chunking & Vector Store Synchronization Engine
=======================================================
Deletes previous chunk artifacts and re-runs Graph-Guided Adaptive Hierarchical
Chunking with recursive parent-child boundary preservation, table header retention,
and vector index synchronization.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import DOCUMENTS_DIR, PROCESSED_DIR
from src.parsers.document_parser import SmartDocumentParser
from src.chunking.pipeline import AdaptiveChunkingPipeline
from src.features.ingestion.institution_resolver import identify_institution
from src.features.ingestion.manifest_manager import update_manifest_entry
from src.infrastructure.vector.chroma import LocalVectorEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RAISE_Rechunker")


def run_rechunking():
    print("=" * 70)
    print("  RAISE VAULT RE-CHUNKING & CHROMADB VECTOR SYNC")
    print("=" * 70)

    chunks_dir = PROCESSED_DIR / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    # 1. Delete previous chunk files
    print("\n[STEP 1] Purging previous chunk files from data/processed/chunks/...")
    old_files = list(chunks_dir.glob("*.json"))
    for f in old_files:
        try:
            f.unlink()
            print(f"  ✓ Deleted: {f.name}")
        except Exception as e:
            print(f"  ✕ Could not delete {f.name}: {e}")

    # 2. Discover active documents
    print("\n[STEP 2] Discovering documents in data/documents/...")
    docs = sorted(DOCUMENTS_DIR.glob("*.pdf"))
    print(f"  Found {len(docs)} documents: {[d.name for d in docs]}")

    parser = SmartDocumentParser()
    chunker = AdaptiveChunkingPipeline()
    vector_engine = LocalVectorEngine()

    total_children = 0
    total_parents = 0

    for pdf_path in docs:
        doc_id = pdf_path.stem.replace(" ", "_").replace("-", "_")
        print(f"\n──────────────────────────────────────────────────────────────────────")
        print(f"-> Processing: {pdf_path.name} (ID: {doc_id})")

        t0 = time.time()
        # Parse document structure
        sections = parser.parse_pdf(pdf_path, engine="fast")
        parse_dur = round(time.time() - t0, 2)
        print(f"   Parsed {len(sections)} sections in {parse_dur}s")

        # Check for pre-extracted Docling/OCR library file to enrich sparse/graphic pages (e.g. Page 9 charts/tables)
        lib_candidates = [
            PROJECT_ROOT / "data" / "library" / f"{doc_id}_extracted.md",
            PROJECT_ROOT / "data" / "library" / f"{pdf_path.stem}_extracted.md",
        ]
        page_map = {}
        for lcf in lib_candidates:
            if lcf.exists():
                try:
                    txt = lcf.read_text(encoding="utf-8")
                    parts = txt.split("\n---\n")
                    for p in parts:
                        m = re.search(r"\[Page\s+(\d+)\]", p)
                        if m:
                            pnum = int(m.group(1))
                            body = re.sub(r"<a id=[^>]+></a>\s*|### Chunk [^\n]+\n|> \*\*Context Breadcrumb:\*\*[^\n]+\n", "", p).strip()
                            if pnum not in page_map or len(body) > len(page_map[pnum]):
                                page_map[pnum] = body
                    print(f"   ✓ Loaded library extraction: {lcf.name} ({len(page_map)} pages mapped)")
                    break
                except Exception as e:
                    print(f"   ▲ Library notice: {e}")

        if page_map:
            enriched_pages = 0
            for sec in sections:
                pno = int(sec.get("page_number") or 1)
                cur_text = (sec.get("text") or "").strip()
                if pno in page_map:
                    lib_text = page_map[pno].strip()
                    if len(lib_text) > len(cur_text) and len(cur_text) < 150:
                        sec["text"] = lib_text
                        sec["is_table"] = True if ("|" in lib_text or "share" in lib_text.lower() or "nature index" in lib_text.lower()) else sec.get("is_table", False)
                        enriched_pages += 1
            if enriched_pages > 0:
                print(f"   ✓ Enriched {enriched_pages} sparse/graphic pages from library extracted markdown")

        # Resolve institution & period
        sample_text = ""
        for sec in sections[:10]:
            t = sec.get("text", "")
            if len(t.strip()) > 30 and not t.strip().startswith("[Page"):
                sample_text = t
                break
        uni, period = identify_institution(pdf_path, sample_text)
        print(f"   Institution: {uni} | Period: {period}")

        # Execute Adaptive Hierarchical Chunking
        t_chunk = time.time()
        res = chunker.process_document(
            parsed_sections=sections,
            document_id=doc_id,
            filename=pdf_path.name,
            university=uni,
            reporting_period=period,
            total_pages=len(sections),
            strategy_override="recursive",
        )
        chunk_dur = round(time.time() - t_chunk, 2)

        child_chunks = res["child_chunks"]
        parent_chunks = res["parent_chunks"]
        diag = res["diagnostic_report"]

        print(f"   Generated {len(child_chunks)} child chunks and {len(parent_chunks)} parent chunks in {chunk_dur}s")

        # Save new chunk artifacts
        chunks_file = chunks_dir / f"{doc_id}_chunks.json"
        parent_file = chunks_dir / f"{doc_id}_parent_chunks.json"
        diag_file = chunks_dir / f"{doc_id}_chunking_diagnostics.json"

        chunks_file.write_text(json.dumps([c.to_dict() for c in child_chunks], indent=2), encoding="utf-8")
        parent_file.write_text(json.dumps([p.to_dict() for p in parent_chunks], indent=2), encoding="utf-8")
        diag_file.write_text(json.dumps(diag.to_dict(), indent=2), encoding="utf-8")
        print(f"   ✓ Wrote {chunks_file.name} ({round(chunks_file.stat().st_size / 1024, 1)} KB)")
        print(f"   ✓ Wrote {parent_file.name} ({round(parent_file.stat().st_size / 1024, 1)} KB)")
        print(f"   ✓ Wrote {diag_file.name}")

        # Synchronize vector index in ChromaDB
        t_vec = time.time()
        try:
            vector_engine.delete_document(pdf_filename=pdf_path.name, doc_id=doc_id)
            vector_count = vector_engine.ingest_chunks([c.to_dict() for c in child_chunks], doc_id=doc_id)
            vec_dur = round(time.time() - t_vec, 2)
            print(f"   ✓ ChromaDB Synced: {vector_count} vector embeddings in {vec_dur}s")
        except Exception as e:
            print(f"   ▲ ChromaDB Notice: {e}")

        # Update manifest
        try:
            update_manifest_entry(
                output_dir=PROCESSED_DIR,
                pdf_path=pdf_path,
                pages_processed=len(sections),
                chunks_count=len(child_chunks),
            )
            print(f"   ✓ Manifest updated for {pdf_path.name}")
        except Exception as e:
            print(f"   ▲ Manifest notice: {e}")

        total_children += len(child_chunks)
        total_parents += len(parent_chunks)

    print("\n" + "=" * 70)
    print(f"  RE-CHUNKING COMPLETE: {total_children} child chunks, {total_parents} parent chunks across {len(docs)} docs")
    print("=" * 70)


if __name__ == "__main__":
    run_rechunking()
