from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from raise_pdf_parsing.cli import app

runner = CliRunner()


def test_run_command_writes_all_three_outputs(sample_pdf_path: Path, tmp_path: Path) -> None:
    parsed_output = tmp_path / "report_blocks.json"
    target_output = tmp_path / "target_blocks.json"
    report_output = tmp_path / "filtering_report.json"

    result = runner.invoke(
        app,
        [
            "run",
            "--input",
            str(sample_pdf_path),
            "--parsed-output",
            str(parsed_output),
            "--target-output",
            str(target_output),
            "--report-output",
            str(report_output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert parsed_output.exists()
    assert target_output.exists()
    assert report_output.exists()

    target = json.loads(target_output.read_text())
    assert target["blocks"]
    assert target["filtering_metadata"]["output_block_count"] == len(target["blocks"])


def test_parse_then_filter_commands_separately(sample_pdf_path: Path, tmp_path: Path) -> None:
    parsed_output = tmp_path / "report_blocks.json"
    target_output = tmp_path / "target_blocks.json"
    report_output = tmp_path / "filtering_report.json"

    parse_result = runner.invoke(
        app, ["parse", "--input", str(sample_pdf_path), "--output", str(parsed_output)]
    )
    assert parse_result.exit_code == 0, parse_result.output
    assert parsed_output.exists()

    filter_result = runner.invoke(
        app,
        [
            "filter",
            "--input",
            str(parsed_output),
            "--output",
            str(target_output),
            "--report",
            str(report_output),
        ],
    )
    assert filter_result.exit_code == 0, filter_result.output
    assert target_output.exists()
