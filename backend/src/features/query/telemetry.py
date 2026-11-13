"""
Query Processing Pipeline Telemetry & State Tracking
====================================================
Component: `src.features.query.telemetry`
Architecture Layer: Pipeline Observability / Stage State Tracking

Overview:
---------
Tracks lifecycle state transitions, per-stage execution durations, and errors
across the RAISE query processing state machine.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

STAGE_NAMES = [
    "RECEIVED",
    "ROUTING",
    "COREFERENCE_RESOLUTION",
    "QUERY_DECOMPOSITION",
    "VECTOR_RETRIEVAL",
    "BM25_RETRIEVAL",
    "GRAPH_RETRIEVAL",
    "FUSION",
    "RERANKING",
    "SYNTHESIS",
    "QUALITY_GATE",
    "COMPLETED",
]

StageStatus = Literal["pending", "running", "completed", "failed", "skipped"]


@dataclass
class StageRecord:
    """Records timing and completion metadata for an individual pipeline stage."""
    stage: str
    status: StageStatus = "pending"
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    latency_ms: float = 0.0
    detail: Optional[str] = None
    error: Optional[str] = None

    def complete(self, detail: Optional[str] = None):
        self.status = "completed"
        self.end_time = time.time()
        self.latency_ms = round((self.end_time - self.start_time) * 1000, 2)
        if detail:
            self.detail = detail

    def skip(self, reason: Optional[str] = None):
        self.status = "skipped"
        self.end_time = time.time()
        self.latency_ms = 0.0
        self.detail = reason or "Skipped by pipeline policy"

    def fail(self, error: str):
        self.status = "failed"
        self.end_time = time.time()
        self.latency_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "detail": self.detail,
            "error": self.error,
        }


class PipelineTelemetry:
    """
    Tracks state machine execution transitions across all retrieval and synthesis stages.
    """

    def __init__(self):
        self.stages: Dict[str, StageRecord] = {
            s: StageRecord(stage=s, status="pending") for s in STAGE_NAMES
        }
        self.start_time = time.time()
        self.stages["RECEIVED"].complete("Request accepted by backend")

    def start_stage(self, stage: str, detail: Optional[str] = None):
        if stage in self.stages:
            self.stages[stage].status = "running"
            self.stages[stage].start_time = time.time()
            if detail:
                self.stages[stage].detail = detail

    def complete_stage(self, stage: str, detail: Optional[str] = None):
        if stage in self.stages:
            self.stages[stage].complete(detail)

    def skip_stage(self, stage: str, reason: Optional[str] = None):
        if stage in self.stages:
            self.stages[stage].skip(reason)

    def fail_stage(self, stage: str, error: str):
        if stage in self.stages:
            self.stages[stage].fail(error)

    def get_total_latency_sec(self) -> float:
        return round(time.time() - self.start_time, 3)

    def to_list(self) -> List[Dict[str, Any]]:
        return [self.stages[s].to_dict() for s in STAGE_NAMES]
