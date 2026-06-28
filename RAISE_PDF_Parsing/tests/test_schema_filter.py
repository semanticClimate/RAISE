from __future__ import annotations

import pytest
from jsonschema.exceptions import SchemaError

from raise_pdf_parsing.filter import filter_blocks
from raise_pdf_parsing.parser import parse_pdf
from raise_pdf_parsing.schema_filter import filter_target_by_schema


def test_custom_schema_keeps_only_matching_blocks(sample_pdf_path) -> None:
    target = filter_blocks(parse_pdf(sample_pdf_path))
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"block_type_guess": {"const": "heading"}},
        "required": ["block_type_guess"],
    }

    filtered, report = filter_target_by_schema(target, schema)

    assert filtered.blocks
    assert all(block.block_type_guess == "heading" for block in filtered.blocks)
    assert report["removed_block_count"] == len(target.blocks) - len(filtered.blocks)
    assert filtered.filtering_metadata.output_block_count == len(filtered.blocks)
    assert filtered.filtering_metadata.retained_pages == sorted(
        {block.page_number for block in filtered.blocks}
    )


def test_custom_schema_does_not_mutate_input(sample_pdf_path) -> None:
    target = filter_blocks(parse_pdf(sample_pdf_path))
    original_count = len(target.blocks)

    filtered, _ = filter_target_by_schema(target, {"type": "object", "required": ["missing"]})

    assert not filtered.blocks
    assert len(target.blocks) == original_count


def test_invalid_custom_schema_is_rejected(sample_pdf_path) -> None:
    target = filter_blocks(parse_pdf(sample_pdf_path))

    with pytest.raises(SchemaError):
        filter_target_by_schema(target, {"type": "not-a-json-schema-type"})
