# RAISE PDF Parsing

Module owner: **Person B**
Support: Person C (Stage 1 layout review), Person A (Stage 2 filtering-rule review)

This module folder implements Person B's RAISE project module:
**Stage 1 (Layout-Aware PDF Parsing) + Stage 2 (Token-Budget Filtering)**.

Main repository:

```text
https://github.com/semanticClimate/RAISE.git
```

Branch:

```text
Harsh-semantification
```

Suggested module folder:

```text
RAISE_PDF_Parsing
```

This module is the very first stage of the pipeline. It receives a raw
university annual-report PDF and produces clean, traceable, research-only
block JSON for the next teammate's semantic-HTML stage.

## Boundary

This module does **not** perform HTML semantification. It does **not**
perform AI structured extraction. It does **not** perform ORCID/ROR/Wikidata
validation. It does **not** decide what counts as a grant, publication, or
faculty achievement -- it only decides which *pages* are research-assessment
content versus noise (financial audit pages, photo galleries, directories,
boilerplate, admin notices), and preserves everything else with full layout
and traceability metadata for the stages downstream.

The two tasks here are PDF parsing (Stage 1) and token-budget filtering
(Stage 2).

## Pipeline

```text
report.pdf --[Stage 1: parse]--> report_blocks.json --[Stage 2: filter]--> target_blocks.json
```

## Stage 1: Layout-Aware PDF Parsing

Input:

```text
data/01_raw/report.pdf
```

Output:

```text
data/02_parsed/report_blocks.json
```

Captures, per block: text, page number, block ID, bounding-box coordinates,
font size/name, bold/italic status, a deterministic reading order (with a
simple two-column detector for multi-column layouts), an early
`block_type_guess` (heading / paragraph / list_item / table / page_number),
a `section_hint` carried forward from the most recent detected heading, and
a text-extraction confidence score. Tables are recovered as real `rows`
(not flattened paragraph text) using pdfplumber's ruling-line table
detector alongside PyMuPDF's font-aware text extraction.

## Stage 2: Token-Budget Filtering

Input:

```text
data/02_parsed/report_blocks.json
```

Output:

```text
data/03_filtered/target_blocks.json
data/03_filtered/filtering_report.json
```

Removes, page by page:

- **Financial / audit pages** -- keyword match against balance-sheet,
  auditor's-report, and similar accounting-statement language.
- **Photo galleries** -- image-dominated, text-sparse pages.
- **Staff directories / contact lists** -- structural regex match on
  repeated "Name, Designation" rows.
- **Non-research administrative notices** -- circulars, meeting minutes,
  tender notices, and similar.
- **Repetitive running headers/footers** -- short text blocks that sit in
  the page margins and repeat across several pages (university name,
  confidentiality notices, page numbers).

Every exclusion is recorded with a page number, category, reason, and the
matched signal in `filtering_report.json`, so a reviewer can audit (and a
PR can challenge) any removal -- nothing is silently dropped.

The keyword/structural thresholds are intentionally conservative: a page is
only excluded when it strongly matches a known noise category. Anything
ambiguous is kept and passed downstream, consistent with the project's
"traceable, validated, reusable" governance principle.

## Output Contract (handoff to Stage 3)

`target_blocks.json` matches the input contract already expected by the
`RAISE_HTML5_Semantification` module:

```json
{
  "source_file": "university_annual_report.pdf",
  "blocks": [
    {
      "block_id": "p1-b004",
      "page_number": 1,
      "text": "RESEARCH ACTIVITIES",
      "bbox": [72, 100, 420, 130],
      "font_size": 18,
      "font_name": "Times-Bold",
      "is_bold": true,
      "is_italic": false,
      "reading_order": 4,
      "block_type_guess": "heading",
      "confidence": 0.98,
      "section_hint": "Research",
      "source_file": "university_annual_report.pdf"
    }
  ],
  "filtering_metadata": {
    "input_block_count": 142,
    "output_block_count": 96,
    "retained_pages": [1, 2, 5, 6, 7],
    "excluded_pages": [
      {
        "page_number": 3,
        "category": "financial_audit",
        "reason": "Page matches 3 financial/audit-statement keywords.",
        "score": 3.0,
        "matched_signals": ["balance sheet", "auditor's report", "trial balance"]
      }
    ],
    "removed_boilerplate_block_count": 9
  }
}
```

The authoritative JSON Schemas for both stage outputs are in `schemas/`:

```text
schemas/report_blocks.schema.json
schemas/target_blocks.schema.json
```

See `docs/HANDOFF.md` for the full handoff checklist for the Stage 3 owner.

## Setup

```bash
pip install -r requirements.txt
# or
pip install -e ".[dev]"
```

## Commands

Stage 1 only:

```bash
python -m raise_pdf_parsing parse --input data/01_raw/report.pdf --output data/02_parsed/report_blocks.json
```

Stage 2 only (re-run filtering rules without re-parsing the PDF):

```bash
python -m raise_pdf_parsing filter --input data/02_parsed/report_blocks.json --output data/03_filtered/target_blocks.json --report data/03_filtered/filtering_report.json
```

End to end:

```bash
python -m raise_pdf_parsing run --input data/01_raw/report.pdf
```

Run quality checks:

```bash
ruff check .
pytest
```

## Colab Demo

```text
../RAISE_PDF_Parsing_Colab.ipynb
```

The repository root notebook is the GitHub/Colab-facing demo. A copy is also
kept under `notebooks/` for module-local editing. The notebook uploads a PDF,
runs Stage 1 + Stage 2, prints the filtering summary, previews
`target_blocks.json`, and downloads `report_blocks.json`,
`target_blocks.json`, and `filtering_report.json` -- the last of those three is
the file to hand straight to the `RAISE_HTML5_Semantification` Colab notebook.

## Limitations

- Reading order for multi-column pages uses a simple left/right split
  heuristic; complex 3+ column layouts are not specifically handled.
- Table detection relies on pdfplumber's ruling-line/text-alignment
  strategy; tables without visible rules and with irregular spacing may be
  preserved as plain paragraph text instead.
- Filtering keyword lists are English-language and tuned for Indian/Western
  university annual-report conventions; they should be reviewed (Person A)
  before use on reports with different structure or language.
- Confidence scores reflect text-extraction quality (encoding integrity),
  not semantic correctness -- this module never judges whether content is
  *true*, only whether it was extracted cleanly and whether the page
  belongs in the research-assessment scope.

## Next Improvements Within This Module

- Configurable per-institution keyword lists for financial/admin filtering.
- OCR fallback (e.g. via Tesseract) for scanned, non-text-layer PDFs.
- GROBID-based parsing option for reports with bibliography-style sections.
- Smarter column detection for 3+ column layouts.
