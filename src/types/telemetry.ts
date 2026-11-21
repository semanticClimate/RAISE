// frontend/src/types/telemetry.ts

export type TelemetrySource = 'WS' | 'CDP' | 'BEACON' | 'FETCH' | 'CLIENT' | 'HTTP_BEACON';
export type TelemetryLevel = 'INFO' | 'WARN' | 'ERROR' | 'DEBUG';
export type TelemetrySubtype =
  | 'console'
  | 'exception'
  | 'unhandled_rejection'
  | 'network'
  | 'hmr'
  | 'navigation'
  | 'system'
  | 'pipeline'
  | 'pipeline_stage'
  | 'browser_event';

export interface BrowserTelemetryPayload {
  source?: TelemetrySource;
  subtype: TelemetrySubtype;
  level: TelemetryLevel;
  message: string;
  url?: string;
  line?: number;
  col?: number;
  stack?: string;
  request_id?: string;
  metadata?: Record<string, unknown>;
  timestamp?: string;
}

export interface NetworkTelemetryMetadata {
  method: string;
  url: string;
  status?: number;
  duration_ms: number;
  request_id?: string;
  error?: string;
  size_bytes?: number;
}

export interface BackendPipelineStageEvent {
  request_id: string;
  stage: string;
  status: 'running' | 'completed' | 'failed' | 'skipped';
  duration_ms?: number;
  metrics?: Record<string, unknown>;
  payload_preview?: string;
  raw_payload?: unknown;
  error?: string | null;
  timestamp?: string;
}

export interface TelemetryBusSnapshot {
  warn_count: number;
  err_count: number;
  http_req_count: number;
  query_count: number;
  active_subscribers?: number;
  uptime_seconds?: number;
  boot_time?: number;
  recent_pipeline_traces_count?: number;
}

export interface BackendLogEvent {
  level: string;
  logger_name: string;
  message: string;
  traceback_str?: string | null;
  filename?: string | null;
  lineno?: number | null;
  timestamp?: string;
}

export interface ConnectionReadyPayload {
  client_ip: string;
  session_token_prefix: string;
  timestamp: number;
  stats?: TelemetryBusSnapshot;
}
