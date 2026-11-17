import {
  AlertCircle,
  ArrowRight,
  Check,
  Cpu,
  Database,
  Download,
  Laptop,
  Layers,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import React, { useState } from 'react';
import { platformAdapter } from '../../features/control-center/services/platformAdapter';
import { useControlCenterStore } from '../../features/control-center/store/useControlCenterStore';

export interface BackendErrorDetails {
  title: string;
  message: string;
  cause?: string;
  action?: string;
  status?: number;
  isOffline?: boolean;
  isTimeout?: boolean;
  isAborted?: boolean;
}

export type ControlCenterSection = 'overview' | 'models' | 'neural' | 'databases' | 'platform' | 'launch';

export interface BackendErrorCardProps {
  error: BackendErrorDetails;
  targetUrl: string;
  onRetry?: () => void;
  onOpenSettings?: () => void;
  onOpenControlCenter?: (tab?: ControlCenterSection) => void;
}

export interface ResponseStoppedBannerProps {
  onRetry?: () => void;
  className?: string;
}

// Unobtrusive [Generation stopped by user] pill rendered when generation cancelled
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

export interface ParsedErrorDiagnosis {
  category:
    | 'neural_embedding'
    | 'neural_reranker'
    | 'neural_verifier'
    | 'llm_inference'
    | 'storage_substrate'
    | 'server_offline'
    | 'generic';
  headline: string;
  cleanMessage: string;
  recommendedAction: string;
  targetTab: ControlCenterSection;
  primaryButtonLabel: string;
  badgeLabel: string;
  modelName?: string;
  isDownloadableModel?: boolean;
}

export function diagnoseBackendError(
  error: BackendErrorDetails,
  targetUrl: string
): ParsedErrorDiagnosis {
  const rawMsg = (error.message || '').trim();
  const rawTitle = (error.title || '').trim();
  const rawCause = (error.cause || '').trim();
  const combined = `${rawTitle} ${rawMsg} ${rawCause}`.toLowerCase();

  // 1. Embedding Model Missing / Unavailable
  const isEmbedding =
    combined.includes('embedding model') ||
    combined.includes('dense_embedding') ||
    combined.includes('embeddinggemma') ||
    combined.includes('bge-large') ||
    combined.includes('bge-small') ||
    combined.includes('all-minilm') ||
    combined.includes('sentence-transformers') ||
    (combined.includes('embedding') &&
      (combined.includes('not available') ||
        combined.includes('not found') ||
        combined.includes('download') ||
        combined.includes('missing')));

  if (isEmbedding) {
    const modelMatch =
      rawMsg.match(/['"]([a-zA-Z0-9_\-./]+(?:embedding|gemma|bge|minilm|bert)[a-zA-Z0-9_\-./]*)['"]/i) ||
      rawMsg.match(/model\s+['"]([^'"]+)['"]/i);
    const modelName =
      modelMatch?.[1] ||
      (combined.includes('google/embeddinggemma-2')
        ? 'google/embeddinggemma-2'
        : combined.includes('bge-large-en-v1.5')
        ? 'BAAI/bge-large-en-v1.5'
        : 'google/embeddinggemma-2');

    return {
      category: 'neural_embedding',
      headline: 'Embedding Model Required',
      cleanMessage: `The embedding model '${modelName}' is not installed or available on this system.`,
      recommendedAction:
        'Download the embedding model in Control Center to enable semantic search and document retrieval.',
      targetTab: 'neural',
      primaryButtonLabel: 'Download in Control Center',
      badgeLabel: 'ASSET MISSING',
      modelName,
      isDownloadableModel: true,
    };
  }

  // 2. Reranker Model Missing / Unavailable
  const isReranker =
    combined.includes('reranker') ||
    combined.includes('cross-encoder') ||
    combined.includes('bge-reranker');

  if (isReranker) {
    const modelMatch =
      rawMsg.match(/['"]([a-zA-Z0-9_\-./]+(?:reranker|cross-encoder)[a-zA-Z0-9_\-./]*)['"]/i) ||
      rawMsg.match(/model\s+['"]([^'"]+)['"]/i);
    const modelName = modelMatch?.[1] || 'BAAI/bge-reranker-v2-m3';

    return {
      category: 'neural_reranker',
      headline: 'Neural Reranker Required',
      cleanMessage: `The cross-encoder reranker '${modelName}' is not cached or available on this system.`,
      recommendedAction:
        'Open the Neural Assets tab in the Control Center to download or configure the reranker.',
      targetTab: 'neural',
      primaryButtonLabel: 'Configure in Control Center',
      badgeLabel: 'ASSET MISSING',
      modelName,
      isDownloadableModel: true,
    };
  }

  // 3. Citation NLI Verifier Missing
  const isVerifier =
    combined.includes('nli') ||
    combined.includes('verifier') ||
    combined.includes('finecat');

  if (isVerifier) {
    const modelMatch = rawMsg.match(/['"]([a-zA-Z0-9_\-./]+(?:finecat|nli)[a-zA-Z0-9_\-./]*)['"]/i);
    const modelName = modelMatch?.[1] || 'dleemiller/finecat-nli-ultra-l';

    return {
      category: 'neural_verifier',
      headline: 'Citation Verifier Required',
      cleanMessage: `The citation verification model '${modelName}' is not cached on disk.`,
      recommendedAction:
        'Open the Neural Assets tab in the Control Center to download or configure the citation verifier.',
      targetTab: 'neural',
      primaryButtonLabel: 'Configure in Control Center',
      badgeLabel: 'ASSET MISSING',
      modelName,
      isDownloadableModel: true,
    };
  }

  // 4. LLM Provider / Inference / API Key Missing or Invalid
  const isLlmConfig =
    combined.includes('api key') ||
    combined.includes('apikey') ||
    combined.includes('api_key') ||
    combined.includes('groq') ||
    combined.includes('gemini') ||
    combined.includes('openai') ||
    combined.includes('anthropic') ||
    combined.includes('deepseek') ||
    combined.includes('openrouter') ||
    combined.includes('vllm') ||
    combined.includes('ollama') ||
    combined.includes('unauthorized') ||
    combined.includes('rate limit') ||
    error.status === 401 ||
    error.status === 403;

  if (isLlmConfig) {
    return {
      category: 'llm_inference',
      headline: 'LLM Provider Configuration Required',
      cleanMessage:
        'The selected language model requires valid API credentials or an active local inference engine.',
      recommendedAction:
        'Open the Inference tab in the Control Center to update your API keys or switch providers.',
      targetTab: 'models',
      primaryButtonLabel: 'Configure Inference in Control Center',
      badgeLabel: 'AUTH / CONFIG',
    };
  }

  // 5. Database Substrates (Postgres / Redis / Neo4j / Chroma)
  const isStorage =
    combined.includes('postgres') ||
    combined.includes('redis') ||
    combined.includes('neo4j') ||
    combined.includes('chroma') ||
    combined.includes('sqlite') ||
    combined.includes('database');

  if (isStorage) {
    return {
      category: 'storage_substrate',
      headline: 'Database Substrate Issue',
      cleanMessage:
        'Could not establish a connection to the configured database, graph, or caching substrate.',
      recommendedAction:
        'Open the Storage tab in the Control Center to check connections or toggle in-memory fallbacks.',
      targetTab: 'databases',
      primaryButtonLabel: 'Configure Storage in Control Center',
      badgeLabel: 'STORAGE ERROR',
    };
  }

  // 6. Server Offline / Unreachable
  if (
    error.isOffline ||
    error.status === 0 ||
    combined.includes('offline') ||
    combined.includes('connection refused') ||
    combined.includes('failed to fetch')
  ) {
    return {
      category: 'server_offline',
      headline: 'Backend Server Offline',
      cleanMessage: `The RAISE gateway server is not responding at ${targetUrl || 'http://localhost:8000'}.`,
      recommendedAction: 'Check that the backend server is running and accessible.',
      targetTab: 'platform',
      primaryButtonLabel: 'Open Control Center',
      badgeLabel: 'OFFLINE',
    };
  }

  // 7. Generic Pipeline Error
  let cleanMsg = rawMsg;
  if (cleanMsg.includes('pip install')) {
    cleanMsg = cleanMsg.split('(run:')[0].trim();
  }
  if (!cleanMsg || cleanMsg === 'Server returned an error') {
    cleanMsg = 'An unexpected error occurred during research query execution.';
  }

  // Prevent confusing "HTTP 200" on error badge
  let badgeLabel = 'ERROR';
  if (error.isTimeout) {
    badgeLabel = 'TIMEOUT';
  } else if (error.status && error.status !== 200) {
    badgeLabel = `HTTP ${error.status}`;
  } else if (rawCause && rawCause !== 'PIPELINE_ERROR') {
    badgeLabel = rawCause.replace(/_/g, ' ');
  } else {
    badgeLabel = 'PIPELINE ERROR';
  }

  return {
    category: 'generic',
    headline: error.title || 'Query Execution Issue',
    cleanMessage: cleanMsg,
    recommendedAction:
      'Review the details below or open the Control Center to verify system configuration.',
    targetTab: 'overview',
    primaryButtonLabel: 'Open Control Center',
    badgeLabel,
  };
}

export const BackendErrorCard: React.FC<BackendErrorCardProps> = ({
  error,
  targetUrl,
  onRetry,
  onOpenSettings,
  onOpenControlCenter,
}) => {
  const { title, message, cause, action, status, isOffline, isAborted } = error;

  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<{ percent: number; status: string } | null>(null);
  const [downloadSuccess, setDownloadSuccess] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

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

  const handleOpenTarget = (tab: ControlCenterSection) => {
    if (onOpenControlCenter) {
      onOpenControlCenter(tab);
    } else {
      useControlCenterStore.getState().openToTab(tab);
    }
  };

  const handleDirectDownload = async () => {
    if (!diagnosis.modelName || isDownloading) return;
    setIsDownloading(true);
    setDownloadError(null);
    try {
      await platformAdapter.pullModel(diagnosis.modelName, (percent, statusText) => {
        setDownloadProgress({ percent, status: statusText });
      });
      setDownloadSuccess(true);
      useControlCenterStore.getState().syncBackendConfig();
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Download failed.';
      setDownloadError(`${errMsg} Please try downloading in Control Center.`);
    } finally {
      setIsDownloading(false);
    }
  };

  // Render Category Icon
  const renderCategoryIcon = () => {
    switch (diagnosis.category) {
      case 'neural_embedding':
      case 'neural_reranker':
      case 'neural_verifier':
        return <Layers className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400" />;
      case 'llm_inference':
        return <Cpu className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" />;
      case 'storage_substrate':
        return <Database className="w-3.5 h-3.5 text-cyan-500 dark:text-cyan-400" />;
      case 'server_offline':
        return <Laptop className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />;
      default:
        return <AlertCircle className="w-3.5 h-3.5 text-rose-500 dark:text-rose-400" />;
    }
  };

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
      {/* Header Banner */}
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${
              isCleanCard
                ? 'bg-amber-100 dark:bg-amber-500/20'
                : isOffline || diagnosis.category === 'server_offline'
                ? 'bg-slate-200/80 dark:bg-white/10'
                : 'bg-rose-100 dark:bg-rose-500/20'
            }`}
          >
            {renderCategoryIcon()}
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

      {/* Clean User-Facing Message */}
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

      {/* Action Guidance */}
      <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-normal mb-3">
        {diagnosis.recommendedAction}
      </p>

      {/* Direct In-Card Download Progress Banner */}
      {isDownloading && (
        <div className="mb-3 p-2.5 rounded-lg bg-indigo-50/80 dark:bg-indigo-950/40 border border-indigo-200/80 dark:border-indigo-800/50 text-xs text-indigo-900 dark:text-indigo-200 space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <span className="inline-flex items-center gap-1.5 font-medium">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600 dark:text-indigo-400" />
              <span>{downloadProgress?.status || 'Downloading model weights...'}</span>
            </span>
            <span className="font-mono font-semibold">
              {downloadProgress?.percent ? `${downloadProgress.percent}%` : ''}
            </span>
          </div>
          {typeof downloadProgress?.percent === 'number' && (
            <div className="w-full bg-indigo-200/60 dark:bg-indigo-900/50 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-indigo-600 dark:bg-indigo-400 h-1.5 rounded-full transition-all duration-200"
                style={{ width: `${Math.min(100, Math.max(0, downloadProgress.percent))}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Download Success Pill */}
      {downloadSuccess && (
        <div className="mb-3 p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/50 text-xs text-emerald-800 dark:text-emerald-300 inline-flex items-center gap-1.5">
          <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span>Model downloaded successfully! Click <strong>Retry Query</strong> to proceed.</span>
        </div>
      )}

      {/* Download Error Pill */}
      {downloadError && (
        <div className="mb-3 p-2 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/50 text-xs text-rose-800 dark:text-rose-300">
          {downloadError}
        </div>
      )}

      {/* Collapsible Technical Details (Hidden by default to prevent cognitive overload) */}
      {(cause || action || message || status !== undefined) && (
        <details className="mb-3 text-[11px] text-slate-500 dark:text-slate-400 group">
          <summary className="cursor-pointer hover:underline select-none inline-flex items-center gap-1 font-mono text-[10px] text-slate-500 dark:text-slate-400">
            <span>Technical details</span>
          </summary>
          <div className="mt-1.5 p-2.5 rounded-lg bg-slate-100/90 dark:bg-white/5 border border-slate-200/80 dark:border-white/10 space-y-1 font-mono text-[10px] text-slate-600 dark:text-slate-300 overflow-x-auto">
            {cause && (
              <div>
                <span className="font-semibold text-rose-600 dark:text-rose-400">Cause: </span>
                <span>{cause}</span>
              </div>
            )}
            {status !== undefined && (
              <div>
                <span className="font-semibold text-slate-500">HTTP Status: </span>
                <span>{status}</span>
              </div>
            )}
            {action && (
              <div>
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">Action: </span>
                <span>{action}</span>
              </div>
            )}
            {message && message !== diagnosis.cleanMessage && (
              <div className="break-all whitespace-pre-wrap">
                <span className="font-semibold text-slate-500">Server message: </span>
                <span>{message}</span>
              </div>
            )}
          </div>
        </details>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-200/60 dark:border-white/[0.06]">
        {/* Direct Link to Control Center Section */}
        <button
          type="button"
          onClick={() => handleOpenTarget(diagnosis.targetTab)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 active:scale-95 rounded-lg transition-all cursor-pointer shadow-2xs"
        >
          <span>{diagnosis.primaryButtonLabel}</span>
          <ArrowRight className="w-3 h-3" />
        </button>

        {/* Optional Direct In-Card Download Button */}
        {diagnosis.isDownloadableModel && diagnosis.modelName && !downloadSuccess && !isDownloading && (
          <button
            type="button"
            onClick={handleDirectDownload}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-200 bg-white/90 hover:bg-slate-100 dark:bg-white/10 dark:hover:bg-white/15 border border-slate-200 dark:border-white/10 rounded-lg transition-all cursor-pointer shadow-2xs"
          >
            <Download className="w-3 h-3 text-slate-600 dark:text-slate-300" />
            <span>Download Model Now</span>
          </button>
        )}

        {/* Retry Query Button */}
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

        {/* Secondary Gateway Settings */}
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
    </div>
  );
};
