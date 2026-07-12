from __future__ import annotations

from pathlib import Path

from raise_pdf_parsing.filter import filter_blocks
from raise_pdf_parsing.parser import parse_pdf


def _filtered(sample_pdf_path: Path):
    return filter_blocks(parse_pdf(sample_pdf_path))


def test_financial_audit_page_excluded(sample_pdf_path: Path) -> None:
    target = _filtered(sample_pdf_path)
    assert 3 not in target.filtering_metadata.retained_pages
    record = next(r for r in target.filtering_metadata.excluded_pages if r.page_number == 3)
    assert record.category == "financial_audit"


def test_photo_gallery_page_excluded(sample_pdf_path: Path) -> None:
    target = _filtered(sample_pdf_path)
    assert 4 not in target.filtering_metadata.retained_pages
    record = next(r for r in target.filtering_metadata.excluded_pages if r.page_number == 4)
    assert record.category == "photo_gallery"


def test_directory_page_excluded(sample_pdf_path: Path) -> None:
    target = _filtered(sample_pdf_path)
    assert 5 not in target.filtering_metadata.retained_pages
    record = next(r for r in target.filtering_metadata.excluded_pages if r.page_number == 5)
    assert record.category == "directory"


def test_admin_notice_page_excluded(sample_pdf_path: Path) -> None:
    target = _filtered(sample_pdf_path)
    assert 6 not in target.filtering_metadata.retained_pages
    record = next(r for r in target.filtering_metadata.excluded_pages if r.page_number == 6)
    assert record.category == "admin_notice"


def test_research_pages_retained(sample_pdf_path: Path) -> None:
    target = _filtered(sample_pdf_path)
    assert target.filtering_metadata.retained_pages == [1, 2, 7]


def test_running_header_and_footer_removed(sample_pdf_path: Path) -> None:
    target = _filtered(sample_pdf_path)
    remaining_text = " ".join(b.text for b in target.blocks)
    assert "Sample University Annual Report 2024-25" not in remaining_text
    assert "Confidential - Internal Circulation Only" not in remaining_text
    assert target.filtering_metadata.removed_boilerplate_block_count > 0


def test_research_content_survives_filtering(sample_pdf_path: Path) -> None:
    target = _filtered(sample_pdf_path)
    texts = [b.text for b in target.blocks]
    assert any("RESEARCH ACTIVITIES" in t for t in texts)
    assert any("PUBLICATIONS BY DEPARTMENT" in t for t in texts)
    assert any("FACULTY ACHIEVEMENTS" in t for t in texts)


def test_table_block_survives_filtering_with_rows_intact(sample_pdf_path: Path) -> None:
    target = _filtered(sample_pdf_path)
    table = next(b for b in target.blocks if b.block_type_guess == "table")
    assert table.rows is not None
    assert len(table.rows) == 4


def test_block_count_accounting_is_consistent(sample_pdf_path: Path) -> None:
    target = _filtered(sample_pdf_path)
    meta = target.filtering_metadata
    assert meta.output_block_count == len(target.blocks)
    assert meta.output_block_count < meta.input_block_count


def test_every_exclusion_has_a_reason(sample_pdf_path: Path) -> None:
    target = _filtered(sample_pdf_path)
    for record in target.filtering_metadata.excluded_pages:
        assert record.reason
        assert record.matched_signals
