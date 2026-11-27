import { create } from 'zustand';
import {
  config,
  getApiBaseUrl,
  getApiMode,
  getStoredApiKey,
  getStoredLastConnectedAt,
  getStoredTunnelUrl,
  getStoredUsername,
  resolveDefaultBaseUrl,
  setApiBaseUrl,
  setApiMode,
  setStoredApiKey,
  setStoredLastConnectedAt,
  setStoredTunnelUrl,
  setStoredUsername,
} from '../app/config';
import { systemService } from '../services/SystemService';
import type { AppMode, BackendCapabilities, ConfigMode } from '../types';
import { logToTerminal } from '../utils/terminalLogger';

interface ModeState {
  appMode: AppMode;
  configMode: ConfigMode;
  apiBaseUrl: string;
  gatewayUsername: string;
  apiKey: string;
  isTunnelConfigured: boolean;
  latencyMs: number;
  lastConnectedAt: number | null;
  capabilities: BackendCapabilities | null;
  isProbing: boolean;
  probeError: string | null;
  isNeuralReady: boolean;
  readinessMessage: string | null;
  consecutiveFailures: number;
  isDegraded: boolean;

  setConfigMode: (mode: ConfigMode) => void;
  setBaseUrl: (url: string) => void;
  setUsername: (name: string) => void;
  setApiKey: (key: string) => void;
  clearTunnelUrl: () => void;
  runCapabilityProbe: () => Promise<void>;
  checkReadiness: () => Promise<boolean>;
  testConnection: (customUrl?: string) => Promise<{
    success: boolean;
    status: number;
    latencyMs: number;
    endpoint: string;
    error?: string;
    isCorsIssue?: boolean;
  }>;
  setAppMode: (mode: AppMode) => void;
}

const resolveInitialTunnel = (): string => {
  if (typeof window !== 'undefined') {
    try {
      const searchParams = new URLSearchParams(window.location.search);
      const paramUrl = searchParams.get('tunnel') || searchParams.get('gateway');
      if (paramUrl && paramUrl.trim() && paramUrl.startsWith('http')) {
        const cleaned = paramUrl.trim().replace(/\/+$/, '');
        setStoredTunnelUrl(cleaned);
        setApiBaseUrl(cleaned);
        return cleaned;
      }
    } catch {}
  }
  const stored = getStoredTunnelUrl();
  if (stored && stored.trim() !== '') return stored.trim();
  if (config.apiBaseUrl && config.apiBaseUrl.trim() !== '') {
    return config.apiBaseUrl.trim();
  }
  return '';
};

const initialTunnel = resolveInitialTunnel();

let offlineRetryTimer: ReturnType<typeof setTimeout> | null = null;
let offlineRetryAttempt = 0;
const OFFLINE_RETRY_DELAYS_MS = [800, 1200, 2000, 3000];

const scheduleOfflineRetry = () => {
  if (typeof window === 'undefined') return;
  if (offlineRetryTimer) clearTimeout(offlineRetryTimer);
  const delayMs =
    OFFLINE_RETRY_DELAYS_MS[Math.min(offlineRetryAttempt, OFFLINE_RETRY_DELAYS_MS.length - 1)];
  offlineRetryAttempt += 1;
  offlineRetryTimer = setTimeout(() => {
    offlineRetryTimer = null;
    const state = useModeStore.getState();
    if (state.appMode === 'offline' && !state.isProbing && state.configMode !== 'mock') {
      state.runCapabilityProbe();
    }
  }, delayMs);
};

const clearOfflineRetry = () => {
  offlineRetryAttempt = 0;
  if (offlineRetryTimer) {
    clearTimeout(offlineRetryTimer);
    offlineRetryTimer = null;
  }
};

