import { type ApiResponse } from '../api/client';
import {
  type AgentQueryRequest,
  type AgentQueryResponse,
  type ChatHistoryResponse,
  type FeedbackStats,
  type PersistedChatSession,
  type SessionDrawerAttachResponse,
  type SessionDrawerRemoveResponse,
  type SessionDrawerResponse,
  type SubgraphQueryRequest,
  type SubgraphQueryResponse,
} from '../types';
import {
  attachSessionDrawerDoc,
  deleteSessionFromServer,
  fetchChatHistory,
  fetchChatSessions,
  fetchSessionDrawer,
  removeSessionDrawerDoc,
  renameSessionOnServer,
  saveChatSession,
  saveThreadBookmark,
  updateSessionDrawerDocs,
} from './chat/chatSessionApi';
import {
  type AbortChatParams,
  type FeedbackPayload,
  type QuerySuggestion,
  executeAbortChat,
  executeAgentQuery,
  executeClearChat,
  fetchFeedbackStats,
  fetchQuerySuggestions,
  submitChatFeedback,
} from './chat/chatFeedbackApi';
import { executeSubgraphQuery } from './chat/chatSubgraphQuery';

export type { AbortChatParams, FeedbackPayload, QuerySuggestion };

export interface ChatServiceInterface {
  submitFeedback?(
    payload: FeedbackPayload,
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; message?: string }>>;
  getFeedbackStats?(signal?: AbortSignal): Promise<ApiResponse<FeedbackStats>>;
  getSuggestions?(
    activeDocs?: string[],
    signal?: AbortSignal
  ): Promise<ApiResponse<QuerySuggestion[]>>;
  querySubgraph(
    req: SubgraphQueryRequest,
    signal?: AbortSignal,
    onStreamChunk?: (chunk: string, accumulated: string) => void,
    onStageUpdate?: (stage: Record<string, unknown>) => void
  ): Promise<ApiResponse<SubgraphQueryResponse>>;
  queryAgent(
    req: AgentQueryRequest,
    signal?: AbortSignal
  ): Promise<ApiResponse<AgentQueryResponse>>;
  clearChat?(threadId?: string, signal?: AbortSignal): Promise<ApiResponse<{ status: string }>>;
  abortChat?(
    params: AbortChatParams | string,
    requestId?: string
  ): Promise<ApiResponse<{ status: string; request_id?: string; message?: string }>>;
  getChatHistory?(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<ChatHistoryResponse>>;
  listChatSessions?(
    username?: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<PersistedChatSession[]>>;
  persistChatSession?(
    session: PersistedChatSession,
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; thread_id: string }>>;
  renameChatSession?(
    sessionId: string,
    newTitle: string,
    username?: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; title?: string }>>;
  deleteChatSession?(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; session_id?: string }>>;
  saveThread?(
    sessionId: string,
    isSaved?: boolean,
    username?: string,
    title?: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; session_id: string; is_saved: boolean }>>;
  getSessionDrawer?(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<SessionDrawerResponse>>;
  attachToSessionDrawer?(
    sessionId: string,
    documentIdOrFilename: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<SessionDrawerAttachResponse>>;
  removeFromSessionDrawer?(
    sessionId: string,
    documentIdOrFilename: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<SessionDrawerRemoveResponse>>;
  updateSessionDrawer?(
    sessionId: string,
    activeDocs: string[],
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; attached_docs?: string[] }>>;
}

export class ChatService implements ChatServiceInterface {
  /**
   * Primary Chat flow:
   * First tries standard POST /api/chat with streaming support.
   * Immediately aborts or returns on fatal HTTP status codes (401, 402, 403, 429, 500, 502, 503, 504).
   * Only falls back to standard JSON /api/chat or SUBGRAPH_QUERY on 404/405.
   */
  public async querySubgraph(
    req: SubgraphQueryRequest,
    signal?: AbortSignal,
    onStreamChunk?: (chunk: string, accumulated: string) => void,
    onStageUpdate?: (stage: Record<string, unknown>) => void
  ): Promise<ApiResponse<SubgraphQueryResponse>> {
    return executeSubgraphQuery(
      req,
      signal,
      onStreamChunk,
      onStageUpdate,
      () => {
        if (req.thread_id) {
          this.abortChat({
            session_id: req.thread_id,
            request_id: req.request_id,
          }).catch(() => {});
        }
      }
    );
  }

  public async queryAgent(
    req: AgentQueryRequest,
    signal?: AbortSignal
  ): Promise<ApiResponse<AgentQueryResponse>> {
    return executeAgentQuery(req, signal);
  }

  public async clearChat(
    threadId?: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; message?: string }>> {
    return executeClearChat(threadId, signal);
  }

  public async abortChat(
    params: AbortChatParams | string,
    requestId?: string
  ): Promise<ApiResponse<{ status: string; request_id?: string; message?: string }>> {
    return executeAbortChat(params, requestId);
  }

  public async getChatHistory(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<ChatHistoryResponse>> {
    return fetchChatHistory(sessionId, signal);
  }

  public async listChatSessions(
    username?: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<PersistedChatSession[]>> {
    return fetchChatSessions(username, signal);
  }

  public async persistChatSession(
    session: PersistedChatSession,
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; thread_id: string }>> {
    return saveChatSession(session, signal);
  }

  public async renameChatSession(
    sessionId: string,
    newTitle: string,
    username: string = '',
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; title?: string }>> {
    return renameSessionOnServer(sessionId, newTitle, username, signal);
  }

  public async saveThread(
    sessionId: string,
    isSaved: boolean = true,
    username: string = '',
    title?: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; session_id: string; is_saved: boolean }>> {
    return saveThreadBookmark(sessionId, isSaved, username, title, signal);
  }

  public async deleteChatSession(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; session_id?: string }>> {
    return deleteSessionFromServer(sessionId, signal);
  }

  public async getSessionDrawer(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<SessionDrawerResponse>> {
    return fetchSessionDrawer(sessionId, signal);
  }

  public async attachToSessionDrawer(
    sessionId: string,
    documentIdOrFilename: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<SessionDrawerAttachResponse>> {
    return attachSessionDrawerDoc(sessionId, documentIdOrFilename, signal);
  }

  public async removeFromSessionDrawer(
    sessionId: string,
    documentIdOrFilename: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<SessionDrawerRemoveResponse>> {
    return removeSessionDrawerDoc(sessionId, documentIdOrFilename, signal);
  }

  public async updateSessionDrawer(
    sessionId: string,
    activeDocs: string[],
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; attached_docs?: string[] }>> {
    return updateSessionDrawerDocs(sessionId, activeDocs, signal);
  }

  public async getSuggestions(
    activeDocs?: string[],
    sessionIdOrSignal?: string | AbortSignal,
    limit: number = 4,
    signal?: AbortSignal
  ): Promise<ApiResponse<QuerySuggestion[]>> {
    return fetchQuerySuggestions(activeDocs, sessionIdOrSignal, limit, signal);
  }

  public async submitFeedback(
    payload: FeedbackPayload,
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; message?: string }>> {
    return submitChatFeedback(payload, signal);
  }

  public async getFeedbackStats(signal?: AbortSignal): Promise<ApiResponse<FeedbackStats>> {
    return fetchFeedbackStats(signal);
  }
}

export const chatService = new ChatService();
