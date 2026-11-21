import { Sparkles } from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { formatThoughtDuration } from './thoughtDurationUtils';
import { getFriendlyThought, STAGE_THOUGHT_MAP } from './thoughtStageMap';

export interface ThoughtDurationProps {
  executionTimeSec?: number | null;
  decomposedQueries?: string[];
  citationsCount?: number;
  chunksCount?: number;
  sourcesCount?: number;
  routingStrategy?: string;
  query?: string;
  requestId?: string;
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
  requestId?: string;
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

export const ResearchStepsAccordion = ThoughtDuration;
export const ThoughtDurationIndicator = ThoughtDuration;
