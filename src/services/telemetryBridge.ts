// frontend/src/services/telemetryBridge.ts

import { getApiBaseUrl } from '../app/config';
import type { BrowserTelemetryPayload, BackendPipelineStageEvent, TelemetryBusSnapshot } from '../types/telemetry';

class TelemetryBridge {
  private ws: WebSocket | null = null;
  private queue: BrowserTelemetryPayload[] = [];
  private isConnecting = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private initialized = false;
  private currentStats: TelemetryBusSnapshot | null = null;
  private isConnected = false;

  public init(): void {
    if (this.initialized || typeof window === 'undefined') return;
    this.initialized = true;

    this.connectWebSocket();
    this.interceptConsole();
    this.interceptGlobalErrors();
    this.interceptViteHMR();
    this.setupPageUnloadBeacon();
  }

  public getStats(): TelemetryBusSnapshot | null {
    return this.currentStats;
  }

  public getIsConnected(): boolean {
    return this.isConnected;
  }

  public getIsConnecting(): boolean {
    return this.isConnecting;
  }

  private resolveWsUrl(): string {
    const base = getApiBaseUrl();
    const isHttps = base.startsWith('https:');
    const host = base.replace(/^https?:\/\//, '').replace(/\/+$/, '');
    const protocol = isHttps ? 'wss:' : 'ws:';
    return `${protocol}//${host}/ws/telemetry`;
  }

  private resolveBeaconUrl(): string {
    const base = getApiBaseUrl().replace(/\/+$/, '');
    return `${base}/api/telemetry/browser`;
  }

  public async connectWebSocket(): Promise<void> {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    this.isConnecting = true;

    try {
      let token = '';
      try {
        const base = getApiBaseUrl().replace(/\/+$/, '');
        const res = await fetch(`${base}/api/v1/auth/handshake`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        if (res.ok) {
          const data = (await res.json()) as { token?: string };
          if (data?.token) {
            token = data.token;
          }
        }
      } catch {
        // Proceed with direct connection if handshake route is unreachable
      }

      const baseUrl = this.resolveWsUrl();
      const url = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.isConnecting = false;
        this.isConnected = true;
        // Flush offline backlog
        while (this.queue.length > 0) {
          const item = this.queue.shift();
          if (item) this.send(item);
        }
      };

      this.ws.onmessage = (event) => {
        try {
          if (event.data === 'ping') {
            this.ws?.send('pong');
            return;
          }
          const parsed = JSON.parse(event.data) as Record<string, any>;
          if (parsed && typeof parsed === 'object') {
            if (parsed.type === 'pipeline_stage') {
              const stageEvent = (parsed.data || parsed) as BackendPipelineStageEvent;
              window.dispatchEvent(new CustomEvent('raise:pipeline_stage', { detail: stageEvent }));
            } else if (parsed.type === 'connection_ready') {
              if (parsed.stats) {
                this.currentStats = parsed.stats as TelemetryBusSnapshot;
              }
              window.dispatchEvent(new CustomEvent('raise:connection_ready', { detail: parsed }));
            } else if (parsed.type === 'backend_log') {
              window.dispatchEvent(new CustomEvent('raise:backend_log', { detail: parsed.data }));
            } else if (parsed.type === 'log_frame') {
              window.dispatchEvent(new CustomEvent('raise:log_frame', { detail: parsed.data }));
            }
          }
        } catch {
          // Ignore ping / parse errors
        }
      };

      this.ws.onclose = () => {
        this.ws = null;
        this.isConnecting = false;
        this.isConnected = false;
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        try {
          this.ws?.close();
        } catch {
          // ignore
        }
      };
    } catch {
      this.isConnected = false;
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connectWebSocket();
    }, 4000);
  }

  public send(payload: BrowserTelemetryPayload): void {
    const enriched: BrowserTelemetryPayload = {
      source: 'WS',
      timestamp: new Date().toISOString(),
      ...payload,
    };

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(enriched));
      } catch {
        this.queue.push(enriched);
      }
    } else {
      this.queue.push(enriched);
      if (this.queue.length > 150) {
        this.queue.shift(); // Bound memory footprint
      }
    }
  }

  private interceptConsole(): void {
    const origError = console.error;
    const origWarn = console.warn;

    console.error = (...args: unknown[]) => {
      origError.apply(console, args);
      const msg = args.map((a) => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' ');
      // Avoid infinite feedback loops
      if (
        msg.includes('[PIPELINE]') ||
        msg.includes('[RAISE Telemetry]') ||
        msg.includes('[WS]') ||
        msg.includes('[TelemetryBridge]')
      ) {
        return;
      }
      this.send({
        subtype: 'console',
        level: 'ERROR',
        message: msg,
      });
    };

    console.warn = (...args: unknown[]) => {
      origWarn.apply(console, args);
      const msg = args.map((a) => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' ');
      if (
        msg.includes('[PIPELINE]') ||
        msg.includes('[RAISE Telemetry]') ||
        msg.includes('[WS]') ||
        msg.includes('[TelemetryBridge]')
      ) {
        return;
      }
      this.send({
        subtype: 'console',
        level: 'WARN',
        message: msg,
      });
    };
  }

  private interceptGlobalErrors(): void {
    window.addEventListener('error', (event: ErrorEvent) => {
      this.send({
        subtype: 'exception',
        level: 'ERROR',
        message: event.message || 'Uncaught client exception',
        url: event.filename,
        line: event.lineno,
        col: event.colno,
        stack: event.error?.stack,
      });
    });

    window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      this.send({
        subtype: 'unhandled_rejection',
        level: 'ERROR',
        message: typeof reason === 'string' ? reason : reason?.message || 'Unhandled Promise Rejection',
        stack: reason?.stack,
      });
    });
  }

  private interceptViteHMR(): void {
    if (import.meta.hot) {
      import.meta.hot.on('vite:beforeUpdate', (event: { updates?: Array<{ path: string }> }) => {
        const paths = event.updates?.map((u) => u.path).join(', ') || 'modules';
        this.send({
          subtype: 'hmr',
          level: 'INFO',
          message: `Vite HMR Updating: ${paths}`,
        });
      });

      import.meta.hot.on('vite:error', (error: { err?: { message?: string; stack?: string }; message?: string }) => {
        this.send({
          subtype: 'hmr',
          level: 'ERROR',
          message: `Vite HMR Compile Error: ${error.err?.message || error.message || 'Build Error'}`,
          stack: error.err?.stack,
        });
      });
    }
  }

  private setupPageUnloadBeacon(): void {
    window.addEventListener('beforeunload', () => {
      if (this.queue.length > 0 && navigator.sendBeacon) {
        try {
          const blob = new Blob([JSON.stringify(this.queue)], { type: 'application/json' });
          navigator.sendBeacon(this.resolveBeaconUrl(), blob);
        } catch {
          // Ignore unload errors
        }
      }
    });
  }
}

export const telemetryBridge = new TelemetryBridge();
