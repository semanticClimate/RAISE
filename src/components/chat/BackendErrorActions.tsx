import { ArrowRight, Download, RefreshCw } from 'lucide-react';
import type React from 'react';
import type { ControlCenterSection } from './errorDiagnosis';

export interface BackendErrorActionsProps {
  targetTab: ControlCenterSection;
  primaryButtonLabel: string;
  isDownloadableModel?: boolean;
  modelName?: string;
  downloadSuccess: boolean;
  isDownloading: boolean;
  onOpenTarget: (tab: ControlCenterSection) => void;
  onDirectDownload: () => void;
  onRetry?: () => void;
  onOpenSettings?: () => void;
}

export const BackendErrorActions: React.FC<BackendErrorActionsProps> = ({
  targetTab,
  primaryButtonLabel,
  isDownloadableModel,
  modelName,
  downloadSuccess,
  isDownloading,
  onOpenTarget,
  onDirectDownload,
  onRetry,
  onOpenSettings,
}) => {
  return (
    <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-200/60 dark:border-white/[0.06]">
      <button
        type="button"
        onClick={() => onOpenTarget(targetTab)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 active:scale-95 rounded-lg transition-all cursor-pointer shadow-2xs"
      >
        <span>{primaryButtonLabel}</span>
        <ArrowRight className="w-3 h-3" />
      </button>

      {isDownloadableModel && modelName && !downloadSuccess && !isDownloading && (
        <button
          type="button"
          onClick={onDirectDownload}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-200 bg-white/90 hover:bg-slate-100 dark:bg-white/10 dark:hover:bg-white/15 border border-slate-200 dark:border-white/10 rounded-lg transition-all cursor-pointer shadow-2xs"
        >
          <Download className="w-3 h-3 text-slate-600 dark:text-slate-300" />
          <span>Download Model Now</span>
        </button>
      )}

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          aria-label="Retry query"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-200 bg-white/80 hover:bg-slate-100 dark:bg-white/5 dark:hover:bg-white/10 border border-slate-200 dark:border-white/10 rounded-lg transition-all cursor-pointer shadow-2xs"
        >
          <RefreshCw className="w-3 h-3 text-slate-500" />
          <span>Retry Query</span>
        </button>
      )}

      {onOpenSettings && (
        <button
          type="button"
          onClick={onOpenSettings}
          className="px-2.5 py-1.5 text-xs font-normal text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:underline cursor-pointer ml-auto"
        >
          Connection Settings
        </button>
      )}
    </div>
  );
};
