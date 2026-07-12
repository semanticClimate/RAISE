"""Stage 1 -- Layout-Aware PDF Parsing.

Owner: Person B.

Input:  a raw annual-report PDF (``data/01_raw/report.pdf``)
Output: ``report_blocks.json`` (``data/02_parsed/report_blocks.json``)

This module turns an unstructured PDF into structured text blocks while
preserving the report's visual logic: page number, block id, coordinates,
font size/name, bold/italic status, a deterministic reading order (with a
simple two-column detector), an early block-type guess, and table rows for
anything that looks like a table. Nothing here decides what is "relevant"
research-assessment content -- that is Stage 2's job.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import pdfplumber

from raise_pdf_parsing.classify import classify_block_type, detect_section_hint
from raise_pdf_parsing.models import Block, PageStats, ReportBlocksDocument
from raise_pdf_parsing.utils import normalize_whitespace, text_confidence, word_count

BOLD_FLAG = 1 << 4
ITALIC_FLAG = 1 << 1
_TABLE_OVERLAP_THRESHOLD = 0.6


def _span_is_bold(span: dict[str, Any]) -> bool:
    font_name = (span.get("font") or "").lower()
    return bool(span.get("flags", 0) & BOLD_FLAG) or "bold" in font_name or "black" in font_name


def _span_is_italic(span: dict[str, Any]) -> bool:
    font_name = (span.get("font") or "").lower()
    return (
        bool(span.get("flags", 0) & ITALIC_FLAG) or "italic" in font_name or "oblique" in font_name
    )


def _dominant_span_attrs(spans: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick font metadata weighted by character count, so a 2-character
    superscript footnote marker can't override the paragraph's real font."""
    if not spans:
        return {"font_size": None, "font_name": None, "is_bold": None, "is_italic": None}

    weights: dict[tuple[float, str], int] = {}
    for span in spans:
        key = (round(span.get("size", 0.0), 1), span.get("font", ""))
        weights[key] = weights.get(key, 0) + max(1, len(span.get("text", "")))
    (font_size, font_name), _ = max(weights.items(), key=lambda item: item[1])

    bold_chars = sum(len(s.get("text", "")) for s in spans if _span_is_bold(s))
    italic_chars = sum(len(s.get("text", "")) for s in spans if _span_is_italic(s))
    total_chars = sum(len(s.get("text", "")) for s in spans) or 1

    return {
        "font_size": float(font_size),
        "font_name": font_name or None,
        "is_bold": bold_chars / total_chars >= 0.5,
        "is_italic": italic_chars / total_chars >= 0.5,
    }


def _block_text(text_block: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    lines_out: list[str] = []
    spans: list[dict[str, Any]] = []
    for line in text_block.get("lines", []):
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))
        line_text = normalize_whitespace(line_text)
        if line_text:
            lines_out.append(line_text)
        spans.extend(line.get("spans", []))
    return "\n".join(lines_out), spans


def _estimate_body_font_size(blocks: list[dict[str, Any]]) -> float:
    sizes: list[float] = []
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if text:
                    sizes.append(round(span.get("size", 0.0), 1))
    if not sizes:
        return 11.0
    return statistics.median(sizes)


def _bbox_overlap_ratio(
    inner: tuple[float, float, float, float], outer: tuple[float, float, float, float]
) -> float:
    ix0, iy0, ix1, iy1 = inner
    ox0, oy0, ox1, oy1 = outer
    inter_w = max(0.0, min(ix1, ox1) - max(ix0, ox0))
    inter_h = max(0.0, min(iy1, oy1) - max(iy0, oy0))
    inter_area = inter_w * inter_h
    inner_area = max(1e-6, (ix1 - ix0) * (iy1 - iy0))
    return inter_area / inner_area


