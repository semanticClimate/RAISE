import { Sparkles } from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { formatThoughtDuration } from './thoughtDurationUtils';

/**
 * Mapping table from backend stages to user-friendly thoughts.
 */
const STAGE_THOUGHT_MAP: Record<string, string> = {
  RECEIVED: 'Thinking...',
  QUERY_INTAKE: 'Analyzing query intent & entities...',
  INTAKE: 'Analyzing query intent & entities...',
  ROUTING: 'Routing query strategy...',
  CONVERSATIONAL: 'Conversational dialogue...',
  PERSONA: 'Persona memory synthesis...',
  COREFERENCE_RESOLUTION: 'Resolving entities & context...',
  QUERY_DECOMPOSITION: 'Decomposing sub-questions...',
  VECTOR_RETRIEVAL: 'Dense vector retrieval...',
  VECTOR: 'Dense vector retrieval...',
  RETRIEVAL: 'Dense vector retrieval...',
  RETRIEVE: 'Dense vector retrieval...',
  BM25_RETRIEVAL: 'Keyword & lexical indexing...',
  BM25: 'Keyword & lexical indexing...',
  GRAPH_RETRIEVAL: 'Traversing knowledge graph...',
  GRAPH: 'Traversing knowledge graph...',
  FUSION: 'Reciprocal rank fusion...',
  RERANKING: 'Cross-encoder reranking...',
  RERANK: 'Cross-encoder reranking...',
  RERANKER: 'Cross-encoder reranking...',
  SYNTHESIS: 'Synthesizing verified response...',
  SYNTHESIZE: 'Synthesizing verified response...',
  GENERATE: 'Synthesizing verified response...',
  GENERATION: 'Synthesizing verified response...',
  QUALITY_GATE: 'Verifying factual grounding...',
  EVALUATION: 'Verifying factual grounding...',
  NLI_VERIFIER: 'Verifying factual grounding...',
  COMPLETED: 'Response finalized',
};

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
function getFriendlyThought(stage?: string, elapsedSec = 0): string {
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
 * Displays above the AI response card: `✦ Thought for {X}s` based strictly on genuine measured duration.
 */
export const ThoughtDuration: React.FC<ThoughtDurationProps> = ({
  executionTimeSec,
  decomposedQueries: _decomposedQueries,
  className = '',
}) => {
  const formattedTime = formatThoughtDuration(executionTimeSec);
  if (!formattedTime) return null;

  return (
    <div
      className={`thought-duration-container mb-2 ml-0.5 select-none ${className}`}
      data-testid="thought-duration"
      role="status"
    >
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium text-slate-500 dark:text-slate-400 bg-slate-100/70 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/10 shadow-2xs">
        <Sparkles className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400 shrink-0" />
        <span>Thought for {formattedTime}</span>
      </div>
    </div>
  );
};

export interface LiveThoughtDurationProps {
  startTimeMs: number;
  stage?: string;
  stageLabel?: string;
  className?: string;
}

/**
 * Live Thought Duration:
 * Renders immediately when query begins, ticking live elapsed seconds in active present tense
 * with dynamic stage phrasing matching the active execution pipeline phase.
 */
export const LiveThoughtDuration: React.FC<LiveThoughtDurationProps> = ({
  startTimeMs,
  stage,
  stageLabel,
  className = '',
}) => {
  const [elapsed, setElapsed] = useState<number>(() =>
    Math.max(0.1, Number(((performance.now() - startTimeMs) / 1000).toFixed(1)))
  );

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(
        Math.max(0.1, Number(((performance.now() - startTimeMs) / 1000).toFixed(1)))
      );
    }, 100);
    return () => clearInterval(timer);
  }, [startTimeMs]);

  const activeLabel =
    stageLabel?.trim() ||
    (stage && STAGE_THOUGHT_MAP[stage.toUpperCase().trim()]) ||
    getFriendlyThought(stage, elapsed) ||
    'Thinking...';

  return (
    <div
      className={`thought-duration-container mb-2 ml-0.5 select-none ${className}`}
      data-testid="live-thought-duration"
      role="status"
      aria-live="polite"
    >
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium text-indigo-600 dark:text-indigo-400 bg-indigo-50/80 dark:bg-indigo-500/10 border border-indigo-200/80 dark:border-indigo-500/20 shadow-2xs">
        <Sparkles
          className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400 shrink-0 animate-spin"
          aria-hidden="true"
        />
        <span className="font-medium tracking-tight">
          {activeLabel} ({elapsed.toFixed(1)}s)
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
