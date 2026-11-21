"""
RAISE TUI — Right Inspector Drawer
==================================
Collapsible right drawer rendering syntax-highlighted Rich tracebacks,
collapsible JSON payload inspection, and live telemetry feeds.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from rich.json import JSON
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static


class InspectorDrawer(Vertical):
    """Toggleable side drawer for deep payload, telemetry, and error stack inspection."""

    def __init__(self, **kwargs):
        super().__init__(id="right-inspector", **kwargs)
        self.current_content: str = ""

    def compose(self) -> ComposeResult:
        yield Static("INSPECTOR DRAWER (Press 'b' to toggle)", id="inspector-title")
        with VerticalScroll(id="inspector-body"):
            yield Static("Select any stage, warning, or error and press Enter/e to inspect.", id="inspector-content")

    def toggle(self) -> bool:
        """Toggles drawer visibility; returns True if now visible."""
        if self.has_class("hidden"):
            self.remove_class("hidden")
            return True
        else:
            self.add_class("hidden")
            return False

    def show_traceback(self, title: str, tb_str: str) -> None:
        self.remove_class("hidden")
        title_widget = self.query_one("#inspector-title", Static)
        title_widget.update(f"✕ {title[:40]}")

        body = self.query_one("#inspector-content", Static)
        self.current_content = tb_str
        syntax = Syntax(tb_str, "pytb", theme="monokai", line_numbers=True, word_wrap=True)
        body.update(syntax)

    def show_json(self, title: str, payload: Any) -> None:
        self.remove_class("hidden")
        title_widget = self.query_one("#inspector-title", Static)
        title_widget.update(f"● {title[:40]}")

        body = self.query_one("#inspector-content", Static)
        try:
            if isinstance(payload, str):
                parsed = json.loads(payload)
                json_str = json.dumps(parsed, indent=2, default=str)
            else:
                json_str = json.dumps(payload, indent=2, default=str)
            self.current_content = json_str
            body.update(JSON(json_str))
        except Exception:
            self.current_content = str(payload)
            body.update(Syntax(str(payload), "text", theme="monokai", word_wrap=True))

    def show_raw(self, title: str, text: str) -> None:
        self.remove_class("hidden")
        title_widget = self.query_one("#inspector-title", Static)
        title_widget.update(f"→ {title[:40]}")

        body = self.query_one("#inspector-content", Static)
        self.current_content = text
        body.update(Text(text, style="#eeeeee"))
