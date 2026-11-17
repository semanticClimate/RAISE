import { type ApiResponse, apiClient } from '../../api/client';
import { ENDPOINTS } from '../../api/endpoints';
import {
  type AgentQueryRequest,
  type AgentQueryResponse,
  AgentQueryResponseSchema,
  type FeedbackStats,
  FeedbackStatsSchema,
} from '../../types';

export interface AbortChatParams {
  request_id?: string;
  session_id?: string;
  chat_id?: string;
}

export interface QuerySuggestion {
  query: string;
  title?: string;
  prompt?: string;
  category?: string;
  grounding_confidence?: string;
  complexity?: string;
  relationship_path?: string;
}

export interface FeedbackPayload {
  session_id?: string;
  rating: 'thumbs_up' | 'thumbs_down' | string;
  query?: string;
  message_id?: string;
  reason?: string;
}

export async function submitChatFeedback(
  payload: FeedbackPayload,
  signal?: AbortSignal
): Promise<ApiResponse<{ status: string; message?: string }>> {
  return apiClient.request<{ status: string; message?: string }>(ENDPOINTS.FEEDBACK, undefined, {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
    timeoutMs: 10000,
  });
}

export async function fetchFeedbackStats(
  signal?: AbortSignal
): Promise<ApiResponse<FeedbackStats>> {
  return apiClient.request<FeedbackStats>(ENDPOINTS.FEEDBACK_STATS, FeedbackStatsSchema, {
    method: 'GET',
    signal,
    timeoutMs: 10000,
  });
}

export async function fetchQuerySuggestions(
  activeDocs?: string[],
  sessionIdOrSignal?: string | AbortSignal,
  limit: number = 4,
  signal?: AbortSignal
): Promise<ApiResponse<QuerySuggestion[]>> {
  let effectiveSessionId: string | undefined;
  let effectiveSignal: AbortSignal | undefined;
  if (sessionIdOrSignal instanceof AbortSignal) {
    effectiveSignal = sessionIdOrSignal;
  } else {
    effectiveSessionId = sessionIdOrSignal;
    effectiveSignal = signal;
  }

  const params = new URLSearchParams();
  if (activeDocs && activeDocs.length > 0) {
    const docsParam = activeDocs.join(',');
    params.set('active_docs', docsParam);
    params.set('drawer', docsParam);
  }
  if (effectiveSessionId) {
    params.set('session_id', effectiveSessionId);
  }
  if (limit) {
    params.set('limit', String(limit));
  }
  const qs = params.toString();
  const endpoint = qs ? `${ENDPOINTS.SUGGESTIONS}?${qs}` : ENDPOINTS.SUGGESTIONS;

  return apiClient.request<QuerySuggestion[]>(endpoint, undefined, {
    method: 'GET',
    signal: effectiveSignal,
    timeoutMs: 15000,
  });
}

export async function executeAgentQuery(
  req: AgentQueryRequest,
  signal?: AbortSignal
): Promise<ApiResponse<AgentQueryResponse>> {
  return apiClient.request<AgentQueryResponse>(ENDPOINTS.AGENT_QUERY, AgentQueryResponseSchema, {
    method: 'POST',
    body: JSON.stringify(req),
    signal,
  });
}

export async function executeClearChat(
  threadId?: string,
  signal?: AbortSignal
): Promise<ApiResponse<{ status: string; message?: string }>> {
  return apiClient.request<{ status: string; message?: string }>(
    ENDPOINTS.CLEAR_CHAT,
    undefined,
    {
      method: 'POST',
      body: JSON.stringify(threadId ? { session_id: threadId, thread_id: threadId } : {}),
      signal,
    }
  );
}

export async function executeAbortChat(
  params: AbortChatParams | string,
  requestId?: string
): Promise<ApiResponse<{ status: string; request_id?: string; message?: string }>> {
  const payload =
    typeof params === 'string'
      ? { chat_id: params, session_id: params, request_id: requestId || '' }
      : {
          request_id: params.request_id,
          session_id: params.session_id || params.chat_id,
          chat_id: params.chat_id || params.session_id,
        };

  return apiClient.request<{ status: string; request_id?: string; message?: string }>(
    ENDPOINTS.CHAT_ABORT,
    undefined,
    {
      method: 'POST',
      body: JSON.stringify(payload),
      timeoutMs: 10000,
    }
  );
}
