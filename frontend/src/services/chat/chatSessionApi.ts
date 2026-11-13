import { z } from 'zod';
import { type ApiResponse, apiClient } from '../../api/client';
import { ENDPOINTS } from '../../api/endpoints';
import {
  type ChatHistoryResponse,
  ChatHistoryResponseSchema,
  type PersistedChatSession,
  PersistedChatSessionSchema,
  type SessionDrawerAttachResponse,
  SessionDrawerAttachResponseSchema,
  type SessionDrawerRemoveResponse,
  SessionDrawerRemoveResponseSchema,
  type SessionDrawerResponse,
  SessionDrawerResponseSchema,
} from '../../types';

export async function fetchChatHistory(
  sessionId: string,
  signal?: AbortSignal
): Promise<ApiResponse<ChatHistoryResponse>> {
  const res = await apiClient.request<ChatHistoryResponse>(
    ENDPOINTS.CHAT_HISTORY_BY_SESSION(sessionId),
    undefined,
    {
      method: 'GET',
      signal,
      timeoutMs: 15000,
    }
  );
  if (res.data) {
    const parsed = ChatHistoryResponseSchema.safeParse(res.data);
    const dataToNormalize = parsed.success ? parsed.data : res.data;
    if (Array.isArray(dataToNormalize.messages)) {
      dataToNormalize.messages = dataToNormalize.messages.map((m: any) => ({
        ...m,
        text: m?.text || m?.content || '',
        content: m?.content || m?.text || '',
      }));
    }
    return { ...res, data: dataToNormalize };
  }
  return res;
}

export async function fetchChatSessions(
  username?: string,
  signal?: AbortSignal
): Promise<ApiResponse<PersistedChatSession[]>> {
  const endpoint = username ? ENDPOINTS.CHAT_SESSIONS_BY_USER(username) : ENDPOINTS.CHAT_SESSIONS;
  const res = await apiClient.request<PersistedChatSession[]>(endpoint, undefined, {
    method: 'GET',
    signal,
    timeoutMs: 15000,
  });
  if (res.data) {
    const parsed = z.array(PersistedChatSessionSchema).safeParse(res.data);
    const rawList = parsed.success ? parsed.data : res.data;
    const normalizedList = rawList.map((session: any) => {
      if (Array.isArray(session.messages)) {
        return {
          ...session,
          messages: session.messages.map((m: any) => ({
            ...m,
            text: m?.text || m?.content || '',
            content: m?.content || m?.text || '',
          })),
        };
      }
      return session;
    });
    return { ...res, data: normalizedList };
  }
  return res;
}

export async function saveChatSession(
  session: PersistedChatSession,
  signal?: AbortSignal
): Promise<ApiResponse<{ status: string; thread_id: string }>> {
  const res = await apiClient.request<{ status: string; thread_id: string }>(
    ENDPOINTS.CHAT_HISTORY,
    undefined,
    {
      method: 'POST',
      body: JSON.stringify(session),
      signal,
      timeoutMs: 15000,
    }
  );
  if (res.data) {
    const schema = z.object({
      status: z.string().default('success'),
      thread_id: z.string().default(session.thread_id),
    });
    const parsed = schema.safeParse(res.data);
    if (parsed.success) {
      return { ...res, data: parsed.data };
    }
  }
  return res;
}

export async function renameSessionOnServer(
  sessionId: string,
  newTitle: string,
  username: string = '',
  signal?: AbortSignal
): Promise<ApiResponse<{ status: string; title?: string }>> {
  const trimmedTitle = newTitle.trim();
  const res = await apiClient.request<{ status: string; title?: string }>(
    ENDPOINTS.RENAME_CHAT_SESSION(sessionId),
    undefined,
    {
      method: 'POST',
      body: JSON.stringify({ title: trimmedTitle }),
      signal,
      timeoutMs: 15000,
    }
  );

  if (res.status === 200) {
    return res;
  }

  return apiClient.request<{ status: string; title?: string }>(
    ENDPOINTS.CHAT_HISTORY,
    undefined,
    {
      method: 'POST',
      body: JSON.stringify({
        thread_id: sessionId,
        session_id: sessionId,
        username,
        title: trimmedTitle,
        updated_at: new Date().toISOString(),
      }),
      signal,
      timeoutMs: 15000,
    }
  );
}

