import { useCallback, useRef, useState } from 'react';
import { getStoredUsername } from '../../../app/config';
import { chatService } from '../../../services/ChatService';
import type { PersistedChatSession } from '../../../types';
import { formatSessionDate, generateUUID, truncateSessionTitle } from '../../../utils/uuid';
import { DEMO_SHOWCASE_SESSION, DEMO_SHOWCASE_SESSION_ID } from '../showcaseSession';
import type { ChatMessage, ChatSession, SourceDocument } from '../types';
import { deduplicateTurns, harvestSourcesFromMessagesAndDocs } from '../utils/messageNormalizer';
import {
  CURRENT_SESSION_KEY,
  DEMO_DELETED_KEY,
  getInitialConversation,
  getInitialSessionId,
  loadSessionsLocally,
  saveSessionsLocally,
} from '../utils/sessionStorageUtils';

export interface UseChatSessionsOptions {
  abortActiveStream: () => void;
  stopSpeaking: () => void;
  setQuery: (q: string) => void;
  sourceDocs: SourceDocument[];
  setSourceDocs: React.Dispatch<React.SetStateAction<SourceDocument[]>>;
  apiReadyDocs: any[];
  setIsPipelineDrawerOpen: (open: boolean) => void;
  setIsAutoScrollLocked: (locked: boolean) => void;
  setShowScrollToBottom: (show: boolean) => void;
  setEditingMessageIndex: (idx: number | null) => void;
  setRegeneratingIndex: (idx: number | null) => void;
  setCopiedKey: (k: string | null) => void;
  setExpandedQVersionsIndex: (idx: number | null) => void;
  setExpandedRespVersionsIndex: (idx: number | null) => void;
}

