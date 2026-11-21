"""
RAISE Antigravity Developer TUI Workbench
==========================================
Powered by Textual + Rich. Provides zero-silence diagnostics, dual-mode execution
(headless vs live browser with optional CDP bridge), Vim-inspired modal engine,
real-time data flow waterfall, and interactive research query studio.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import urllib.error
import urllib.request
import webbrowser

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import TabbedContent, TabPane

from src.cli.tui.theme import TUI_CSS
from src.cli.tui.modal_engine import Mode, ModeManager, copy_to_clipboard
from src.cli.tui.header import TopStatusHeader
from src.cli.tui.inspector import InspectorDrawer
from src.cli.tui.composer import ComposerDock
from src.cli.tui.tabs.boot_tab import BootDiagnosticsTab
from src.cli.tui.tabs.query_tab import QueryLiveTab
from src.cli.tui.tabs.data_flow_tab import DataFlowTab
from src.cli.tui.tabs.backend_tab import BackendLogTab
from src.cli.tui.tabs.browser_tab import BrowserTelemetryTab
from src.cli.tui.commands import RaiseCommandProvider, parse_and_dispatch_command
from src.core.telemetry_bus import get_telemetry_bus
from src.cli.cdp_bridge import CDPBridge

logger = logging.getLogger("RAISE_TUI")


class RaiseTuiApp(App):
    """RAISE Interactive Terminal Developer Workbench & Diagnostic Studio."""

    CSS = TUI_CSS
    COMMANDS = {RaiseCommandProvider}
    TITLE = "RAISE Academic GraphRAG Studio"

    BINDINGS = [
        ("1", "key_tab_1", "Boot"),
        ("2", "key_tab_2", "Query"),
        ("3", "key_tab_3", "Data Flow"),
        ("4", "key_tab_4", "Backend"),
        ("5", "key_tab_5", "Browser"),
        ("b", "toggle_drawer", "Toggle Drawer"),
        ("i", "enter_insert", "Insert"),
        ("a", "enter_insert", "Append"),
        ("escape", "exit_to_normal", "Normal"),
        ("colon", "enter_command", "Command"),
        ("slash", "enter_search", "Search"),
        ("ctrl+p", "command_palette", "Palette"),
        ("question_mark", "show_help", "Help"),
        ("y", "yank_clipboard", "Copy"),
        ("p", "toggle_pause_scroll", "Pause"),
    ]

    def __init__(
        self,
        supervisor: Any = None,
        is_headless: bool = False,
        use_cdp: bool = False,
        focused_doc: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.supervisor = supervisor
        self.is_headless = is_headless
        self.use_cdp = use_cdp
        self.focused_doc = focused_doc
        self.bus = get_telemetry_bus()
        self.mode_manager = ModeManager(on_mode_change=self._on_mode_changed)

        # CDP Bridge instance
        self.cdp_bridge: Optional[CDPBridge] = CDPBridge(port=9222) if use_cdp else None
        self.cdp_thread: Optional[threading.Thread] = None

        # Child UI widgets
        browser_label = "CDP" if use_cdp else ("HEADLESS" if is_headless else "LIVE")
        self.header = TopStatusHeader(browser_mode=browser_label)
        self.inspector = InspectorDrawer()
        self.composer = ComposerDock(
            on_submit=self.handle_composer_submit,
            on_mode_change_request=self.mode_manager.set_mode,
        )

        self.tab_boot = BootDiagnosticsTab(on_inspect=self.show_inspector)
        self.tab_query = QueryLiveTab(on_inspect=self.show_inspector)
        self.tab_data_flow = DataFlowTab(on_inspect=self.show_inspector)
        self.tab_backend = BackendLogTab(on_inspect=self.show_inspector)
        self.tab_browser = BrowserTelemetryTab(
            is_headless=is_headless,
            on_open_browser=self.open_browser_action,
            on_inspect=self.show_inspector,
        )

    def compose(self) -> ComposeResult:
        yield self.header
        with Horizontal(id="main-container"):
            with TabbedContent(initial="pane-query", id="tabbed-content"):
                with TabPane("[1] BOOT", id="pane-boot"):
                    yield self.tab_boot
                with TabPane("[2] QUERY", id="pane-query"):
                    yield self.tab_query
                with TabPane("[3] DATA FLOW", id="pane-data-flow"):
                    yield self.tab_data_flow
                with TabPane("[4] BACKEND", id="pane-backend"):
                    yield self.tab_backend
                with TabPane("[5] BROWSER", id="pane-browser"):
                    yield self.tab_browser
            yield self.inspector
        yield self.composer

    def on_mount(self) -> None:
        """Called once TUI application finishes mounting."""
        if self.use_cdp and self.cdp_bridge:
            self._start_cdp_worker()

    def _on_mode_changed(self, new_mode: Mode) -> None:
        self.composer.set_mode_display(new_mode)

    # =========================================================================
    # Keyboard & Modal Input Handling
    # =========================================================================

    def on_key(self, event: events.Key) -> None:
        """Global key event interceptor enforcing modal editing rules."""
        cur_mode = self.mode_manager.current_mode

        if cur_mode in (Mode.INSERT, Mode.COMMAND, Mode.SEARCH):
            if event.key == "escape":
                self.action_exit_to_normal()
                event.prevent_default()
                event.stop()
                return
            elif event.key == "up":
                self.composer.history_up()
                event.prevent_default()
                event.stop()
                return
            elif event.key == "down":
                self.composer.history_down()
                event.prevent_default()
                event.stop()
                return
            # Let normal text insertion proceed in composer input
            return

        # NORMAL MODE KEY HANDLING
        if cur_mode == Mode.NORMAL:
            if event.key == "1":
                self.switch_tab("pane-boot")
                event.prevent_default()
            elif event.key == "2":
                self.switch_tab("pane-query")
                event.prevent_default()
            elif event.key == "3":
                self.switch_tab("pane-data-flow")
                event.prevent_default()
            elif event.key == "4":
                self.switch_tab("pane-backend")
                event.prevent_default()
            elif event.key == "5":
                self.switch_tab("pane-browser")
                event.prevent_default()
            elif event.key in ("i", "a"):
                self.action_enter_insert()
                event.prevent_default()
            elif event.key == "colon":
                self.action_enter_command()
                event.prevent_default()
            elif event.key == "slash":
                self.action_enter_search()
                event.prevent_default()
            elif event.key == "b":
                self.action_toggle_drawer()
                event.prevent_default()
            elif event.key == "question_mark":
                self.action_show_help()
                event.prevent_default()
            elif event.key == "y":
                self.action_yank_clipboard()
                event.prevent_default()
            elif event.key == "p":
                self.action_toggle_pause_scroll()
                event.prevent_default()
            elif event.key == "q":
                self.exit_application()
                event.prevent_default()

    def action_key_tab_1(self) -> None:
        self.switch_tab("pane-boot")

    def action_key_tab_2(self) -> None:
        self.switch_tab("pane-query")

    def action_key_tab_3(self) -> None:
        self.switch_tab("pane-data-flow")

    def action_key_tab_4(self) -> None:
        self.switch_tab("pane-backend")

    def action_key_tab_5(self) -> None:
        self.switch_tab("pane-browser")

    def action_toggle_drawer(self) -> None:
        self.inspector.toggle()

    def action_enter_insert(self) -> None:
        self.mode_manager.set_mode(Mode.INSERT)
        inp = self.composer.query_one("#composer-input")
        inp.focus()

    def action_enter_command(self) -> None:
        self.mode_manager.set_mode(Mode.COMMAND)
        inp = self.composer.query_one("#composer-input")
        inp.value = ":"
        inp.focus()

    def action_enter_search(self) -> None:
        self.mode_manager.set_mode(Mode.SEARCH)
        inp = self.composer.query_one("#composer-input")
        inp.value = "/"
        inp.focus()

    def action_exit_to_normal(self) -> None:
        self.mode_manager.set_mode(Mode.NORMAL)
        # Blur the input box so navigation keys don't type
        tabbed = self.query_one(TabbedContent)
        tabbed.focus()

    def action_show_help(self) -> None:
        help_text = (
            "RAISE TUI KEYBOARD CHEATSHEET:\n\n"
            "  1 - 5       : Switch directly between Tabs 1-5\n"
            "  i / a       : Enter INSERT mode (focus query composer)\n"
            "  :           : Enter COMMAND mode (Ex command line)\n"
            "  /           : Enter SEARCH mode\n"
            "  Esc         : Return to NORMAL mode\n"
            "  b           : Toggle Inspector Drawer (Right side)\n"
            "  Ctrl+P      : Fuzzy Command Palette\n"
            "  y           : Copy selected content to system clipboard\n"
            "  p           : Pause / resume live log streaming\n"
            "  q / :q      : Clean graceful shutdown of all processes\n\n"
            "EX COMMANDS:\n"
            "  :open-browser [--cdp]  : Start Vite and launch browser\n"
            "  :stop-frontend         : Stop Vite to save RAM/CPU\n"
            "  :restart backend       : Restart FastAPI gateway\n"
            "  :restart frontend      : Restart Vite dev server\n"
            "  :filter all|warn|err   : Filter backend log stream\n"
            "  :dump-debug            : Export forensic diagnostic bundle"
        )
        self.inspector.show_traceback("Keyboard & Command Help", help_text)

    def action_yank_clipboard(self) -> None:
        copied = copy_to_clipboard(self.inspector.current_content)
        if copied:
            self.notify("Copied inspector content to system clipboard", title="Clipboard")
        else:
            self.notify("Failed to copy or clipboard empty", title="Clipboard", severity="warning")

    def action_toggle_pause_scroll(self) -> None:
        self.notify("Auto-scroll toggle toggled", title="Stream")

    # =========================================================================
    # Tab & Inspector Operations
    # =========================================================================

    def switch_tab(self, tab_id: str) -> None:
        clean_id = tab_id.replace("tab-", "pane-")
        try:
            tabbed = self.query_one(TabbedContent)
            tabbed.active = clean_id
        except Exception as e:
            logger.warning(f"Failed to switch tab to {tab_id}: {e}")

    def show_inspector(self, title: str, payload: Any) -> None:
        if isinstance(payload, str) and ("Traceback" in payload or "STDERR" in payload):
            self.inspector.show_traceback(title, payload)
        else:
            self.inspector.show_json(title, payload)

    def toggle_inspector(self) -> None:
        self.inspector.toggle()

    def set_log_filter(self, level: str) -> None:
        self.switch_tab("pane-backend")
        self.tab_backend.set_filter(level)

    def clear_active_tab(self) -> None:
        try:
            tabbed = self.query_one(TabbedContent)
            active_id = tabbed.active
            if active_id == "pane-backend":
                self.tab_backend.query_one("#backend-rich-log").clear()
            elif active_id == "pane-browser":
                self.tab_browser.query_one("#browser-rich-log").clear()
        except Exception:
            pass

    # =========================================================================
    # Composer & Execution Engine
    # =========================================================================

    def handle_composer_submit(self, text: str) -> None:
        """Handles submission from bottom composer box."""
        clean = text.strip()
        if not clean:
            return

        if clean.startswith(":") or clean.startswith("/"):
            parse_and_dispatch_command(clean, self, self.on_command_output)
            self.action_exit_to_normal()
            return

        # Plain research query
        self.run_query_action(clean)
        self.action_exit_to_normal()

    def on_command_output(self, message: str) -> None:
        self.notify(message, title="RAISE System")

    def run_query_action(self, query: str) -> None:
        """Executes a research query through backend GraphRAG in a worker thread."""
        self.switch_tab("pane-query")
        self.tab_query.display_query_start(query)

        req_id = f"req-tui-{int(time.time() * 1000)}"
        session_id = f"tui-{int(time.time())}"

        def _worker():
            t0 = time.perf_counter()
            active_docs = [self.focused_doc] if self.focused_doc else None
            payload = {
                "query": query,
                "mode": "expert",
                "stream": False,
                "active_docs": active_docs,
                "session_id": session_id,
                "request_id": req_id,
            }

            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8000/api/chat",
                    data=data,
                    headers={"Content-Type": "application/json", "User-Agent": "RAISE-TUI-Workbench"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=120.0) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    res["execution_time"] = round(time.perf_counter() - t0, 2)
                    res["request_id"] = req_id
                    self.call_from_thread(self.tab_query.display_query_result, res)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                res = {
                    "grounded_answer": f"**Query Failed (HTTP {e.code})**: {err_body}",
                    "citations": [],
                    "request_id": req_id,
                    "status": f"HTTP_{e.code}",
                    "execution_time": round(time.perf_counter() - t0, 2),
                }
                self.call_from_thread(self.tab_query.display_query_result, res)
            except Exception as e:
                res = {
                    "grounded_answer": f"**Query Execution Error**: {type(e).__name__}: {e}",
                    "citations": [],
                    "request_id": req_id,
                    "status": "ERROR",
                    "execution_time": round(time.perf_counter() - t0, 2),
                }
                self.call_from_thread(self.tab_query.display_query_result, res)

        threading.Thread(target=_worker, daemon=True).start()

    # =========================================================================
    # Lifecycle, Subprocesses & Service Management
    # =========================================================================

    def open_browser_action(self, cdp: bool = False) -> None:
        """Boots Vite dev server on-demand and launches browser UI."""
        if self.supervisor:
            if not self.supervisor.frontend_proc or self.supervisor.frontend_proc.poll() is not None:
                self.supervisor.start_frontend()

        target_url = "http://localhost:5173"

        if cdp:
            if not self.cdp_bridge:
                self.cdp_bridge = CDPBridge(port=9222, target_url=target_url)
            self._start_cdp_worker()
            self.header.browser_mode = "CDP"
        else:
            try:
                webbrowser.open(target_url)
            except Exception:
                pass
            self.header.browser_mode = "LIVE"

        self.tab_browser.is_headless = False
        self.notify("Launched Vite Frontend & Web Browser UI", title="Browser")

    def _start_cdp_worker(self) -> None:
        if not self.cdp_bridge:
            return

        def _cdp_runner():
            if self.cdp_bridge.launch_browser():
                try:
                    asyncio.run(self.cdp_bridge.run())
                except Exception as e:
                    logger.warning(f"CDP Bridge event loop terminated: {e}")

        self.cdp_thread = threading.Thread(target=_cdp_runner, daemon=True)
        self.cdp_thread.start()

    def stop_frontend(self) -> None:
        if self.supervisor and self.supervisor.frontend_proc:
            try:
                self.supervisor.stop_frontend()
            except Exception:
                pass
        self.header.browser_mode = "HEADLESS"
        self.notify("Frontend Vite process stopped to conserve RAM/CPU.", title="Process")

    def restart_backend(self) -> None:
        if self.supervisor:
            self.notify("Restarting backend gateway on :8000...", title="Backend")
            threading.Thread(target=self.supervisor.restart_backend, daemon=True).start()

    def restart_frontend(self) -> None:
        if self.supervisor:
            self.notify("Restarting frontend dev server on :5173...", title="Frontend")
            threading.Thread(target=self.supervisor.restart_frontend, daemon=True).start()

    def dump_debug_bundle(self) -> None:
        bundle_path = self.bus.dump_debug_bundle()
        self.show_inspector("Diagnostic Debug Bundle Exported", {"path": str(bundle_path)})
        self.notify(f"Diagnostic bundle written: {Path(bundle_path).name}", title="Debug Export")

    def exit_application(self) -> None:
        """Initiates full graceful shutdown of supervisor and TUI."""
        if self.supervisor:
            try:
                self.supervisor.shutdown()
            except Exception:
                pass
        if self.cdp_bridge:
            try:
                self.cdp_bridge.stop()
            except Exception:
                pass
        self.exit()
