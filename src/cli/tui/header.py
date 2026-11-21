"""
RAISE TUI — Pinned Status Header
================================
Displays real-time system substrate mode, port statuses (8000, 5173),
active LLM synthesizer, browser mode, and dynamic WARN/ERR badges.
"""

from __future__ import annotations

import socket
import time
from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static

from src.core.telemetry_bus import get_telemetry_bus
from src.core.config import models


def is_port_listening(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.15)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


class TopStatusHeader(Static):
    """Pinned top status bar with live infrastructure indicators."""

    api_online: reactive[bool] = reactive(False)
    vite_online: reactive[bool] = reactive(False)
    warn_count: reactive[int] = reactive(0)
    err_count: reactive[int] = reactive(0)

    def __init__(
        self,
        substrate_mode: str = "FAST",
        llm_label: str = "vllm:Qwen2.5-14B",
        browser_mode: str = "HEADLESS",
        **kwargs,
    ):
        super().__init__(id="top-header", **kwargs)
        self.substrate_mode = substrate_mode
        self.llm_label = llm_label
        self.browser_mode = browser_mode
        self.bus = get_telemetry_bus()

    def on_mount(self) -> None:
        self.refresh_status()
        self.set_interval(1.5, self.refresh_status)

    def refresh_status(self) -> None:
        self.api_online = is_port_listening(8000)
        self.vite_online = is_port_listening(5173)
        self.warn_count = self.bus.warn_count
        self.err_count = self.bus.err_count
        self.update(self._render_header_text())

    def _render_header_text(self) -> Text:
        t = Text()
        # Title & Substrate
        t.append("RAISE ", style="bold #5fd7ff")
        t.append("// ", style="dim")
        t.append(f"{self.substrate_mode} ", style="bold #af87ff")
        t.append("· ", style="dim")

        # FastAPI :8000
        t.append("API :8000 ", style="bold #eeeeee")
        if self.api_online:
            t.append("● ", style="bold #87d787")
        else:
            t.append("○ ", style="dim #ff5f5f")
        t.append("· ", style="dim")

        # Vite :5173
        t.append("VITE :5173 ", style="bold #eeeeee")
        if self.vite_online:
            t.append("● ", style="bold #87d787")
        else:
            t.append("○ ", style="dim #ffd75f")
        t.append("· ", style="dim")

        # LLM Synthesizer
        t.append(f"LLM {self.llm_label} ", style="bold #eeeeee")
        t.append("● ", style="bold #87d787")
        t.append("· ", style="dim")

        # Browser state
        b_color = "#87d787" if self.browser_mode in ("LIVE", "BROWSER", "CDP") else "#ffd75f"
        t.append(f"BROWSER {self.browser_mode} ", style=f"bold {b_color}")
        t.append("│ ", style="dim")

        # Warning / Error badges
        w_style = "bold #ffd75f" if self.warn_count > 0 else "dim"
        e_style = "bold #ff5f5f" if self.err_count > 0 else "dim"
        t.append(f"WARN: {self.warn_count} ", style=w_style)
        t.append(f"ERR: {self.err_count}", style=e_style)

        return t