export function useChatSessions({
  abortActiveStream,
  stopSpeaking,
  setQuery,
  sourceDocs,
  setSourceDocs,
  apiReadyDocs,
  setIsPipelineDrawerOpen,
  setIsAutoScrollLocked,
  setShowScrollToBottom,
  setEditingMessageIndex,
  setRegeneratingIndex,
  setCopiedKey,
  setExpandedQVersionsIndex,
  setExpandedRespVersionsIndex,
}: UseChatSessionsOptions) {
  const [sessions, setSessions] = useState<ChatSession[]>(loadSessionsLocally);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(getInitialSessionId);
  const [conversation, setConversation] = useState<ChatMessage[]>(getInitialConversation);

  const [forkNotification, setForkNotification] = useState<{
    parentTitle: string;
    parentSessionId: string;
    forkedTurnIndex: number;
    forkedSessionId: string;
  } | null>(null);

  const [originalNotification, setOriginalNotification] = useState<{
    branchTitle: string;
    branchSessionId: string;
  } | null>(null);

  const currentSessionIdRef = useRef<string | null>(currentSessionId);
  currentSessionIdRef.current = currentSessionId;

  // Sync session in memory and update local storage
  const updateSessionInMemory = useCallback(
    (messages: ChatMessage[], effectiveSessionId: string) => {
      const activeSourceIds = sourceDocs.filter((d) => d.selected).map((d) => d.id);
      const activeSourceNames = sourceDocs.filter((d) => d.selected).map((d) => d.name);
      setSessions((prev) => {
        const idx = prev.findIndex((s) => s.id === effectiveSessionId);
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = {
            ...updated[idx],
            messages,
            selectedSourceIds: activeSourceIds,
            sources: sourceDocs,
            attached_docs: activeSourceNames,
            updated_at: new Date().toISOString(),
          };
          saveSessionsLocally(updated);
          return updated;
        }

        const firstUser = messages.find((m) => m.role === 'user');
        const rawTitle = firstUser?.text || (firstUser as any)?.content || 'Research Inquiry';
        const newSession: ChatSession = {
          id: effectiveSessionId,
          thread_id: effectiveSessionId,
          session_id: effectiveSessionId,
          username: getStoredUsername(),
          title: truncateSessionTitle(rawTitle),
          timestamp: formatSessionDate(new Date()),
          messages,
          selectedSourceIds: activeSourceIds,
          sources: sourceDocs,
          attached_docs: activeSourceNames,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        const updated = [newSession, ...prev];
        saveSessionsLocally(updated);
        return updated;
      });
    },
    [sourceDocs]
  );

  const handleSelectSession = useCallback(
    (session: ChatSession) => {
      // 1. Abort any ongoing stream to prevent bleed across sessions
      abortActiveStream();
      stopSpeaking();

      setEditingMessageIndex(null);
      setRegeneratingIndex(null);
      setCopiedKey(null);
      setExpandedQVersionsIndex(null);
      setExpandedRespVersionsIndex(null);
      setForkNotification(null);
      setOriginalNotification(null);
      setIsAutoScrollLocked(false);
      setShowScrollToBottom(false);

      setCurrentSessionId(session.id);
      currentSessionIdRef.current = session.id;

      try {
        localStorage.setItem(CURRENT_SESSION_KEY, session.id);
        if (typeof window !== 'undefined' && window.history?.replaceState) {
          const url = new URL(window.location.href);
          url.searchParams.set('session', session.id);
          window.history.replaceState({}, document.title, url.toString());
        }
      } catch {}

      // Immediately render cached messages
      const normalizedCached = deduplicateTurns(
        (session.messages || []).map((m: any) => ({
          ...m,
          text: m?.text || m?.content || '',
          content: m?.content || m?.text || '',
        }))
      );
      setConversation(normalizedCached);

      if (session.id === DEMO_SHOWCASE_SESSION_ID) {
        setConversation(DEMO_SHOWCASE_SESSION.messages);
        setSourceDocs([]);
        setIsPipelineDrawerOpen(false);
        return;
      }

      let initialSources = session.sources ?? [];
      if (
        initialSources.length === 0 &&
        ((session.attached_docs && session.attached_docs.length > 0) ||
          (session.messages && session.messages.length > 0))
      ) {
        initialSources = harvestSourcesFromMessagesAndDocs(
          session.messages || [],
          initialSources,
          session.attached_docs || [],
          apiReadyDocs
        );
      }
      setSourceDocs(initialSources);
      setIsPipelineDrawerOpen(false);

      // Asynchronously fetch fresh history from backend with stale-closure safety check
      chatService
        .getChatHistory?.(session.id)
        .then((res) => {
          if (currentSessionIdRef.current !== session.id) return;
          if (res?.data?.messages && Array.isArray(res.data.messages)) {
            const remoteMsgs = deduplicateTurns(
              res.data.messages.map((m: any) => ({
                ...m,
                text: m?.text || m?.content || '',
                content: m?.content || m?.text || '',
              }))
            );
            if (remoteMsgs.length > 0) {
              setConversation(remoteMsgs);
            }
          }
        })
        .catch(() => {});
    },
    [
      abortActiveStream,
      stopSpeaking,
      setEditingMessageIndex,
      setRegeneratingIndex,
      setCopiedKey,
      setExpandedQVersionsIndex,
      setExpandedRespVersionsIndex,
      setIsAutoScrollLocked,
      setShowScrollToBottom,
      apiReadyDocs,
      setSourceDocs,
      setIsPipelineDrawerOpen,
    ]
  );

  const handleNewChat = useCallback(() => {
    abortActiveStream();
    stopSpeaking();

    setConversation([]);
    setCurrentSessionId(null);
    currentSessionIdRef.current = null;
    setQuery('');
    setForkNotification(null);
    setOriginalNotification(null);
    setEditingMessageIndex(null);
    setRegeneratingIndex(null);
    setCopiedKey(null);
    setExpandedQVersionsIndex(null);
    setExpandedRespVersionsIndex(null);
    setIsAutoScrollLocked(false);
    setShowScrollToBottom(false);

    try {
      localStorage.removeItem(CURRENT_SESSION_KEY);
      if (typeof window !== 'undefined' && window.history?.replaceState) {
        const url = new URL(window.location.href);
        url.searchParams.delete('session');
        url.searchParams.delete('session_id');
        window.history.replaceState({}, document.title, url.toString());
      }
    } catch {}
  }, [
    abortActiveStream,
    stopSpeaking,
    setQuery,
    setEditingMessageIndex,
    setRegeneratingIndex,
    setCopiedKey,
    setExpandedQVersionsIndex,
    setExpandedRespVersionsIndex,
    setIsAutoScrollLocked,
    setShowScrollToBottom,
  ]);

  const handleDeleteSession = useCallback(
    (sessionId: string) => {
      if (sessionId === DEMO_SHOWCASE_SESSION_ID) {
        try {
          localStorage.setItem(DEMO_DELETED_KEY, 'true');
        } catch {}
      }
      setSessions((prev) => {
        const updated = prev.filter((s) => s.id !== sessionId);
        saveSessionsLocally(updated, true);
        return updated;
      });
      if (currentSessionId === sessionId) {
        handleNewChat();
      }
      chatService.deleteChatSession?.(sessionId).catch(() => {});
    },
    [currentSessionId, handleNewChat]
  );

  const handleDeleteAllChats = useCallback(async () => {
    try {
      localStorage.setItem(DEMO_DELETED_KEY, 'true');
    } catch {}
    setSessions([]);
    saveSessionsLocally([], true);
    handleNewChat();
    try {
      await chatService.clearChat?.(undefined);
    } catch {}
  }, [handleNewChat]);

  const handleSaveRename = useCallback((sessionId: string, newTitle: string) => {
    const trimmed = newTitle.trim();
    if (!trimmed) return;
    setSessions((prev) => {
      const updated = prev.map((s) => (s.id === sessionId ? { ...s, title: trimmed } : s));
      saveSessionsLocally(updated);
      return updated;
    });
    chatService.renameChatSession?.(sessionId, trimmed).catch(() => {});
  }, []);

  const handleForkConversation = useCallback(
    (turnIndex: number) => {
      if (conversation.length === 0) return;

      let targetEndIndex = turnIndex;
      if (
        conversation[turnIndex]?.role === 'user' &&
        conversation[turnIndex + 1]?.role === 'assistant'
      ) {
        targetEndIndex = turnIndex + 1;
      }

      const slicedMessages = conversation.slice(0, targetEndIndex + 1);
      if (slicedMessages.length === 0) return;

      const clonedMessages: ChatMessage[] = JSON.parse(
        JSON.stringify(slicedMessages)
      ) as ChatMessage[];
      const newSessionId = generateUUID();

      const parentSession = sessions.find((s) => s.id === currentSessionId);
      const rawParentTitle = parentSession?.title || 'Previous chat';
      const cleanParentTitle =
        rawParentTitle.replace(/^\[(?:Fork|Branch)\]\s*/i, '').trim() || 'Previous chat';

      const forkedTitle = `[Branch] ${truncateSessionTitle(cleanParentTitle, 32)}`;
      const forkedSession: ChatSession = {
        id: newSessionId,
        thread_id: newSessionId,
        session_id: newSessionId,
        username: getStoredUsername(),
        title: forkedTitle,
        timestamp: formatSessionDate(new Date()),
        messages: clonedMessages,
        selectedSourceIds: sourceDocs.filter((d) => d.selected).map((d) => d.id),
        sources: [...sourceDocs],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        forkedFromSessionId: currentSessionId || undefined,
        forkedFromTitle: cleanParentTitle,
        forkedAtTurnIndex: turnIndex,
        forkedAtTimestamp: new Date().toISOString(),
      };

      setSessions((prev) => {
        const updated = [forkedSession, ...prev];
        saveSessionsLocally(updated);
        return updated;
      });

      handleSelectSession(forkedSession);
      setForkNotification({
        parentTitle: cleanParentTitle,
        parentSessionId: currentSessionId || '',
        forkedTurnIndex: turnIndex,
        forkedSessionId: newSessionId,
      });

      const persistPayload: PersistedChatSession = {
        session_id: forkedSession.id,
        thread_id: forkedSession.id,
        username: forkedSession.username || getStoredUsername(),
        title: forkedSession.title,
        messages: forkedSession.messages || [],
        selectedSourceIds: forkedSession.selectedSourceIds,
        sources: forkedSession.sources,
        is_saved: false,
        created_at: forkedSession.created_at,
        updated_at: forkedSession.updated_at,
      };
      chatService.persistChatSession?.(persistPayload).catch(() => {});
    },
    [conversation, sessions, currentSessionId, sourceDocs, handleSelectSession]
  );

  return {
    sessions,
    setSessions,
    currentSessionId,
    setCurrentSessionId,
    conversation,
    setConversation,
    forkNotification,
    setForkNotification,
    originalNotification,
    setOriginalNotification,
    updateSessionInMemory,
    handleSelectSession,
    handleNewChat,
    handleDeleteSession,
    handleDeleteAllChats,
    handleSaveRename,
    handleForkConversation,
  };
}
