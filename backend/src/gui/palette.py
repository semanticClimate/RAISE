"""
RAISE GUI Color Palette & OLED Aesthetics
==========================================
Purpose:
  Provides centralized color palettes, background tones, text styles, and accent colors
  conforming to the OLED pitch-black and pure green (#10b981 / #22c55e) design specifications.

Author: RAISE Core Architecture Team
Maintainability: Keep under 60 lines with immutable color constants.
"""

from __future__ import annotations

# OLED Pitch Black Palette with Pure Green (#10b981 / #22c55e) Accents
BG_BLACK = "#000000"
PANEL_BG = "#060608"
CARD_BG = "#0b0b0e"
CARD_HEADER = "#111116"
BORDER_COLOR = "#222226"
BORDER_GREEN = "#10b981"
BORDER_ACCENT = "#22c55e"

TEXT_WHITE = "#ffffff"
TEXT_PRIMARY = "#f4f4f5"
TEXT_MUTED = "#9ca3af"
TEXT_DIM = "#6b7280"

# Proper Green Palette
GREEN_BRIGHT = "#22c55e"
GREEN_EMERALD = "#10b981"
GREEN_DARK = "#064e3b"
GREEN_BG_CHIP = "#052e16"

# Auxiliary Accents
ACCENT_CYAN = "#38bdf8"
ACCENT_AMBER = "#f59e0b"
ACCENT_RED = "#ef4444"
ACCENT_PURPLE = "#c084fc"
