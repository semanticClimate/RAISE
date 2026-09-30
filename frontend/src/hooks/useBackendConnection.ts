import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from 'react';
import { useModeStore } from '../stores/modeStore';
import { systemService } from '../services/SystemService';
import type { AppMode, BackendCapabilities } from '../types';
import { sanitizeTunnelUrl, validateTunnelUrl } from '../utils/urlValidation';

export interface ConnectionPreset {
  id: string;
  name: string;
  url: string;
  description: string;
}

export const CONNECTION_PRESETS: ConnectionPreset[] = [
  {
    id: 'localhost',
    name: 'Local Default',
    url: 'http://localhost:8000',
    description: 'FastAPI gateway running locally on standard port 8000',
  },
  {
    id: 'loopback',
    name: 'IPv4 Loopback',
    url: 'http://127.0.0.1:8000',
    description: 'Direct IPv4 loopback address (avoids IPv6 resolution quirks)',
  },
];

export interface UseBackendConnectionOptions {
  /**
   * If true, runs a silent background ping every intervalMs when connected.
   * Default: true.
   */
  enableHeartbeat?: boolean;
  /**
   * Heartbeat interval in milliseconds.
   * Default: 30000 (30 seconds).
   */
  heartbeatIntervalMs?: number;
  /**
   * If true, automatically attempts local backend detection on startup if disconnected.
   * Default: false (manual or opt-in).
   */
  autoDetectLocalOnMount?: boolean;
}

export interface UseBackendConnectionResult {
  // State
  appMode: AppMode;
  apiBaseUrl: string;
  isConnected: boolean;
  isConnecting: boolean;
  isOffline: boolean;
  isTunnelConfigured: boolean;
  latencyMs: number;
  lastConnectedAt: number | null;
  capabilities: BackendCapabilities | null;
  probeError: string | null;
  isPendingTransition: boolean;

  // Actions
  connect: (targetUrl: string) => Promise<{ success: boolean; error?: string; latencyMs: number }>;
  disconnect: () => void;
  scanLocalPorts: () => Promise<string | null>;
  retry: () => Promise<boolean>;
  testUrl: (url: string) => Promise<{ success: boolean; latencyMs: number; status: number; error?: string; isCorsIssue?: boolean }>;
  setAppMode: (mode: AppMode) => void;
}

/**
 * Modern React 19 hook for managing RAISE Backend & Cloudflare Gateway connectivity.
 * Combines Zustand store persistence, async transition wrapping, periodic heartbeats,
 * port auto-discovery, and verified diagnostic reporting.
 */
