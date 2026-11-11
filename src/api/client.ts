import type { z } from 'zod';
import { config, getApiBaseUrl, getApiMode, getStoredApiKey } from '../app/config';
import type { ApiError } from '../types';
import { normalizeError } from '../utils/errorMapper';
import { sanitizeStreamText } from '../utils/sanitizeStreamText';
import { logToTerminal } from '../utils/terminalLogger';
import { executeStreamRequest } from './streamClient';

export { sanitizeStreamText };

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  skipModeCheck?: boolean; // Force real network call (used during capability probe)
  onStageUpdate?: (stage: {
    node?: string;
    stage?: string;
    status?: string;
    step?: number;
    total_steps?: number;
    label?: string;
    detail?: string;
    [key: string]: unknown;
  }) => void;
  onMetadata?: (metadata: Record<string, unknown>) => void;
}

export interface ApiResponse<T> {
  data: T | null;
  error: ApiError | null;
  isMock: boolean;
  status: number;
}

export interface StreamResult {
  text: string;
  error: ApiError | null;
  status: number;
  metadata?: Record<string, unknown>;
}

export function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === 'string') return err;
  if (
    typeof err === 'object' &&
    err !== null &&
    'message' in err &&
    typeof (err as { message: unknown }).message === 'string'
  ) {
    return (err as { message: string }).message;
  }
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}

class ApiClient {
  public async request<T>(
    endpoint: string,
    schema?: { safeParse: (data: unknown) => { success: true; data: T } | { success: false; error: z.ZodError } },
    options: RequestOptions = {}
  ): Promise<ApiResponse<T>> {
    const method = options.method || 'GET';
    const startTime = Date.now();

    // Summarize payload for terminal display (lightweight preview without main-thread JSON.parse)
    let details: string | undefined;
    if (typeof options.body === 'string') {
      const preview = options.body.slice(0, 300);
      const queryMatch = preview.match(/"query"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"/);
      const msgMatch = preview.match(/"message"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"/);
      const query = queryMatch?.[1];
      const message = msgMatch?.[1];
      details = query
        ? `Query: "${query.slice(0, 70)}${query.length > 70 ? '...' : ''}"`
        : message
          ? `Message: "${message.slice(0, 70)}${message.length > 70 ? '...' : ''}"`
          : options.body.slice(0, 100);
    } else if (options.body instanceof FormData) {
      details = 'Multipart/form-data (Document Upload)';
    }

    logToTerminal({
      type: 'REQ',
      method,
      endpoint,
      details,
    });

    if (options.signal?.aborted) {
      const normErr = normalizeError(
        new DOMException('The user aborted a request.', 'AbortError'),
        endpoint,
        0
      );
      logToTerminal({
        type: 'ERR',
        method,
        endpoint,
        status: 0,
        durationMs: Date.now() - startTime,
        error: 'Request aborted by client signal',
      });
      return { data: null, error: normErr, isMock: getApiMode() === 'mock', status: 0 };
    }

    const currentMode = getApiMode();

    // 1. MOCK MODE
    if (currentMode === 'mock' && !options.skipModeCheck) {
      const normErr = normalizeError(
        new Error('Mock adapter is not included in live deployment build.'),
        endpoint,
        0
      );
      return { data: null, error: normErr, isMock: false, status: 0 };
    }

    // 2. REMOTE OR AUTO MODE
    const baseUrl = getApiBaseUrl();
    const url = endpoint.startsWith('http') ? endpoint : `${baseUrl}${endpoint}`;
    const timeoutMs =
      options.timeoutMs ||
      (endpoint.includes('upload') ? config.uploadTimeoutMs : config.defaultTimeoutMs);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    // Merge external signal if provided
    if (options.signal) {
      options.signal.addEventListener('abort', () => controller.abort(), { once: true });
    }

    const headers: Record<string, string> = {
      'X-Request-ID': `req-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      ...(options.headers as Record<string, string>),
    };

    // Attach optional API Key / Bearer token if configured
    const apiKey = getStoredApiKey();
    if (apiKey && !headers.Authorization) {
      headers.Authorization = `Bearer ${apiKey}`;
      headers['X-API-Key'] = apiKey;
    }

    // If body is NOT FormData, default to application/json
    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (!response.ok) {
        let errJson: unknown = null;
        try {
          errJson = await response.json();
        } catch {
          errJson = await response.text();
        }
        const normErr = normalizeError(errJson || response.statusText, endpoint, response.status);
        logToTerminal({
          type: 'ERR',
          method,
          endpoint,
          status: response.status,
          durationMs: Date.now() - startTime,
          error: `Gateway HTTP ${response.status}: ${normErr.message}`,
        });
        return { data: null, error: normErr, isMock: false, status: response.status };
      }

      // Check content type for binary data (like PDF)
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/pdf') || contentType.includes('octet-stream')) {
        const blob = await response.blob();
        logToTerminal({
          type: 'RES',
          method,
          endpoint,
          status: response.status,
          durationMs: Date.now() - startTime,
          message: `Binary PDF Stream Received (${blob.size} bytes)`,
        });
        return { data: blob as unknown as T, error: null, isMock: false, status: response.status };
      }

      const json = await response.json();

      if (schema) {
        const parseResult = schema.safeParse(json);
        if (!parseResult.success) {
          const normErr = normalizeError(parseResult.error, endpoint, response.status);
          logToTerminal({
            type: 'ERR',
            method,
            endpoint,
            status: response.status,
            durationMs: Date.now() - startTime,
            error: `Contract Violation: ${normErr.message}`,
          });
          return { data: null, error: normErr, isMock: false, status: response.status };
        }
        logToTerminal({
          type: 'RES',
          method,
          endpoint,
          status: response.status,
          durationMs: Date.now() - startTime,
          message: 'Live Gateway Response 200 OK (Validated)',
        });
        return { data: parseResult.data, error: null, isMock: false, status: response.status };
      }

      logToTerminal({
        type: 'RES',
        method,
        endpoint,
        status: response.status,
        durationMs: Date.now() - startTime,
        message: 'Live Gateway Response 200 OK',
      });
      return { data: json as T, error: null, isMock: false, status: response.status };
    } catch (err: unknown) {
      clearTimeout(timer);

      const errMessage = getErrorMessage(err);
      const isCorsOrOffline =
        err instanceof TypeError &&
        (errMessage.includes('fetch') ||
          errMessage.includes('NetworkError') ||
          errMessage.includes('Failed'));

      const normErr = isCorsOrOffline
        ? {
            code: 'BACKEND_UNREACHABLE',
            message:
              'Unable to connect to the backend server. Please verify that the server is online.',
            status: 0,
            endpoint,
            retryable: true,
            timestamp: new Date().toISOString(),
          }
        : normalizeError(err, endpoint, 0);

      logToTerminal({
        type: 'ERR',
        method,
        endpoint,
        status: 0,
        durationMs: Date.now() - startTime,
        error: `Network Fetch Exception: ${normErr.message} (Target: ${url})`,
      });
      return { data: null, error: normErr, isMock: false, status: 0 };
    }
  }

  /**
   * Streaming support for LLM text responses (SSE or chunked transfer)
   */
  public async requestStream(
    endpoint: string,
    options: RequestOptions = {},
    onChunk?: (textChunk: string, fullAccumulatedText: string) => void
  ): Promise<StreamResult> {
    return executeStreamRequest(endpoint, options, onChunk);
  }
}

export const apiClient = new ApiClient();
