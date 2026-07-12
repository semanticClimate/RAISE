from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from raise_pdf_parsing.main import run_filter, run_parse, run_pipeline

app = typer.Typer(help="RAISE Stage 1 (PDF parsing) + Stage 2 (token-budget filtering).")
console = Console()

RAW_PDF_OPTION = typer.Option(Path("data/01_raw/report.pdf"), "--input", "-i")
PARSED_INPUT_OPTION = typer.Option(Path("data/02_parsed/report_blocks.json"), "--input", "-i")
PARSED_OUTPUT_OPTION = typer.Option(Path("data/02_parsed/report_blocks.json"), "--output", "-o")
TARGET_OUTPUT_OPTION = typer.Option(Path("data/03_filtered/target_blocks.json"), "--output", "-o")
FILTERING_REPORT_OPTION = typer.Option(Path("data/03_filtered/filtering_report.json"), "--report")
PARSED_OUTPUT_RUN_OPTION = typer.Option(
    Path("data/02_parsed/report_blocks.json"), "--parsed-output"
)
TARGET_OUTPUT_RUN_OPTION = typer.Option(
    Path("data/03_filtered/target_blocks.json"), "--target-output"
)
REPORT_OUTPUT_RUN_OPTION = typer.Option(
    Path("data/03_filtered/filtering_report.json"), "--report-output"
)


@app.command()
def parse(
    input: Path = RAW_PDF_OPTION,
    output: Path = PARSED_OUTPUT_OPTION,
) -> None:
    """Stage 1: extract layout-aware blocks from a raw annual-report PDF."""
    report = run_parse(input, output)
    console.print(f"[green]Parsed[/green] {report.page_count} pages, {len(report.blocks)} blocks.")
    console.print(f"[green]Wrote:[/green] {output}")


@app.command("filter")
def filter_cmd(
    input: Path = PARSED_INPUT_OPTION,
    output: Path = TARGET_OUTPUT_OPTION,
    report: Path = FILTERING_REPORT_OPTION,
) -> None:
    """Stage 2: remove non-research pages and boilerplate."""
    target = run_filter(input, output, report)
    meta = target.filtering_metadata
    console.print(
        f"[green]Kept[/green] {meta.output_block_count}/{meta.input_block_count} blocks, "
        f"excluded {len(meta.excluded_pages)} page(s)."
    )
    console.print(f"[green]Wrote:[/green] {output}")
    console.print(f"[green]Wrote:[/green] {report}")


@app.command()
def run(
    input: Path = RAW_PDF_OPTION,
    parsed_output: Path = PARSED_OUTPUT_RUN_OPTION,
    target_output: Path = TARGET_OUTPUT_RUN_OPTION,
    report_output: Path = REPORT_OUTPUT_RUN_OPTION,
) -> None:
    """Stage 1 + Stage 2 end to end: PDF -> report_blocks.json -> target_blocks.json."""
    parsed, target = run_pipeline(input, parsed_output, target_output, report_output)
    meta = target.filtering_metadata

    table = Table(title="RAISE PDF Parsing + Filtering Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Pages parsed", str(parsed.page_count))
    table.add_row("Blocks extracted (Stage 1)", str(len(parsed.blocks)))
    table.add_row("Pages retained", f"{len(meta.retained_pages)}/{meta.input_page_count}")
    table.add_row("Pages excluded", str(len(meta.excluded_pages)))
    table.add_row("Boilerplate blocks removed", str(meta.removed_boilerplate_block_count))
    table.add_row("Blocks kept (Stage 2)", str(meta.output_block_count))
    console.print(table)

    if meta.excluded_pages:
        excl_table = Table(title="Excluded Pages")
        excl_table.add_column("Page")
        excl_table.add_column("Category")
        excl_table.add_column("Reason")
        for record in meta.excluded_pages:
            excl_table.add_row(str(record.page_number), record.category, record.reason)
        console.print(excl_table)

    console.print(f"[green]Wrote:[/green] {parsed_output}")
    console.print(f"[green]Wrote:[/green] {target_output}")
    console.print(f"[green]Wrote:[/green] {report_output}")


if __name__ == "__main__":
    app()
