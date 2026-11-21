"""
RAISE TUI — Tab 4: Backend Telemetry & Diagnostic Stream
========================================================
Unbuffered Python/FastAPI/Uvicorn log stream with syntax-highlighted tracebacks
and filterable severity levels (ALL, WARN+, ERR).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, RichLog, Static

from src.core.telemetry_bus import get_telemetry_bus, TelemetryEvent


class BackendLogTab(Vertical):
    """Tab 4: Live unbuffered FastAPI/Python logs with traceback formatting."""

    def __init__(self, on_inspect: Optional[Callable[[str, Any], None]] = None, **kwargs):
        super().__init__(id="tab-backend", classes="tab-pane", **kwargs)
        self.inspect_callback = on_inspect
        self.bus = get_telemetry_bus()
        self.filter_level = "ALL"  # "ALL", "WARN", "ERR"
        self.log_entries: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="backend-filter-bar"):
            yield Static("FILTER: ", id="filter-label")
            yield Button("ALL", id="btn-filter-all", variant="primary")
            yield Button("WARN+", id="btn-filter-warn")
            yield Button("ERR", id="btn-filter-err")
        yield RichLog(id="backend-rich-log", wrap=True, highlight=True, markup=True)

    def on_mount(self) -> None:
        self.bus.subscribe_sync(self._on_bus_event)
        # Load existing buffered backend logs
        for ev in self.bus.get_recent_events(limit=200):
            if ev.get("event_type") == "backend_log":
                self.add_log_entry(ev.get("data", {}))

    def on_unmount(self) -> None:
        self.bus.unsubscribe_sync(self._on_bus_event)

    def _on_bus_event(self, event: TelemetryEvent) -> None:
        if event.event_type == "backend_log":
            self.app.call_from_thread(self.add_log_entry, event.data)

    def add_log_entry(self, data: Dict[str, Any]) -> None:
        self.log_entries.append(data)
        level = str(data.get("level", "INFO")).upper()

        if self.filter_level == "WARN" and "WARN" not in level and "ERR" not in level:
            return
        if self.filter_level == "ERR" and "ERR" not in level and "CRIT" not in level:
            return

        log_widget = self.query_one("#backend-rich-log", RichLog)

        t = Text()
        # Level badge
        if "ERR" in level or "CRIT" in level:
            t.append("✕ ERR  ", style="bold #ff5f5f")
        elif "WARN" in level:
            t.append("▲ WARN ", style="bold #ffd75f")
        else:
            t.append("● INFO ", style="bold #87d787")

        logger_name = str(data.get("logger", "backend"))
        t.append(f"[{logger_name}] ", style="bold #5fd7ff")
        t.append(str(data.get("message", "")), style="#eeeeee")

        fn = data.get("filename")
        ln = data.get("lineno")
        if fn and ln:
            t.append(f" ({fn}:{ln})", style="dim")

        log_widget.write(t)

        tb = data.get("traceback")
        if tb and self.inspect_callback:
            # Auto-notify inspector if severe error
            pass

    def set_filter(self, level: str) -> None:
        self.filter_level = level.upper()
        log_widget = self.query_one("#backend-rich-log", RichLog)
        log_widget.clear()
        for d in self.log_entries:
            self.add_log_entry(d)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-filter-all":
            self.set_filter("ALL")
        elif event.button.id == "btn-filter-warn":
            self.set_filter("WARN")
        elif event.button.id == "btn-filter-err":
            self.set_filter("ERR")
