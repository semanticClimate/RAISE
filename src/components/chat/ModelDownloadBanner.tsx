import { Check, Loader2 } from 'lucide-react';
import type React from 'react';

export interface ModelDownloadBannerProps {
  isDownloading: boolean;
  downloadProgress: { percent: number; status: string } | null;
  downloadSuccess: boolean;
  downloadError: string | null;
}

export const ModelDownloadBanner: React.FC<ModelDownloadBannerProps> = ({
  isDownloading,
  downloadProgress,
  downloadSuccess,
  downloadError,
}) => {
  if (!isDownloading && !downloadSuccess && !downloadError) return null;

  return (
    <>
      {isDownloading && (
        <div className="mb-3 p-2.5 rounded-lg bg-indigo-50/80 dark:bg-indigo-950/40 border border-indigo-200/80 dark:border-indigo-800/50 text-xs text-indigo-900 dark:text-indigo-200 space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <span className="inline-flex items-center gap-1.5 font-medium">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600 dark:text-indigo-400" />
              <span>
                {downloadProgress?.status || 'Downloading model weights...'}
              </span>
            </span>
            <span className="font-mono font-semibold">
              {downloadProgress?.percent ? `${downloadProgress.percent}%` : ''}
            </span>
          </div>
          {typeof downloadProgress?.percent === 'number' && (
            <div className="w-full bg-indigo-200/60 dark:bg-indigo-900/50 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-indigo-600 dark:bg-indigo-400 h-1.5 rounded-full transition-all duration-200"
                style={{
                  width: `${Math.min(100, Math.max(0, downloadProgress.percent))}%`,
                }}
              />
            </div>
          )}
        </div>
      )}

      {downloadSuccess && (
        <div className="mb-3 p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/50 text-xs text-emerald-800 dark:text-emerald-300 inline-flex items-center gap-1.5">
          <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span>
            Model downloaded successfully! Click <strong>Retry Query</strong> to
            proceed.
          </span>
        </div>
      )}

      {downloadError && (
        <div className="mb-3 p-2 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/50 text-xs text-rose-800 dark:text-rose-300">
          {downloadError}
        </div>
      )}
    </>
  );
};
