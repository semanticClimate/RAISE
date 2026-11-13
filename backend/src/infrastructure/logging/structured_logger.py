"""
RAISE Structlog Structured Telemetry & Context Logger
=====================================================
Structured Telemetry, Context Logger, and Database Tracing.
Architecture Layer: Observability, Trace Binding, and OpenTelemetry Alignment

Why Structlog:
--------------
  - Unstructured string logs ('Processing query for user 123...') are unparseable in enterprise dashboards.
  - Structlog creates structured key-value event streams with bound contextual metadata (session_id, trace_id, duration_ms).
  - Emits machine-readable JSON for OpenTelemetry collectors, Datadog, Grafana Loki, and CloudWatch.
  - Microsecond overhead with zero-copy log processing pipelines.

Components:
-----------
  1. configure_structured_logging: Configures formatting processors and log level filters.
  2. get_pipeline_logger: Returns context-bound logger with module metadata.
  3. ContextTracer: Context manager for timing execution spans and attaching diagnostic telemetry.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Dict, Optional

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    structlog = None
    HAS_STRUCTLOG = False


def configure_structured_logging(json_format: Optional[bool] = None) -> None:
    """
    Configures structlog processors for unified logging.
    Emits JSON in live environments or clean console key-values in development.
    """
    if not HAS_STRUCTLOG:
        return

    use_json = json_format if json_format is not None else (os.getenv("LOG_FORMAT", "").lower() == "json")

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if use_json:
        formatter_processor = structlog.processors.JSONRenderer()
    else:
        formatter_processor = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.format_exc_info,
            formatter_processor,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_pipeline_logger(name: str = "raise.pipeline") -> Any:
    """
    Returns a structured logger bound with module name.
    """
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)


class ContextTracer:
    """
    Context manager that records execution duration and structured metadata.
    """

    def __init__(self, logger: Any, operation: str, **initial_context: Any):
        self.logger = logger
        self.operation = operation
        self.context = initial_context
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.time()
        if hasattr(self.logger, "info"):
            self.logger.info(f"Started {self.operation}", operation=self.operation, **self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = round((time.time() - self.start_time) * 1000.0, 2)
        if exc_type is not None:
            if hasattr(self.logger, "error"):
                self.logger.error(
                    f"Failed {self.operation}",
                    operation=self.operation,
                    duration_ms=duration_ms,
                    error=str(exc_val),
                    **self.context,
                )
        else:
            if hasattr(self.logger, "info"):
                self.logger.info(
                    f"Completed {self.operation}",
                    operation=self.operation,
                    duration_ms=duration_ms,
                    **self.context,
                )


def log_db_operation(
    db_type: str,
    operation: str,
    duration_ms: float,
    success: bool = True,
    records_count: int = 0,
    **extra: Any,
) -> None:
    """
    Structured database telemetry logger supporting Neo4j, Redis, and PostgreSQL.
    Emits structured events with latency and error status.
    """
    p_logger = get_pipeline_logger(f"raise.database.{db_type.lower()}")
    event = f"{db_type.upper()} {operation} {'succeeded' if success else 'failed'}"
    payload = {
        "database": db_type.lower(),
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "success": success,
        "records_count": records_count,
        **extra,
    }
    if success:
        if hasattr(p_logger, "info"):
            p_logger.info(event, **payload)
    else:
        if hasattr(p_logger, "error"):
            p_logger.error(event, **payload)


# Auto-configure structlog on import
if HAS_STRUCTLOG:
    configure_structured_logging()
