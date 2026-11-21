import { type ApiResponse, apiClient } from '../../api/client';
import { ENDPOINTS } from '../../api/endpoints';
import {
  type SubgraphQueryRequest,
  type SubgraphQueryResponse,
  SubgraphQueryResponseSchema,
} from '../../types';
import { normalizeError } from '../../utils/errorMapper';
import {
  FATAL_HTTP_STATUSES,
  isRefusalAnswer,
  synthesizeSubgraphResponse,
} from './chatResponseSynthesizer';

export async function executeSubgraphQuery(
  req: SubgraphQueryRequest,
  signal?: AbortSignal,
  onStreamChunk?: (chunk: string, accumulated: string) => void,
  onStageUpdate?: (stage: Record<string, unknown>) => void,
  onAbort?: () => void
): Promise<ApiResponse<SubgraphQueryResponse>> {
  const effectiveMode = req.mode || (req.hops && req.hops > 1 ? 'expert' : 'fast');
  const effectiveRequestId =
    req.request_id || `req-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
  const startTime = Date.now();
  let accumulatedStreamText = '';

  // 1. If streaming callback is provided, attempt streaming via POST /api/chat
  if (onStreamChunk) {
    if (signal && onAbort) {
      signal.addEventListener('abort', onAbort, { once: true });
    }

    const wrappedOnStreamChunk = (chunk: string, accumulated: string) => {
      accumulatedStreamText = accumulated || accumulatedStreamText + chunk;
      onStreamChunk(chunk, accumulated);
    };

    const streamRes = await apiClient.requestStream(
      ENDPOINTS.CHAT,
      {
        method: 'POST',
        headers: {
          'X-Request-Id': effectiveRequestId,
        },
        body: JSON.stringify({
          message: req.query,
          query: req.query,
          mode: effectiveMode,
          stream: true,
          chat_history: req.chat_history,
          session_id: req.thread_id,
          thread_id: req.thread_id,
          request_id: effectiveRequestId,
          active_docs:
            req.active_docs && req.active_docs.length > 0 ? req.active_docs : undefined,
          format: 'sse',
          document_filter: req.document_filter,
          hops: req.hops ?? (effectiveMode === 'expert' ? 3 : effectiveMode === 'conversational' ? 0 : 1),
          top_k: req.top_k ?? (effectiveMode === 'expert' ? 8 : effectiveMode === 'conversational' ? 0 : 4),
          parser: req.parser || (effectiveMode === 'expert' ? 'docling' : 'fast'),
          full_potential: effectiveMode === 'expert',
        }),
        signal,
        timeoutMs: 90000,
        onStageUpdate,
      },
      wrappedOnStreamChunk
    );

    // Stop fallback waterfall immediately on abort
    if (signal?.aborted || streamRes.error?.code === 'CLIENT_REQUEST_CANCELLED') {
      return {
        data: null,
        error:
          streamRes.error ||
          normalizeError(new DOMException('Client request cancelled', 'AbortError'), ENDPOINTS.CHAT),
        isMock: false,
        status: streamRes.status || 499,
      };
    }

    // Stop waterfall on server errors, auth, quota, or rate limit
    if (streamRes.status && FATAL_HTTP_STATUSES.has(streamRes.status)) {
      return {
        data: null,
        error: streamRes.error,
        isMock: false,
        status: streamRes.status,
      };
    }

    const meta = streamRes.metadata || {};
    const metaParts =
      (meta.candidates as any)?.[0]?.content?.parts?.[0]?.text ||
      (meta.choices as any)?.[0]?.message?.content ||
      '';

    const resolvedStreamText =
      streamRes.text ||
      accumulatedStreamText ||
      (typeof meta.grounded_answer === 'string' ? meta.grounded_answer : '') ||
      (typeof meta.answer === 'string' ? meta.answer : '') ||
      (typeof meta.reply === 'string' ? meta.reply : '') ||
      (typeof meta.content === 'string' ? meta.content : '') ||
      (typeof metaParts === 'string' ? metaParts : '');

    // If stream received text tokens, synthesize and return
    if (resolvedStreamText.trim().length > 0) {
      const synthesized = synthesizeSubgraphResponse(
        meta,
        resolvedStreamText,
        req,
        startTime
      );
      return {
        data: synthesized,
        error: null,
        isMock: false,
        status: 200,
      };
    }

    // If stream emitted an error payload or terminated abnormally, propagate error
    if (streamRes.error) {
      return {
        data: null,
        error: streamRes.error,
        isMock: false,
        status: streamRes.status || 500,
      };
    }

    // If stream completed HTTP 200 but emitted 0 tokens and no error, supply grounded fallback
    if (streamRes.status === 200) {
      const fallbackText =
        'No grounded answer could be synthesized from the active documents. Please verify that your document is attached to your drawer, check your model configuration in the Control Center, or click Retry.';
      const synthesizedFallback = synthesizeSubgraphResponse(
        meta,
        fallbackText,
        req,
        startTime
      );
      return {
        data: synthesizedFallback,
        error: null,
        isMock: false,
        status: 200,
      };
    }

    // Only fall through to non-streaming if endpoint not found (404 / 405)
    if (streamRes.status !== 404 && streamRes.status !== 405 && streamRes.status !== 0) {
      return {
        data: null,
        error: streamRes.error,
        isMock: false,
        status: streamRes.status,
      };
    }
  }

  // 2. Standard JSON call: First try /api/chat
  const chatPayload = {
    message: req.query,
    query: req.query,
    mode: effectiveMode,
    stream: false,
    chat_history: req.chat_history,
    session_id: req.thread_id,
    thread_id: req.thread_id,
    request_id: effectiveRequestId,
    active_docs:
      req.active_docs && req.active_docs.length > 0 ? req.active_docs : undefined,
    document_filter: req.document_filter,
    hops: req.hops ?? (effectiveMode === 'expert' ? 3 : effectiveMode === 'conversational' ? 0 : 1),
    top_k: req.top_k ?? (effectiveMode === 'expert' ? 8 : effectiveMode === 'conversational' ? 0 : 4),
    parser: req.parser || (effectiveMode === 'expert' ? 'docling' : 'fast'),
    full_potential: effectiveMode === 'expert',
  };

  const chatRes = await apiClient.request<Record<string, unknown>>(
    ENDPOINTS.CHAT,
    undefined,
    {
      method: 'POST',
      headers: {
        'X-Request-Id': effectiveRequestId,
      },
      body: JSON.stringify(chatPayload),
      signal,
      timeoutMs: 45000,
    }
  );

  // Check cancellation
  if (signal?.aborted || chatRes.error?.code === 'CLIENT_REQUEST_CANCELLED') {
    return {
      data: null,
      error:
        chatRes.error ||
        normalizeError(new DOMException('Client request cancelled', 'AbortError'), ENDPOINTS.CHAT),
      isMock: chatRes.isMock,
      status: chatRes.status || 499,
    };
  }

  if (chatRes.status && FATAL_HTTP_STATUSES.has(chatRes.status)) {
    return {
      data: null,
      error: chatRes.error,
      isMock: chatRes.isMock,
      status: chatRes.status,
    };
  }

  if (chatRes.status === 200 && chatRes.data) {
    const rawData = chatRes.data;
    const candidatesText = (rawData as any)?.candidates?.[0]?.content?.parts?.[0]?.text || '';
    const choicesText = (rawData as any)?.choices?.[0]?.message?.content || '';
    const rawAns =
      (typeof rawData.grounded_answer === 'string' ? rawData.grounded_answer : '') ||
      (typeof rawData.answer === 'string' ? rawData.answer : '') ||
      (typeof (rawData as any).reply === 'string' ? (rawData as any).reply : '') ||
      (typeof (rawData as any).content === 'string' ? (rawData as any).content : '') ||
      (typeof (rawData as any).text === 'string' ? (rawData as any).text : '') ||
      (typeof (rawData as any).output === 'string' ? (rawData as any).output : '') ||
      (typeof (rawData as any).result === 'string' ? (rawData as any).result : '') ||
      candidatesText ||
      choicesText;

    if (rawAns || rawData.top_chunks || rawData.citations) {
      const synthesized = synthesizeSubgraphResponse(rawData, rawAns, req, startTime);
      return {
        data: synthesized,
        error: null,
        isMock: chatRes.isMock,
        status: 200,
      };
    }
  }

  // 3. Fallback to /api/subgraph/query only on 404/405
  if (chatRes.status !== 404 && chatRes.status !== 405 && chatRes.status !== 0) {
    return {
      data: null,
      error: chatRes.error,
      isMock: chatRes.isMock,
      status: chatRes.status,
    };
  }

  const fallbackRes = await apiClient.request<SubgraphQueryResponse>(
    ENDPOINTS.SUBGRAPH_QUERY,
    SubgraphQueryResponseSchema,
    {
      method: 'POST',
      body: JSON.stringify(req),
      signal,
      timeoutMs: 45000,
    }
  );

  if (fallbackRes.status === 200 && fallbackRes.data) {
    const data = fallbackRes.data;
    if (isRefusalAnswer(data.grounded_answer) && data.quality_gate_decision === 'accept') {
      data.quality_gate_decision = 'unable_to_verify';
    }
    return fallbackRes;
  }

  return {
    data: null,
    error: fallbackRes.error || chatRes.error,
    isMock: chatRes.isMock,
    status: fallbackRes.status || chatRes.status,
  };
}
