import { z } from 'zod';
import { type ApiResponse, apiClient, sanitizeStreamText } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import {
  type AgentQueryRequest,
  type AgentQueryResponse,
  AgentQueryResponseSchema,
  type ChatHistoryResponse,
  ChatHistoryResponseSchema,
  type Citation,
  type FeedbackStats,
  FeedbackStatsSchema,
  type PersistedChatSession,
  PersistedChatSessionSchema,
  type SessionDrawerAttachResponse,
  SessionDrawerAttachResponseSchema,
  type SessionDrawerRemoveResponse,
  SessionDrawerRemoveResponseSchema,
  type SessionDrawerResponse,
  SessionDrawerResponseSchema,
  type SubgraphQueryRequest,
  type SubgraphQueryResponse,
  SubgraphQueryResponseSchema,
  type TopChunk,
  type VerifiedClaim,
} from '../types';
import { normalizeCitation } from '../utils/citationParser';

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
  clearChat?(threadId?: string, signal?: AbortSignal, confirm?: boolean): Promise<ApiResponse<{ status: string; message?: string }>>;
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
   * If /api/chat returns 404 or backend is specialized RAISE LangGraph,
   * cleanly falls back to POST /api/graphrag/subgraph-query.
   */
  public async querySubgraph(
    req: SubgraphQueryRequest,
    signal?: AbortSignal,
    onStreamChunk?: (chunk: string, accumulated: string) => void,
    onStageUpdate?: (stage: Record<string, unknown>) => void
  ): Promise<ApiResponse<SubgraphQueryResponse>> {
    const effectiveMode = req.mode || (req.hops && req.hops > 1 ? 'expert' : 'fast');
    const startTime = Date.now();

    // 1. If streaming callback is provided, attempt streaming via POST /api/chat
    if (onStreamChunk) {
      const streamRes = await apiClient.requestStream(
        ENDPOINTS.CHAT,
        {
          method: 'POST',
          body: JSON.stringify({
            message: req.query,
            query: req.query,
            mode: effectiveMode,
            stream: true,
            chat_history: req.chat_history,
            session_id: req.thread_id,
            thread_id: req.thread_id,
            request_id: req.request_id,
            active_docs:
              req.active_docs && req.active_docs.length > 0 ? req.active_docs : undefined,
            format: 'sse',
            document_filter: req.document_filter,
            hops: req.hops ?? (effectiveMode === 'expert' ? 3 : 1),
            top_k: req.top_k ?? (effectiveMode === 'expert' ? 8 : 4),
          }),
          signal,
          timeoutMs: 90000,
          onStageUpdate,
        },
        onStreamChunk
      );

      const resolvedStreamText =
        streamRes.text ||
        (typeof streamRes.metadata?.grounded_answer === 'string'
          ? (streamRes.metadata.grounded_answer as string)
          : '') ||
        (typeof streamRes.metadata?.answer === 'string'
          ? (streamRes.metadata.answer as string)
          : '') ||
        (typeof streamRes.metadata?.reply === 'string'
          ? (streamRes.metadata.reply as string)
          : '') ||
        (typeof (streamRes.metadata as any)?.response === 'string'
          ? ((streamRes.metadata as any).response as string)
          : '');

      // If streaming was explicitly cancelled or errored out, do NOT make a duplicate non-streaming request
      if (streamRes.error) {
        return {
          data: null,
          error: streamRes.error,
          isMock: false,
          status: streamRes.status || 0,
        };
      }

      // If streaming /api/chat succeeded (status 200) and we have text or terminal completion payload
      if (
        streamRes.status === 200 &&
        (resolvedStreamText ||
          streamRes.metadata?.status === 'SUCCESS' ||
          streamRes.metadata?.status === 'completed')
      ) {
        const durationSec = Number(((Date.now() - startTime) / 1000).toFixed(2));
        const meta = streamRes.metadata || {};
        let citations: Citation[] = Array.isArray(meta.citations)
          ? meta.citations.map((c: unknown, idx: number) =>
              normalizeCitation(c, idx + 1, req.active_docs?.[0])
            )
          : [];

        if (
          citations.length === 0 &&
          Array.isArray(meta.top_chunks) &&
          meta.top_chunks.length > 0
        ) {
          citations = (meta.top_chunks as unknown[]).map((chk: unknown, idx: number) => {
            const chkObj = chk && typeof chk === 'object' ? (chk as Record<string, unknown>) : {};
            const chkMeta =
              chkObj.metadata && typeof chkObj.metadata === 'object'
                ? (chkObj.metadata as Record<string, unknown>)
                : {};
            return normalizeCitation(
              {
                chunk_id: chkObj.chunk_id || chkObj.id,
                pdf_filename:
                  chkObj.pdf_filename ||
                  chkObj.filename ||
                  chkMeta.pdf_filename ||
                  chkMeta.filename,
                primary_page:
                  chkObj.primary_page ?? chkObj.page ?? chkMeta.primary_page ?? chkMeta.page,
                heading: chkObj.heading || chkMeta.heading,
                plain_text: chkObj.plain_text || chkObj.text || chkObj.content,
                similarity: typeof chkObj.similarity === 'number' ? chkObj.similarity : 0.9,
              },
              idx + 1,
              req.active_docs?.[0]
            );
          });
        }
        const subgraph =
          meta.subgraph && typeof meta.subgraph === 'object'
            ? (meta.subgraph as SubgraphQueryResponse['subgraph'])
            : { nodes: [], edges: [] };

        const synthesizedResp: SubgraphQueryResponse = {
          query: req.query,
          grounded_answer: resolvedStreamText,
          latency_sec: durationSec,
          execution_time: durationSec,
          traceability_score:
            typeof meta.traceability_score === 'number' ? meta.traceability_score : 0.95,
          subgraph,
          citations,
          verified_claims: (Array.isArray(meta.verified_claims)
            ? meta.verified_claims
            : []) as VerifiedClaim[],
          quality_gate_decision: (meta.quality_gate_decision as SubgraphQueryResponse['quality_gate_decision']) || 'accept',
          selected_tools: (Array.isArray(meta.selected_tools)
            ? meta.selected_tools
            : []) as string[],
          cypher_repair_count: typeof meta.cypher_repair_count === 'number' ? meta.cypher_repair_count : 0,
          path_critic_expanded: Boolean(meta.path_critic_expanded),
          top_chunks: (Array.isArray(meta.top_chunks) ? meta.top_chunks : []) as TopChunk[],
          retry_count: typeof meta.retry_count === 'number' ? meta.retry_count : 0,
          decomposed_queries: (Array.isArray(meta.decomposed_queries)
            ? meta.decomposed_queries
            : []) as string[],
          follow_up_inquiries: Array.isArray(meta.follow_up_inquiries)
            ? (meta.follow_up_inquiries as string[])
            : Array.isArray(meta.suggestions)
              ? (meta.suggestions as string[])
              : [],
          suggestions: Array.isArray(meta.suggestions)
            ? (meta.suggestions as string[])
            : Array.isArray(meta.follow_up_inquiries)
              ? (meta.follow_up_inquiries as string[])
              : [],
          persisted: typeof meta.persisted === 'boolean' ? meta.persisted : undefined,
          saved: typeof meta.saved === 'boolean' ? meta.saved : undefined,
          persistence_status: typeof meta.persistence_status === 'string' ? meta.persistence_status : undefined,
          persistence_error: typeof meta.persistence_error === 'string' ? meta.persistence_error : null,
        };
        const parsed = SubgraphQueryResponseSchema.safeParse(synthesizedResp);
        return {
          data: parsed.success ? parsed.data : synthesizedResp,
          error: null,
          isMock: false,
          status: 200,
        };
      }

      // If /api/chat stream failed, continue and fall back to standard JSON request and SUBGRAPH_QUERY
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
      active_docs:
        req.active_docs && req.active_docs.length > 0 ? req.active_docs : undefined,
      format: 'raw',
      document_filter: req.document_filter,
      hops: req.hops ?? (effectiveMode === 'expert' ? 3 : 1),
      top_k: req.top_k ?? (effectiveMode === 'expert' ? 8 : 4),
      parser: 'docling',
      full_potential: effectiveMode === 'expert',
      request_id: req.request_id,
    };

    const chatRes = await apiClient.request<Record<string, unknown>>(ENDPOINTS.CHAT, undefined, {
      method: 'POST',
      body: JSON.stringify(chatPayload),
      signal,
      timeoutMs: 90000,
    });

    // If /api/chat was found and succeeded
    if (chatRes.status === 200 && chatRes.data) {
      const data = chatRes.data;
      const answerText =
        (typeof data.reply === 'string' ? data.reply : undefined) ||
        (typeof data.response === 'string' ? data.response : undefined) ||
        (typeof data.answer === 'string' ? data.answer : undefined) ||
        (typeof data.message === 'string' ? data.message : undefined) ||
        (typeof data.output === 'string' ? data.output : undefined) ||
        (typeof data.grounded_answer === 'string' ? data.grounded_answer : undefined) ||
        JSON.stringify(data);

      const actualDurationSec = Number(((Date.now() - startTime) / 1000).toFixed(2));
      const isRefusal =
        answerText.includes('INSUFFICIENT_EVIDENCE') ||
        answerText.toLowerCase().includes('do not contain sufficient evidence') ||
        answerText.toLowerCase().includes('unable to verify');
      const normalizedDecision: SubgraphQueryResponse['quality_gate_decision'] =
        data.quality_gate_decision && data.quality_gate_decision !== 'accept'
          ? (data.quality_gate_decision as SubgraphQueryResponse['quality_gate_decision'])
          : isRefusal
            ? 'unable_to_verify'
            : ((data.quality_gate_decision as SubgraphQueryResponse['quality_gate_decision']) || 'accept');

      const synthesizedResp: SubgraphQueryResponse = {
        query: req.query,
        grounded_answer: sanitizeStreamText(answerText),
        latency_sec:
          typeof data.latency_sec === 'number' && data.latency_sec > 0
            ? data.latency_sec
            : actualDurationSec,
        execution_time:
          typeof data.execution_time === 'number' && data.execution_time > 0
            ? data.execution_time
            : actualDurationSec,
        traceability_score:
          typeof data.traceability_score === 'number' ? data.traceability_score : 0.95,
        subgraph:
          data.subgraph && typeof data.subgraph === 'object'
            ? (data.subgraph as SubgraphQueryResponse['subgraph'])
            : { nodes: [], edges: [] },
        citations: (() => {
          let cits: Citation[] = Array.isArray(data.citations)
            ? data.citations.map((c: unknown, idx: number) =>
                normalizeCitation(c, idx + 1, req.active_docs?.[0])
              )
            : [];
          if (cits.length === 0 && Array.isArray(data.top_chunks) && data.top_chunks.length > 0) {
            cits = (data.top_chunks as unknown[]).map((chk: unknown, idx: number) => {
              const chkObj = chk && typeof chk === 'object' ? (chk as Record<string, unknown>) : {};
              const chkMeta =
                chkObj.metadata && typeof chkObj.metadata === 'object'
                  ? (chkObj.metadata as Record<string, unknown>)
                  : {};
              return normalizeCitation(
                {
                  chunk_id: chkObj.chunk_id || chkObj.id,
                  pdf_filename:
                    chkObj.pdf_filename ||
                    chkObj.filename ||
                    chkMeta.pdf_filename ||
                    chkMeta.filename,
                  primary_page:
                    chkObj.primary_page ??
                    chkObj.page ??
                    chkMeta.primary_page ??
                    chkMeta.page,
                  heading: chkObj.heading || chkMeta.heading,
                  plain_text: chkObj.plain_text || chkObj.text || chkObj.content,
                  similarity: typeof chkObj.similarity === 'number' ? chkObj.similarity : 0.9,
                },
                idx + 1,
                req.active_docs?.[0]
              );
            });
          }
          return cits;
        })(),
        verified_claims: (Array.isArray(data.verified_claims) ? data.verified_claims : []) as VerifiedClaim[],
        quality_gate_decision: normalizedDecision,
        selected_tools: Array.isArray(data.selected_tools) ? (data.selected_tools as string[]) : [],
        cypher_repair_count: typeof data.cypher_repair_count === 'number' ? data.cypher_repair_count : 0,
        path_critic_expanded: Boolean(data.path_critic_expanded),
        top_chunks: (Array.isArray(data.top_chunks) ? data.top_chunks : []) as TopChunk[],
        retry_count: typeof data.retry_count === 'number' ? data.retry_count : 0,
        decomposed_queries: Array.isArray(data.decomposed_queries) ? (data.decomposed_queries as string[]) : [],
        follow_up_inquiries: Array.isArray(data.follow_up_inquiries)
          ? (data.follow_up_inquiries as string[])
          : Array.isArray(data.suggestions)
            ? (data.suggestions as string[])
            : [],
        suggestions: Array.isArray(data.suggestions)
          ? (data.suggestions as string[])
          : Array.isArray(data.follow_up_inquiries)
            ? (data.follow_up_inquiries as string[])
            : [],
        persisted: typeof data.persisted === 'boolean' ? data.persisted : undefined,
        saved: typeof data.saved === 'boolean' ? data.saved : undefined,
        persistence_status: typeof data.persistence_status === 'string' ? data.persistence_status : undefined,
        persistence_error: typeof data.persistence_error === 'string' ? data.persistence_error : null,
      };

      const parsed = SubgraphQueryResponseSchema.safeParse(synthesizedResp);
      return {
        data: parsed.success ? parsed.data : synthesizedResp,
        error: null,
        isMock: chatRes.isMock,
        status: 200,
      };
    }

    // 3. Fallback to /api/graphrag/subgraph-query if /api/chat is 404, 500, or errored
    const fallbackRes = await apiClient.request<SubgraphQueryResponse>(
      ENDPOINTS.SUBGRAPH_QUERY,
      SubgraphQueryResponseSchema,
      {
        method: 'POST',
        body: JSON.stringify(req),
        signal,
        timeoutMs: 90000,
      }
    );

    if (fallbackRes.status === 200 && fallbackRes.data) {
      const data = fallbackRes.data;
      const isRefusal =
        (data.grounded_answer && data.grounded_answer.includes('INSUFFICIENT_EVIDENCE')) ||
        (data.grounded_answer && data.grounded_answer.toLowerCase().includes('do not contain sufficient evidence'));
      if (isRefusal && data.quality_gate_decision === 'accept') {
        data.quality_gate_decision = 'unable_to_verify';
      }
      return fallbackRes;
    }

    // Return the response error
    return {
      data: null,
      error: fallbackRes.error || chatRes.error,
      isMock: chatRes.isMock,
      status: fallbackRes.status || chatRes.status,
    };
  }

  /**
   * Direct multi-tool AgentRouter query
   */
  public async queryAgent(
    req: AgentQueryRequest,
    signal?: AbortSignal
  ): Promise<ApiResponse<AgentQueryResponse>> {
    return apiClient.request<AgentQueryResponse>(ENDPOINTS.AGENT_QUERY, AgentQueryResponseSchema, {
      method: 'POST',
      body: JSON.stringify(req),
      signal,
    });
  }

  /**
   * Clear Chat History on backend
   */
  public async clearChat(
    threadId?: string,
    signal?: AbortSignal,
    confirm?: boolean
  ): Promise<ApiResponse<{ status: string; message?: string }>> {
    return apiClient.request<{ status: string; message?: string }>(
      ENDPOINTS.CLEAR_CHAT,
      undefined,
      {
        method: 'POST',
        body: JSON.stringify(
          threadId
            ? { session_id: threadId, thread_id: threadId }
            : { confirm: Boolean(confirm) }
        ),
        signal,
      }
    );
  }

  /**
   * Server-Side Inference Cancellation
   * Sends POST /api/chat/abort with { request_id, session_id }
   * Backend prunes Redis job mapping and terminates vLLM GPU inference.
   */
  public async abortChat(
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

  /**
   * Cross-Session Chat History Restoration
   * GET /api/chat/history?session_id={thread_id}
   */
  public async getChatHistory(
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
      if (parsed.success) {
        return { ...res, data: parsed.data };
      }
    }
    return res;
  }

  /**
   * List all saved chat sessions for the current user from PostgreSQL
   * GET /api/chat/sessions?username={username}
   */
  public async listChatSessions(
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
      if (parsed.success) {
        return { ...res, data: parsed.data };
      }
    }
    return res;
  }

  /**
   * Persist full session and messages to PostgreSQL on backend per (session_id, username) key
   * POST /api/chat/history
   */
  public async persistChatSession(
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

  /**
   * Rename a chat session in PostgreSQL backend
   * POST /api/chat/sessions/{id}/rename with fallback to POST /api/chat/history
   */
  public async renameChatSession(
    sessionId: string,
    newTitle: string,
    username: string = '',
    signal?: AbortSignal
  ): Promise<ApiResponse<{ status: string; title?: string }>> {
    const trimmedTitle = newTitle.trim();
    // Try dedicated session rename endpoint
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

    // Fallback to chat history sync if rename endpoint returned 404
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

  /**
   * Save / Bookmark a research thread to PostgreSQL per user
   * POST /api/chat/history with is_saved: true
   */
  public async saveThread(
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

  /**
   * Delete a chat session from PostgreSQL backend
   * DELETE /api/chat/history?session_id={thread_id}
   */
  public async deleteChatSession(
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

  /**
   * Dedicated Drawer GET endpoint:
   * GET /api/chat/sessions/{session_id}/drawer
   * Returns authoritative attached documents & enriched metadata for a given chat session.
   */
  public async getSessionDrawer(
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

  /**
   * Dedicated Drawer Attach endpoint:
   * POST /api/chat/sessions/{session_id}/drawer/attach
   * Idempotently attaches a Library document to the current session's Drawer.
   */
  public async attachToSessionDrawer(
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

  /**
   * Dedicated Drawer Remove endpoint:
   * POST /api/chat/sessions/{session_id}/drawer/remove
   * Removes a document from the current session's Drawer without deleting it from the Library.
   */
  public async removeFromSessionDrawer(
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

  /**
   * Persist active drawer documents to PostgreSQL session_metadata:
   * PATCH /api/chat/sessions/{session_id}/drawer
   * Payload: { active_docs: string[] }
   */
  public async updateSessionDrawer(
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

  /**
   * Dynamic graph-grounded question suggestions from uploaded documents
   * GET /api/suggestions?active_docs={docNames}&drawer={docNames}
   * Rule: If 0 documents are in the drawer, backend returns []
   */
  public async getSuggestions(
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

  /**
   * Submit user satisfaction feedback (thumbs_up / thumbs_down) to backend PostgreSQL
   * POST /api/feedback
   */
  public async submitFeedback(
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

  /**
   * User Satisfaction Feedback Analytics Telemetry
   * GET /api/feedback/stats
   */
  public async getFeedbackStats(signal?: AbortSignal): Promise<ApiResponse<FeedbackStats>> {
    return apiClient.request<FeedbackStats>(ENDPOINTS.FEEDBACK_STATS, FeedbackStatsSchema, {
      method: 'GET',
      signal,
      timeoutMs: 10000,
    });
  }
}

export const chatService = new ChatService();
