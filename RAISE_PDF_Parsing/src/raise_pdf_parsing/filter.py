"""Stage 2 -- Token-Budget Filtering.

Owner: Person B (filtering rules reviewed by Person A).

Input:  ``report_blocks.json`` (Stage 1 output)
Output: ``target_blocks.json`` plus an auditable ``filtering_report.json``

Removes financial-audit pages, photo galleries, directory/contact-list
pages, repetitive header/footer notices, and non-research admin content,
so the AI extraction stage (Stage 4) only ever sees research-assessment
content. Every exclusion is recorded with a reason so the decision is
traceable, per the project's data-governance rules.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

from raise_pdf_parsing.classify import looks_like_page_number
from raise_pdf_parsing.models import (
    Block,
    ExclusionRecord,
    FilteringMetadata,
    PageStats,
    ReportBlocksDocument,
    TargetBlocksDocument,
)

RULES_VERSION = "1.0.0"

FINANCIAL_AUDIT_KEYWORDS = (
    "balance sheet",
    "income and expenditure",
    "statement of accounts",
    "auditor's report",
    "auditors report",
    "receipts and payments",
    "statutory audit",
    "financial statements",
    "trial balance",
    "depreciation schedule",
    "corpus fund",
    "provident fund account",
    "schedule of fixed assets",
    "audited accounts",
)

ADMIN_NOTICE_KEYWORDS = (
    "minutes of the meeting",
    "office order",
    "circular no",
    "tender notice",
    "agenda item",
    "board of governors",
    "syndicate meeting",
    "notification no",
    "attendance register",
    "leave record",
    "purchase order",
)

# Keyword score required before a text-keyword category is allowed to
# exclude a page. Kept deliberately conservative -- false negatives (an
# admin page that slips through to Stage 4) are far cheaper than false
# positives (real research content silently dropped before anyone sees it).
KEYWORD_SCORE_THRESHOLD = 2

PHOTO_GALLERY_IMAGE_RATIO = 0.30
PHOTO_GALLERY_MAX_WORDS = 60

DIRECTORY_ROW_RE = re.compile(
    r"\b(Dr|Prof|Mr|Ms|Mrs)\.?\s+[A-Z][A-Za-z.\s]{2,40},?\s*"
    r"(Professor|Associate Professor|Assistant Professor|Lecturer|Registrar|"
    r"Director|Dean|Officer|Coordinator|HOD)\b",
    re.IGNORECASE,
)
DIRECTORY_MIN_ROW_MATCHES = 4

HEADER_FOOTER_MARGIN_RATIO = 0.08  # top/bottom 8% of the page counts as running margin
BOILERPLATE_MIN_PAGES = 3
BOILERPLATE_MAX_WORDS = 14
_LEADING_NUM_RE = re.compile(r"^\s*0*(\d+)\b\s*")
_TRAILING_NUM_RE = re.compile(r"\s*\b0*(\d+)\s*$")
_TRAILING_PAGE_WORD_RE = re.compile(r"(?i)\bpage\b\s*$")
_TRAILING_SEP_RE = re.compile(r"[\s\-|:.]+$")
_LEADING_SEP_RE = re.compile(r"^[\s\-|:.]+")


def _boilerplate_key(text: str, page_number: int) -> str:
    """Normalize a margin block for repetition matching.

    Real PDF layout engines frequently merge a static running notice with
    the page's own page-number digit into a single text block (e.g.
    "Confidential | Page 3", or a leading "04" glued to a section label).
    To dedupe those across pages without also collapsing genuinely
    different per-page content that merely *ends* in a small number (a
    "STAGE 1" / "STAGE 2" kicker label, for example), a leading or trailing
    numeric token is only stripped when it is an exact match for that
    block's own page number -- never a generic digit-collapse.
    """
    working = text.strip()

    trailing = _TRAILING_NUM_RE.search(working)
    if trailing and int(trailing.group(1)) == page_number:
        working = working[: trailing.start()]
        working = _TRAILING_PAGE_WORD_RE.sub("", working)
        working = _TRAILING_SEP_RE.sub("", working)

    leading = _LEADING_NUM_RE.match(working)
    if leading and int(leading.group(1)) == page_number:
        working = working[leading.end() :]
        working = _LEADING_SEP_RE.sub("", working)

    return working.strip().lower()


def _keyword_score(text: str, keywords: tuple[str, ...]) -> tuple[float, list[str]]:
    lowered = text.lower()
    matched = [kw for kw in keywords if kw in lowered]
    return float(len(matched)), matched


def _page_text(blocks: list[Block]) -> str:
    return "\n".join(b.text for b in blocks)


def _classify_page(
    page_stat: PageStats, page_blocks: list[Block]
) -> tuple[str, str, float, list[str]]:
    """Return (category, reason, score, matched_signals).

    category == "research_target" means: keep the page. Any other category
    means: exclude it, with `reason`/`matched_signals` explaining why.
    """
    # 1. Photo gallery: image-dominant, text-sparse pages. Purely structural,
    #    so it is checked first and does not depend on keyword luck.
    if (
        page_stat.image_area_ratio >= PHOTO_GALLERY_IMAGE_RATIO
        and page_stat.word_count <= PHOTO_GALLERY_MAX_WORDS
        and page_stat.image_count >= 2
    ):
        return (
            "photo_gallery",
            "Page is dominated by images with very little text "
            f"(image_area_ratio={page_stat.image_area_ratio}, words={page_stat.word_count}).",
            page_stat.image_area_ratio,
            [
                f"image_area_ratio={page_stat.image_area_ratio}",
                f"word_count={page_stat.word_count}",
            ],
        )

    page_text = _page_text(page_blocks)

    # 2. Directory / contact list: structural regex pattern, also independent of keywords.
    directory_matches = DIRECTORY_ROW_RE.findall(page_text)
    if len(directory_matches) >= DIRECTORY_MIN_ROW_MATCHES:
        return (
            "directory",
            f"Page contains {len(directory_matches)} name/designation rows, "
            "matching a staff directory or contact-list pattern.",
            float(len(directory_matches)),
            [f"directory_row_matches={len(directory_matches)}"],
        )

    # 3. Financial / audit content.
    fin_score, fin_matches = _keyword_score(page_text, FINANCIAL_AUDIT_KEYWORDS)
    if fin_score >= KEYWORD_SCORE_THRESHOLD:
        return (
            "financial_audit",
            f"Page matches {int(fin_score)} financial/audit-statement keywords.",
            fin_score,
            fin_matches,
        )

    # 4. Non-research administrative notices.
    admin_score, admin_matches = _keyword_score(page_text, ADMIN_NOTICE_KEYWORDS)
    if admin_score >= KEYWORD_SCORE_THRESHOLD:
        return (
            "admin_notice",
            f"Page matches {int(admin_score)} non-research administrative keywords.",
            admin_score,
            admin_matches,
        )

    return "research_target", "Page retained as research-assessment content.", 0.0, []


def _is_running_margin_block(block: Block, page_stat: PageStats | None) -> bool:
    if page_stat is None or not block.bbox or len(block.bbox) != 4:
        return False
    _, y0, _, y1 = block.bbox
    top_margin = page_stat.page_height * HEADER_FOOTER_MARGIN_RATIO
    bottom_margin = page_stat.page_height * (1 - HEADER_FOOTER_MARGIN_RATIO)
    return y1 <= top_margin or y0 >= bottom_margin


def _find_boilerplate_texts(
    blocks: list[Block], page_stats_by_number: dict[int, PageStats]
) -> set[str]:
    """Detect running headers/footers: short text blocks that live in the
    page margins and repeat across several distinct pages."""
    margin_occurrences: dict[str, set[int]] = defaultdict(set)
    for block in blocks:
        text = block.text.strip()
        if not text or len(text.split()) > BOILERPLATE_MAX_WORDS:
            continue
        if not _is_running_margin_block(block, page_stats_by_number.get(block.page_number)):
            continue
        margin_occurrences[_boilerplate_key(text, block.page_number)].add(block.page_number)

    min_pages = min(BOILERPLATE_MIN_PAGES, max(2, math.ceil(len(page_stats_by_number) * 0.4)))
    return {key for key, pages in margin_occurrences.items() if len(pages) >= min_pages}


def filter_blocks(report: ReportBlocksDocument) -> TargetBlocksDocument:
    """Apply Stage 2 token-budget filtering to a Stage 1 ``ReportBlocksDocument``."""
    page_stats_by_number = {ps.page_number: ps for ps in report.page_stats}
    blocks_by_page: dict[int, list[Block]] = defaultdict(list)
    for block in report.blocks:
        blocks_by_page[block.page_number].append(block)

    excluded: list[ExclusionRecord] = []
    excluded_pages: set[int] = set()
    for page_number, page_stat in page_stats_by_number.items():
        category, reason, score, matched = _classify_page(
            page_stat, blocks_by_page.get(page_number, [])
        )
        if category != "research_target":
            excluded_pages.add(page_number)
            excluded.append(
                ExclusionRecord(
                    page_number=page_number,
                    reason=reason,
                    category=category,
                    score=score,
                    matched_signals=matched,
                )
            )

    boilerplate_texts = _find_boilerplate_texts(report.blocks, page_stats_by_number)

    kept_blocks: list[Block] = []
    removed_boilerplate = 0
    boilerplate_examples: list[str] = []
    for block in report.blocks:
        if block.page_number in excluded_pages:
            continue
        if looks_like_page_number(block.text):
            removed_boilerplate += 1
            continue
        if _boilerplate_key(
            block.text, block.page_number
        ) in boilerplate_texts and _is_running_margin_block(
            block, page_stats_by_number.get(block.page_number)
        ):
            removed_boilerplate += 1
            if len(boilerplate_examples) < 5 and block.text not in boilerplate_examples:
                boilerplate_examples.append(block.text)
            continue
        kept_blocks.append(block)

    retained_pages = sorted(set(page_stats_by_number) - excluded_pages)

    metadata = FilteringMetadata(
        input_block_count=len(report.blocks),
        output_block_count=len(kept_blocks),
        input_page_count=len(page_stats_by_number),
        retained_pages=retained_pages,
        excluded_pages=sorted(excluded, key=lambda r: r.page_number),
        removed_boilerplate_block_count=removed_boilerplate,
        boilerplate_examples=boilerplate_examples,
        rules_version=RULES_VERSION,
    )

    return TargetBlocksDocument(
        source_file=report.source_file,
        blocks=kept_blocks,
        filtering_metadata=metadata,
    )
