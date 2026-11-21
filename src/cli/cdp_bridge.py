"""
RAISE Chromium DevTools Protocol (CDP) Telemetry Bridge
======================================================
Attaches directly to Chrome or Edge via remote debugging port 9222 to capture
unfiltered browser console logs, uncaught exceptions, CORS/CSP errors,
and network failures without requiring frontend modification.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional
import urllib.request

from src.core.telemetry_bus import get_telemetry_bus

logger = logging.getLogger("RAISE_CDPBridge")


def find_browser_executable() -> Optional[str]:
    """Locates Chrome or Edge binary across standard Windows and system locations."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    for name in ("chrome", "google-chrome", "msedge", "edge", "chromium"):
        which_path = shutil.which(name)
        if which_path:
            return which_path
    return None


class CDPBridge:
    def __init__(self, port: int = 9222, target_url: str = "http://localhost:5173"):
        self.port = port
        self.target_url = target_url
        self.browser_proc: Optional[subprocess.Popen] = None
        self.bus = get_telemetry_bus()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._profile_dir = Path(tempfile.gettempdir()) / "raise_cdp_profile"

    def launch_browser(self) -> bool:
        """Launches Chromium or Edge with remote debugging enabled."""
        browser_exe = find_browser_executable()
        if not browser_exe:
            self.bus.emit_browser_event(
                source="CDP",
                event_subtype="system",
                level="WARN",
                message="No Chromium/Edge binary found on PATH. CDP telemetry unavailable.",
            )
            return False

        self._profile_dir.mkdir(parents=True, exist_ok=True)
        args = [
            browser_exe,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self._profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
            self.target_url,
        ]

        try:
            self.browser_proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.bus.emit_browser_event(
                source="CDP",
                event_subtype="system",
                level="INFO",
                message=f"Browser launched with CDP on port {self.port} ({Path(browser_exe).name})",
            )
            return True
        except Exception as e:
            self.bus.emit_browser_event(
                source="CDP",
                event_subtype="system",
                level="ERROR",
                message=f"Failed to launch browser with CDP: {e}",
            )
            return False

    async def connect_and_listen(self) -> None:
        """Polls for debugger WebSocket and streams Runtime, Log, and Network events."""
        import websockets

        self._running = True
        ws_url: Optional[str] = None

        # Poll for CDP endpoint readiness (up to 12s)
        for _ in range(24):
            if not self._running:
                return
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{self.port}/json")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    tabs = json.loads(resp.read().decode("utf-8"))
                    # Find page target
                    for tab in tabs:
                        if tab.get("type") == "page" and "webSocketDebuggerUrl" in tab:
                            ws_url = tab["webSocketDebuggerUrl"]
                            break
                    if ws_url:
                        break
            except Exception:
                await asyncio.sleep(0.5)

        if not ws_url:
            self.bus.emit_browser_event(
                source="CDP",
                event_subtype="system",
                level="WARN",
                message="CDP target page not ready or unreachable on port 9222.",
            )
            return

        try:
            async with websockets.connect(ws_url, max_size=10_000_000) as ws:
                self.bus.emit_browser_event(
                    source="CDP",
                    event_subtype="system",
                    level="INFO",
                    message="Connected to Chrome DevTools Protocol stream.",
                )

                # Enable DevTools domains
                await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
                await ws.send(json.dumps({"id": 2, "method": "Log.enable"}))
                await ws.send(json.dumps({"id": 3, "method": "Network.enable"}))

                while self._running:
                    try:
                        msg_str = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        msg = json.loads(msg_str)
                        method = msg.get("method", "")
                        params = msg.get("params", {})

                        if method == "Runtime.consoleAPICalled":
                            c_type = params.get("type", "log")
                            args = params.get("args", [])
                            values = [str(a.get("value", a.get("description", ""))) for a in args]
                            text = " ".join(values)
                            level = "ERROR" if c_type in ("error", "assert") else ("WARN" if c_type == "warning" else "INFO")
                            self.bus.emit_browser_event(
                                source="CDP",
                                event_subtype="console",
                                level=level,
                                message=f"[{c_type.upper()}] {text}",
                                details=params,
                            )

                        elif method == "Runtime.exceptionThrown":
                            details = params.get("exceptionDetails", {})
                            text = details.get("text", "Uncaught Exception")
                            exc = details.get("exception", {})
                            desc = exc.get("description") or text
                            self.bus.emit_browser_event(
                                source="CDP",
                                event_subtype="exception",
                                level="ERROR",
                                message=desc,
                                details=details,
                            )

                        elif method == "Log.entryAdded":
                            entry = params.get("entry", {})
                            text = entry.get("text", "")
                            level = entry.get("level", "info").upper()
                            source = entry.get("source", "browser")
                            self.bus.emit_browser_event(
                                source="CDP",
                                event_subtype="log",
                                level=level,
                                message=f"[{source.upper()}] {text}",
                                details=entry,
                            )

                        elif method == "Network.loadingFailed":
                            url = params.get("url", "")
                            err_text = params.get("errorText", "Failed")
                            canceled = params.get("canceled", False)
                            if not canceled:
                                self.bus.emit_browser_event(
                                    source="CDP",
                                    event_subtype="network",
                                    level="ERROR",
                                    message=f"Failed loading {url}: {err_text}",
                                    details=params,
                                )

                        elif method == "Network.responseReceived":
                            resp = params.get("response", {})
                            status = resp.get("status", 200)
                            url = resp.get("url", "")
                            if status >= 400:
                                self.bus.emit_browser_event(
                                    source="CDP",
                                    event_subtype="network",
                                    level="WARN" if status < 500 else "ERROR",
                                    message=f"HTTP {status} on {url}",
                                    details=resp,
                                )
                    except asyncio.TimeoutError:
                        continue
                    except Exception as loop_err:
                        if self._running:
                            logger.debug(f"CDP message stream notice: {loop_err}")
                        break
        except Exception as conn_err:
            if self._running:
                self.bus.emit_browser_event(
                    source="CDP",
                    event_subtype="system",
                    level="WARN",
                    message=f"CDP connection ended: {conn_err}",
                )

    def stop(self) -> None:
        self._running = False
        if self.browser_proc:
            try:
                self.browser_proc.terminate()
                self.browser_proc.wait(timeout=2.0)
            except Exception:
                try:
                    self.browser_proc.kill()
                except Exception:
                    pass
            self.browser_proc = None
