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
 */

/**
 * Formats duration seconds into human-readable notation (Gemini / ChatGPT style):
 * - Sub-100ms: e.g. "90ms"
 * - Sub-60s: e.g. "0.8s", "1.4s"
 * - >= 60s: e.g. "1m 12s"
 */
export function formatThoughtDuration(durationSec?: number | null): string | null {
  if (typeof durationSec !== 'number' || Number.isNaN(durationSec) || durationSec <= 0) {
    return null;
  }
  if (durationSec >= 60) {
    const mins = Math.floor(durationSec / 60);
    const secs = Math.round(durationSec % 60);
    return `${mins}m ${secs}s`;
  }
  if (durationSec < 0.1) {
    const ms = Math.round(durationSec * 1000);
    return `${ms}ms`;
  }
  return `${durationSec.toFixed(1)}s`;
}

export interface ResolveTurnExecutionTimeParams {
  activeRespDuration?: number | null;
  msgDuration?: number | null;
  activeResp?: {
    response?: {
      latency_sec?: number | null;
      execution_time?: number | null;
      elapsed_ms?: number | null;
    } | null;
  } | null;
  msg?: {
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
 */
export function resolveTurnExecutionTime({
  activeRespDuration,
  msgDuration,
  activeResp,
  msg,
  calcHistoryDuration,
}: ResolveTurnExecutionTimeParams): number | null {
  // 1. Explicitly committed duration on active response version
  if (typeof activeRespDuration === 'number' && activeRespDuration > 0) {
    return Number(activeRespDuration.toFixed(1));
  }

  // 2. Explicitly committed duration on chat message
  if (typeof msgDuration === 'number' && msgDuration > 0) {
    return Number(msgDuration.toFixed(1));
  }

  // 3. Backend response latency telemetry
  const resp = activeResp?.response || msg?.response;
  if (typeof resp?.latency_sec === 'number' && resp.latency_sec > 0) {
    return Number(resp.latency_sec.toFixed(1));
  }
  if (typeof (resp as any)?.execution_time === 'number' && (resp as any).execution_time > 0) {
    return Number((resp as any).execution_time.toFixed(1));
  }
  if (typeof (resp as any)?.elapsed_ms === 'number' && (resp as any).elapsed_ms > 0) {
    return Number(((resp as any).elapsed_ms / 1000).toFixed(1));
  }

  // 4. Fallback to historical timestamp difference between user turn & assistant turn
  if (typeof calcHistoryDuration === 'number' && calcHistoryDuration > 0) {
    return Number(calcHistoryDuration.toFixed(1));
  }

  return null;
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
    if (diff > 0 && diff < 120) {
      return Number(diff.toFixed(1));
    }
  } catch {
    // Non-parseable timestamps fallback cleanly to null
  }
  return null;
}
