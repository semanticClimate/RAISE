"""End-to-end orchestration for Stage 1 (parsing) and Stage 2 (filtering).

This is the only module other code should import to run the pipeline --
it owns I/O (reading the PDF, writing JSON) and leaves `parser.py` /
`filter.py` as pure, easily-testable transformation functions.
"""

from __future__ import annotations

import json
from pathlib import Path

from raise_pdf_parsing.filter import filter_blocks
from raise_pdf_parsing.models import ReportBlocksDocument, TargetBlocksDocument
from raise_pdf_parsing.parser import parse_pdf


def _write_json(document, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document.model_dump(exclude_none=False), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def run_parse(pdf_path: str | Path, output_path: str | Path) -> ReportBlocksDocument:
    """Stage 1: PDF -> report_blocks.json."""
    report = parse_pdf(pdf_path)
    _write_json(report, Path(output_path))
    return report


def run_filter(
    input_path: str | Path, output_path: str | Path, report_output_path: str | Path | None = None
) -> TargetBlocksDocument:
    """Stage 2: report_blocks.json -> target_blocks.json (+ filtering_report.json)."""
    raw = json.loads(Path(input_path).read_text(encoding="utf-8"))
    report = ReportBlocksDocument.model_validate(raw)
    target = filter_blocks(report)
    _write_json(target, Path(output_path))
    if report_output_path:
        Path(report_output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_output_path).write_text(
            json.dumps(target.filtering_metadata.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return target


def run_pipeline(
    pdf_path: str | Path,
    parsed_output_path: str | Path,
    target_output_path: str | Path,
    filtering_report_path: str | Path | None = None,
) -> tuple[ReportBlocksDocument, TargetBlocksDocument]:
    """Stage 1 + Stage 2 end to end: PDF -> report_blocks.json -> target_blocks.json."""
    report = run_parse(pdf_path, parsed_output_path)
    target = filter_blocks(report)
    _write_json(target, Path(target_output_path))
    if filtering_report_path:
        Path(filtering_report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(filtering_report_path).write_text(
            json.dumps(target.filtering_metadata.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return report, target
