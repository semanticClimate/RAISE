"""Proves the Stage 1 -> Stage 2 -> Stage 3 handoff actually works, by
running this module's ``target_blocks.json`` output straight through the
real, installed ``raise_html5_semantification`` package (the
``RAISE_HTML5_Semantification`` module, branch ``siddharth-semantification``)
with zero translation. If this test fails, the contract documented in
``docs/HANDOFF.md`` has drifted from what Stage 3 actually expects.

Skipped automatically if the Stage 3 package is not installed in the
current environment (e.g. ``pip install -e ../RAISE_HTML5_Semantification``
or the GitHub-installed wheel used by its Colab notebook).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raise_pdf_parsing.filter import filter_blocks
from raise_pdf_parsing.parser import parse_pdf

raise_html5_semantification = pytest.importorskip(
    "raise_html5_semantification",
    reason="RAISE_HTML5_Semantification (Stage 3) is not installed in this environment.",
)


def test_target_blocks_json_loads_into_stage3_without_translation(
    sample_pdf_path: Path, tmp_path: Path
) -> None:
    from raise_html5_semantification.loader import load_blocks

    target = filter_blocks(parse_pdf(sample_pdf_path))
    target_path = tmp_path / "target_blocks.json"
    target_path.write_text(json.dumps(target.model_dump(), indent=2), encoding="utf-8")

    blocks = load_blocks(target_path)
    assert len(blocks) == target.filtering_metadata.output_block_count
    # No alias translation should have been necessary: every block already
    # carries a non-empty, non-generated block_id from Stage 1.
    assert all(not getattr(b, "generated_block_id", False) for b in blocks)


def test_target_blocks_json_produces_valid_traceable_html(
    sample_pdf_path: Path, tmp_path: Path
) -> None:
    from raise_html5_semantification.main import build_report

    target = filter_blocks(parse_pdf(sample_pdf_path))
    target_path = tmp_path / "target_blocks.json"
    target_path.write_text(json.dumps(target.model_dump(), indent=2), encoding="utf-8")

    build_report(
        input_path=target_path,
        output_path=tmp_path / "report.html",
        validation_output_path=tmp_path / "validation_report.json",
        profile_output_path=tmp_path / "semantic_profile.json",
    )

    validation = json.loads((tmp_path / "validation_report.json").read_text())
    assert validation["ok"] is True
    assert validation["issues"] == []
    assert validation["input_block_count"] == target.filtering_metadata.output_block_count
    assert validation["traceable_element_count"] > 0

    html = (tmp_path / "report.html").read_text()
    assert 'data-source-block="p1-b002"' in html
    assert "RESEARCH ACTIVITIES" in html
    # Filtered-out content must never reach the Stage 3 output.
    assert "Balance Sheet" not in html
    assert "Circular No" not in html
