import { Sparkles } from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { ThoughtDuration } from './ThoughtDuration';
import { getFriendlyThought } from './thoughtStageMap';

export interface QueryLifecycleTrackerProps {
  query?: string;
  stage?: string;
  onAbort?: () => void;
  decomposedQueries?: string[];
  isComplete?: boolean;
  durationSec?: number | null;
}

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
      className="query-lifecycle-tracker inline-flex items-center gap-2 py-1.5 px-3 text-xs rounded-xl bg-slate-100/80 dark:bg-white/[0.05] border border-slate-200/80 dark:border-white/10 text-slate-700 dark:text-slate-300 select-none animate-in fade-in duration-250 ease-[cubic-bezier(0,0,0.2,1)] shadow-2xs"
      data-testid="query-lifecycle-tracker"
      role="status"
      aria-live="polite"
    >
      <Sparkles
        className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 animate-pulse shrink-0"
        aria-hidden="true"
      />
      <span className="font-medium tracking-tight">{activeThought}</span>
      <span className="text-slate-400 dark:text-slate-500 font-mono text-[11px] font-medium shrink-0">
        ({elapsedSec.toFixed(1)}s)
      </span>
      <div className="sr-only">
        {query && <span>Query: {query}. </span>}
        <span>Current research step: {activeThought}</span>
      </div>
    </div>
  );
};

// Re-exports for backwards compatibility
export {
  ThoughtDuration,
  LiveThoughtDuration,
  ResearchStepsAccordion,
  ThoughtDurationIndicator,
} from './ThoughtDuration';
export type {
  ThoughtDurationProps,
  LiveThoughtDurationProps,
} from './ThoughtDuration';
export { STAGE_THOUGHT_MAP, getFriendlyThought } from './thoughtStageMap';
