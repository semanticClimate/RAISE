"""
Academic Institution & Reporting Period Resolver
================================================
Component: `src.features.ingestion.institution_resolver`
Architecture Layer: Ingestion / Entity Canonicalization & Metadata Extraction

Overview:
---------
Resolves canonical university / research council names and academic / reporting fiscal years
from PDF filenames and cover page text.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Tuple

logger = logging.getLogger("raise.ingestion.institution_resolver")


def identify_institution(pdf_path: Path, first_page_text: str) -> Tuple[str, str]:
    """Dynamically determine canonical institution or organization name and academic/reporting year (zero hardcoded entities)."""
    combined_text = (pdf_path.name + " " + first_page_text[:1000]).lower()

    # Dynamic extraction: identify capitalized organizational entities from cover page
    inst_match = re.search(
        r"\b([A-Z][a-zA-Z\s&]{4,60}?(?:University|Institute(?:\s+of\s+[A-Za-z\s]+)?|Council(?:\s+of\s+[A-Za-z\s]+)?|Research Park|Foundation|Center|Centre|Laboratory|College|Corporation|Board))\b",
        first_page_text[:1500]
    )
    if inst_match and len(inst_match.group(1).strip()) > 5:
        uni = inst_match.group(1).strip()
        # Optional parenthetical acronym e.g. (NIPGR), (BRIC), (MIT)
        acro_match = re.search(rf"{re.escape(uni)}\s*\(([A-Z]{{2,8}})\)", first_page_text[:1800], re.IGNORECASE)
        if acro_match:
            uni = f"{uni} ({acro_match.group(1).upper()})"
    else:
        uni = pdf_path.stem.replace("_", " ").replace("-", " ").title()

    year_match = re.search(r"(20[12][0-9](?:[-–][0-9]{2,4})?)", combined_text)
    year = year_match.group(1) if year_match else "2024-25"

    return uni, year