export function useBackendConnection(
  options: UseBackendConnectionOptions = {}
): UseBackendConnectionResult {
  const {
    enableHeartbeat = true,
    heartbeatIntervalMs = 30000,
    autoDetectLocalOnMount = false,
  } = options;

  const [isPendingTransition, startTransition] = useTransition();
  const [isScanning, setIsScanning] = useState(false);

  const {
    appMode,
    apiBaseUrl,
    setBaseUrl,
    clearTunnelUrl,
    testConnection,
    isProbing,
    latencyMs,
    lastConnectedAt,
    capabilities,
    probeError,
    setAppMode,
    runCapabilityProbe,
  } = useModeStore();

  const isConnected = appMode === 'connected';
  const isConnecting = isProbing || isScanning || isPendingTransition;
  const isOffline = appMode === 'offline';
  const isTunnelConfigured = Boolean(apiBaseUrl && apiBaseUrl.trim() !== '');

  // Heartbeat reference to prevent overlapping probes
  const heartbeatInFlight = useRef(false);

  /**
   * Test a custom target URL without permanently saving it to state
   */
  const testUrl = useCallback(
    async (url: string) => {
      const sanitized = sanitizeTunnelUrl(url.trim());
      return await systemService.testConnection(sanitized);
    },
    []
  );

  /**
   * Connect to a specific backend or Cloudflare Tunnel URL
   */
  const connect = useCallback(
    async (targetUrl: string) => {
      const raw = targetUrl.trim();
      const val = validateTunnelUrl(raw);
      if (val.error) {
        return { success: false, error: val.error, latencyMs: 0 };
      }

      const sanitized = sanitizeTunnelUrl(raw);

      return new Promise<{ success: boolean; error?: string; latencyMs: number }>((resolve) => {
        startTransition(async () => {
          setBaseUrl(sanitized);
          const result = await testConnection(sanitized);
          if (result.success) {
            resolve({ success: true, latencyMs: result.latencyMs });
          } else {
            resolve({
              success: false,
              error: result.error || 'Backend unreachable',
              latencyMs: result.latencyMs,
            });
          }
        });
      });
    },
    [setBaseUrl, testConnection]
  );

  /**
   * Disconnect from current backend and return to offline state
   */
  const disconnect = useCallback(() => {
    startTransition(() => {
      clearTunnelUrl();
    });
  }, [clearTunnelUrl]);

  /**
   * Retry the existing saved URL connection
   */
  const retry = useCallback(async () => {
    if (!apiBaseUrl) return false;
    const res = await testConnection(apiBaseUrl);
    return res.success;
  }, [apiBaseUrl, testConnection]);

  /**
   * Scan common local ports (8000, 8001, 8080) for a running RAISE FastAPI instance
   */
  const scanLocalPorts = useCallback(async (): Promise<string | null> => {
    setIsScanning(true);
    const candidatePorts = [
      'http://localhost:8000',
      'http://127.0.0.1:8000',
      'http://localhost:8001',
      'http://localhost:8080',
    ];

    let found: string | null = null;
    for (const url of candidatePorts) {
      try {
        const res = await systemService.testConnection(url);
        if (res.success) {
          found = url;
          break;
        }
      } catch {
        // continue scanning
      }
    }

    setIsScanning(false);

    if (found) {
      startTransition(() => {
        setBaseUrl(found!);
        runCapabilityProbe();
      });
    }

    return found;
  }, [setBaseUrl, runCapabilityProbe]);

  // Periodic heartbeat when connected to keep latency and liveness authoritative
  useEffect(() => {
    if (!enableHeartbeat || !isConnected || !apiBaseUrl) return;

    const timer = setInterval(async () => {
      if (heartbeatInFlight.current) return;
      heartbeatInFlight.current = true;
      try {
        await testConnection(apiBaseUrl);
      } catch {
        // Ignore background ping errors, store handles offline transitions
      } finally {
        heartbeatInFlight.current = false;
      }
    }, heartbeatIntervalMs);

    return () => clearInterval(timer);
  }, [enableHeartbeat, isConnected, apiBaseUrl, heartbeatIntervalMs, testConnection]);

  // Auto-detect local backend on mount if requested and currently offline
  useEffect(() => {
    if (autoDetectLocalOnMount && isOffline && !isTunnelConfigured) {
      scanLocalPorts();
    }
  }, [autoDetectLocalOnMount, isOffline, isTunnelConfigured, scanLocalPorts]);

  return useMemo(
    () => ({
      appMode,
      apiBaseUrl,
      isConnected,
      isConnecting,
      isOffline,
      isTunnelConfigured,
      latencyMs,
      lastConnectedAt,
      capabilities,
      probeError,
      isPendingTransition,
      connect,
      disconnect,
      scanLocalPorts,
      retry,
      testUrl,
      setAppMode,
    }),
    [
      appMode,
      apiBaseUrl,
      isConnected,
      isConnecting,
      isOffline,
      isTunnelConfigured,
      latencyMs,
      lastConnectedAt,
      capabilities,
      probeError,
      isPendingTransition,
      connect,
      disconnect,
      scanLocalPorts,
      retry,
      testUrl,
      setAppMode,
    ]
  );
}