def _detect_columns(blocks: list[dict[str, Any]], page_width: float) -> bool:
    """A cheap two-column detector: true if a meaningful share of blocks sit
    entirely in either the left or right half of the page (i.e. nothing
    spans the full width) and both halves are used. Uses each block's
    horizontal center point rather than requiring the whole block to clear
    a fixed gap from the midline, since a normal column gutter is much
    narrower than half the page width."""
    if page_width <= 0:
        return False
    max_narrow_width = page_width * 0.55
    midpoint = page_width / 2
    narrow, wide = 0, 0
    left, right = 0, 0
    for block in blocks:
        x0, _, x1, _ = block["bbox"]
        if (x1 - x0) > max_narrow_width:
            wide += 1
            continue
        narrow += 1
        center = (x0 + x1) / 2
        if center < midpoint:
            left += 1
        else:
            right += 1
    if narrow < 4:
        return False
    return left >= 2 and right >= 2 and wide <= narrow


def _order_blocks(blocks: list[dict[str, Any]], page_width: float) -> list[dict[str, Any]]:
    """Sort blocks into reading order, splitting into left/right columns
    first when the page looks like a two-column layout."""
    if not blocks:
        return blocks

    if _detect_columns(blocks, page_width):
        midpoint = page_width / 2
        left = [b for b in blocks if (b["bbox"][0] + b["bbox"][2]) / 2 < midpoint]
        right = [b for b in blocks if (b["bbox"][0] + b["bbox"][2]) / 2 >= midpoint]
        left.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        right.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        for b in left:
            b["column_index"] = 0
        for b in right:
            b["column_index"] = 1
        return left + right

    blocks.sort(key=lambda b: (round(b["bbox"][1], 0), b["bbox"][0]))
    for b in blocks:
        b["column_index"] = 0
    return blocks


def _extract_text_blocks(page: fitz.Page) -> list[dict[str, Any]]:
    raw = page.get_text("dict")
    body_size = _estimate_body_font_size(raw.get("blocks", []))
    out: list[dict[str, Any]] = []
    for raw_block in raw.get("blocks", []):
        if raw_block.get("type") != 0:  # 0 = text, 1 = image
            continue
        text, spans = _block_text(raw_block)
        if not text.strip():
            continue
        attrs = _dominant_span_attrs(spans)
        block_type, type_confidence = classify_block_type(
            text, attrs["font_size"], attrs["is_bold"], body_size
        )
        out.append(
            {
                "bbox": list(raw_block.get("bbox", (0, 0, 0, 0))),
                "text": text,
                "font_size": attrs["font_size"],
                "font_name": attrs["font_name"],
                "is_bold": attrs["is_bold"],
                "is_italic": attrs["is_italic"],
                "block_type_guess": block_type,
                "type_confidence": type_confidence,
                "line_count": text.count("\n") + 1,
                "word_count": word_count(text),
            }
        )
    return out


def _extract_table_blocks(
    pdf_path: Path, page_number: int, page_height: float
) -> list[dict[str, Any]]:
    """Use pdfplumber's table detector to recover well-formed tables.
    PyMuPDF is excellent for text/font/bbox; pdfplumber's ruling-line and
    text-alignment table strategy is the more reliable of the two for
    tabular data, so the two libraries are used together here."""
    out: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        plumber_page = pdf.pages[page_number - 1]
        found_tables = plumber_page.find_tables()
        for table in found_tables:
            rows = table.extract()
            rows = [
                [("" if cell is None else str(cell).strip()) for cell in row] for row in rows if row
            ]
            if not rows or all(all(not cell for cell in row) for row in rows):
                continue
            x0, top, x1, bottom = table.bbox
            # pdfplumber's y-origin is top-down already, matching PyMuPDF's bbox convention.
            out.append(
                {
                    "bbox": [x0, top, x1, bottom],
                    "text": "\n".join(" | ".join(row) for row in rows),
                    "rows": rows,
                    "font_size": None,
                    "font_name": None,
                    "is_bold": None,
                    "is_italic": None,
                    "block_type_guess": "table",
                    "type_confidence": 0.9 if len(rows) > 1 else 0.6,
                    "line_count": len(rows),
                    "word_count": sum(word_count(" ".join(row)) for row in rows),
                }
            )
    return out


