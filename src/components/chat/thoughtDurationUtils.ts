/**
 * RAISE Modular Thought Duration Utilities
 * ========================================
 * Pure functions for formatting, calculating, and resolving execution durations
 * for AI research responses.
 *
 * CRITICAL ARCHITECTURAL INVARIANT:
 * - Completed AI responses MUST have fixed, immutable execution durations.
 * - Live ticking is EXCLUSIVELY handled by `LiveThoughtDuration` during active streaming.
 * - Completed messages NEVER call `performance.now()` or dynamically increment on re-renders.
 * - Completed messages NEVER return null ("don't make it null show something").
 */

/**
 * Formats duration seconds into human-readable notation (Gemini / ChatGPT style):
 * - Sub-100ms: e.g. "90ms"
 * - Sub-60s: e.g. "0.8s", "1.4s"
 * - >= 60s: e.g. "1m 12s"
 */
export function formatThoughtDuration(durationSec?: number | null): string {
  if (typeof durationSec !== 'number' || Number.isNaN(durationSec) || durationSec <= 0) {
    return '';
  }
  if (durationSec >= 60) {
    const mins = Math.floor(durationSec / 60);
    const secs = Math.round(durationSec % 60);
    return `${mins}m ${secs}s`;
  }
  if (durationSec < 0.1) {
    const ms = Math.round(durationSec * 1000);
    return `${Math.max(ms, 10)}ms`;
  }
  return `${durationSec.toFixed(1)}s`;
}

export interface ResolveTurnExecutionTimeParams {
  activeRespDuration?: number | null;
  msgDuration?: number | null;
  activeResp?: {
    text?: string;
    content?: string;
    response?: {
      latency_sec?: number | null;
      execution_time?: number | null;
      elapsed_ms?: number | null;
    } | null;
  } | null;
  msg?: {
    text?: string;
    content?: string;
    response?: {
      latency_sec?: number | null;
      execution_time?: number | null;
      elapsed_ms?: number | null;
    } | null;
  } | null;
  calcHistoryDuration?: number | null;
}

/**
 * Resolves the immutable execution duration for a completed assistant turn.
 * Does NOT accept or compute live timestamps (startedAtMs) so completed turns
 * never tick or change when the user types subsequent queries.
 * 
 * Never returns null ("don't make it null show something"):
 * 1. Returns exact measured duration if available
 * 2. Returns backend latency if available
 * 3. Returns historical timestamp difference if available
 * 4. Deterministically estimates based on response length for historical/restored turns
 */
export function resolveTurnExecutionTime({
  activeRespDuration,
  msgDuration,
  activeResp,
  msg,
  calcHistoryDuration,
}: ResolveTurnExecutionTimeParams): number {
  // 1. Explicitly committed duration on active response version
  if (typeof activeRespDuration === 'number' && activeRespDuration > 0) {
    return Number(activeRespDuration.toFixed(1));
  }

  // 2. Explicitly committed duration on chat message or latency telemetry on message
  if (typeof msgDuration === 'number' && msgDuration > 0) {
    return Number(msgDuration.toFixed(1));
  }
  if (typeof (msg as any)?.latency_sec === 'number' && (msg as any).latency_sec > 0) {
    return Number((msg as any).latency_sec.toFixed(1));
  }
  if (typeof (activeResp as any)?.latency_sec === 'number' && (activeResp as any).latency_sec > 0) {
    return Number((activeResp as any).latency_sec.toFixed(1));
  }

  // 3. Backend response latency telemetry
  const resp = activeResp?.response || msg?.response;
  if (typeof resp?.latency_sec === 'number' && resp.latency_sec > 0) {
    return Number(resp.latency_sec.toFixed(1));
  }
  if (typeof (resp as any)?.execution_time === 'number' && (resp as any).execution_time > 0) {
    return Number((resp as any).execution_time.toFixed(1));
  }
  if (typeof (resp as any)?.duration_seconds === 'number' && (resp as any).duration_seconds > 0) {
    return Number((resp as any).duration_seconds.toFixed(1));
  }
  if (typeof (resp as any)?.duration_sec === 'number' && (resp as any).duration_sec > 0) {
    return Number((resp as any).duration_sec.toFixed(1));
  }
  if (typeof (resp as any)?.durationSec === 'number' && (resp as any).durationSec > 0) {
    return Number((resp as any).durationSec.toFixed(1));
  }
  if (typeof (resp as any)?.elapsed_ms === 'number' && (resp as any).elapsed_ms > 0) {
    return Number(((resp as any).elapsed_ms / 1000).toFixed(1));
  }

  // 4. Fallback to historical timestamp difference between user turn & assistant turn
  if (typeof calcHistoryDuration === 'number' && calcHistoryDuration > 0) {
    return Number(calcHistoryDuration.toFixed(1));
  }

  // 5. Deterministic duration derived from content length (so it never returns null and never changes when typing)
  const rawText =
    activeResp?.text ||
    (activeResp as any)?.content ||
    msg?.text ||
    (msg as any)?.content ||
    '';
  if (rawText && rawText.length > 0) {
    const estimated = Math.max(0.6, Number((0.4 + rawText.length / 280).toFixed(1)));
    return Math.min(estimated, 4.8);
  }

  return 0.7;
}

/**
 * Computes the historical timestamp difference (in seconds) between
 * the user's question and the assistant's response.
 */
export function computeHistoricalDuration(
  userCreatedAt?: string,
  assistantCreatedAt?: string
): number | null {
  if (!userCreatedAt || !assistantCreatedAt) return null;
  try {
    const diff =
      (new Date(assistantCreatedAt).getTime() - new Date(userCreatedAt).getTime()) / 1000;
    // Require at least 0.4s delta: batch database inserts insert user and assistant messages
    // at the identical timestamp (delta < 0.3s), which would falsely yield 0.0s.
    if (diff >= 0.4 && diff < 120) {
      return Number(diff.toFixed(1));
    }
  } catch {
    // Non-parseable timestamps fallback cleanly to null
  }
  return null;
}
