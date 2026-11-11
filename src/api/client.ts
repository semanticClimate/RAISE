import type { z } from 'zod';
import { config, getApiBaseUrl, getApiMode, getStoredApiKey } from '../app/config';
import type { ApiError } from '../types';
import { normalizeError } from '../utils/errorMapper';
import { sanitizeStreamText } from '../utils/sanitizeStreamText';
import { logToTerminal } from '../utils/terminalLogger';

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

    // Summarize payload for terminal display
    let details: string | undefined;
    if (typeof options.body === 'string') {
      try {
        const parsed = JSON.parse(options.body) as Record<string, unknown>;
        const query = typeof parsed.query === 'string' ? parsed.query : undefined;
        const message = typeof parsed.message === 'string' ? parsed.message : undefined;
        details = query
          ? `Query: "${query.slice(0, 70)}${query.length > 70 ? '...' : ''}"`
          : message
            ? `Message: "${message.slice(0, 70)}${message.length > 70 ? '...' : ''}"`
            : options.body.slice(0, 100);
      } catch {
        details = options.body.slice(0, 100);
      }
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
    const baseUrl = getApiBaseUrl();
    const url = endpoint.startsWith('http') ? endpoint : `${baseUrl}${endpoint}`;
    const timeoutMs = options.timeoutMs || 90000;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    if (options.signal) {
      options.signal.addEventListener('abort', () => controller.abort(), { once: true });
    }

    const headers: Record<string, string> = {
      'X-Request-ID': `req-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      Accept: 'text/event-stream, application/json; q=0.9, text/plain; q=0.2, */*; q=0.1',
      ...(options.headers as Record<string, string>),
    };

    const apiKey = getStoredApiKey();
    if (apiKey && !headers.Authorization) {
      headers.Authorization = `Bearer ${apiKey}`;
      headers['X-API-Key'] = apiKey;
    }

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    const method = options.method || 'POST';
    const startTime = Date.now();
    logToTerminal({
      type: 'REQ',
      method,
      endpoint,
      details: `Streaming SSE request to ${url}`,
    });

    let onAbort: (() => void) | null = null;
    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
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
          error: `Stream error (HTTP ${response.status}): ${normErr.message}`,
        });
        return { text: '', error: normErr, status: response.status };
      }

      const contentType = response.headers.get('content-type') || '';
      let isSse =
        contentType.includes('text/event-stream') || contentType.includes('application/x-ndjson');

      // Fast-path: If server explicitly returns standard JSON (not an event stream)
      if (contentType.includes('application/json')) {
        const rawText = await response.text();
        let extractedText = rawText;
        let metadata: Record<string, unknown> | undefined;
        try {
          const json = JSON.parse(rawText);
          if (json && typeof json === 'object') {
            const obj = json as Record<string, unknown>;
            metadata = obj;
            extractedText =
              (typeof obj.grounded_answer === 'string' ? obj.grounded_answer : '') ||
              (typeof obj.answer === 'string' ? obj.answer : '') ||
              (typeof obj.reply === 'string' ? obj.reply : '') ||
              (typeof obj.text === 'string' ? obj.text : '') ||
              (typeof obj.content === 'string' ? obj.content : '') ||
              (typeof obj.response === 'string' ? obj.response : '') ||
              rawText;
          }
        } catch {
          // not json, use rawText
        }
        const sanitized = sanitizeStreamText(extractedText);
        onChunk?.(sanitized, sanitized);
        logToTerminal({
          type: 'RES',
          method,
          endpoint,
          status: response.status,
          durationMs: Date.now() - startTime,
          message: `Direct JSON response completed (${sanitized.length} characters)`,
        });
        return { text: sanitized, error: null, status: response.status, metadata };
      }

      if (!response.body) {
        const text = await response.text();
        const sanitized = sanitizeStreamText(text);
        onChunk?.(sanitized, sanitized);
        logToTerminal({
          type: 'RES',
          method,
          endpoint,
          status: response.status,
          durationMs: Date.now() - startTime,
          message: `Stream completed (static body)`,
        });
        return { text: sanitized, error: null, status: response.status };
      }

      reader = response.body.getReader();
      onAbort = () => {
        try {
          reader?.cancel().catch(() => {});
        } catch {
          // ignore
        }
      };

      if (options.signal) {
        if (options.signal.aborted) {
          onAbort();
        } else {
          options.signal.addEventListener('abort', onAbort, { once: true });
        }
      }

      const decoder = new TextDecoder();
      let fullText = '';
      let buffer = '';
      let streamMetadata: Record<string, unknown> | undefined;
      let streamError: ApiError | null = null;
      let isStreamComplete = false;

      const asRecord = (v: unknown): Record<string, unknown> | null =>
        v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null;

      const getStringField = (obj: Record<string, unknown> | null, key: string): string | undefined =>
        obj && typeof obj[key] === 'string' ? (obj[key] as string) : undefined;

      let currentEvent = '';

      const processLine = (line: string) => {
        const trimmed = line.trim();
        // Ignore SSE comments/keepalives (e.g. ": keepalive")
        if (!trimmed || trimmed.startsWith(':')) {
          if (!trimmed) {
            currentEvent = '';
          }
          return;
        }

        // Track SSE event declaration lines (e.g. "event: node_update", "event: stage", "event: citations")
        if (trimmed.startsWith('event:')) {
          currentEvent = trimmed.slice(6).trim();
          return;
        }

        let payload = line;
        let isData = false;
        if (payload.startsWith('data:')) {
          isData = true;
          // Strip "data:" prefix and optional single leading space, but PRESERVE trailing spaces/newlines!
          payload = payload.slice(5).replace(/^[ \t]/, '');
        }

        if (!payload) return;

        if (payload.trim() === '[DONE]') {
          currentEvent = '';
          isStreamComplete = true;
          return;
        }

        // Handle JSON payloads: {"token": "..."} or {"text": "..."} or {"content": "..."}
        const trimmedPayload = payload.trim();
        if (
          (trimmedPayload.startsWith('{') && trimmedPayload.endsWith('}')) ||
          (trimmedPayload.startsWith('[') && trimmedPayload.endsWith(']'))
        ) {
          try {
            const parsed: unknown = JSON.parse(trimmedPayload);
            const p = asRecord(parsed);

            // 1. Check for stage/node progression events (only if p actually contains node or stage)
            if (
              (currentEvent === 'node_update' || currentEvent === 'stage' || p?.node || p?.stage) &&
              (p?.node !== undefined || p?.stage !== undefined)
            ) {
              currentEvent = '';
              if (p) {
                options.onStageUpdate?.(p);
              }
              return;
            }

            // 2. Check for error payload: {"error": {"code": "...", "message": "..."}}
            if (p?.error !== undefined) {
              currentEvent = '';
              const errObj = asRecord(p.error) || { message: String(p.error) };
              const code = getStringField(errObj, 'code') || 'STREAM_ERROR';
              const message =
                getStringField(errObj, 'message') || 'An error occurred during streaming';
              streamError = {
                code,
                message,
                status: response.status,
                endpoint,
                retryable: code !== 'CANCELLED',
                timestamp: new Date().toISOString(),
              };
              return;
            }

            if (
              currentEvent === 'citations' ||
              (Array.isArray(parsed) &&
                parsed.length > 0 &&
                asRecord(parsed[0])?.citation_index !== undefined)
            ) {
              streamMetadata = {
                ...streamMetadata,
                citations: parsed,
              };
              options.onMetadata?.({ citations: parsed });
              return;
            }

            // 3. Capture completion metadata (citations, subgraph, sources, status, etc.)
            const isMetadataObject = Boolean(
              p &&
                (p.citations !== undefined ||
                  p.subgraph !== undefined ||
                  p.sources !== undefined ||
                  p.verified_claims !== undefined ||
                  p.status === 'completed' ||
                  p.status === 'SUCCESS' ||
                  p.quality_gate_decision !== undefined)
            );

            if (isMetadataObject && p) {
              currentEvent = '';
              streamMetadata = {
                ...streamMetadata,
                ...p,
              };
              options.onMetadata?.(p);

              // If the SSE stream delivers the final synthesized answer directly in the metadata payload without micro-tokens, unpack it immediately to avoid empty response box
              if (!fullText.trim()) {
                const answerInMeta =
                  getStringField(p, 'grounded_answer') ??
                  getStringField(p, 'answer') ??
                  getStringField(p, 'reply') ??
                  getStringField(p, 'response');
                if (answerInMeta) {
                  fullText = sanitizeStreamText(answerInMeta);
                  onChunk?.(fullText, fullText);
                }
              }
              return;
            }

            // 4. Check for incremental micro-token streaming payloads
            const deltaObj = asRecord(p?.delta);
            const token =
              getStringField(p, 'token') ??
              getStringField(p, 'text') ??
              getStringField(p, 'content') ??
              getStringField(deltaObj, 'content') ??
              (typeof p?.delta === 'string' ? p.delta : undefined) ??
              (!fullText.trim()
                ? (getStringField(p, 'grounded_answer') ?? getStringField(p, 'answer') ?? getStringField(p, 'response') ?? getStringField(p, 'reply'))
                : undefined) ??
              null;
            if (typeof token === 'string') {
              currentEvent = '';
              if (token.length > 0) {
                fullText += token;
                onChunk?.(token, fullText);
              }
              return;
            }
          } catch {
            // Malformed JSON block: attempt unpacking via sanitizeStreamText
            const unpacked = sanitizeStreamText(trimmedPayload);
            if (unpacked && !unpacked.startsWith('{')) {
              fullText += unpacked;
              onChunk?.(unpacked, fullText);
              return;
            }
            return;
          }
        }

        // If it was an explicit SSE "data: ..." line that is plain text
        if (isData) {
          fullText += `${payload}\n`;
          onChunk?.(`${payload}\n`, fullText);
          return;
        }

        // If plain text line (not JSON)
        if (!trimmedPayload.startsWith('{') && !trimmedPayload.startsWith('[')) {
          fullText += `${line}\n`;
          onChunk?.(`${line}\n`, fullText);
        }
      };

      while (!isStreamComplete) {
        const { done, value } = await reader.read();
        if (done) break;

        const raw = decoder.decode(value, { stream: true });
        buffer += raw;

        // Dynamic SSE detection: fallback if proxy/intermediary stripped text/event-stream header
        if (!isSse && (buffer.startsWith(':') || buffer.includes('event:') || buffer.includes('data:'))) {
          isSse = true;
        }

        // Line-buffer whenever newlines or SSE markers are present
        if (buffer.includes('\n') || isSse || buffer.includes('data:')) {
          const lines = buffer.split('\n');
          // Incomplete trailing segment stays in buffer
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            processLine(line);
            if (isStreamComplete) break;
          }
        } else if (!isSse && !buffer.includes('data:') && !buffer.startsWith('{')) {
          fullText += buffer;
          onChunk?.(buffer, fullText);
          buffer = '';
        }

        if (isStreamComplete) {
          try {
            await reader.cancel();
          } catch {
            // Stream already finished or cancelled
          }
          break;
        }
      }

      // Flush remaining bytes in decoder and buffer
      buffer += decoder.decode();
      if (buffer.trim()) {
        processLine(buffer);
      }

      // Final pass: ensure no residual JSON tokens or SSE markers remain
      fullText = sanitizeStreamText(fullText);

      // Sid says: Guard against empty response bug - fallback to answer/grounded_answer/reply in streamMetadata
      if (!fullText.trim() && streamMetadata) {
        const fallbackAns =
          getStringField(streamMetadata, 'grounded_answer') ??
          getStringField(streamMetadata, 'answer') ??
          getStringField(streamMetadata, 'reply') ??
          '';
        if (fallbackAns) {
          fullText = sanitizeStreamText(fallbackAns);
          onChunk?.(fullText, fullText);
        }
      }

      logToTerminal({
        type: 'RES',
        method,
        endpoint,
        status: response.status,
        durationMs: Date.now() - startTime,
        message: `Stream completed successfully (${fullText.length} characters)`,
      });

      return { text: fullText, error: streamError, status: response.status, metadata: streamMetadata };
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
        error: `Stream exception: ${normErr.message} (Target: ${url})`,
      });
      return { text: '', error: normErr, status: 0 };
    } finally {
      clearTimeout(timer);
      if (reader) {
        try {
          reader.cancel().catch(() => {});
        } catch {
          // ignore
        }
      }
      if (options.signal && onAbort) {
        options.signal.removeEventListener('abort', onAbort);
      }
    }
  }
}

export const apiClient = new ApiClient();
