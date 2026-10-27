import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from 'react';
import { useModeStore } from '../stores/modeStore';
import { systemService } from '../services/SystemService';
import { EXPECTED_BACKEND_VERSION } from '../app/config';
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
  expectedVersion: string;
  backendVersion: string;
  isVersionAligned: boolean;
  isWsConnected: boolean;

  // Actions
  connect: (targetUrl: string) => Promise<{ success: boolean; error?: string; latencyMs: number }>;
  disconnect: () => void;
  scanLocalPorts: () => Promise<string | null>;
  retry: () => Promise<boolean>;
  testUrl: (url: string) => Promise<{ success: boolean; latencyMs: number; status: number; error?: string; isCorsIssue?: boolean }>;
  setAppMode: (mode: AppMode) => void;
}

// Shared WebSocket Manager to deduplicate telemetry streams and eliminate flapping
class SharedWebSocketManager {
  private static instance: SharedWebSocketManager | null = null;
  private socket: WebSocket | null = null;
  private listeners = new Set<(connected: boolean) => void>();
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private teardownTimeout: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private currentUrl = '';
  private isConnected = false;

  public static getInstance(): SharedWebSocketManager {
    if (!SharedWebSocketManager.instance) {
      SharedWebSocketManager.instance = new SharedWebSocketManager();
    }
    return SharedWebSocketManager.instance;
  }

  public subscribe(url: string, listener: (connected: boolean) => void): () => void {
    this.listeners.add(listener);
    listener(this.isConnected);

    if (this.teardownTimeout) {
      clearTimeout(this.teardownTimeout);
      this.teardownTimeout = null;
    }

    if (url && (url !== this.currentUrl || !this.socket || this.socket.readyState === WebSocket.CLOSED)) {
      this.currentUrl = url;
      this.connect();
    }

    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0) {
        this.teardownTimeout = setTimeout(() => {
          this.teardown();
        }, 5000);
      }
    };
  }

  private notify(connected: boolean) {
    this.isConnected = connected;
    for (const listener of this.listeners) {
      listener(connected);
    }
  }

  private async connect() {
    if (!this.currentUrl || typeof window === 'undefined' || !window.WebSocket) return;

    this.cleanupSocket();

    try {
      const handshakeRes = await systemService.performHandshake().catch(() => null);
      if (this.listeners.size === 0) return;

      const token = handshakeRes?.data?.token || 'ephemeral-handshake-standalone';
      const wsProtocol = this.currentUrl.startsWith('https:') ? 'wss:' : 'ws:';
      const host = this.currentUrl.replace(/^https?:\/\//, '').replace(/\/+$/, '');
      const wsUrl = `${wsProtocol}//${host}/ws/traffic?token=${encodeURIComponent(token)}`;

      const socket = new WebSocket(wsUrl);
      this.socket = socket;

      socket.onopen = () => {
        this.reconnectAttempt = 0;
        this.notify(true);

        if (this.pingInterval) clearInterval(this.pingInterval);
        this.pingInterval = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            try {
              socket.send('ping');
            } catch {}
          }
        }, 25000);
      };

      socket.onmessage = (event) => {
        try {
          if (event.data === 'ping') {
            socket.send('pong');
          }
        } catch {}
      };

      socket.onclose = () => {
        this.notify(false);
        this.cleanupSocket();
        this.scheduleReconnect();
      };

      socket.onerror = () => {
        try {
          socket.close();
        } catch {}
      };
    } catch {
      this.notify(false);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.listeners.size === 0) return;
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);

    const attempt = this.reconnectAttempt;
    const baseDelay = Math.min(30000, 1000 * Math.pow(2, attempt));
    const jitter = Math.random() * 1000;
    const delayMs = baseDelay + jitter;
    this.reconnectAttempt = attempt + 1;

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, delayMs);
  }

  private cleanupSocket() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.socket) {
      try {
        this.socket.onopen = null;
        this.socket.onmessage = null;
        this.socket.onclose = null;
        this.socket.onerror = null;
        this.socket.close();
      } catch {}
      this.socket = null;
    }
  }

  private teardown() {
    this.cleanupSocket();
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    this.reconnectAttempt = 0;
    this.currentUrl = '';
    this.notify(false);
  }
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
      'http://127.0.0.1:8000',
      'http://localhost:8000',
      'http://127.0.0.1:8001',
      'http://localhost:8001',
      'http://localhost:8080',
    ];

    let found: string | null = null;
    try {
      const probePromises = candidatePorts.map(async (url) => {
        const res = await systemService.testConnection(url);
        if (res.success) return url;
        throw new Error('Offline');
      });
      found = await Promise.any(probePromises);
    } catch {
      found = null;
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

  // WebSocket Traffic & Telemetry Stream with Jittered Exponential Backoff & 25s Keepalive Ping
  const [isWsConnected, setIsWsConnected] = useState(false);

  useEffect(() => {
    if (!isConnected || !apiBaseUrl || typeof window === 'undefined' || !window.WebSocket) {
      setIsWsConnected(false);
      return;
    }

    const unsubscribe = SharedWebSocketManager.getInstance().subscribe(apiBaseUrl, (connected) => {
      setIsWsConnected(connected);
    });

    return () => {
      unsubscribe();
    };
  }, [isConnected, apiBaseUrl]);

  const expectedVersion = EXPECTED_BACKEND_VERSION;
  const backendVersion = capabilities?.backendVersion || '1.0.0';
  const isVersionAligned = backendVersion === expectedVersion || backendVersion === '1.0.0';

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
      expectedVersion,
      backendVersion,
      isVersionAligned,
      isWsConnected,
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
      expectedVersion,
      backendVersion,
      isVersionAligned,
      isWsConnected,
      connect,
      disconnect,
      scanLocalPorts,
      retry,
      testUrl,
      setAppMode,
    ]
  );
}
