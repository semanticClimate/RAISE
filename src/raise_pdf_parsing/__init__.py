"""RAISE PDF Parsing + Filtering (Stage 1 + Stage 2).

Owner: Person B.

Converts a raw university annual-report PDF into ``report_blocks.json``
(layout-aware text/table blocks with full traceability), then filters that
into ``target_blocks.json`` (research-assessment content only), ready to
hand to the ``RAISE_HTML5_Semantification`` module (Stage 3).
"""

from raise_pdf_parsing.main import run_filter, run_parse, run_pipeline

__all__ = ["run_parse", "run_filter", "run_pipeline"]
__version__ = "0.1.0"
