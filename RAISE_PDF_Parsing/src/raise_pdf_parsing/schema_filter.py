"""Filter Stage 2 blocks with a user-supplied JSON Schema."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from raise_pdf_parsing.models import TargetBlocksDocument


def validate_custom_schema(schema: dict[str, Any]) -> None:
    """Raise ``SchemaError`` when *schema* is not a valid Draft 2020-12 schema."""
    Draft202012Validator.check_schema(schema)


def filter_target_by_schema(
    target: TargetBlocksDocument, schema: dict[str, Any]
) -> tuple[TargetBlocksDocument, dict[str, Any]]:
    """Keep only blocks that validate against a custom per-block schema.

    The input document is not mutated. The audit report records every removed
    block and its first validation failure.
    """
    validate_custom_schema(schema)
    validator = Draft202012Validator(schema)
    kept = []
    removed = []

    for block in target.blocks:
        errors = sorted(
            validator.iter_errors(block.model_dump()),
            key=lambda error: tuple(str(part) for part in error.path),
        )
        if not errors:
            kept.append(block)
            continue
        first = errors[0]
        removed.append(
            {
                "block_id": block.block_id,
                "page_number": block.page_number,
                "reason": first.message,
                "schema_path": "/".join(str(part) for part in first.schema_path),
            }
        )

    filtered = target.model_copy(deep=True)
    filtered.blocks = kept
    filtered.filtering_metadata.output_block_count = len(kept)
    filtered.filtering_metadata.retained_pages = sorted({block.page_number for block in kept})

    report = {
        "input_block_count": len(target.blocks),
        "output_block_count": len(kept),
        "removed_block_count": len(removed),
        "removed_blocks": removed,
    }
    return filtered, report