def _merge_text_and_tables(
    text_blocks: list[dict[str, Any]], table_blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Drop text blocks that are mostly contained inside a detected table's
    bounding box, so table content is represented once (as a table block
    with real rows) instead of also leaking through as paragraph blocks."""
    if not table_blocks:
        return text_blocks
    kept: list[dict[str, Any]] = []
    for text_block in text_blocks:
        inside_table = any(
            _bbox_overlap_ratio(tuple(text_block["bbox"]), tuple(table["bbox"]))
            >= _TABLE_OVERLAP_THRESHOLD
            for table in table_blocks
        )
        if not inside_table:
            kept.append(text_block)
    return kept + table_blocks


def _page_stats(
    page: fitz.Page, text_count: int, table_count: int, words: int, multi_col: bool
) -> PageStats:
    rect = page.rect
    images = page.get_images(full=True)
    image_area = 0.0
    for image_info in images:
        try:
            bbox_list = page.get_image_bbox(image_info)
            image_area += max(0.0, bbox_list.width) * max(0.0, bbox_list.height)
        except ValueError:
            continue
    page_area = max(1.0, rect.width * rect.height)
    return PageStats(
        page_number=page.number + 1,
        page_width=rect.width,
        page_height=rect.height,
        image_count=len(images),
        image_area_ratio=round(min(1.0, image_area / page_area), 4),
        text_block_count=text_count,
        table_block_count=table_count,
        word_count=words,
        is_multi_column=multi_col,
    )


def parse_pdf(pdf_path: str | Path, source_file: str | None = None) -> ReportBlocksDocument:
    """Parse ``pdf_path`` into the Stage 1 ``report_blocks`` document."""
    pdf_path = Path(pdf_path)
    source_name = source_file or pdf_path.name

    doc = fitz.open(pdf_path)
    all_blocks: list[Block] = []
    page_stats: list[PageStats] = []
    global_index = 0

    try:
        for page in doc:
            page_number = page.number + 1
            text_blocks = _extract_text_blocks(page)
            table_blocks = _extract_table_blocks(pdf_path, page_number, page.rect.height)
            merged = _merge_text_and_tables(text_blocks, table_blocks)
            multi_col = _detect_columns(merged, page.rect.width) if merged else False
            ordered = _order_blocks(merged, page.rect.width)

            current_section: str | None = None
            for local_index, raw_block in enumerate(ordered, start=1):
                global_index += 1
                if raw_block.get("block_type_guess") == "heading":
                    hint = detect_section_hint(raw_block["text"])
                    if hint:
                        current_section = hint

                confidence = raw_block.get("type_confidence", 0.5)
                if raw_block.get("rows") is None:
                    # Blend the type-classifier confidence with raw text-extraction
                    # confidence so badly-encoded text can't masquerade as a clean heading.
                    confidence = round(
                        0.5 * confidence + 0.5 * text_confidence(raw_block["text"]), 3
                    )

                block = Block(
                    block_id=f"p{page_number}-b{local_index:03d}",
                    page_number=page_number,
                    text=raw_block["text"],
                    bbox=[round(v, 2) for v in raw_block["bbox"]],
                    font_size=raw_block.get("font_size"),
                    font_name=raw_block.get("font_name"),
                    is_bold=raw_block.get("is_bold"),
                    is_italic=raw_block.get("is_italic"),
                    reading_order=global_index,
                    block_type_guess=raw_block.get("block_type_guess"),
                    confidence=confidence,
                    section_hint=current_section,
                    source_file=source_name,
                    rows=raw_block.get("rows"),
                    line_count=raw_block.get("line_count"),
                    word_count=raw_block.get("word_count"),
                    column_index=raw_block.get("column_index"),
                )
                all_blocks.append(block)

            text_count = sum(1 for b in merged if b.get("block_type_guess") != "table")
            table_count = sum(1 for b in merged if b.get("block_type_guess") == "table")
            words = sum(b.get("word_count", 0) for b in merged)
            page_stats.append(_page_stats(page, text_count, table_count, words, multi_col))
    finally:
        doc.close()

    return ReportBlocksDocument(
        source_file=source_name,
        page_count=len(page_stats),
        page_stats=page_stats,
        blocks=all_blocks,
    )