export async function saveThreadBookmark(
  sessionId: string,
  isSaved: boolean = true,
  username: string = '',
  title?: string,
  signal?: AbortSignal
): Promise<ApiResponse<{ status: string; session_id: string; is_saved: boolean }>> {
  return apiClient.request<{ status: string; session_id: string; is_saved: boolean }>(
    ENDPOINTS.CHAT_HISTORY,
    undefined,
    {
      method: 'POST',
      body: JSON.stringify({
        thread_id: sessionId,
        session_id: sessionId,
        username,
        title,
        is_saved: isSaved,
        updated_at: new Date().toISOString(),
      }),
      signal,
      timeoutMs: 15000,
    }
  );
}

export async function deleteSessionFromServer(
  sessionId: string,
  signal?: AbortSignal
): Promise<ApiResponse<{ status: string; session_id?: string }>> {
  const schema = z.object({
    status: z.string().default('success'),
    session_id: z.string().optional(),
  });
  const res = await apiClient.request<{ status: string; session_id?: string }>(
    ENDPOINTS.DELETE_CHAT_SESSION(sessionId),
    undefined,
    {
      method: 'DELETE',
      signal,
      timeoutMs: 15000,
    }
  );
  if (res.status === 404 || res.status === 405) {
    const fallbackRes = await apiClient.request<{ status: string; session_id?: string }>(
      ENDPOINTS.CHAT_SESSION_BY_ID(sessionId),
      undefined,
      {
        method: 'DELETE',
        signal,
        timeoutMs: 15000,
      }
    );
    if (fallbackRes.data) {
      const parsed = schema.safeParse(fallbackRes.data);
      if (parsed.success) {
        return { ...fallbackRes, data: parsed.data };
      }
    }
    return fallbackRes;
  }
  if (res.data) {
    const parsed = schema.safeParse(res.data);
    if (parsed.success) {
      return { ...res, data: parsed.data };
    }
  }
  return res;
}

export async function fetchSessionDrawer(
  sessionId: string,
  signal?: AbortSignal
): Promise<ApiResponse<SessionDrawerResponse>> {
  return apiClient.request<SessionDrawerResponse>(
    ENDPOINTS.SESSION_DRAWER(sessionId),
    SessionDrawerResponseSchema,
    {
      method: 'GET',
      signal,
      timeoutMs: 15000,
    }
  );
}

export async function attachSessionDrawerDoc(
  sessionId: string,
  documentIdOrFilename: string,
  signal?: AbortSignal
): Promise<ApiResponse<SessionDrawerAttachResponse>> {
  return apiClient.request<SessionDrawerAttachResponse>(
    ENDPOINTS.SESSION_DRAWER_ATTACH(sessionId),
    SessionDrawerAttachResponseSchema,
    {
      method: 'POST',
      body: JSON.stringify({
        filename: documentIdOrFilename,
        document_id: documentIdOrFilename,
        document: documentIdOrFilename,
      }),
      signal,
      timeoutMs: 15000,
    }
  );
}

export async function removeSessionDrawerDoc(
  sessionId: string,
  documentIdOrFilename: string,
  signal?: AbortSignal
): Promise<ApiResponse<SessionDrawerRemoveResponse>> {
  return apiClient.request<SessionDrawerRemoveResponse>(
    ENDPOINTS.SESSION_DRAWER_REMOVE(sessionId),
    SessionDrawerRemoveResponseSchema,
    {
      method: 'POST',
      body: JSON.stringify({
        filename: documentIdOrFilename,
        document_id: documentIdOrFilename,
        document: documentIdOrFilename,
      }),
      signal,
      timeoutMs: 15000,
    }
  );
}

export async function updateSessionDrawerDocs(
  sessionId: string,
  activeDocs: string[],
  signal?: AbortSignal
): Promise<ApiResponse<{ status: string; attached_docs?: string[] }>> {
  return apiClient.request<{ status: string; attached_docs?: string[] }>(
    ENDPOINTS.SESSION_DRAWER(sessionId),
    undefined,
    {
      method: 'PATCH',
      body: JSON.stringify({ active_docs: activeDocs }),
      signal,
      timeoutMs: 10000,
    }
  );
}
