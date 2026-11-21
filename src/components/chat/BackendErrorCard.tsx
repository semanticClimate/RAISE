import { AlertCircle, Cpu, Database, Laptop, Layers } from 'lucide-react';
import type React from 'react';
import { useControlCenterStore } from '../../features/control-center/store/useControlCenterStore';
import { BackendErrorActions } from './BackendErrorActions';
import { ModelDownloadBanner } from './ModelDownloadBanner';
import { ResponseStoppedBanner } from './ResponseStoppedBanner';
import {
  type BackendErrorDetails,
  type ControlCenterSection,
  diagnoseBackendError,
} from './errorDiagnosis';
import { useModelPull } from './useModelPull';

export interface BackendErrorCardProps {
  error: BackendErrorDetails;
  targetUrl: string;
  onRetry?: () => void;
  onOpenSettings?: () => void;
  onOpenControlCenter?: (tab?: ControlCenterSection) => void;
}

export const BackendErrorCard: React.FC<BackendErrorCardProps> = ({
  error,
  targetUrl,
  onRetry,
  onOpenSettings,
  onOpenControlCenter,
}) => {
  const { title, message, isOffline, isAborted } = error;
  const isUserAbort =
    isAborted ||
    title?.toLowerCase().includes('stopped') ||
    title?.toLowerCase().includes('aborted') ||
    message?.toLowerCase().includes('aborted') ||
    message?.toLowerCase().includes('cancelled locally') ||
    message?.toLowerCase().includes('response stopped');

  if (isUserAbort) {
    return <ResponseStoppedBanner onRetry={onRetry} className="my-1" />;
  }

  const diagnosis = diagnoseBackendError(error, targetUrl);
  const {
    isDownloading,
    downloadProgress,
    downloadSuccess,
    downloadError,
    handleDirectDownload,
  } = useModelPull(diagnosis.modelName);

  const handleOpenTarget = (tab: ControlCenterSection) => {
    if (onOpenControlCenter) {
      onOpenControlCenter(tab);
    } else {
      useControlCenterStore.getState().openToTab(tab);
    }
  };

  const CategoryIcon =
    diagnosis.category === 'neural_embedding' ||
    diagnosis.category === 'neural_reranker' ||
    diagnosis.category === 'neural_verifier'
      ? Layers
      : diagnosis.category === 'llm_inference'
        ? Cpu
        : diagnosis.category === 'storage_substrate'
          ? Database
          : diagnosis.category === 'server_offline'
            ? Laptop
            : AlertCircle;

  const isCleanCard =
    diagnosis.category === 'neural_embedding' ||
    diagnosis.category === 'neural_reranker' ||
    diagnosis.category === 'neural_verifier' ||
    diagnosis.category === 'llm_inference' ||
    diagnosis.category === 'storage_substrate';

  return (
    <div
      role="alert"
      className={`backend-error-card rounded-xl p-4 shadow-2xs transition-all max-w-2xl border ${
        isCleanCard
          ? 'bg-amber-50/50 dark:bg-[#1a1612]/90 border-amber-200/80 dark:border-amber-500/25'
          : isOffline || diagnosis.category === 'server_offline'
            ? 'bg-slate-50/90 dark:bg-white/[0.04] border-slate-200/90 dark:border-white/10'
            : 'bg-rose-50/70 dark:bg-[#1a1219]/90 border-rose-200/80 dark:border-rose-500/25'
      }`}
    >
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${
              isCleanCard
                ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-500 dark:text-amber-400'
                : isOffline || diagnosis.category === 'server_offline'
                  ? 'bg-slate-200/80 dark:bg-white/10 text-slate-500 dark:text-slate-400'
                  : 'bg-rose-100 dark:bg-rose-500/20 text-rose-500 dark:text-rose-400'
            }`}
          >
            <CategoryIcon className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h3
              className={`text-xs font-semibold truncate ${
                isCleanCard
                  ? 'text-amber-950 dark:text-amber-200'
                  : isOffline || diagnosis.category === 'server_offline'
                    ? 'text-slate-800 dark:text-slate-200'
                    : 'text-rose-950 dark:text-rose-200'
              }`}
            >
              {diagnosis.headline}
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
              isCleanCard
                ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-800 dark:text-amber-300'
                : isOffline || diagnosis.category === 'server_offline'
                  ? 'bg-slate-200/80 dark:bg-white/10 text-slate-600 dark:text-slate-400'
                  : 'bg-rose-100 dark:bg-rose-500/20 text-rose-700 dark:text-rose-300'
            }`}
          >
            {diagnosis.badgeLabel}
          </span>
        </div>
      </div>

      <p
        className={`text-[12px] leading-relaxed font-medium mb-1 ${
          isCleanCard
            ? 'text-amber-900/90 dark:text-amber-200/90'
            : isOffline || diagnosis.category === 'server_offline'
              ? 'text-slate-700 dark:text-slate-200'
              : 'text-rose-900/90 dark:text-rose-200/90'
        }`}
      >
        {diagnosis.cleanMessage}
      </p>

      <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-normal mb-3">
        {diagnosis.recommendedAction}
      </p>

      <ModelDownloadBanner
        isDownloading={isDownloading}
        downloadProgress={downloadProgress}
        downloadSuccess={downloadSuccess}
        downloadError={downloadError}
      />

      <div className="mb-3 p-2.5 rounded-lg bg-slate-100/80 dark:bg-white/5 border border-slate-200/80 dark:border-white/10 text-xs">
        <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 block mb-1">
          How to resolve:
        </span>
        <ul className="space-y-1 text-[11px] text-slate-600 dark:text-slate-400 list-disc list-inside">
          <li>Click <strong>Retry Query</strong> below to attempt again.</li>
          <li>
            If the problem persists, click <strong>{diagnosis.primaryButtonLabel}</strong> to check your configuration.
          </li>
        </ul>
      </div>

      <BackendErrorActions
        targetTab={diagnosis.targetTab}
        primaryButtonLabel={diagnosis.primaryButtonLabel}
        isDownloadableModel={diagnosis.isDownloadableModel}
        modelName={diagnosis.modelName}
        downloadSuccess={downloadSuccess}
        isDownloading={isDownloading}
        onOpenTarget={handleOpenTarget}
        onDirectDownload={handleDirectDownload}
        onRetry={onRetry}
        onOpenSettings={onOpenSettings}
      />
    </div>
  );
};

// Re-exports for backwards compatibility
export { ResponseStoppedBanner } from './ResponseStoppedBanner';
export type { ResponseStoppedBannerProps } from './ResponseStoppedBanner';
export type {
  BackendErrorDetails,
  ControlCenterSection,
  ParsedErrorDiagnosis,
} from './errorDiagnosis';
export { BackendErrorActions } from './BackendErrorActions';
