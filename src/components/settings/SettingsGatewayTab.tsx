import {
  AlertCircle,
  AlertTriangle,
  Check,
  Copy,
  Radio,
  RefreshCw,
  RotateCcw,
  ThumbsDown,
  ThumbsUp,
  X,
  Zap,
} from 'lucide-react';
import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { setApiBaseUrl } from '../../app/config';
import { GatewayStatusPill } from '../../features/header/GatewayStatusPill';
import { chatService } from '../../services/ChatService';
import { useModeStore } from '../../stores/modeStore';
import type { FeedbackStats } from '../../types';
import { getClientSystemAndTime } from '../../utils/formatters';
import {
  sanitizeTunnelUrl,
  validateTunnelUrl,
} from '../../utils/urlValidation';
import { LLMRoutingOrchestrator } from './LLMRoutingOrchestrator';

export interface SettingsGatewayTabProps {
  onCloseSettings?: () => void;
}

export const SettingsGatewayTab: React.FC<SettingsGatewayTabProps> = () => {
  const {
    appMode,
    apiBaseUrl,
    setBaseUrl,
    gatewayUsername,
    setUsername,
    clearTunnelUrl,
    testConnection,
    isProbing,
    isTunnelConfigured,
  } = useModeStore();

  const isConnected = appMode === 'connected' || appMode === 'degraded';
  const isGatewayActive = isConnected && isTunnelConfigured;

  const [detectedClient] = useState(getClientSystemAndTime);
  const [urlInput, setUrlInput] = useState(apiBaseUrl);
  const inputRef = useRef<HTMLInputElement>(null);
  const [usernameInput, setUsernameInput] = useState(
    gatewayUsername && gatewayUsername !== 'Operator' ? gatewayUsername : detectedClient
  );
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  const [isLoadingFeedbackStats, setIsLoadingFeedbackStats] = useState(false);
  const [isScanningLocal, setIsScanningLocal] = useState(false);

  const fetchFeedbackStats = async () => {
    if (!isGatewayActive) {
      setFeedbackStats(null);
      return;
    }
    setIsLoadingFeedbackStats(true);
    try {
      const res = await chatService.getFeedbackStats?.();
      if (res?.data) {
        setFeedbackStats(res.data);
      } else {
        setFeedbackStats(null);
      }
    } catch {
      setFeedbackStats(null);
    } finally {
      setIsLoadingFeedbackStats(false);
    }
  };

  useEffect(() => {
    if (isGatewayActive) {
      fetchFeedbackStats();
    } else {
      setFeedbackStats(null);
    }
  }, [apiBaseUrl, appMode, isGatewayActive]);

  useEffect(() => {
    setUrlInput(apiBaseUrl);
  }, [apiBaseUrl]);

  useEffect(() => {
    if (gatewayUsername && gatewayUsername !== 'Operator') {
      setUsernameInput(gatewayUsername);
    }
  }, [gatewayUsername]);

  const validation = useMemo(() => validateTunnelUrl(urlInput), [urlInput]);

  const handleScanLocalBackend = async () => {
    setIsScanningLocal(true);
    setStatusNotice('Scanning local gateway port (8000)...');
    const localCandidates = [
      'http://127.0.0.1:8000',
      'http://localhost:8000',
    ];

    let foundUrl: string | null = null;
    for (const cand of localCandidates) {
      try {
        const res = await testConnection(cand);
        if (res.success) {
          foundUrl = cand;
          break;
        }
      } catch {
        // Continue probing
      }
    }

    setIsScanningLocal(false);
    if (foundUrl) {
      setUrlInput(foundUrl);
      setBaseUrl(foundUrl);
      setStatusNotice(`Connected to local backend at ${foundUrl}`);
    } else {
      setStatusNotice('No local backend detected on port 8000.');
    }
    setTimeout(() => setStatusNotice(null), 4000);
  };

  const handleResetToLocalhost = async () => {
    const localhostUrl = 'http://127.0.0.1:8000';
    setApiBaseUrl(localhostUrl, false);
    setBaseUrl(localhostUrl);
    setUrlInput(localhostUrl);
    try {
      localStorage.removeItem('raise_tunnel_url');
      localStorage.removeItem('raise_gateway_url');
    } catch {}
    setStatusNotice('Resetting to localhost (http://127.0.0.1:8000)...');
    const result = await testConnection(localhostUrl);
    if (result.success) {
      setStatusNotice('Connected to localhost:8000');
    } else {
      setStatusNotice('Reset complete. Backend offline on 127.0.0.1:8000.');
    }
    setTimeout(() => setStatusNotice(null), 4000);
  };

  const handleConnect = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanInput = urlInput.trim();

    const currentValidation = validateTunnelUrl(cleanInput);
    if (cleanInput && currentValidation.error) {
      setStatusNotice(currentValidation.error);
      return;
    }

    const sanitizedUrl = cleanInput ? sanitizeTunnelUrl(cleanInput) : apiBaseUrl;
    if (cleanInput) {
      setUrlInput(sanitizedUrl);
      setBaseUrl(sanitizedUrl);
    }
    setUsername(usernameInput);

    setStatusNotice('Connecting...');
    const result = await testConnection(sanitizedUrl || apiBaseUrl);

    if (result.success) {
      setStatusNotice('Connected successfully');
    } else {
      setStatusNotice(result.error || 'Connection failed');
    }
    setTimeout(() => setStatusNotice(null), 4000);
  };

  const handlePaste = async () => {
    try {
      if (navigator.clipboard?.readText) {
        const text = await navigator.clipboard.readText();
        if (text && text.trim()) {
          setUrlInput(text.trim());
        }
      }
    } catch {
      // Permission fallback
    }
  };

  const handleEmptyUrl = () => {
    setUrlInput('');
    clearTunnelUrl();
    inputRef.current?.focus();
  };

  return (
    <div className="space-y-5 animate-in fade-in duration-200 max-w-lg" data-testid="settings-gateway-tab">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 pb-3 border-b border-slate-200/80 dark:border-[#292929] max-w-lg">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white">
          Backend Gateway
        </h3>

        <GatewayStatusPill />
      </div>

      {/* Notice Banner */}
      {statusNotice && (
        <div
          data-testid="gateway-save-success-banner"
          className={`px-3 py-2 rounded-lg text-xs flex items-center justify-between gap-2 animate-in fade-in ${
            isConnected
              ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400'
              : 'bg-slate-100 dark:bg-white/[0.06] border border-slate-200 dark:border-white/10 text-slate-700 dark:text-slate-300'
          }`}
        >
          <span>{statusNotice}</span>
          <button
            type="button"
            onClick={() => setStatusNotice(null)}
            className="p-0.5 text-slate-400 hover:text-slate-600 dark:hover:text-white cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* URL Input */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block">
          Backend Gateway URL
        </label>
        <div className="relative">
          <input
            ref={inputRef}
            type="text"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="http://127.0.0.1:8000"
            data-testid="gateway-tunnel-url-input"
            className={`w-full text-xs pl-3 pr-16 py-2 rounded-xl bg-slate-50 dark:bg-[#12141d] border ${
              validation.error
                ? 'border-rose-400 dark:border-rose-500'
                : validation.warning
                  ? 'border-amber-400 dark:border-amber-500'
                  : 'border-slate-200 dark:border-[#37393b] focus:border-indigo-500 dark:focus:border-[#a8c7fa]'
            } text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:outline-none font-mono transition-all`}
          />

          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
            {urlInput.length > 0 && (
              <button
                type="button"
                onClick={handleEmptyUrl}
                title="Clear"
                aria-label="Clear URL"
                data-testid="gateway-clear-btn"
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              type="button"
              onClick={handlePaste}
              title="Paste"
              aria-label="Paste from clipboard"
              data-testid="gateway-paste-url-btn"
              className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded cursor-pointer"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {validation.error && (
          <div
            data-testid="gateway-url-error"
            className="p-2 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 text-xs text-rose-700 dark:text-rose-300 flex items-center justify-between gap-2"
          >
            <div className="flex items-center gap-1.5 min-w-0">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 text-rose-500" />
              <span className="truncate">{validation.error}</span>
            </div>
            {validation.suggestedFix && (
              <button
                type="button"
                data-testid="gateway-url-fix-btn"
                onClick={() => setUrlInput(validation.suggestedFix!)}
                className="underline font-medium text-[11px] shrink-0 cursor-pointer"
              >
                Apply https://
              </button>
            )}
          </div>
        )}

        {!validation.error && validation.warning && (
          <div
            data-testid="gateway-url-warning"
            className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/50 text-xs text-amber-800 dark:text-amber-300 flex items-center justify-between gap-2"
          >
            <div className="flex items-center gap-1.5 min-w-0">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-500" />
              <span className="truncate">{validation.warning}</span>
            </div>
            {validation.suggestedFix && (
              <button
                type="button"
                data-testid="gateway-url-trim-btn"
                onClick={() => setUrlInput(validation.suggestedFix!)}
                className="underline font-medium text-[11px] shrink-0 cursor-pointer"
              >
                Trim to base URL
              </button>
            )}
          </div>
        )}
      </div>

      {/* Username / Client */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block">
          Client System &amp; Time
        </label>
        <input
          type="text"
          value={usernameInput}
          onChange={(e) => setUsernameInput(e.target.value)}
          placeholder={detectedClient}
          data-testid="gateway-username-input"
          className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 dark:bg-[#12141d] border border-slate-200 dark:border-[#37393b] text-slate-700 dark:text-slate-200 focus:outline-none font-mono"
        />
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          type="button"
          disabled={isProbing || isScanningLocal || Boolean(validation.error)}
          onClick={() => handleConnect()}
          data-testid="gateway-connect-btn"
          className="py-2 px-4 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white dark:bg-[#a8c7fa] dark:hover:bg-[#8ab4f8] dark:text-[#041e49] transition-all cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
        >
          {isProbing ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : isConnected ? (
            <Check className="w-3.5 h-3.5" />
          ) : (
            <Zap className="w-3.5 h-3.5" />
          )}
          <span>{isProbing ? 'Connecting...' : isConnected ? 'Connected' : 'Connect'}</span>
        </button>

        <button
          type="button"
          disabled={isProbing || isScanningLocal}
          onClick={handleScanLocalBackend}
          data-testid="gateway-scan-local-btn"
          className="py-2 px-3 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200 dark:bg-white/[0.08] dark:hover:bg-white/[0.14] text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-white/10 transition-all cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
        >
          <Radio className={`w-3.5 h-3.5 text-indigo-500 ${isScanningLocal ? 'animate-pulse' : ''}`} />
          <span>{isScanningLocal ? 'Scanning...' : 'Scan Local Backend'}</span>
        </button>

        <button
          type="button"
          disabled={isProbing}
          onClick={handleResetToLocalhost}
          data-testid="gateway-reset-localhost-btn"
          className="py-2 px-3 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200 dark:bg-white/[0.08] dark:hover:bg-white/[0.14] text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-white/10 transition-all cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
        >
          <RotateCcw className="w-3.5 h-3.5 text-emerald-500" />
          <span>Reset to Localhost</span>
        </button>
      </div>

      {/* Dynamic Model Routing (when connected) */}
      {isGatewayActive && (
        <div
          className="pt-4 border-t border-slate-200/80 dark:border-[#292929]"
          data-testid="dynamic-models-widget"
        >
          <LLMRoutingOrchestrator />
        </div>
      )}

      {/* User Feedback Analytics (when connected) */}
      {isGatewayActive && (
        <div
          className="pt-4 border-t border-slate-200/80 dark:border-[#292929] space-y-2.5"
          data-testid="feedback-analytics-widget"
        >
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-slate-900 dark:text-white uppercase tracking-wider">
              User Satisfaction &amp; Telemetry
            </h4>
            <button
              type="button"
              onClick={fetchFeedbackStats}
              disabled={isLoadingFeedbackStats}
              title="Refresh"
              className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-white cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingFeedbackStats ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {feedbackStats && feedbackStats.total_feedback > 0 ? (
            <div className="p-3 rounded-xl bg-slate-50/50 dark:bg-white/[0.02] border border-slate-200/80 dark:border-[#292929] space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span>
                  Ratio: <strong className="font-mono" data-testid="satisfaction-ratio-value">{(feedbackStats.satisfaction_ratio * 100).toFixed(1)}%</strong>
                </span>
                <span>
                  Total: <strong className="font-mono" data-testid="total-feedback-value">{feedbackStats.total_feedback}</strong>
                </span>
              </div>
              <div className="w-full bg-slate-200 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden flex">
                <div
                  className="bg-emerald-500 h-full"
                  style={{ width: `${Math.round(feedbackStats.satisfaction_ratio * 100)}%` }}
                />
                <div
                  className="bg-rose-500 h-full"
                  style={{ width: `${100 - Math.round(feedbackStats.satisfaction_ratio * 100)}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] pt-0.5">
                <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1" data-testid="thumbs-up-count">
                  <ThumbsUp className="w-3 h-3" /> {feedbackStats.thumbs_up} helpful
                </span>
                <span className="text-rose-600 dark:text-rose-400 flex items-center gap-1" data-testid="thumbs-down-count">
                  <ThumbsDown className="w-3 h-3" /> {feedbackStats.thumbs_down} unhelpful
                </span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              No feedback data recorded yet.
            </p>
          )}
        </div>
      )}
    </div>
  );
};
