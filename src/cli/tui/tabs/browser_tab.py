"""
RAISE TUI — Tab 5: Browser Telemetry Stream & Headless Switcher
==============================================================
Streams live browser events ([WS] frontend hooks + [CDP] DevTools logs).
In --no-browser mode, displays a RAM/CPU-saving headless banner with on-demand Vite launcher.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, RichLog, Static

from src.core.telemetry_bus import get_telemetry_bus, TelemetryEvent


class BrowserTelemetryTab(Vertical):
    """Tab 5: Browser Telemetry Stream & Headless Mode Manager."""

    def __init__(
        self,
        is_headless: bool = False,
        on_open_browser: Optional[Callable[[bool], None]] = None,
        on_inspect: Optional[Callable[[str, Any], None]] = None,
        **kwargs,
    ):
        super().__init__(id="tab-browser", classes="tab-pane", **kwargs)
        self.is_headless = is_headless
        self.open_browser_callback = on_open_browser
        self.inspect_callback = on_inspect
        self.bus = get_telemetry_bus()
        self.browser_entries: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        if self.is_headless:
            yield Static(
                "HEADLESS MODE ACTIVE (Vite OFF — RAM/CPU Saved)\n"
                "Run ':open-browser' in COMMAND mode or click below to launch React UI.",
                id="headless-banner",
            )
            yield Button("Launch Frontend UI (:open-browser)", id="btn-launch-browser", variant="success")
        else:
            yield Static("BROWSER TELEMETRY STREAM ([WS] Frontend + [CDP] DevTools)", id="browser-title")

        yield RichLog(id="browser-rich-log", wrap=True, highlight=True, markup=True)

    def on_mount(self) -> None:
        self.bus.subscribe_sync(self._on_bus_event)
        for ev in self.bus.get_recent_events(limit=200):
            if ev.get("event_type") == "browser_event":
                self.add_browser_entry(ev.get("data", {}))

    def on_unmount(self) -> None:
        self.bus.unsubscribe_sync(self._on_bus_event)

    def _on_bus_event(self, event: TelemetryEvent) -> None:
        if event.event_type == "browser_event":
            self.app.call_from_thread(self.add_browser_entry, event.data)

    def add_browser_entry(self, data: Dict[str, Any]) -> None:
        self.browser_entries.append(data)
        log_widget = self.query_one("#browser-rich-log", RichLog)

        t = Text()
        source = str(data.get("source", "WS")).upper()
        level = str(data.get("level", "INFO")).upper()

        if "ERR" in level:
            t.append("✕ ", style="bold #ff5f5f")
        elif "WARN" in level:
            t.append("▲ ", style="bold #ffd75f")
        else:
            t.append("● ", style="bold #87d787")

        src_style = "#af87ff" if source == "CDP" else "#5fd7ff"
        t.append(f"[{source}] ", style=f"bold {src_style}")

        subtype = str(data.get("subtype", "")).upper()
        if subtype:
            t.append(f"[{subtype}] ", style="dim")

        msg = str(data.get("message", ""))
        t.append(msg, style="#eeeeee")

        log_widget.write(t)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-launch-browser":
            if self.open_browser_callback:
                self.open_browser_callback(False)
            banner = self.query("#headless-banner")
            if banner:
                banner.first().update("Vite Frontend is launching on http://localhost:5173...")
            btn = self.query("#btn-launch-browser")
            if btn:
                btn.first().remove()
