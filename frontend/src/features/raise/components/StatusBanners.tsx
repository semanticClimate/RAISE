import React from 'react';

export interface StatusBannersProps {
  appMode: string;
  onOpenConfigureLlm: () => void;
  onRetryConnection: () => void;
  errorPopup: {
    title: string;
    message?: string;
    onRetry?: () => void;
  } | null;
  onCloseErrorPopup: () => void;
}

export const StatusBanners: React.FC<StatusBannersProps> = ({
  appMode,
  onOpenConfigureLlm,
  onRetryConnection,
  errorPopup,
  onCloseErrorPopup,
}) => {
  return (
    <>
      {/* Gateway Disconnected / Offline Notice with Retry & Connect */}
      {appMode === 'offline' && (
        <div className="fixed top-14 sm:top-16 left-0 sm:left-16 right-0 z-30 flex justify-center px-[clamp(0.5rem,2vw,1rem)] pt-1 pointer-events-none animate-in fade-in slide-in-from-top-1 duration-200">
          <div
            data-testid="gateway-disconnected-notice"
            className="pointer-events-auto inline-flex items-center gap-1.5 sm:gap-2 py-1 px-3 rounded-full bg-rose-500/15 dark:bg-rose-950/75 border border-rose-500/30 text-rose-950 dark:text-rose-200 shadow-sm backdrop-blur-md text-[clamp(10px,2.4vw,12px)] max-w-[calc(100vw-1.5rem)] sm:max-w-none text-center sm:text-left"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0 animate-pulse" />
            <span className="leading-tight truncate sm:whitespace-normal font-medium">
              Backend Gateway not connected.
            </span>
            <button
              type="button"
              aria-label="Connect Gateway"
              onClick={onOpenConfigureLlm}
              className="font-bold underline hover:text-rose-950 dark:hover:text-white cursor-pointer ml-1 inline-flex items-center gap-1 shrink-0"
            >
              Connect Gateway
            </button>
            <span className="text-rose-300 dark:text-rose-600">·</span>
            <button
              type="button"
              aria-label="Retry Connection"
              onClick={onRetryConnection}
              className="font-medium underline hover:text-rose-950 dark:hover:text-white cursor-pointer inline-flex items-center gap-1 shrink-0"
            >
              <svg
                className="w-3 h-3"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
              >
                <polyline points="1 4 1 10 7 10" />
                <polyline points="23 20 23 14 17 14" />
                <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
              </svg>
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Little Error Popup Toast */}
      {errorPopup && (
        <div
          data-testid="little-error-popup"
          role="alert"
          className="fixed bottom-[clamp(4.5rem,10vh,5.5rem)] sm:bottom-5 right-3 sm:right-5 z-50 max-w-sm w-[calc(100vw-1.5rem)] sm:w-auto p-3 sm:p-3.5 rounded-2xl bg-white/95 dark:bg-[#181a20]/95 text-slate-900 dark:text-white border border-slate-200/90 dark:border-white/15 shadow-2xl backdrop-blur-md flex items-center gap-3 animate-in fade-in slide-in-from-bottom-2 duration-200 select-none"
        >
          <div className="w-8 h-8 rounded-xl bg-rose-50 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400 flex items-center justify-center shrink-0 shadow-2xs">
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-slate-900 dark:text-white truncate">
              {errorPopup.title}
            </p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
              {errorPopup.message || 'Please try again.'}
            </p>
          </div>
          {errorPopup.onRetry && (
            <button
              type="button"
              onClick={() => {
                const retryFn = errorPopup.onRetry;
                onCloseErrorPopup();
                retryFn?.();
              }}
              className="px-2.5 py-1 text-[11px] font-semibold bg-rose-600 hover:bg-rose-700 text-white rounded-lg transition-colors cursor-pointer shrink-0 shadow-xs"
            >
              Retry
            </button>
          )}
          <button
            type="button"
            onClick={onCloseErrorPopup}
            className="text-slate-400 hover:text-slate-700 dark:hover:text-white p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 transition-colors cursor-pointer shrink-0"
            aria-label="Close error popup"
          >
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}
    </>
  );
};