export const useModeStore = create<ModeState>((set, get) => ({
  appMode: getApiMode() === 'mock' ? 'mock' : 'offline',
  configMode: getApiMode(),
  apiBaseUrl: getApiBaseUrl(),
  gatewayUsername: getStoredUsername(),
  apiKey: getStoredApiKey(),
  isTunnelConfigured: Boolean(
    (initialTunnel && initialTunnel.trim() !== '') ||
    (config.apiBaseUrl && config.apiBaseUrl.trim() !== '')
  ),
  latencyMs: 0,
  lastConnectedAt: getStoredLastConnectedAt(),
  capabilities: null,
  isProbing: false,
  probeError: null,
  isNeuralReady: true,
  readinessMessage: null,
  consecutiveFailures: 0,
  isDegraded: false,

  setConfigMode: (mode: ConfigMode) => {
    setApiMode(mode);
    set({ configMode: mode });
    get().runCapabilityProbe();
  },

  setBaseUrl: (url: string) => {
    const cleaned = url.trim().replace(/\/+$/, '');
    setApiBaseUrl(cleaned);
    setStoredTunnelUrl(cleaned);
    set({
      apiBaseUrl: cleaned,
      isTunnelConfigured: Boolean(cleaned && cleaned.trim() !== ''),
    });
    get().runCapabilityProbe();
  },

  setUsername: (name: string) => {
    const cleanName = name.trim();
    if (cleanName && cleanName !== 'Operator') {
      setStoredUsername(cleanName);
      set({ gatewayUsername: cleanName });
    } else {
      setStoredUsername('');
      set({ gatewayUsername: getStoredUsername() });
    }
  },

  setApiKey: (key: string) => {
    setStoredApiKey(key);
    set({ apiKey: key.trim() });
  },

  clearTunnelUrl: () => {
    setStoredTunnelUrl('');
    const defaultUrl = resolveDefaultBaseUrl();
    setApiBaseUrl(defaultUrl, false);
    set({
      apiBaseUrl: defaultUrl,
      isTunnelConfigured: true,
      appMode: 'offline',
      capabilities: null,
      latencyMs: 0,
      probeError: null,
      consecutiveFailures: 0,
      isDegraded: false,
    });
    scheduleOfflineRetry();
  },

  setAppMode: (appMode: AppMode) => {
    if (appMode === 'connected' || appMode === 'degraded') {
      clearOfflineRetry();
    } else if (appMode === 'offline') {
      scheduleOfflineRetry();
    }
    set({ appMode });
  },

  testConnection: async (customUrl?: string) => {
    const target = customUrl || get().apiBaseUrl;
    set({ isProbing: true, probeError: null });
    logToTerminal({
      type: 'REQ',
      method: 'GET',
      endpoint: '/health',
      details: `Probing Pipeline Tunnel Gateway at: ${target}`,
    });
    const result = await systemService.testConnection(target);
    if (result.success) {
      logToTerminal({
        type: 'RES',
        method: 'GET',
        endpoint: result.endpoint,
        status: result.status,
        durationMs: result.latencyMs,
        details: `Pipeline Connected! (HTTP ${result.status}, ${result.latencyMs}ms)`,
      });
    } else {
      logToTerminal({
        type: 'ERR',
        method: 'GET',
        endpoint: result.endpoint,
        status: result.status,
        error: result.error || 'Pipeline Connection Failed',
        details: `Target was: ${target}`,
      });
    }

    const isSuccess = result.success;
    const prevFailures = get().consecutiveFailures || 0;
    const consecutiveFailures = isSuccess ? 0 : prevFailures + 1;

    let computedMode: AppMode = get().appMode;
    let isDegraded = false;

    if (isSuccess) {
      computedMode = 'connected';
      clearOfflineRetry();
      setStoredLastConnectedAt();
    } else if (consecutiveFailures < 3 && (get().appMode === 'connected' || get().appMode === 'degraded')) {
      // Keep workstation operational during transient Docling/RAG compute congestion
      computedMode = 'connected';
      isDegraded = true;
    } else {
      computedMode = 'offline';
      isDegraded = false;
      scheduleOfflineRetry();
    }

    set({
      isProbing: false,
      consecutiveFailures,
      isDegraded,
      latencyMs: result.latencyMs,
      appMode: computedMode,
      probeError: isSuccess ? null : (result.error || null),
      lastConnectedAt: isSuccess ? Date.now() : get().lastConnectedAt,
    });
    return result;
  },

  runCapabilityProbe: async () => {
    const { configMode, isTunnelConfigured } = get();

    if (configMode === 'mock') {
      set({
        appMode: 'mock',
        latencyMs: 0,
        capabilities: {
          apiReachable: true,
          openApiReachable: true,
          handshakeAvailable: true,
          backendVersion: '1.0.0',
          chatAvailable: true,
          documentsAvailable: true,
          graphAvailable: true,
          searchAvailable: true,
          hardwareTelemetryAvailable: true,
          neo4jStatusAvailable: true,
          sseStreamingAvailable: false,
          serverAbortAvailable: false,
          asyncSourceStatusAvailable: false,
          lastProbeTime: new Date().toISOString(),
          latencyMs: 12,
        },
        isProbing: false,
        probeError: null,
      });
      return;
    }

    const targetUrl = get().apiBaseUrl || config.apiBaseUrl;
    if (!isTunnelConfigured && !targetUrl) {
      set({
        appMode: 'offline',
        capabilities: null,
        isProbing: false,
        probeError: null,
      });
      return;
    }

    set({ isProbing: true, probeError: null });

    try {
      let earlyConnected = false;
      const caps = await systemService.probeCapabilities((earlyCaps) => {
        earlyConnected = true;
        clearOfflineRetry();
        setStoredLastConnectedAt();
        set({
          capabilities: earlyCaps,
          appMode: 'connected',
          latencyMs: earlyCaps.latencyMs,
          isProbing: false,
          lastConnectedAt: Date.now(),
        });
        get().checkReadiness();
      });

      let computedMode: AppMode = 'offline';
      if (caps.apiReachable) {
        computedMode = 'connected';
        clearOfflineRetry();
        setStoredLastConnectedAt();
        if (!earlyConnected) {
          get().checkReadiness();
        }
      } else {
        // Fast fallback probe to local gateway if a remote/tunnel URL failed
        const currentTarget = get().apiBaseUrl || config.apiBaseUrl;
        if (
          currentTarget &&
          !currentTarget.includes('127.0.0.1:8000') &&
          !currentTarget.includes('localhost:8000')
        ) {
          try {
            const fallbackRes = await systemService.testConnection('http://127.0.0.1:8000');
            if (fallbackRes.success) {
              get().clearTunnelUrl();
              const localCaps = await systemService.probeCapabilities((earlyLocalCaps) => {
                clearOfflineRetry();
                set({
                  capabilities: earlyLocalCaps,
                  appMode: 'connected',
                  latencyMs: earlyLocalCaps.latencyMs,
                  isProbing: false,
                  lastConnectedAt: Date.now(),
                });
                get().checkReadiness();
              });
              if (localCaps.apiReachable) {
                clearOfflineRetry();
                set({
                  capabilities: localCaps,
                  appMode: 'connected',
                  latencyMs: localCaps.latencyMs,
                  isProbing: false,
                  lastConnectedAt: Date.now(),
                });
                return;
              }
            }
          } catch {}
        }
        computedMode = 'offline';
        scheduleOfflineRetry();
      }

      set({
        capabilities: caps,
        appMode: computedMode,
        latencyMs: caps.latencyMs,
        isProbing: false,
        lastConnectedAt: caps.apiReachable ? Date.now() : get().lastConnectedAt,
      });
    } catch (err: unknown) {
      // Fast fallback probe to local gateway on network error / timeout
      const currentTarget = get().apiBaseUrl || config.apiBaseUrl;
      if (
        currentTarget &&
        !currentTarget.includes('127.0.0.1:8000') &&
        !currentTarget.includes('localhost:8000')
      ) {
        try {
          const fallbackRes = await systemService.testConnection('http://127.0.0.1:8000');
          if (fallbackRes.success) {
            get().clearTunnelUrl();
            const localCaps = await systemService.probeCapabilities();
            if (localCaps.apiReachable) {
              clearOfflineRetry();
              set({
                capabilities: localCaps,
                appMode: 'connected',
                latencyMs: localCaps.latencyMs,
                isProbing: false,
                lastConnectedAt: Date.now(),
              });
              get().checkReadiness();
              return;
            }
          }
        } catch {}
      }

      set({
        capabilities: null,
        appMode: 'offline',
        isProbing: false,
        probeError: err instanceof Error ? err.message : String(err ?? 'Capability probe failed'),
      });
      scheduleOfflineRetry();
    }
  },

  checkReadiness: async () => {
    const targetUrl = get().apiBaseUrl || config.apiBaseUrl;
    if (!targetUrl) return true;
    try {
      const res = await systemService.checkReadiness(targetUrl);
      if (res.ready) {
        set({ isNeuralReady: true, readinessMessage: null });
        return true;
      }
      set({
        isNeuralReady: false,
        readinessMessage: res.message || 'Warming up AI neural models (embeddings, reranker, NLI)...',
      });
      setTimeout(() => {
        if (get().appMode === 'connected' || get().appMode === 'degraded') {
          get().checkReadiness();
        }
      }, 2500);
      return false;
    } catch {
      set({ isNeuralReady: true, readinessMessage: null });
      return true;
    }
  },
}));

// Automatically probe backend connectivity on application launch
if (typeof window !== 'undefined') {
  setTimeout(() => {
    useModeStore.getState().runCapabilityProbe();
  }, 50);
}
