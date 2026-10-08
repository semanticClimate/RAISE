"""
RAISE Telemetry ANSI Styling Palette & Observability Modes
===========================================================
Purpose:
  Provides centralized ANSI terminal styling constants, Observability Modes (ObsMode),
  and formatting primitives for metric display and ANSI string stripping.

Components:
  - `C`: ANSI escape code palette for high-contrast dark terminal observability.
  - `ObsMode`: Display detail enum (NORMAL, VERBOSE, TRACE, DEBUG).
  - `strip_ansi`: Regular expression utility removing terminal escape codes.
  - `format_metric`: Visual badge formatter for MetricValue types.

Author: RAISE Core Architecture Team
Maintainability: Keep under 100 lines with zero side effects.
"""

from __future__ import annotations
import re
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.cli.models import MetricValue


class C:
    """High-contrast ANSI styling palette for RAISE Observability Console."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    
    TITLE = "\033[1;95m"
    BANNER = "\033[1;96m"
    SECTION = "\033[1;93m"
    SUCCESS = "\033[1;92m"
    WARN = "\033[1;93m"
    DANGER = "\033[1;91m"
    ACCENT = "\033[1;96m"
    INFO = "\033[94m"
    MUTED = "\033[90m"
    NUM = "\033[1;93m"         # Bold Gold
    DEV_TAG = "\033[1;93;41m"  # Bold Yellow on Red
    CITATION = "\033[1;96m"    # Bold Cyan
    ENTITY = "\033[1;94m"      # Bold Blue
    RELATION = "\033[1;95m"    # Bold Magenta


class ObsMode(str, Enum):
    NORMAL = "NORMAL"      # Answer + Citations + Confidence + Total Latency
    VERBOSE = "VERBOSE"    # Request + Intent + Retrieval Summary + Answer + Quality Scorecard + Latency Bars
    TRACE = "TRACE"        # Full 8 Observability Layers (Default)
    DEBUG = "DEBUG"        # Full 8 Layers + Raw Cypher + Candidate Funnel + Chunk IDs + Raw Timings


def strip_ansi(text: str) -> str:
    """Strips ANSI escape codes from string for accurate length calculation."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


def format_metric(m: MetricValue, fmt: str = "") -> str:
    """Helper to style metric values with color and honest state badges."""
    from src.cli.models import MetricState

    if not m.is_available:
        return f"{C.MUTED}-- [{m.state.value}]{C.RESET}"
    val_str = f"{m.value:{fmt}}" if fmt and isinstance(m.value, (int, float)) else str(m.value)
    unit_str = f" {m.unit}" if m.unit else ""
    if m.state == MetricState.MEASURED:
        return f"{C.NUM}{val_str}{C.RESET}{unit_str}"
    elif m.state == MetricState.DERIVED:
        return f"{C.NUM}{val_str}{C.RESET}{unit_str} {C.MUTED}[DERIVED]{C.RESET}"
    elif m.state == MetricState.ESTIMATED:
        return f"{C.NUM}{val_str}{C.RESET}{unit_str} {C.MUTED}[ESTIMATED]{C.RESET}"
    return f"{C.NUM}{val_str}{C.RESET}{unit_str}"
