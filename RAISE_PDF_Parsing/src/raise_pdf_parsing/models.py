from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Block(BaseModel):
    """A single layout-aware content block extracted from one page of a PDF.

    Field names intentionally match the contract already consumed by the
    downstream ``RAISE_HTML5_Semantification`` module (see
    ``raise_html5_semantification.models.Block`` / ``FIELD_ALIASES`` in the
    ``siddharth-semantification`` branch) so ``target_blocks.json`` produced
    here can be handed to that module without translation.
    """

    model_config = ConfigDict(extra="allow")

    block_id: str
    page_number: int
    text: str = ""
    bbox: list[float] = Field(default_factory=list)
    font_size: float | None = None
    font_name: str | None = None
    is_bold: bool | None = None
    is_italic: bool | None = None
    reading_order: int | None = None
    block_type_guess: str | None = None
    confidence: float | None = None
    section_hint: str | None = None
    source_file: str | None = None
    rows: list[list[Any]] | None = None

    # Stage-1-only diagnostic metadata. Harmless extras for downstream
    # consumers (the loader they use allows unknown fields), useful for
    # Stage 2 filtering decisions and for human audit.
    line_count: int | None = None
    word_count: int | None = None
    column_index: int | None = None


class PageStats(BaseModel):
    """Per-page signals collected during Stage 1, consumed by Stage 2 filtering."""

    page_number: int
    page_width: float
    page_height: float
    image_count: int = 0
    image_area_ratio: float = 0.0
    text_block_count: int = 0
    table_block_count: int = 0
    word_count: int = 0
    is_multi_column: bool = False


class ReportBlocksDocument(BaseModel):
    """Stage 1 output contract: ``report_blocks.json``."""

    source_file: str
    stage: str = "report_blocks"
    schema_version: str = "1.0.0"
    page_count: int = 0
    page_stats: list[PageStats] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)


class ExclusionRecord(BaseModel):
    page_number: int
    reason: str
    category: str
    score: float = 0.0
    matched_signals: list[str] = Field(default_factory=list)


class FilteringMetadata(BaseModel):
    input_block_count: int
    output_block_count: int
    input_page_count: int
    retained_pages: list[int]
    excluded_pages: list[ExclusionRecord] = Field(default_factory=list)
    removed_boilerplate_block_count: int = 0
    boilerplate_examples: list[str] = Field(default_factory=list)
    rules_version: str = "1.0.0"


class TargetBlocksDocument(BaseModel):
    """Stage 2 output contract: ``target_blocks.json``."""

    source_file: str
    stage: str = "target_blocks"
    schema_version: str = "1.0.0"
    blocks: list[Block] = Field(default_factory=list)
    filtering_metadata: FilteringMetadata
