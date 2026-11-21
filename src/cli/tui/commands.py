"""
RAISE TUI — Command Palette Provider & Ex/Slash Command Engine
=============================================================
Dispatches Ex-style commands (:), Antigravity slash commands (/),
and powers Textual's fuzzy Command Palette (Ctrl+P).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from textual.command import CommandPalette, Hit, Hits, Provider

from src.core.telemetry_bus import get_telemetry_bus


class RaiseCommandProvider(Provider):
    """Fuzzy command provider for Textual's Ctrl+P command palette."""

    async def search(self, query: str) -> Hits:
        app = self.app
        matcher = self.matcher(query)

        commands = [
            ("Switch to Tab 1: BOOT", lambda: app.switch_tab("tab-boot"), "View boot diagnostics and pre-flight logs"),
            ("Switch to Tab 2: QUERY", lambda: app.switch_tab("tab-query"), "Interactive research query workbench"),
            ("Switch to Tab 3: DATA FLOW", lambda: app.switch_tab("tab-data-flow"), "Real-time pipeline stage waterfall"),
            ("Switch to Tab 4: BACKEND", lambda: app.switch_tab("tab-backend"), "Live FastAPI/Python unbuffered logs"),
            ("Switch to Tab 5: BROWSER", lambda: app.switch_tab("tab-browser"), "Live browser & CDP DevTools stream"),
            ("Toggle Inspector Drawer (b)", lambda: app.toggle_inspector(), "Show/hide right inspection drawer"),
            ("Open Browser UI (:open-browser)", lambda: app.open_browser_action(cdp=False), "Start Vite and launch browser"),
            ("Open Browser with CDP (:open-browser --cdp)", lambda: app.open_browser_action(cdp=True), "Start browser with Chrome DevTools Protocol"),
            ("Filter Logs: ALL", lambda: app.set_log_filter("ALL"), "Show all backend logs"),
            ("Filter Logs: WARN+", lambda: app.set_log_filter("WARN"), "Show warnings and errors only"),
            ("Filter Logs: ERR", lambda: app.set_log_filter("ERR"), "Show errors only"),
            ("Dump Diagnostic Bundle (:dump-debug)", lambda: app.dump_debug_bundle(), "Write debug bundle JSON"),
            ("Quit RAISE (:q)", lambda: app.exit_application(), "Graceful shutdown of all services"),
        ]

        for title, action, desc in commands:
            score = matcher.match(f"{title} {desc}")
            if score > 0:
                yield Hit(
                    score=score,
                    match_style="bold #5fd7ff",
                    title=title,
                    text=desc,
                    command=action,
                )


def parse_and_dispatch_command(
    raw_cmd: str,
    app: Any,
    on_output: Callable[[str], None],
) -> None:
    """Parses Ex commands (leading :) or slash commands (leading /)."""
    cmd = raw_cmd.strip()
    bus = get_telemetry_bus()

    # Ex-style commands
    if cmd.startswith(":"):
        action = cmd[1:].strip().lower()
        if action in ("q", "qa", "quit", "exit"):
            on_output("Initiating clean graceful shutdown...")
            app.exit_application()
        elif action == "open-browser":
            on_output("Starting Vite and launching browser...")
            app.open_browser_action(cdp=False)
        elif action in ("open-browser --cdp", "cdp"):
            on_output("Starting Vite and launching browser with CDP attached...")
            app.open_browser_action(cdp=True)
        elif action == "restart backend":
            on_output("Restarting backend service...")
            app.restart_backend()
        elif action == "restart frontend":
            on_output("Restarting frontend service...")
            app.restart_frontend()
        elif action == "stop-frontend":
            on_output("Stopping frontend service...")
            app.stop_frontend()
        elif action.startswith("filter "):
            flt = action.split(" ", 1)[1].strip().upper()
            if flt in ("ALL", "WARN", "ERR"):
                app.set_log_filter(flt)
                on_output(f"Log filter set to: {flt}")
            else:
                on_output("Usage: :filter all|warn|err")
        elif action in ("dump-debug", "export-debug"):
            bundle_path = bus.dump_debug_bundle()
            on_output(f"Diagnostic bundle written: {bundle_path}")
        elif action == "clear":
            app.clear_active_tab()
            on_output("Cleared active tab view.")
        else:
            on_output(f"Unknown command: :{action}. Press '?' or Ctrl+P for help.")
        return

    # Slash commands
    if cmd.startswith("/"):
        parts = cmd[1:].strip().split(" ", 1)
        sub = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if sub in ("help", "?"):
            on_output(
                "COMMANDS:\n"
                "  :open-browser [--cdp]  Launch React UI\n"
                "  :restart backend       Restart FastAPI\n"
                "  :restart frontend      Restart Vite\n"
                "  :filter all|warn|err   Filter backend logs\n"
                "  :dump-debug            Create forensic debug bundle\n"
                "  :q                     Graceful shutdown\n"
                "  /query <text>          Execute research query\n"
                "  Ctrl+P                 Fuzzy Command Palette\n"
                "  b                      Toggle right Inspector Drawer"
            )
        elif sub == "query":
            if arg:
                app.run_query_action(arg)
            else:
                on_output("Usage: /query <your question>")
        elif sub == "browser":
            app.open_browser_action(cdp=False)
        elif sub == "cdp":
            app.open_browser_action(cdp=True)
        elif sub in ("export-debug", "dump-debug"):
            bundle_path = bus.dump_debug_bundle()
            on_output(f"Diagnostic bundle written: {bundle_path}")
        elif sub == "clear":
            app.clear_active_tab()
        else:
            on_output(f"Unknown slash command: /{sub}. Type /help for assistance.")
        return
