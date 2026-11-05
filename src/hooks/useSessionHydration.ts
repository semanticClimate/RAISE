import { useCallback, useEffect, useState } from 'react';
import { chatService } from '../services/ChatService';
import type { ChatMessage, ChatSession, SourceDocument } from '../types';

export interface UseSessionHydrationOptions {
  isTunnelConfigured: boolean;
  isOnline: boolean;
  currentSessionId: string | null;
  onSessionsSynced?: (sessions: ChatSession[]) => void;
  onMessagesSynced?: (messages: ChatMessage[]) => void;
}

export interface UseSessionHydrationResult {
  isHydrating: boolean;
  hydrateSessions: () => Promise<void>;
  hydrateCurrentMessages: (sessionId: string) => Promise<void>;
}

function getStoredUsername(): string | undefined {
  try {
    return localStorage.getItem('raise_username') || undefined;
  } catch {
    return undefined;
  }
}

/**
 * useSessionHydration:
 * Stale-While-Revalidate session management hook that decouples remote session
 * and chat history reconciliation from root layout re-renders.
 */
export function useSessionHydration({
  isTunnelConfigured,
  isOnline,
  currentSessionId,
  onSessionsSynced,
  onMessagesSynced,
}: UseSessionHydrationOptions): UseSessionHydrationResult {
  const [isHydrating, setIsHydrating] = useState(false);

  const hydrateCurrentMessages = useCallback(
    async (sessionId: string) => {
      if (!sessionId || !isOnline) return;
      try {
        const historyRes = await chatService.getChatHistory?.(sessionId);
        if (
          !historyRes?.data?.messages ||
          !Array.isArray(historyRes.data.messages) ||
          historyRes.status === 503 ||
          historyRes.error?.status === 503
        ) {
          return;
        }

        const remoteMsgs: ChatMessage[] = (historyRes.data.messages as any[]).map(
          (m: any) => ({
            ...m,
            text: m?.text || m?.content || '',
            content: m?.content || m?.text || '',
            durationSec:
              m.durationSec ?? m.response?.latency_sec ?? m.response?.execution_time,
          })
        );

        if (remoteMsgs.length > 0) {
          onMessagesSynced?.(remoteMsgs);
        }
      } catch (err) {
        console.warn(`Could not hydrate chat history for session ${sessionId}:`, err);
      }
    },
    [isOnline, onMessagesSynced]
  );

  const hydrateSessions = useCallback(async () => {
    if (!isTunnelConfigured || !isOnline) return;
    setIsHydrating(true);
    try {
      const username = getStoredUsername();
      const sessionsRes = await chatService.listChatSessions?.(username);

      if (
        sessionsRes?.status === 503 ||
        sessionsRes?.error?.status === 503 ||
        !sessionsRes?.data ||
        !Array.isArray(sessionsRes.data)
      ) {
        return;
      }

      const fetchedSessions: ChatSession[] = sessionsRes.data.map((item: any) => {
        const attachedDocList: string[] = Array.isArray(item.attached_docs)
          ? item.attached_docs
          : [];
        let resolvedSources = Array.isArray(item.sources) ? item.sources : [];

        if (attachedDocList.length > 0 && resolvedSources.length === 0) {
          resolvedSources = attachedDocList.map((docName: string, idx: number) => ({
            id: `attached-${idx}-${docName}`,
            name: docName,
            size: '12 MB',
            pages: 20,
            selected: true,
            color: 'indigo' as const,
            status: 'ready' as const,
          }));
        }

        return {
          id: item.thread_id || item.session_id || item.id,
          thread_id: item.thread_id || item.session_id || item.id,
          session_id: item.thread_id || item.session_id || item.id,
          title: item.title || 'Chat Session',
          timestamp: item.timestamp || item.updated_at || item.created_at || 'Just now',
          messages: Array.isArray(item.messages)
            ? item.messages.map((m: any) => ({
                ...m,
                text: m?.text || m?.content || '',
                content: m?.content || m?.text || '',
              }))
            : [],
          selectedSourceIds:
            item.selectedSourceIds ||
            resolvedSources.filter((s: SourceDocument) => s.selected).map((s: SourceDocument) => s.id),
          sources: resolvedSources,
          attached_docs: attachedDocList,
          is_saved: Boolean(item.is_saved),
          created_at: item.created_at,
          updated_at: item.updated_at,
        };
      });

      onSessionsSynced?.(fetchedSessions);

      if (currentSessionId) {
        await hydrateCurrentMessages(currentSessionId);
      }
    } catch (err) {
      console.warn('Could not sync chat sessions from backend:', err);
    } finally {
      setIsHydrating(false);
    }
  }, [isTunnelConfigured, isOnline, currentSessionId, hydrateCurrentMessages, onSessionsSynced]);

  useEffect(() => {
    hydrateSessions();
  }, [hydrateSessions]);

  return {
    isHydrating,
    hydrateSessions,
    hydrateCurrentMessages,
  };
}
