from __future__ import annotations

from pathlib import Path

from raise_pdf_parsing.parser import parse_pdf


def test_parses_every_page(sample_pdf_path: Path) -> None:
    report = parse_pdf(sample_pdf_path)
    assert report.page_count == 7
    assert len(report.blocks) > 0


def test_blocks_have_stable_deterministic_ids(sample_pdf_path: Path) -> None:
    first = parse_pdf(sample_pdf_path)
    second = parse_pdf(sample_pdf_path)
    assert [b.block_id for b in first.blocks] == [b.block_id for b in second.blocks]


def test_reading_order_is_monotonic(sample_pdf_path: Path) -> None:
    report = parse_pdf(sample_pdf_path)
    orders = [b.reading_order for b in report.blocks]
    assert orders == sorted(orders)
    assert len(set(orders)) == len(orders)  # strictly increasing, no duplicates


def test_heading_detected_with_bold_large_font(sample_pdf_path: Path) -> None:
    report = parse_pdf(sample_pdf_path)
    heading = next(b for b in report.blocks if b.text.strip() == "RESEARCH ACTIVITIES")
    assert heading.block_type_guess == "heading"
    assert heading.is_bold is True
    assert heading.font_size and heading.font_size >= 16
    assert heading.section_hint == "Research"


def test_bullet_list_items_classified(sample_pdf_path: Path) -> None:
    report = parse_pdf(sample_pdf_path)
    bullets = [b for b in report.blocks if b.text.startswith("- ")]
    assert bullets
    assert all(b.block_type_guess == "list_item" for b in bullets)


def test_table_extracted_with_rows(sample_pdf_path: Path) -> None:
    report = parse_pdf(sample_pdf_path)
    table_blocks = [b for b in report.blocks if b.block_type_guess == "table"]
    assert len(table_blocks) == 1
    table = table_blocks[0]
    assert table.rows is not None
    assert table.rows[0] == ["Department", "Journal Articles", "Conference Papers"]
    assert ["Engineering", "12", "9"] in table.rows


def test_table_rows_not_duplicated_as_paragraphs(sample_pdf_path: Path) -> None:
    report = parse_pdf(sample_pdf_path)
    page_2_blocks = [b for b in report.blocks if b.page_number == 2]
    # "Engineering" should appear inside the table block's rows, not as its own paragraph block.
    standalone_engineering = [
        b for b in page_2_blocks if b.block_type_guess != "table" and "Engineering" in b.text
    ]
    assert standalone_engineering == []


def test_two_column_page_reads_left_column_before_right(sample_pdf_path: Path) -> None:
    report = parse_pdf(sample_pdf_path)
    page_7 = [b for b in report.blocks if b.page_number == 7]
    page_7_sorted = sorted(page_7, key=lambda b: b.reading_order)
    left_positions = [i for i, b in enumerate(page_7_sorted) if "Left column" in b.text]
    right_positions = [i for i, b in enumerate(page_7_sorted) if "Right column" in b.text]
    assert left_positions and right_positions
    assert max(left_positions) < min(right_positions)


def test_page_stats_capture_images_and_words(sample_pdf_path: Path) -> None:
    report = parse_pdf(sample_pdf_path)
    photo_page = next(ps for ps in report.page_stats if ps.page_number == 4)
    assert photo_page.image_count == 4
    assert photo_page.image_area_ratio > 0.3
    assert photo_page.word_count < 60


def test_confidence_in_valid_range(sample_pdf_path: Path) -> None:
    report = parse_pdf(sample_pdf_path)
    for block in report.blocks:
        if block.confidence is not None:
            assert 0.0 <= block.confidence <= 1.0
