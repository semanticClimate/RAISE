import { type ApiResponse, apiClient } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { getApiBaseUrl } from '../app/config';
import {
  type BackendCapabilities,
  type HardwareTelemetry,
  HardwareTelemetrySchema,
  type Neo4jStatus,
  Neo4jStatusSchema,
  type AuthHandshakeResponse,
  AuthHandshakeResponseSchema,
} from '../types';

export class SystemService {
  private static openApiCheckCache: { reachable: boolean; timestamp: number } | null = null;
  private static activeProbePromise: Promise<BackendCapabilities> | null = null;

  /**
   * Probe test connections via POST /api/system/test-connections
   */
  public async testConnections(
    payload?: Record<string, unknown>,
    signal?: AbortSignal
  ): Promise<ApiResponse<unknown>> {
    return apiClient.request(
      ENDPOINTS.SYSTEM_TEST_CONNECTIONS,
      undefined,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
        signal,
        skipModeCheck: true,
        timeoutMs: 4000,
      }
    );
  }

  /**
   * Hardware telemetry (GPU VRAM, System RAM, active models)
   */
  public async getHardwareTelemetry(signal?: AbortSignal): Promise<ApiResponse<HardwareTelemetry>> {
    return apiClient.request<HardwareTelemetry>(
      ENDPOINTS.HARDWARE_TELEMETRY,
      HardwareTelemetrySchema,
      {
        method: 'GET',
        signal,
      }
    );
  }

  /**
   * Neo4j Bolt connection status and node count
   */
  public async getNeo4jStatus(signal?: AbortSignal): Promise<ApiResponse<Neo4jStatus>> {
    return apiClient.request<Neo4jStatus>(ENDPOINTS.NEO4J_STATUS, Neo4jStatusSchema, {
      method: 'GET',
      signal,
    });
  }

  /**
   * Dynamically discovered LLMs from live backend provider APIs
   */
  public async getDynamicLLMs(signal?: AbortSignal): Promise<ApiResponse<unknown>> {
    return apiClient.request(
      ENDPOINTS.SYSTEM_DYNAMIC_LLMS,
      undefined,
      {
        method: 'GET',
        signal,
        timeoutMs: 4000,
      }
    );
  }

  /**
   * Models discovered by provider from live model registries
   */
  public async getDiscoveredModels(provider?: string, signal?: AbortSignal): Promise<ApiResponse<unknown>> {
    const url = provider
      ? `${ENDPOINTS.SYSTEM_MODELS_DISCOVERED}?provider=${encodeURIComponent(provider)}`
      : ENDPOINTS.SYSTEM_MODELS_DISCOVERED;
    return apiClient.request(
      url,
      undefined,
      {
        method: 'GET',
        signal,
        timeoutMs: 4000,
      }
    );
  }

  /**
   * Two-Step Security Handshake:
   * Requests an ephemeral single-use session token from backend gateway
   */
  public async performHandshake(signal?: AbortSignal): Promise<ApiResponse<AuthHandshakeResponse>> {
    let res = await apiClient.request<AuthHandshakeResponse>(
      ENDPOINTS.AUTH_HANDSHAKE,
      AuthHandshakeResponseSchema,
      {
        method: 'POST',
        signal,
        skipModeCheck: true,
        timeoutMs: 3000,
      }
    );

    if (res.status !== 200) {
      res = await apiClient.request<AuthHandshakeResponse>(
        ENDPOINTS.AUTH_HANDSHAKE_SESSION,
        AuthHandshakeResponseSchema,
        {
          method: 'POST',
          signal,
          skipModeCheck: true,
          timeoutMs: 3000,
        }
      );
    }

    return res;
  }

  /**
   * Centralized capability and health detection probe.
   * Deduplicates concurrent in-flight calls and caches openapi.json inspection.
   */
  public async probeCapabilities(): Promise<BackendCapabilities> {
    if (SystemService.activeProbePromise) {
      return SystemService.activeProbePromise;
    }
    SystemService.activeProbePromise = this._executeProbeCapabilities().finally(() => {
      // Clear coalescing gate after 1.5s
      setTimeout(() => {
        SystemService.activeProbePromise = null;
      }, 1500);
    });
    return SystemService.activeProbePromise;
  }

  private async _probeOpenApiLightweight(): Promise<boolean> {
    const now = Date.now();
    if (
      SystemService.openApiCheckCache &&
      now - SystemService.openApiCheckCache.timestamp < 300_000
    ) {
      return SystemService.openApiCheckCache.reachable;
    }
    try {
      const fullUrl = `${getApiBaseUrl().replace(/\/+$/, '')}${ENDPOINTS.OPENAPI}`;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 1800);
      const res = await fetch(fullUrl, {
        method: 'HEAD',
        signal: controller.signal,
      });
      clearTimeout(timer);
      const reachable = res.status >= 200 && res.status < 400;
      SystemService.openApiCheckCache = { reachable, timestamp: now };
      return reachable;
    } catch {
      // Fallback: assume reachable if core API was alive
      const reachable = true;
      SystemService.openApiCheckCache = { reachable, timestamp: now };
      return reachable;
    }
  }

  private async _executeProbeCapabilities(): Promise<BackendCapabilities> {
    const startTime = performance.now();
    const timestamp = new Date().toISOString();

    const capabilities: BackendCapabilities = {
      apiReachable: false,
      openApiReachable: false,
      handshakeAvailable: false,
      backendVersion: '1.0.0',
      chatAvailable: false,
      documentsAvailable: false,
      graphAvailable: false,
      searchAvailable: false,
      hardwareTelemetryAvailable: false,
      neo4jStatusAvailable: false,
      sseStreamingAvailable: false,
      serverAbortAvailable: false,
      asyncSourceStatusAvailable: false,
      lastProbeTime: timestamp,
      latencyMs: 0,
    };

    try {
      // 1. Fast-path connection alive check via /api/health with quick /health fallback
      let aliveRes = await apiClient.request(ENDPOINTS.HEALTH, undefined, {
        method: 'GET',
        skipModeCheck: true,
        timeoutMs: 1800,
      });

      if (aliveRes.status !== 200) {
        aliveRes = await apiClient.request(ENDPOINTS.HEALTH_ALT, undefined, {
          method: 'GET',
          skipModeCheck: true,
          timeoutMs: 1800,
        });
      }

      if (aliveRes.status !== 200) {
        aliveRes = await apiClient.request(ENDPOINTS.INDEX, undefined, {
          method: 'GET',
          skipModeCheck: true,
          timeoutMs: 1800,
        });
      }

      capabilities.latencyMs = Math.round(performance.now() - startTime);

      if (aliveRes.status >= 200 && aliveRes.status < 400) {
        capabilities.apiReachable = true;
        capabilities.chatAvailable = true;
        capabilities.documentsAvailable = true;
        capabilities.searchAvailable = true;
        // Rely on /api/health for handshake availability without burning single-use tokens
        capabilities.handshakeAvailable = true;

        const resData =
          aliveRes.data && typeof aliveRes.data === 'object'
            ? (aliveRes.data as Record<string, unknown>)
            : null;
        if (typeof resData?.version === 'string' || typeof resData?.api_version === 'string') {
          capabilities.backendVersion = String(resData.version || resData.api_version);
        }

        // 2. High-speed concurrent inspection of remaining subsystems
        // Notice: performHandshake() is intentionally omitted here to prevent token churn
        const [openApiSuccess, telemRes, neo4jRes] = await Promise.allSettled([
          this._probeOpenApiLightweight(),
          apiClient.request(ENDPOINTS.HARDWARE_TELEMETRY, undefined, {
            method: 'GET',
            skipModeCheck: true,
            timeoutMs: 2000,
          }),
          apiClient.request(ENDPOINTS.NEO4J_STATUS, undefined, {
            method: 'GET',
            skipModeCheck: true,
            timeoutMs: 2000,
          }),
        ]);

        if (openApiSuccess.status === 'fulfilled' && openApiSuccess.value === true) {
          capabilities.openApiReachable = true;
        }

        if (telemRes.status === 'fulfilled' && telemRes.value.status === 200) {
          capabilities.hardwareTelemetryAvailable = true;
        }

        if (neo4jRes.status === 'fulfilled' && neo4jRes.value.status === 200) {
          capabilities.neo4jStatusAvailable = true;
          const neoData =
            neo4jRes.value.data && typeof neo4jRes.value.data === 'object'
              ? (neo4jRes.value.data as Record<string, unknown>)
              : null;
          if (neoData && neoData.connected !== false) {
            capabilities.graphAvailable = true;
          }
        }
      }
    } catch {
      // Ignore network errors in probe
    }

    return capabilities;
  }

  /**
   * Test Cloudflare Tunnel / Gateway connection directly with fast-path race
   * Probes /api/health and fallbacks with low-latency concurrent resolution
   */
  public async testConnection(customUrl?: string): Promise<{
    success: boolean;
    status: number;
    latencyMs: number;
    endpoint: string;
    version?: string;
    isVersionAligned?: boolean;
    error?: string;
    isCorsIssue?: boolean;
  }> {
    const rawTarget = (customUrl || getApiBaseUrl()).trim().replace(/\/+$/, '');
    const startTime = performance.now();

    // Fast-path 1: Try /api/health directly with a responsive 2000ms timeout
    const fetchEndpoint = async (ep: string, timeoutMs: number) => {
      const fullUrl = `${rawTarget}${ep}`;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const res = await fetch(fullUrl, {
          method: 'GET',
          signal: controller.signal,
          headers: {
            Accept: 'application/json, text/plain, */*',
            'Cache-Control': 'no-cache',
          },
        });
        clearTimeout(timer);
        return { res, endpoint: ep };
      } catch (err: unknown) {
        clearTimeout(timer);
        throw err;
      }
    };

    try {
      const { res, endpoint } = await fetchEndpoint('/api/health', 2000);
      const latencyMs = Math.round(performance.now() - startTime);
      if (res.status < 500) {
        let parsedVersion: string | undefined;
        let isVersionAligned = true;
        try {
          const body = (await res.clone().json().catch(() => null)) as Record<string, unknown> | null;
          parsedVersion = typeof body?.version === 'string' ? body.version : typeof body?.api_version === 'string' ? body.api_version : undefined;
          if (parsedVersion) {
            isVersionAligned = parsedVersion === '1.0.0';
          }
        } catch {}

        return {
          success: true,
          status: res.status,
          latencyMs,
          endpoint,
          version: parsedVersion ?? '1.0.0',
          isVersionAligned,
        };
      }
    } catch {
      // /api/health failed or timed out; proceed to parallel fallback probe
    }

    // Fast-path 2: Probe secondary endpoints in parallel with 2500ms timeout
    const fallbackEndpoints = ['/health', '/', '/api/documents', '/docs'];
    try {
      const probePromises = fallbackEndpoints.map(async (ep) => {
        const result = await fetchEndpoint(ep, 2500);
        if (result.res.status < 500) {
          return result;
        }
        throw new Error(`Status ${result.res.status}`);
      });

      const firstSuccess = await Promise.any(probePromises);
      const latencyMs = Math.round(performance.now() - startTime);
      let parsedVersion: string | undefined;
      let isVersionAligned = true;
      try {
        const body = (await firstSuccess.res.clone().json().catch(() => null)) as Record<string, unknown> | null;
        parsedVersion = typeof body?.version === 'string' ? body.version : typeof body?.api_version === 'string' ? body.api_version : undefined;
        if (parsedVersion) {
          isVersionAligned = parsedVersion === '1.0.0';
        }
      } catch {}

      return {
        success: true,
        status: firstSuccess.res.status,
        latencyMs,
        endpoint: firstSuccess.endpoint,
        version: parsedVersion ?? '1.0.0',
        isVersionAligned,
      };
    } catch {
      const latencyMs = Math.round(performance.now() - startTime);
      return {
        success: false,
        status: 0,
        latencyMs,
        endpoint: '/api/health',
        isCorsIssue: true,
        error: `Cannot reach ${rawTarget}. Please verify that the backend server is running and accessible.`,
      };
    }
  }
}

export const systemService = new SystemService();
