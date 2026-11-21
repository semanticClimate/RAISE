"""
RAISE TUI — Tab 3: Data Flow & Real-Time Pipeline Waterfall X-Ray
================================================================
Displays live stage execution waterfall, metrics, and data transfer inspection per request_id.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from src.core.telemetry_bus import get_telemetry_bus


class DataFlowTab(Vertical):
    """Tab 3: Real-Time Functioning & Data Transfer Waterfall X-Ray."""

    def __init__(self, on_inspect: Optional[Callable[[str, Any], None]] = None, **kwargs):
        super().__init__(id="tab-data-flow", classes="tab-pane", **kwargs)
        self.inspect_callback = on_inspect
        self.bus = get_telemetry_bus()
        self.stage_records: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("DATA FLOW & PIPELINE STAGE WATERFALL (Press Enter to inspect stage payloads)", id="flow-title")
        yield DataTable(id="flow-table")

    def on_mount(self) -> None:
        table = self.query_one("#flow-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Request ID", "Stage", "Status", "Duration", "Key Metrics", "Payload Preview")
        self.refresh_stages()
        self.set_interval(1.5, self.refresh_stages)

    def refresh_stages(self) -> None:
        table = self.query_one("#flow-table", DataTable)
        traces = self.bus.get_all_pipeline_traces()
        all_stages: List[Dict[str, Any]] = []
        for req_id, stages in traces.items():
            for s in stages:
                all_stages.append(s)

        if len(all_stages) == len(self.stage_records):
            return

        self.stage_records = all_stages
        table.clear()
        for idx, s in enumerate(self.stage_records[-150:]):
            req_txt = Text(str(s.get("request_id", "req_?")), style="bold #af87ff")
            stage_name = str(s.get("stage", "")).upper()
            stage_txt = Text(stage_name, style="bold #5fd7ff")
            status = str(s.get("status", "")).upper()
            status_style = "#87d787" if "COMPL" in status or "SUCC" in status else ("#ffd75f" if "RUN" in status else "#ff5f5f")
            status_txt = Text(status, style=f"bold {status_style}")

            dur = s.get("duration_ms", 0.0)
            dur_txt = Text(f"{dur:.1f}ms", style="dim")

            metrics = s.get("metrics") or {}
            metrics_str = ", ".join(f"{k}:{v}" for k, v in list(metrics.items())[:3])
            metrics_txt = Text(metrics_str, style="#eeeeee")

            preview = s.get("payload_preview") or ""
            preview_txt = Text(preview[:40], style="dim")

            table.add_row(req_txt, stage_txt, status_txt, dur_txt, metrics_txt, preview_txt, key=str(idx))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            row_idx = int(event.row_key.value)
            if 0 <= row_idx < len(self.stage_records):
                stage_data = self.stage_records[row_idx]
                title = f"Stage: {stage_data.get('stage', '').upper()} ({stage_data.get('request_id', '')})"
                payload_to_show = stage_data.get("raw_payload") or stage_data.get("metrics") or stage_data
                if self.inspect_callback:
                    self.inspect_callback(title, payload_to_show)
        except Exception:
            pass
