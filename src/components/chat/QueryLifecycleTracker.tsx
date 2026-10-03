import { Sparkles } from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';

/**
 * Mapping table from backend stages to user-friendly thoughts.
 */
export const STAGE_THOUGHT_MAP: Record<string, string> = {
  RECEIVED: 'Analyzing your question...',
  ROUTING: 'Analyzing question and scoping topics...',
  QUERY_DECOMPOSITION: 'Structuring research topics...',
  VECTOR_RETRIEVAL: 'Searching attached documents...',
  GRAPH_RETRIEVAL: 'Exploring concept relationships in knowledge graph...',
  FUSION: 'Finding the most relevant evidence...',
  RERANKING: 'Ranking and verifying evidence chunks...',
  SYNTHESIS: 'Synthesizing research findings...',
};

export const RESEARCH_STEPS = [
  { key: 'ROUTING', label: 'Analyzing your question...' },
  { key: 'QUERY_DECOMPOSITION', label: 'Structuring research topics...' },
  { key: 'VECTOR_RETRIEVAL', label: 'Searching attached documents...' },
  { key: 'GRAPH_RETRIEVAL', label: 'Exploring concept relationships in knowledge graph...' },
  { key: 'FUSION', label: 'Finding the most relevant evidence...' },
  { key: 'SYNTHESIS', label: 'Synthesizing research findings...' },
];

export interface QueryLifecycleTrackerProps {
  query?: string;
  stage?: string;
  onAbort?: () => void;
  decomposedQueries?: string[];
  isComplete?: boolean;
  durationSec?: number | null;
}

/**
 * Resolves the active friendly status phrase from either an explicit stage
 * or the elapsed time during autonomous pipeline execution.
 */
export function getFriendlyThought(stage?: string, elapsedSec = 0): string {
  if (stage) {
    const normalized = stage.toUpperCase().trim();
    if (STAGE_THOUGHT_MAP[normalized]) {
      return STAGE_THOUGHT_MAP[normalized];
    }
  }

  if (elapsedSec >= 3.5) {
    return STAGE_THOUGHT_MAP.SYNTHESIS;
  }
  if (elapsedSec >= 2.8) {
    return STAGE_THOUGHT_MAP.FUSION;
  }
  if (elapsedSec >= 2.1) {
    return STAGE_THOUGHT_MAP.GRAPH_RETRIEVAL;
  }
  if (elapsedSec >= 1.4) {
    return STAGE_THOUGHT_MAP.VECTOR_RETRIEVAL;
  }
  if (elapsedSec >= 0.7) {
    return STAGE_THOUGHT_MAP.QUERY_DECOMPOSITION;
  }
  return STAGE_THOUGHT_MAP.ROUTING;
}

/**
 * Formats elapsed duration into human-readable seconds or milliseconds based strictly
 * on actual measured execution time (never hardcoded):
 * - When durationSec is invalid or <= 0, returns null
 * - When < 1s, outputs e.g. "450ms"
 * - When >= 1s and < 60s, outputs e.g. "1.8s"
 * - When >= 60s, outputs e.g. "1m 12s"
 */
export function formatThoughtDuration(durationSec?: number | null): string | null {
  if (typeof durationSec !== 'number' || Number.isNaN(durationSec) || durationSec <= 0) {
    return null;
  }
  if (durationSec < 1) {
    const ms = Math.round(durationSec * 1000);
    return `${Math.max(ms, 1)}ms`;
  }
  if (durationSec >= 60) {
    const mins = Math.floor(durationSec / 60);
    const secs = Math.round(durationSec % 60);
    return `${mins}m ${secs}s`;
  }
  return `${durationSec.toFixed(1)}s`;
}

export interface ThoughtDurationProps {
  executionTimeSec?: number | null;
  decomposedQueries?: string[];
  citationsCount?: number;
  chunksCount?: number;
  sourcesCount?: number;
  routingStrategy?: string;
  query?: string;
  className?: string;
}

/**
 * Clean Thought Badge (Gemini / ChatGPT style):
 * Displays above the AI response card: `✦ Thought for {X}s` (or `✦ Thought` if no duration recorded).
 * Does not show any expandable accordion or fake hardcoded durations.
 */
export const ThoughtDuration: React.FC<ThoughtDurationProps> = ({
  executionTimeSec,
  className = '',
}) => {
  const formattedTime = formatThoughtDuration(executionTimeSec);

  return (
    <div
      className={`thought-duration-container mb-2 ml-0.5 select-none ${className}`}
      data-testid="thought-duration"
    >
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium text-slate-500 dark:text-slate-400 bg-slate-100/70 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/10 shadow-2xs">
        <Sparkles
          className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400 shrink-0"
          aria-hidden="true"
        />
        <span className="font-medium tracking-tight">
          {formattedTime ? `Thought for ${formattedTime}` : 'Thought'}
        </span>
      </div>
    </div>
  );
};

// Aliases for backwards compatibility
export const ResearchStepsAccordion = ThoughtDuration;
export const ThoughtDurationIndicator = ThoughtDuration;

/**
 * Active Thinking UI (Gemini / ChatGPT style):
 * Subtle, pulsing status indicator with active friendly phrase and live elapsed seconds.
 * E.g. `✦ Exploring concept relationships in knowledge graph... (2.4s)`
 */
export const QueryLifecycleTracker: React.FC<QueryLifecycleTrackerProps> = ({
  query,
  stage,
  onAbort: _onAbort,
  isComplete,
  durationSec,
}) => {
  const [elapsedSec, setElapsedSec] = useState<number>(0);

  useEffect(() => {
    if (isComplete) return;

    const startTime = Date.now();
    const timer = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;
      setElapsedSec(parseFloat(elapsed.toFixed(1)));
    }, 100);

    return () => clearInterval(timer);
  }, [isComplete]);

  if (isComplete) {
    const finalSec =
      typeof durationSec === 'number' && durationSec > 0
        ? durationSec
        : elapsedSec > 0
          ? elapsedSec
          : null;

    return <ThoughtDuration executionTimeSec={finalSec} query={query} />;
  }

  const activeThought = getFriendlyThought(stage, elapsedSec);

  return (
    <div
      className="query-lifecycle-tracker inline-flex items-center gap-2 py-1.5 px-3 text-xs rounded-xl bg-slate-100/80 dark:bg-white/[0.05] border border-slate-200/80 dark:border-white/10 text-slate-700 dark:text-slate-300 select-none animate-in fade-in duration-200 shadow-2xs"
      data-testid="query-lifecycle-tracker"
      role="status"
      aria-live="polite"
    >
      {/* Subtle pulsing sparkle glyph */}
      <Sparkles
        className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 animate-pulse shrink-0"
        aria-hidden="true"
      />

      {/* Active human-readable thought label */}
      <span className="font-medium tracking-tight">{activeThought}</span>

      {/* Elapsed seconds timer */}
      <span className="text-slate-400 dark:text-slate-500 font-mono text-[11px] font-medium shrink-0">
        ({elapsedSec.toFixed(1)}s)
      </span>

      {/* Screen-reader accessible context */}
      <div className="sr-only">
        {query && <span>Query: {query}. </span>}
        <span>Current research step: {activeThought}</span>
      </div>
    </div>
  );
};
