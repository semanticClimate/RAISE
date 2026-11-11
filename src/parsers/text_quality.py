"""
RAISE Document Parsing Quality & Normalization Subsystem
=========================================================
Purpose:
  Provides text normalization, semantic markdown section coalescing,
  and a quality gate for evaluating parsed PDF text prior
  to downstream embedding, vectorization, and knowledge graph ingestion.

Architecture:
  - TextNormalizer / normalize_text:
      Cleans spacing artifacts, zero-width spaces, hyphenated word line breaks,
      spaced uppercase/lowercase anomalies ("S N A P S H O T" -> "SNAPSHOT"),
      and degenerate table placeholder strings.
  - SectionCoalescer / coalesce_markdown_sections:
      Merges micro-sections emitted by Docling TableFormer / LayoutFormer into
      coherent, high-information semantic chunks respecting target word thresholds.
  - TextQualityGate:
      Assesses text quality metrics (garbled token ratio, token repetition,
      average word length) to intercept corrupted or OCR-hallucinated documents.

Author: RAISE Core Architecture Team
Maintainability: Keep under 250 lines with pure functional transformation logic.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List


def normalize_text(text: str) -> str:
    """
    Normalizes OCR and PDF extraction artifacts:
    - Coalesces tracked/spaced uppercase & lowercase letters:
        "S N A P S H O T" -> "SNAPSHOT", "e c o n o m i c" -> "economic"
    - Reconnects hyphenated word breaks: "de-\\nvelopment" -> "development"
    - Strips zero-width & non-standard spacing characters
    - Strips degenerate table placeholder strings
    - Cleans up excessive horizontal/vertical whitespace
    """
    if not text:
        return ""
    # 1. Strip zero-width spaces and control glyphs
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    text = text.replace('\xa0', ' ')

    # 2. Reconnect hyphenated word line-breaks: "inno-\nvation" -> "innovation"
    text = re.sub(r'(\b[a-zA-Z]+)-\s*\n\s*([a-zA-Z]+\b)', r'\1\2', text)

    # 3. Coalesce spaced uppercase letters (e.g. "S N A P S H O T" -> "SNAPSHOT")
    text = re.sub(r'\b([A-Z]\s){2,}[A-Z]\b', lambda m: m.group(0).replace(' ', ''), text)

    # 4. Coalesce spaced lowercase letters (e.g. "e c o n o m i c" -> "economic")
    text = re.sub(r'\b([a-z]\s){2,}[a-z]\b', lambda m: m.group(0).replace(' ', ''), text)

    # 5. Strip empty table placeholder artifacts
    text = re.sub(r'\[Table placeholder:\s*0\s*rows?,\s*0\s*cols?\]', '', text, flags=re.IGNORECASE)

    # 6. Clean up excessive horizontal and vertical whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def coalesce_markdown_sections(
    sections: List[str],
    target_words: int = 450,
    min_words: int = 120,
    max_words: int = 700,
) -> List[str]:
    """
    Coalesces micro-sections produced by Docling TableFormer / LayoutFormer
    into coherent, high-information semantic chunks.
    Ensures tables remain intact with their introducing context.
    """
    coalesced: List[str] = []
    current_chunk: List[str] = []
    current_word_count = 0

    for sec in sections:
        sec_clean = sec.strip()
        if not sec_clean or len(sec_clean) < 15:
            continue
        sec_words = len(sec_clean.split())

        if sec_words >= max_words:
            if current_chunk:
                coalesced.append("\n\n".join(current_chunk))
                current_chunk = []
                current_word_count = 0
            coalesced.append(sec_clean)
            continue

        if current_word_count + sec_words > target_words and current_word_count >= min_words:
            coalesced.append("\n\n".join(current_chunk))
            current_chunk = [sec_clean]
            current_word_count = sec_words
        else:
            current_chunk.append(sec_clean)
            current_word_count += sec_words

    if current_chunk:
        coalesced.append("\n\n".join(current_chunk))

    return coalesced


class TextQualityGate:
    """
    Quality gate evaluating parsed PDF text prior to embedding and indexing:
      - garbled_token_ratio: ratio of non-printable or corrupted character tokens
      - avg_word_length: detects single-letter fragmentation (< 1.8) or run-together text (> 24.0)
      - repetition_ratio: flags OCR hallucination loops (e.g. repeated words)
    """

    @staticmethod
    def assess(text: str) -> Dict[str, Any]:
        """
        Assesses string content against quality standards.
        Returns a dictionary containing boolean 'is_acceptable' flag, failure reasons,
        and statistical text attributes.
        """
        if not text or not text.strip():
            return {
                "is_acceptable": False,
                "reason": "empty_text",
                "word_count": 0,
                "avg_word_len": 0.0,
                "garbled_ratio": 1.0,
                "repetition_ratio": 0.0,
            }

        words = text.strip().split()
        total_words = len(words)
        if total_words == 0:
            return {
                "is_acceptable": False,
                "reason": "no_words",
                "word_count": 0,
                "avg_word_len": 0.0,
                "garbled_ratio": 1.0,
                "repetition_ratio": 0.0,
            }

        avg_len = sum(len(w) for w in words) / total_words

        # Check for garbled tokens
        garbled_count = 0
        for w in words:
            if len(w) > 35:
                garbled_count += 1
            elif re.search(r"([a-zA-Z0-9])\1{4,}", w):
                garbled_count += 1
            elif re.search(r"[^\x20-\x7E\u00A0-\u024F\u0900-\u097F\u20B9\n\r\t]", w):
                garbled_count += 1

        garbled_ratio = garbled_count / total_words

        # Check token repetition
        rep_count = sum(1 for i in range(1, total_words) if words[i].lower() == words[i-1].lower())
        repetition_ratio = rep_count / total_words

        is_acceptable = (
            garbled_ratio < 0.25
            and repetition_ratio < 0.35
            and 1.8 <= avg_len <= 24.0
        )

        reason = "pass"
        if not is_acceptable:
            reasons = []
            if garbled_ratio >= 0.25:
                reasons.append(f"garbled_ratio_{garbled_ratio:.2f}>=0.25")
            if repetition_ratio >= 0.35:
                reasons.append(f"repetition_ratio_{repetition_ratio:.2f}>=0.35")
            if avg_len < 1.8 or avg_len > 24.0:
                reasons.append(f"abnormal_avg_len_{avg_len:.1f}")
            reason = "; ".join(reasons)

        return {
            "is_acceptable": is_acceptable,
            "reason": reason,
            "word_count": total_words,
            "avg_word_len": round(avg_len, 2),
            "garbled_ratio": round(garbled_ratio, 4),
            "repetition_ratio": round(repetition_ratio, 4),
        }
