"""
RAISE TUI — Tab 1: Boot Diagnostics & Pre-flight Checklist
==========================================================
Displays every boot step, pre-flight check, durations, and expandable raw stderr.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static


class BootDiagnosticsTab(Vertical):
    """Tab 1: Auto-loads boot_diagnostics.jsonl and renders structured pre-flight checks."""

    def __init__(self, on_inspect: Optional[Callable[[str, Any], None]] = None, **kwargs):
        super().__init__(id="tab-boot", classes="tab-pane", **kwargs)
        self.inspect_callback = on_inspect
        self.records: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("BOOT DIAGNOSTICS & PRE-FLIGHT CHECKLIST (Press Enter to inspect raw details)", id="boot-title")
        yield DataTable(id="boot-table")

    def on_mount(self) -> None:
        table = self.query_one("#boot-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Status", "Stage", "Message", "Duration", "Timestamp")
        self.load_boot_logs()
        self.set_interval(2.0, self.load_boot_logs)

    def load_boot_logs(self) -> None:
        table = self.query_one("#boot-table", DataTable)
        repo_root = Path(__file__).resolve().parents[4]
        log_file = repo_root / "backend" / "logs" / "boot_diagnostics.jsonl"
        if not log_file.exists():
            return

        new_records = []
        try:
            for line in log_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    new_records.append(json.loads(line))
        except Exception:
            return

        if len(new_records) == len(self.records):
            return

        self.records = new_records
        table.clear()
        for idx, r in enumerate(self.records):
            level = str(r.get("level", "INFO")).upper()
            if "ERR" in level:
                status_txt = Text("✕ FAIL", style="bold #ff5f5f")
            elif "WARN" in level:
                status_txt = Text("▲ WARN", style="bold #ffd75f")
            else:
                status_txt = Text("✓ OK", style="bold #87d787")

            stage_txt = Text(str(r.get("stage", "BOOT")), style="bold #af87ff")
            msg_txt = Text(str(r.get("message", "")), style="#eeeeee")
            dur = r.get("duration_ms", 0)
            dur_txt = Text(f"{dur}ms" if dur > 0 else "-", style="dim")
            ts = r.get("ts", "")
            time_part = ts.split("T")[-1][:8] if "T" in ts else ts
            ts_txt = Text(time_part, style="dim")

            table.add_row(status_txt, stage_txt, msg_txt, dur_txt, ts_txt, key=str(idx))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            row_idx = int(event.row_key.value)
            if 0 <= row_idx < len(self.records):
                record = self.records[row_idx]
                title = f"{record.get('stage', 'BOOT')} Diagnostics"
                if self.inspect_callback:
                    if record.get("stderr"):
                        self.inspect_callback(title, f"MESSAGE: {record.get('message')}\n\nSTDERR:\n{record.get('stderr')}")
                    else:
                        self.inspect_callback(title, record)
        except Exception:
            pass
