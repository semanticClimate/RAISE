"""
RAISE Telemetry Event Bus & Pipeline Instrumentation
===================================================
High-throughput, non-blocking telemetry event bus capturing unified observability
across HTTP lifecycle, GraphRAG pipeline stages, Python logging/warnings,
and browser/CDP runtime diagnostics.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import threading
import time
import traceback
from typing import Any, Callable, Deque, Dict, List, Optional, Set

logger = logging.getLogger("RAISE_TelemetryBus")

# Maximum retained events in memory for instant TUI / WebSocket replay
MAX_RING_EVENTS = 2000
MAX_PIPELINE_TRACES = 50


@dataclass
class TelemetryEvent:
    event_type: str  # "http_request", "http_response", "pipeline_stage", "backend_log", "browser_event"
    data: Dict[str, Any]
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")
    epoch: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "ts": self.ts,
            "epoch": self.epoch,
            "data": self.data,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class TelemetryBus:
    """
    Central event hub connecting backend services, pipeline execution stages,
    logging handlers, and the Textual TUI / frontend telemetry streams.
    """

    _instance: Optional["TelemetryBus"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._events: Deque[TelemetryEvent] = deque(maxlen=MAX_RING_EVENTS)
        self._pipeline_traces: Dict[str, List[Dict[str, Any]]] = {}
        self._recent_request_ids: Deque[str] = deque(maxlen=MAX_PIPELINE_TRACES)
        self._async_subscribers: Set[asyncio.Queue] = set()
        self._sync_subscribers: Set[Callable[[TelemetryEvent], None]] = set()
        self._sub_lock = threading.Lock()

        # Observability Counters
        self.warn_count = 0
        self.err_count = 0
        self.http_req_count = 0
        self.query_count = 0

        # Boot time
        self.boot_time = time.time()

    @classmethod
    def get_instance(cls) -> "TelemetryBus":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def emit(self, event_type: str, data: Dict[str, Any]) -> TelemetryEvent:
        """Thread-safe event broadcast to all async and sync subscribers."""
        # Update metrics
        if event_type == "backend_log":
            level = str(data.get("level", "")).upper()
            if "WARN" in level:
                self.warn_count += 1
            elif "ERR" in level or "CRIT" in level or "FATAL" in level:
                self.err_count += 1
        elif event_type == "browser_event":
            level = str(data.get("level", "")).upper()
            if "ERR" in level:
                self.err_count += 1
            elif "WARN" in level:
                self.warn_count += 1
        elif event_type == "http_request":
            self.http_req_count += 1
            if "/api/chat" in data.get("path", "") or "/graphrag" in data.get("path", ""):
                self.query_count += 1
        elif event_type == "pipeline_stage":
            req_id = data.get("request_id")
            if req_id:
                with self._sub_lock:
                    if req_id not in self._pipeline_traces:
                        self._pipeline_traces[req_id] = []
                        self._recent_request_ids.append(req_id)
                        # Trim older request traces
                        while len(self._pipeline_traces) > MAX_PIPELINE_TRACES:
                            oldest = self._recent_request_ids.popleft()
                            self._pipeline_traces.pop(oldest, None)
                    self._pipeline_traces[req_id].append(data)

        event = TelemetryEvent(event_type=event_type, data=data)
        with self._sub_lock:
            self._events.append(event)
            # Dispatch to sync callbacks
            for cb in list(self._sync_subscribers):
                try:
                    cb(event)
                except Exception as cb_err:
                    logger.debug(f"Sync subscriber error: {cb_err}")

            # Dispatch to async queues
            dead_queues = []
            for q in list(self._async_subscribers):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                        q.put_nowait(event)
                    except Exception:
                        pass
                except Exception:
                    dead_queues.append(q)

            for dq in dead_queues:
                self._async_subscribers.discard(dq)

        return event

    def subscribe_async(self, queue: asyncio.Queue) -> None:
        with self._sub_lock:
            self._async_subscribers.add(queue)

    def unsubscribe_async(self, queue: asyncio.Queue) -> None:
        with self._sub_lock:
            self._async_subscribers.discard(queue)

    def subscribe_sync(self, callback: Callable[[TelemetryEvent], None]) -> None:
        with self._sub_lock:
            self._sync_subscribers.add(callback)

    def unsubscribe_sync(self, callback: Callable[[TelemetryEvent], None]) -> None:
        with self._sub_lock:
            self._sync_subscribers.discard(callback)

    def get_recent_events(self, limit: int = 100, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._sub_lock:
            evs = list(self._events)
        if event_type:
            evs = [e for e in evs if e.event_type == event_type]
        return [e.to_dict() for e in evs[-limit:]]

    def get_pipeline_trace(self, request_id: str) -> List[Dict[str, Any]]:
        with self._sub_lock:
            return list(self._pipeline_traces.get(request_id, []))

    def get_all_pipeline_traces(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._sub_lock:
            return {k: list(v) for k, v in self._pipeline_traces.items()}

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "uptime_sec": round(time.time() - self.boot_time, 1),
            "warn_count": self.warn_count,
            "err_count": self.err_count,
            "http_req_count": self.http_req_count,
            "query_count": self.query_count,
            "recent_traces_count": len(self._pipeline_traces),
            "total_events_buffered": len(self._events),
        }

    def emit_http_request(
        self,
        method: str,
        path: str,
        origin: str,
        request_id: str,
        client_ip: str = "127.0.0.1",
        user_agent: str = "",
    ) -> None:
        self.emit(
            "http_request",
            {
                "method": method,
                "path": path,
                "origin": origin,
                "request_id": request_id,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "start_time": time.time(),
            },
        )

    def emit_http_response(
        self,
        method: str,
        path: str,
        origin: str,
        request_id: str,
        status_code: int,
        duration_ms: float,
        payload_bytes: int = 0,
        error: Optional[str] = None,
    ) -> None:
        self.emit(
            "http_response",
            {
                "method": method,
                "path": path,
                "origin": origin,
                "request_id": request_id,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "payload_bytes": payload_bytes,
                "error": error,
            },
        )

    def emit_pipeline_stage(
        self,
        request_id: str,
        stage: str,
        status: str,  # "running", "completed", "failed", "skipped"
        duration_ms: float = 0.0,
        metrics: Optional[Dict[str, Any]] = None,
        payload_preview: Optional[str] = None,
        raw_payload: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        self.emit(
            "pipeline_stage",
            {
                "request_id": request_id,
                "stage": stage,
                "status": status,
                "duration_ms": round(duration_ms, 2),
                "metrics": metrics or {},
                "payload_preview": payload_preview,
                "raw_payload": raw_payload,
                "error": error,
            },
        )

    def emit_backend_log(
        self,
        level: str,
        logger_name: str,
        message: str,
        traceback_str: Optional[str] = None,
        filename: Optional[str] = None,
        lineno: Optional[int] = None,
    ) -> None:
        self.emit(
            "backend_log",
            {
                "level": level.upper(),
                "logger": logger_name,
                "message": message,
                "traceback": traceback_str,
                "filename": filename,
                "lineno": lineno,
            },
        )

    def emit_browser_event(
        self,
        source: str,  # "WS", "CDP", "HTTP_BEACON"
        event_subtype: str,  # "console", "error", "unhandledrejection", "fetch", "hmr", "network"
        level: str,  # "INFO", "WARN", "ERROR", "DEBUG"
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.emit(
            "browser_event",
            {
                "source": source,
                "subtype": event_subtype,
                "level": level.upper(),
                "message": message,
                "details": details or {},
            },
        )

    def dump_debug_bundle(self, output_path: Optional[Path] = None) -> Path:
        """
        Creates a self-contained forensic debug bundle JSON file containing boot logs,
        recent warnings/errors, browser/CDP events, and full pipeline execution waterfalls.
        """
        repo_root = Path(__file__).resolve().parents[3]
        logs_dir = repo_root / "backend" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        if output_path is None:
            ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_path = logs_dir / f"debug_bundle_{ts_slug}.json"

        boot_logs: List[Dict[str, Any]] = []
        boot_path = logs_dir / "boot_diagnostics.jsonl"
        if boot_path.exists():
            try:
                for line in boot_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        boot_logs.append(json.loads(line))
            except Exception as e:
                boot_logs.append({"error": f"Failed reading boot_diagnostics: {e}"})

        bundle = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "snapshot": self.get_snapshot(),
            "boot_diagnostics": boot_logs,
            "recent_events": [e.to_dict() for e in list(self._events)[-300:]],
            "pipeline_traces": self.get_all_pipeline_traces(),
        }

        output_path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
        return output_path


def get_telemetry_bus() -> TelemetryBus:
    return TelemetryBus.get_instance()


# ==============================================================================
# Non-Invasive Python Warning & Logging Hooks
# ==============================================================================

class TelemetryLogHandler(logging.Handler):
    """Intercepts warnings and errors from the root logger and streams them to the bus."""

    def __init__(self, bus: TelemetryBus):
        super().__init__()
        self.bus = bus
        self.setLevel(logging.WARNING)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            tb_str = None
            if record.exc_info:
                tb_str = "".join(traceback.format_exception(*record.exc_info))
            self.bus.emit_backend_log(
                level=record.levelname,
                logger_name=record.name,
                message=self.format(record),
                traceback_str=tb_str,
                filename=record.filename,
                lineno=record.lineno,
            )
        except Exception:
            self.handleError(record)


_original_showwarning = None

def _telemetry_showwarning(message, category, filename, lineno, file=None, line=None):
    bus = get_telemetry_bus()
    msg_str = str(message)
    cat_name = category.__name__ if hasattr(category, "__name__") else str(category)
    bus.emit_backend_log(
        level="WARN",
        logger_name=f"Warning:{cat_name}",
        message=f"{cat_name}: {msg_str} ({filename}:{lineno})",
        filename=filename,
        lineno=lineno,
    )
    if _original_showwarning:
        _original_showwarning(message, category, filename, lineno, file=file, line=line)


def install_telemetry_hooks() -> None:
    """Installs root log handler and warnings.showwarning hook to prevent silent drops."""
    global _original_showwarning
    bus = get_telemetry_bus()

    # Hook warnings
    if _original_showwarning is None:
        _original_showwarning = sys.modules["warnings"].showwarning
        sys.modules["warnings"].showwarning = _telemetry_showwarning

    # Hook root logger
    root_log = logging.getLogger()
    if not any(isinstance(h, TelemetryLogHandler) for h in root_log.handlers):
        handler = TelemetryLogHandler(bus)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root_log.addHandler(handler)


# ==============================================================================
# Pipeline Stage Context Manager
# ==============================================================================

class PipelineStageTracker:
    def __init__(self, request_id: str, stage: str, bus: TelemetryBus, initial_meta: Optional[Dict[str, Any]] = None):
        self.request_id = request_id
        self.stage = stage
        self.bus = bus
        self.metrics: Dict[str, Any] = initial_meta or {}
        self.payload_preview: Optional[str] = None
        self.raw_payload: Optional[Any] = None
        self.start_time: float = 0.0

    def set_metric(self, key: str, value: Any) -> None:
        self.metrics[key] = value

    def set_payload(self, raw: Any, preview: Optional[str] = None) -> None:
        self.raw_payload = raw
        if preview:
            self.payload_preview = preview
        elif isinstance(raw, str):
            self.payload_preview = raw[:300] + ("..." if len(raw) > 300 else "")
        elif isinstance(raw, (dict, list)):
            s = json.dumps(raw, default=str)
            self.payload_preview = s[:300] + ("..." if len(s) > 300 else "")

    def __enter__(self) -> "PipelineStageTracker":
        self.start_time = time.perf_counter()
        self.bus.emit_pipeline_stage(
            request_id=self.request_id,
            stage=self.stage,
            status="running",
            metrics=self.metrics,
            payload_preview=self.payload_preview,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        elapsed_ms = (time.perf_counter() - self.start_time) * 1000
        if exc_val is not None:
            err_msg = str(exc_val)
            self.bus.emit_pipeline_stage(
                request_id=self.request_id,
                stage=self.stage,
                status="failed",
                duration_ms=elapsed_ms,
                metrics=self.metrics,
                payload_preview=self.payload_preview,
                raw_payload=self.raw_payload,
                error=err_msg,
            )
        else:
            self.bus.emit_pipeline_stage(
                request_id=self.request_id,
                stage=self.stage,
                status="completed",
                duration_ms=elapsed_ms,
                metrics=self.metrics,
                payload_preview=self.payload_preview,
                raw_payload=self.raw_payload,
            )


def trace_stage(request_id: str, stage: str, **initial_meta: Any) -> PipelineStageTracker:
    """Convenience context manager for wrapping a pipeline step."""
    bus = get_telemetry_bus()
    return PipelineStageTracker(request_id=request_id, stage=stage, bus=bus, initial_meta=initial_meta)
