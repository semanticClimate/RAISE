import type React from 'react';

export interface QueryBoxVoiceErrorProps {
  voiceError: string | null;
  onDismiss: () => void;
}

export const QueryBoxVoiceError: React.FC<QueryBoxVoiceErrorProps> = ({ voiceError, onDismiss }) => {
  if (!voiceError) return null;

  return (
    <div className="mt-2 px-3 py-1.5 text-xs text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 rounded-xl flex items-center justify-between gap-2 animate-in fade-in duration-150">
      <div className="flex items-center gap-1.5 min-w-0">
        <svg
          className="w-4 h-4 text-rose-500 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
        <span>{voiceError}</span>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="p-1 text-rose-500 hover:text-rose-700 dark:hover:text-rose-200 rounded-md cursor-pointer"
        aria-label="Dismiss error"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
};
