"""Builds a small, fully synthetic "university annual report" PDF that
exercises every Stage 1 / Stage 2 behaviour this module implements:
headings, paragraphs, bullet lists, a ruled table, a two-column page, a
financial-audit page, a photo-gallery page, a staff-directory page, an
admin-notice page, and a running header/footer repeated on every page.

No real institution, person, or report is represented -- every name,
figure, and notice below is invented for testing purposes only.
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

PAGE_WIDTH, PAGE_HEIGHT = 595, 842  # A4 in points

HEADER_TEXT = "Sample University Annual Report 2024-25"
FOOTER_TEXT = "Confidential - Internal Circulation Only"


def _add_running_margins(page: fitz.Page, page_number: int) -> None:
    page.insert_text((72, 30), HEADER_TEXT, fontsize=8, fontname="helv")
    page.insert_text((72, PAGE_HEIGHT - 25), FOOTER_TEXT, fontsize=8, fontname="helv")
    page.insert_text(
        (PAGE_WIDTH - 90, PAGE_HEIGHT - 25), f"Page {page_number}", fontsize=8, fontname="helv"
    )


def _solid_image_bytes(color: tuple[int, int, int], size: tuple[int, int] = (220, 220)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _insert_body_lines(
    page: fitz.Page,
    lines: list[str],
    start_y: int,
    line_height: int = 20,
    fontsize: int = 11,
) -> None:
    for index, line in enumerate(lines):
        page.insert_text(
            (72, start_y + index * line_height), line, fontsize=fontsize, fontname="tiro"
        )


def build_sample_annual_report(path: Path) -> None:
    doc = fitz.open()

    # --- Page 1: research narrative (heading, paragraph, bullet list) ---
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    _add_running_margins(page, 1)
    page.insert_text((72, 110), "RESEARCH ACTIVITIES", fontsize=18, fontname="hebo")
    _insert_body_lines(
        page,
        start_y=150,
        line_height=18,
        lines=[
            "The Department of Computer Science continued funded research in renewable",
            "energy systems and high-performance computing throughout the reporting year.",
        ],
    )
    _insert_body_lines(
        page,
        start_y=200,
        lines=[
            "- Publications increased by 18 percent over last year",
            "- Three new research grants were awarded",
            "- Two patents were filed by faculty members",
        ],
    )

    # --- Page 2: a ruled table (Faculty vs Publications) ---
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    _add_running_margins(page, 2)
    page.insert_text((72, 110), "PUBLICATIONS BY DEPARTMENT", fontsize=16, fontname="hebo")

    col_x = [72, 260, 420, 520]
    row_y = [150, 180, 210, 240, 270]
    for x in col_x:
        page.draw_line((x, row_y[0]), (x, row_y[-1]))
    for y in row_y:
        page.draw_line((col_x[0], y), (col_x[-1], y))

    table_rows = [
        ("Department", "Journal Articles", "Conference Papers"),
        ("Engineering", "12", "9"),
        ("Computer Science", "20", "14"),
        ("Physics", "8", "5"),
    ]
    for row_index, row in enumerate(table_rows):
        y = row_y[row_index] + 20
        for col_index, cell in enumerate(row):
            page.insert_text((col_x[col_index] + 8, y), cell, fontsize=10, fontname="tiro")

    # --- Page 3: financial / audit page (should be EXCLUDED by Stage 2) ---
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    _add_running_margins(page, 3)
    page.insert_text((72, 110), "STATEMENT OF ACCOUNTS", fontsize=16, fontname="hebo")
    _insert_body_lines(
        page,
        start_y=150,
        lines=[
            "Balance Sheet as at 31 March 2025",
            "Auditor's Report attached as Annexure IV.",
            "Receipts and Payments account reconciled with the trial balance.",
            "Schedule of Fixed Assets and depreciation schedule enclosed.",
        ],
    )

    # --- Page 4: photo gallery (image-dominant, should be EXCLUDED) ---
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    _add_running_margins(page, 4)
    page.insert_text((72, 110), "Campus Moments", fontsize=12, fontname="hebo")
    colors = [(180, 200, 220), (220, 180, 180), (180, 220, 180), (220, 220, 180)]
    positions = [(72, 140), (320, 140), (72, 420), (320, 420)]
    for color, (x, y) in zip(colors, positions, strict=False):
        page.insert_image(fitz.Rect(x, y, x + 220, y + 220), stream=_solid_image_bytes(color))

    # --- Page 5: staff directory (should be EXCLUDED) ---
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    _add_running_margins(page, 5)
    page.insert_text((72, 110), "DIRECTORY OF FACULTY CONTACTS", fontsize=14, fontname="hebo")
    _insert_body_lines(
        page,
        start_y=150,
        line_height=22,
        lines=[
            "Dr. Asha Verma, Professor, ext. 2210, asha.verma@example.edu",
            "Dr. Ramesh Iyer, Associate Professor, ext. 2233, ramesh.iyer@example.edu",
            "Prof. Kavita Rao, Dean, ext. 2001, kavita.rao@example.edu",
            "Mr. Sanjay Mehta, Registrar, ext. 2005, sanjay.mehta@example.edu",
            "Dr. Leela Nair, Assistant Professor, ext. 2244, leela.nair@example.edu",
            "Dr. Vikram Shah, HOD, ext. 2110, vikram.shah@example.edu",
        ],
        fontsize=10,
    )

    # --- Page 6: admin notice (should be EXCLUDED) ---
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    _add_running_margins(page, 6)
    page.insert_text((72, 110), "OFFICE CIRCULAR", fontsize=14, fontname="hebo")
    _insert_body_lines(
        page,
        start_y=150,
        lines=[
            "Circular No. 18/2025 regarding revised attendance register format.",
            "Minutes of the meeting of the Board of Governors held on 4 March 2025.",
            "Tender Notice for campus housekeeping services is enclosed.",
        ],
    )

    # --- Page 7: two-column research page (tests multi-column reading order) ---
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    _add_running_margins(page, 7)
    page.insert_text((72, 110), "FACULTY ACHIEVEMENTS", fontsize=16, fontname="hebo")
    left_lines = [
        "Left column line one about awards.",
        "Left column line two about honours.",
        "Left column line three about grants.",
    ]
    right_lines = [
        "Right column line one about outreach.",
        "Right column line two about workshops.",
        "Right column line three about MoUs signed.",
    ]
    for index, line in enumerate(left_lines):
        page.insert_text((72, 150 + index * 20), line, fontsize=10, fontname="tiro")
    for index, line in enumerate(right_lines):
        page.insert_text((320, 150 + index * 20), line, fontsize=10, fontname="tiro")

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


if __name__ == "__main__":
    build_sample_annual_report(Path(__file__).with_name("sample_annual_report.pdf"))
