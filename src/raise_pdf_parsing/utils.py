from __future__ import annotations

import re
import unicodedata

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_PRINTABLE_RE = re.compile(r"[ -~]")  # basic ASCII printable range


def slugify(text: str) -> str:
    """Turn arbitrary text into a short, stable, filesystem/id-safe slug."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_RE.sub("-", normalized.lower()).strip("-")
    return slug or "block"


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def text_confidence(text: str) -> float:
    """Heuristic extraction-confidence score in [0, 1] for born-digital PDF text.

    Born-digital text extracted by PyMuPDF is reliable almost all of the
    time; the main failure mode is broken font encodings, which surface as
    runs of control characters, the Unicode replacement character, or very
    low printable-character density. This is *not* OCR confidence -- it is a
    deterministic sanity score so badly-encoded blocks can be routed to
    human review downstream instead of silently trusted.
    """
    stripped = text.strip()
    if not stripped:
        return 0.0

    length = len(stripped)
    printable = len(_PRINTABLE_RE.findall(stripped))
    replacement_chars = stripped.count("\ufffd")
    control_chars = sum(1 for ch in stripped if unicodedata.category(ch) == "Cc")

    printable_ratio = printable / length
    penalty = (replacement_chars + control_chars) / length

    score = 0.6 + 0.4 * printable_ratio - penalty
    if length < 3:
        score -= 0.15
    return round(clamp(score), 3)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()
