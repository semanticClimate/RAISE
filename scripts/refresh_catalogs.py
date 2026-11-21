"""
RAISE OKF Catalog Refresh & Visualizer Builder
==============================================
Regenerates all Open Knowledge Format (.okf.md) profiles for active documents in
`data/documents/` using newly structured chunks and updated metadata, and builds
the standalone interactive Cytoscape.js visualizer (`viz.html` and `index.html`).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import DOCUMENTS_DIR, PROCESSED_DIR, CATALOGS_DIR
from src.features.catalog.catalog_extractor import extract_okf_profile_from_pdf
from src.features.catalog.knowledge_catalog import KnowledgeCatalogRegistry
from src.features.catalog.visualizer import generate_okf_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RAISE_Catalog_Refresh")


def run_refresh():
    print("=" * 70)
    print("  RAISE OKF CATALOG REFRESH & VISUALIZER BUILDER")
    print("=" * 70)

    chunks_dir = PROCESSED_DIR / "chunks"
    CATALOGS_DIR.mkdir(parents=True, exist_ok=True)
    registry = KnowledgeCatalogRegistry.get_instance(catalog_dir=CATALOGS_DIR)

    pdf_files = sorted(DOCUMENTS_DIR.glob("*.pdf"))
    print(f"\n[STEP 1] Generating OKF profiles for {len(pdf_files)} active documents...")

    for pdf in pdf_files:
        safe_stem = pdf.stem.replace(" ", "_").replace("-", "_")
        chunks_file = chunks_dir / f"{safe_stem}_chunks.json"
        chunks = []
        if chunks_file.exists():
            try:
                chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  ▲ Notice reading {chunks_file.name}: {e}")

        # Extract & persist profile
        prof = extract_okf_profile_from_pdf(
            pdf_path=pdf,
            chunks=chunks,
            registry=registry,
        )
        print(f"  ✓ Refreshed OKF Profile: {prof.document_id} -> {prof.institution_name} ({prof.reporting_period})")

    # Step 2: Build HTML Visualizer
    print("\n[STEP 2] Generating interactive Cytoscape.js OKF Visualizer...")
    html_path = generate_okf_html(catalog_dir=CATALOGS_DIR)
    print(f"  ✓ Generated: {html_path} ({round(html_path.stat().st_size / 1024, 1)} KB)")

    viz_path = CATALOGS_DIR / "viz.html"
    print(f"  ✓ Generated: {viz_path} ({round(viz_path.stat().st_size / 1024, 1)} KB)")
    print("\n" + "=" * 70)
    print("  OKF REFRESH & VISUALIZATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_refresh()
