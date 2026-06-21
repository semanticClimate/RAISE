from __future__ import annotations

import re

from raise_pdf_parsing.utils import word_count

# Keyword vocabulary kept aligned with the section keywords already
# documented by the downstream HTML-semantification module's README
# (Department, Research, Publications, Grants, Patents, Faculty, Awards,
# Collaboration, Workshop, Conference, Outreach, Activities) and extended
# with the Stage-4 dossier extraction categories from the project vision
# deck (grants, faculty achievements, publications, patents, collaborations,
# conferences, student outcomes, open science, outreach, ranking).
SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Research": ("research activities", "research highlights", "research output"),
    "Grants": ("grants", "funded projects", "sponsored research", "research funding"),
    "Publications": ("publications", "journal articles", "research papers"),
    "Patents": ("patents", "intellectual property", "ipr cell"),
    "Faculty": ("faculty achievements", "faculty profile", "faculty awards", "faculty"),
    "Collaborations": ("collaboration", "mou signed", "industry partnership", "moUs"),
    "Conferences": ("conference", "seminar", "workshop", "symposium"),
    "Student Outcomes": ("student outcomes", "placement", "phd awarded", "scholars graduated"),
    "Open Science": ("open access", "open science", "data repository", "preprint"),
    "Outreach": ("outreach", "community engagement", "extension activities"),
    "Ranking": ("ranking", "nirf", "accreditation", "naac"),
    "Department": ("department of",),
    "Awards": ("awards", "honours", "recognition"),
}

_FLAT_SECTION_KEYWORDS: list[tuple[str, str]] = [
    (keyword, section) for section, keywords in SECTION_KEYWORDS.items() for keyword in keywords
]

_BULLET_RE = re.compile(r"^\s*([\u2022\u2023\u25E6\u2043\u2219•◦‣*\-]|\(?\d{1,3}[.)])\s+")
_PAGE_NUMBER_RE = re.compile(r"^(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?$", re.IGNORECASE)
_UPPER_RATIO_THRESHOLD = 0.7


def looks_like_page_number(text: str) -> bool:
    return bool(_PAGE_NUMBER_RE.match(text.strip()))


def looks_like_bullet(text: str) -> bool:
    return bool(_BULLET_RE.match(text))


def _uppercase_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    upper = sum(1 for ch in letters if ch.isupper())
    return upper / len(letters)


def classify_block_type(
    text: str,
    font_size: float | None,
    is_bold: bool | None,
    body_font_size: float,
) -> tuple[str, float]:
    """Heuristically classify a text block as heading / list_item / paragraph.

    Table blocks are identified separately (they come from the table
    extractor, not from this font-based heuristic) and are never passed
    through this function as plain text.
    """
    stripped = text.strip()
    if not stripped:
        return "empty", 0.0

    if looks_like_page_number(stripped):
        return "page_number", 0.95

    if looks_like_bullet(stripped):
        return "list_item", 0.85

    words = word_count(stripped)
    size = font_size or body_font_size
    relative_size = size / body_font_size if body_font_size else 1.0

    heading_score = 0.0
    if relative_size >= 1.35:
        heading_score += 0.45
    elif relative_size >= 1.15:
        heading_score += 0.25
    if is_bold:
        heading_score += 0.25
    if words <= 8:
        heading_score += 0.15
    if _uppercase_ratio(stripped) >= _UPPER_RATIO_THRESHOLD and words <= 12:
        heading_score += 0.2
    if stripped.endswith((".", ",", ";")):
        heading_score -= 0.3

    if heading_score >= 0.5:
        confidence = min(0.99, 0.55 + heading_score / 2)
        return "heading", round(confidence, 3)

    return "paragraph", 0.9 if words >= 4 else 0.6


def detect_section_hint(text: str) -> str | None:
    lowered = text.lower()
    for keyword, section in _FLAT_SECTION_KEYWORDS:
        if keyword in lowered:
            return section
    return None
