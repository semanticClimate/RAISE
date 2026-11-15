import { getApiBaseUrl, getApiMode, getStoredApiKey } from '../app/config';
import { normalizeError } from '../utils/errorMapper';
import { sanitizeStreamText } from '../utils/sanitizeStreamText';
import { logToTerminal } from '../utils/terminalLogger';
import { getErrorMessage, type RequestOptions, type StreamResult } from './client';
import { createStreamLineParser, type StreamLineParserState } from './streamLineParser';

export async function executeStreamRequest(
  endpoint: string,
  options: RequestOptions = {},
  onChunk?: (chunk: string, accumulated: string) => void
): Promise<StreamResult> {
  const method = options.method || 'POST';
  const startTime = Date.now();

  if (typeof window !== 'undefined') {
    (window as any).__RAISE_ACTIVE_OPS__ = ((window as any).__RAISE_ACTIVE_OPS__ || 0) + 1;
    (window as any).__RAISE_ACTIVE_STREAM__ = true;
  }

  let details: string | undefined;
  if (typeof options.body === 'string') {
    const preview = options.body.slice(0, 300);
    const queryMatch = preview.match(/"query"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"/);
    const msgMatch = preview.match(/"message"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"/);
    const query = queryMatch?.[1];
    const message = msgMatch?.[1];
    details = query
      ? `Stream Query: "${query.slice(0, 70)}${query.length > 70 ? '...' : ''}"`
      : message
        ? `Stream Message: "${message.slice(0, 70)}${message.length > 70 ? '...' : ''}"`
        : options.body.slice(0, 100);
  }

  logToTerminal({
    type: 'REQ',
    method,
    endpoint,
    details: details || 'SSE Stream Request',
  });

  if (options.signal?.aborted) {
    const normErr = normalizeError(
      new DOMException('The user aborted a request.', 'AbortError'),
      endpoint,
      0
    );
    return { text: '', error: normErr, status: 0 };
  }

  const isMock = getApiMode() === 'mock';
  if (isMock) {
    const mockText = 'Simulation response (mock mode active).';
    onChunk?.(mockText, mockText);
    return { text: mockText, error: null, status: 200 };
  }

  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has('Accept')) {
    headers.set('Accept', 'text/event-stream, application/json, text/plain, */*');
  }
  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const apiKey = getStoredApiKey();
  if (apiKey && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${apiKey}`);
  }

  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? 90000;
  let timer: ReturnType<typeof setTimeout> | undefined;
  if (timeoutMs > 0) {
    timer = setTimeout(() => {
      controller.abort();
    }, timeoutMs);
  }

  const forwardAbort = () => controller.abort();
  if (options.signal) {
    options.signal.addEventListener('abort', forwardAbort, { once: true });
  }

  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  let onAbort: (() => void) | undefined;
  let watchdogTimer: ReturnType<typeof setTimeout> | null = null;

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timer);

    if (!response.ok) {
      let rawErr = '';
      try {
        rawErr = await response.text();
      } catch {}
      const normErr = normalizeError(new Error(rawErr), endpoint, response.status);
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
      } catch {}
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
      } catch {}
    };

    if (options.signal) {
      if (options.signal.aborted) {
        onAbort();
      } else {
        options.signal.addEventListener('abort', onAbort, { once: true });
      }
    }

    const decoder = new TextDecoder();
    let buffer = '';

    const streamState: StreamLineParserState = {
      fullText: '',
      currentEvent: '',
      streamMetadata: undefined,
      streamError: null,
      isStreamComplete: false,
    };

    const resetWatchdog = () => {
      if (watchdogTimer) clearTimeout(watchdogTimer);
      watchdogTimer = setTimeout(() => {
        controller.abort();
      }, 60000);
    };
    resetWatchdog();

    const processLine = createStreamLineParser(
      {
        options: {
          ...options,
          onKeepalive: resetWatchdog,
        },
        endpoint,
        responseStatus: response.status,
        onChunk,
      },
      streamState
    );

    while (!streamState.isStreamComplete) {
      resetWatchdog();
      const { done, value } = await reader.read();
      if (done) break;

      const raw = decoder.decode(value, { stream: true });
      buffer += raw;

      if (!isSse && (buffer.startsWith(':') || buffer.includes('event:') || buffer.includes('data:'))) {
        isSse = true;
      }

      if (buffer.includes('\n') || isSse || buffer.includes('data:')) {
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          processLine(line);
          if (streamState.isStreamComplete) break;
        }
      } else if (!isSse && !buffer.includes('data:') && !buffer.startsWith('{')) {
        streamState.fullText += buffer;
        onChunk?.(buffer, streamState.fullText);
        buffer = '';
      }

      if (streamState.isStreamComplete) {
        try {
          await reader.cancel();
        } catch {}
        break;
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      processLine(buffer);
    }

    streamState.fullText = sanitizeStreamText(streamState.fullText);

    if (!streamState.fullText.trim() && streamState.streamMetadata) {
      const meta = streamState.streamMetadata;
      const fallbackCand = Array.isArray((meta as any).candidates)
        ? (meta as any).candidates[0]?.content?.parts?.[0]?.text
        : undefined;
      const fallbackAns =
        (typeof meta.grounded_answer === 'string' ? meta.grounded_answer : undefined) ??
        (typeof meta.answer === 'string' ? meta.answer : undefined) ??
        (typeof meta.reply === 'string' ? meta.reply : undefined) ??
        (typeof meta.response === 'string' ? meta.response : undefined) ??
        (typeof meta.output === 'string' ? meta.output : undefined) ??
        (typeof meta.result === 'string' ? meta.result : undefined) ??
        fallbackCand ??
        '';
      if (fallbackAns) {
        streamState.fullText = sanitizeStreamText(fallbackAns);
        onChunk?.(streamState.fullText, streamState.fullText);
      }
    }

    logToTerminal({
      type: 'RES',
      method,
      endpoint,
      status: response.status,
      durationMs: Date.now() - startTime,
      message: `Stream completed successfully (${streamState.fullText.length} characters)`,
    });

    return {
      text: streamState.fullText,
      error: streamState.streamError,
      status: response.status,
      metadata: streamState.streamMetadata,
    };
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
      : normalizeError(err, endpoint);

    logToTerminal({
      type: 'ERR',
      method,
      endpoint,
      status: normErr.status,
      durationMs: Date.now() - startTime,
      error: `Stream exception: ${normErr.message}`,
    });

    return { text: '', error: normErr, status: normErr.status };
  } finally {
    if (typeof window !== 'undefined') {
      (window as any).__RAISE_ACTIVE_OPS__ = Math.max(
        0,
        ((window as any).__RAISE_ACTIVE_OPS__ || 1) - 1
      );
      (window as any).__RAISE_ACTIVE_STREAM__ = (window as any).__RAISE_ACTIVE_OPS__ > 0;
    }
    clearTimeout(timer);
    if (watchdogTimer) clearTimeout(watchdogTimer);
    if (options.signal && onAbort) {
      options.signal.removeEventListener('abort', onAbort);
    }
  }
}
