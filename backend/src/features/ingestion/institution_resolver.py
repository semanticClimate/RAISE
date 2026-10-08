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
    """Determine canonical institution name and academic/reporting year."""
    combined_text = (pdf_path.name + " " + first_page_text[:1000]).lower()

    if re.search(r"\b(iit madras research park|iitmrp)\b", combined_text):
        uni = "IIT Madras Research Park (IITMRP)"
    elif re.search(r"\b(indian institute of technology madras|iit madras|iitm)\b", combined_text):
        uni = "Indian Institute of Technology Madras (IIT Madras)"
    elif re.search(r"\b(biotechnology research and innovation council|bric)\b", combined_text):
        uni = "Biotechnology Research and Innovation Council (BRIC)"
    elif re.search(r"\b(national institute of plant genome research|nipgr)\b", combined_text):
        uni = "National Institute of Plant Genome Research (NIPGR)"
    elif re.search(r"\b(astrabio innovations council|astrabio)\b", combined_text):
        uni = "AstraBio Innovations Council"
    elif re.search(r"\b(panjab university|\(pu\))\b", combined_text):
        uni = "Panjab University"
    elif re.search(r"\b(delhi university|university of delhi|\(du\))\b", combined_text):
        uni = "Delhi University"
    elif re.search(r"\b(national stock exchange|nse)\b", combined_text):
        uni = "National Stock Exchange of India (NSE)"
    else:
        uni = pdf_path.stem.replace("_", " ").replace("-", " ").title()

    year_match = re.search(r"(20[12][0-9](?:[-–][0-9]{2,4})?)", combined_text)
    year = year_match.group(1) if year_match else "2024-25"

    return uni, year
