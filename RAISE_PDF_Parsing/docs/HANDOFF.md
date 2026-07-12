# Handoff to Stage 3 (RAISE_HTML5_Semantification)

## Status

This is the authoritative schema and a real prepared JSON document for the
upstream stage that `RAISE_HTML5_Semantification/docs/SCHEMA_INTEGRATION.md`
asks for. It replaces the temporary packaged schema
(`semantic_input.schema.json`) once reviewed.

## What This Module Hands Off

- **Schema file**: `schemas/target_blocks.schema.json` (draft 2020-12,
  references `schemas/report_blocks.schema.json#/$defs/block` for the
  shared block shape).
- **Representative valid document**: `data/03_filtered/target_blocks.json`,
  produced by running this module's `run` command against a real PDF (see
  `tests/fixtures/` for a synthetic annual report exercising every
  filtering category, and `outputs/` for a worked example).
- **Edge cases already covered by Stage 2 and worth adding as Stage 3 test
  fixtures too**: a financial-audit page, a photo-gallery page, a staff
  directory page, a running header/footer repeated across pages, and a
  low-confidence (badly encoded) block that survives filtering but should
  be flagged for human review downstream.
- **Schema owner**: Person B (filtering-rule changes reviewed by Person A).
- **Change process**: schema changes bump `schema_version` in both
  `report_blocks.json` and `target_blocks.json`; breaking changes require a
  fixture update on both sides of the handoff.

## Root Structure And Field Meanings

- Root object: `{"source_file": ..., "blocks": [...], "filtering_metadata": {...}}`.
  `blocks` is the content-block array (matches the `BLOCK_CONTAINER_KEYS`
  alias `"blocks"` already recognized by the Stage 3 loader).
- `block_id`: stable string, format `p{page}-b{local_index:03d}`, generated
  deterministically -- never null, never regenerated between runs on the
  same PDF.
- `page_number`: 1-indexed integer, always present.
- `bbox`: `[x0, y0, x1, y1]` in PDF points, top-left origin (PyMuPDF / pdfplumber
  convention -- y increases downward).
- `font_size` / `font_name` / `is_bold` / `is_italic`: null for table blocks
  (a table has no single dominant font); always present for text blocks.
- `confidence`: `[0, 1]`. For text blocks this blends the block-type
  classifier's confidence with a text-extraction integrity score (penalizes
  replacement characters / control characters from broken font encodings).
  It is **not** a semantic-correctness score.
- `reading_order`: monotonically increasing integer across the whole
  document, already resolved for simple two-column layouts.
- `block_type_guess`: one of `heading`, `paragraph`, `list_item`, `table`,
  `page_number`, `empty`. Page-number blocks are dropped during Stage 2
  filtering, so they should not appear in `target_blocks.json` in practice.
- `section_hint`: the most recently detected section keyword (e.g.
  `"Research"`, `"Grants"`, `"Publications"`) carried forward from the last
  heading-classified block; null until the first recognized heading.
- `rows`: present only on `block_type_guess == "table"` blocks; a list of
  rows, each a list of cell strings, in original reading order.
- `source_file`: the original PDF filename, repeated on every block for
  block-level traceability even if blocks are later processed independently.

## Rules For Stable IDs And Traceability

- `block_id` is derived purely from page number and position within the
  page's reading order, so the same PDF always produces the same IDs
  (no randomness, no UUIDs that would break golden-file tests).
- `filtering_metadata.excluded_pages` records page-level traceability: which
  pages were dropped, by which category, and which signal(s) triggered it.
- `filtering_metadata.boilerplate_examples` records up to five removed
  running-header/footer strings as a spot-check sample.

## Enums / Controlled Values

- `block_type_guess`: `heading | paragraph | list_item | table | page_number | empty`
- `filtering_metadata.excluded_pages[].category`: `financial_audit | photo_gallery | directory | admin_notice`

## Compatibility Already Checked Against the Stage 3 Loader

The `Block` field names and aliasing in this module were written to match
`raise_html5_semantification.models.FIELD_ALIASES` exactly (`block_id`,
`page_number`, `text`, `bbox`, `font_size`, `font_name`, `is_bold`,
`is_italic`, `reading_order`, `block_type_guess`, `confidence`,
`section_hint`, `source_file`, `rows`) -- no alias translation is required
on the Stage 3 side. `tests/test_handoff_compatibility.py` in this module
installs the Stage 3 package from the `siddharth-semantification` branch
and runs `build_report()` directly against this module's `target_blocks.json`
output to confirm the contract holds end to end.
