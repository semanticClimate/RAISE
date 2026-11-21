import { RefreshCw } from 'lucide-react';
import type React from 'react';

export interface ResponseStoppedBannerProps {
  onRetry?: () => void;
  className?: string;
}

/**
 * Unobtrusive [Generation stopped by user] pill rendered when generation cancelled.
 * WCAG accessible and adhering to modern-web-guidance.
 */
export const ResponseStoppedBanner: React.FC<ResponseStoppedBannerProps> = ({
  onRetry,
  className = '',
}) => {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`response-stopped-banner inline-flex items-center gap-2 py-1 px-2.5 rounded-full bg-slate-100/90 dark:bg-white/[0.06] border border-slate-200/80 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 select-none animate-in fade-in duration-200 shadow-2xs ${className}`}
      data-testid="response-stopped-banner"
    >
      <div className="w-2 h-2 rounded-full bg-amber-500/80 shrink-0" />
      <span className="font-mono text-[11px] font-medium text-slate-700 dark:text-slate-300">
        [Generation stopped by user]
      </span>
      {onRetry && (
        <>
          <span className="text-slate-300 dark:text-slate-600">·</span>
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1 font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 hover:underline cursor-pointer"
            aria-label="Retry response"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Retry</span>
          </button>
        </>
      )}
    </div>
  );
};
