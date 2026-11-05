import { AlertTriangle, Check, Copy, RotateCw, Sparkles, Square } from 'lucide-react';
import React from 'react';
import type { Citation } from '../../types';
import { AnswerMarkdown } from './AnswerMarkdown';
import { LiveThoughtDuration, ThoughtDuration } from './QueryLifecycleTracker';

export interface ActiveStreamingBubbleProps {
  content: string;
  isCurrentlyActive: boolean;
  isStopped?: boolean;
  persistenceFailed?: boolean;
  executionTimeSec?: number | null;
  startedAtMs?: number;
  citations?: Citation[];
  onViewPdf?: (fileName: string, page: number, mode?: 'page' | 'full' | 'view') => void;
  onCopy?: () => void;
  isCopied?: boolean;
  onRegenerate?: () => void;
  onAbort?: () => void;
  className?: string;
}

/**
 * ActiveStreamingBubble:
 * Isolated assistant response component that renders the in-flight SSE stream
 * and final synthesized response without triggering full-tree layout reconciliations.
 */
export const ActiveStreamingBubble: React.FC<ActiveStreamingBubbleProps> = React.memo(
  ({
    content,
    isCurrentlyActive,
    isStopped = false,
    persistenceFailed = false,
    executionTimeSec,
    startedAtMs,
    citations = [],
    onViewPdf,
    onCopy,
    isCopied = false,
    onRegenerate,
    onAbort,
    className = '',
  }) => {
    const hasContent = Boolean(content && content.trim().length > 0);

    return (
      <div
        className={`content-visibility-auto flex flex-col items-center group/response w-full mb-5 ${className}`}
      >
        {/* Thinking & Searching Tracker */}
        {isCurrentlyActive ? (
          <div className="w-full max-w-[clamp(36rem,90vw,58rem)] mx-auto mb-2 flex items-center justify-between">
            <LiveThoughtDuration startTimeMs={startedAtMs || performance.now()} />
            {onAbort && (
              <button
                type="button"
                onClick={onAbort}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium text-rose-600 dark:text-rose-400 bg-rose-50/80 dark:bg-rose-500/10 border border-rose-200/80 dark:border-rose-500/20 hover:bg-rose-100 dark:hover:bg-rose-500/20 transition-all cursor-pointer shadow-2xs"
                title="Stop generation"
              >
                <Square className="w-3 h-3 fill-current" />
                <span>Stop</span>
              </button>
            )}
          </div>
        ) : (
          !isStopped && (
            <div className="w-full max-w-[clamp(36rem,90vw,58rem)] mx-auto">
              <ThoughtDuration executionTimeSec={executionTimeSec} />
            </div>
          )
        )}

        {/* AI Response Card Box */}
        {(hasContent || isCurrentlyActive) && (
          <div className="ai-response-card w-full max-w-[clamp(36rem,90vw,58rem)] mx-auto bg-white dark:bg-[#131622] border border-slate-200/90 dark:border-white/[0.08] rounded-2xl rounded-tl-sm p-[clamp(0.875rem,2.5vw,1.5rem)] shadow-sm dark:shadow-xl transition-all">
            {/* Save-failure warning banner */}
            {persistenceFailed && (
              <div
                data-testid="persistence-failure-warning"
                className="mb-3.5 px-3.5 py-2.5 bg-amber-500/10 dark:bg-amber-500/15 border border-amber-500/30 rounded-xl flex items-center gap-2.5 text-xs text-amber-800 dark:text-amber-200"
              >
                <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                <span>
                  <strong>Save Warning:</strong> Message was generated but could not be saved to
                  backend database. This turn is not saved and will disappear on page refresh.
                </span>
              </div>
            )}

            {/* Markdown Answer Body */}
            {hasContent ? (
              <AnswerMarkdown
                content={content}
                citations={citations}
                showCitations={citations.length > 0}
                onViewPdf={onViewPdf}
              />
            ) : isCurrentlyActive ? (
              <div className="flex items-center gap-2.5 text-slate-400 text-sm py-2">
                <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" />
                <span className="font-mono text-xs">Synthesizing evidence...</span>
              </div>
            ) : null}

            {/* Action Bar when response is complete */}
            {!isCurrentlyActive && hasContent && (
              <div className="flex items-center justify-between pt-3 mt-3 border-t border-slate-100 dark:border-white/[0.06] text-xs text-slate-500">
                <div className="flex items-center gap-1.5">
                  {onCopy && (
                    <button
                      type="button"
                      onClick={onCopy}
                      className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/5 text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors flex items-center gap-1"
                      title={isCopied ? 'Copied to clipboard' : 'Copy answer'}
                    >
                      {isCopied ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-500" />
                          <span className="text-[11px] text-emerald-500">Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span className="text-[11px]">Copy</span>
                        </>
                      )}
                    </button>
                  )}

                  {onRegenerate && (
                    <button
                      type="button"
                      onClick={onRegenerate}
                      className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/5 text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors flex items-center gap-1"
                      title="Regenerate response"
                    >
                      <RotateCw className="w-3.5 h-3.5" />
                      <span className="text-[11px]">Regenerate</span>
                    </button>
                  )}
                </div>

                {isStopped && (
                  <span className="text-[11px] font-mono text-amber-500/80 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                    Stopped by user
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }
);

ActiveStreamingBubble.displayName = 'ActiveStreamingBubble';
