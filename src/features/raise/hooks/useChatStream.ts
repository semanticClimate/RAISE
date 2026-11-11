import { useCallback, useEffect, useRef, useState } from 'react';
import { chatService } from '../../../services/ChatService';
import { useFilterStore } from '../../../stores/filterStore';
import { AdaptiveStreamBuffer } from '../../../utils/adaptiveStreamBuffer';
import { isConversationalQuery } from '../../../utils/queryClassifier';
import { sanitizeStreamText } from '../../../utils/sanitizeStreamText';
import { generateUUID } from '../../../utils/uuid';
import type { ChatMessage, QuestionVersion, ResponseVersion, SourceDocument } from '../types';
import {
  deduplicateTurns,
  getFormattedChatHistory,
  isResponsePersisted,
} from '../utils/messageNormalizer';

export interface UseChatStreamOptions {
  currentSessionId: string | null;
  setCurrentSessionId: (id: string) => void;
  conversation: ChatMessage[];
  setConversation: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  sourceDocs: SourceDocument[];
  setIsSourcesDrawerOpen: (open: boolean) => void;
  parseMode: 'fast' | 'expert';
  isLlmConfigured: boolean;
  setIsControlCenterOpen: (open: boolean) => void;
  updateSessionInMemory: (msgs: ChatMessage[], threadId: string) => void;
  setIsAutoScrollLocked: (locked: boolean) => void;
  setShowScrollToBottom: (show: boolean) => void;
}

export function useChatStream({
  currentSessionId,
  setCurrentSessionId,
  conversation,
  setConversation,
  sourceDocs,
  setIsSourcesDrawerOpen,
  parseMode,
  isLlmConfigured,
  setIsControlCenterOpen,
  updateSessionInMemory,
  setIsAutoScrollLocked,
  setShowScrollToBottom,
}: UseChatStreamOptions) {
  const [isLoading, setIsLoading] = useState(false);
  const [activeExecutingQuery, setActiveExecutingQuery] = useState('');
  const [activeStreamingStage, setActiveStreamingStage] = useState<Record<string, unknown> | null>(
    null
  );
  const [littleErrorPopup, setLittleErrorPopup] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const isUserAbortingRef = useRef<boolean>(false);
  const isUnmountedRef = useRef<boolean>(false);
  const latestStreamedTextRef = useRef<string>('');
  const adaptiveBufferRef = useRef<AdaptiveStreamBuffer | null>(null);
  const streamTargetIndexRef = useRef<number | 'last'>('last');
  const activeRequestIdRef = useRef<string | null>(null);
  const isSubmittingQueryRef = useRef<boolean>(false);
  const queryStartTimeRef = useRef<number | null>(null);

  useEffect(() => {
    isUnmountedRef.current = false;
    return () => {
      isUnmountedRef.current = true;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const flushStreamToConversation = useCallback(
    (targetIndex: number | 'last', accumulatedText: string) => {
      latestStreamedTextRef.current = accumulatedText;
      streamTargetIndexRef.current = targetIndex;

      if (!adaptiveBufferRef.current) {
        adaptiveBufferRef.current = new AdaptiveStreamBuffer({
          minIntervalMs: 16,
          maxIntervalMs: 45,
          onFlush: (text) => {
            if (isUnmountedRef.current) return;
            const idx = streamTargetIndexRef.current;
            setConversation((prev) => {
              const updated = [...prev];
              const targetIdx = idx === 'last' ? updated.length - 1 : idx;
              if (targetIdx >= 0 && updated[targetIdx] && updated[targetIdx].role === 'assistant') {
                if (
                  updated[targetIdx].text === text &&
                  (updated[targetIdx] as any).content === text
                ) {
                  return prev;
                }
                updated[targetIdx] = {
                  ...updated[targetIdx],
                  text,
                  content: text,
                };
                return updated;
              }
              if (idx === 'last' && (!updated[targetIdx] || updated[targetIdx].role !== 'assistant')) {
                return [...updated, { role: 'assistant', text, content: text }];
              }
              return prev;
            });
          },
        });
      }

      adaptiveBufferRef.current.push(accumulatedText);
    },
    [setConversation]
  );

  const flushPendingStreamRafImmediately = useCallback((targetIndex: number | 'last') => {
    streamTargetIndexRef.current = targetIndex;
    if (adaptiveBufferRef.current) {
      adaptiveBufferRef.current.flushImmediately();
      adaptiveBufferRef.current.reset();
    }
  }, []);

  const abortActiveQuery = useCallback(() => {
    isUserAbortingRef.current = true;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    flushPendingStreamRafImmediately(streamTargetIndexRef.current);
    setIsLoading(false);
    setActiveStreamingStage(null);
    isSubmittingQueryRef.current = false;
  }, [flushPendingStreamRafImmediately]);

  // Execute a fresh query
  const executeQuery = useCallback(
    async (q: string) => {
      const trimmed = q.trim();
      if (!trimmed || isSubmittingQueryRef.current) return;

      if (!isLlmConfigured) {
        setIsControlCenterOpen(true);
        return;
      }
      isSubmittingQueryRef.current = true;

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      const enterTimestamp = performance.now();
      queryStartTimeRef.current = enterTimestamp;

      const userMsg: ChatMessage = {
        role: 'user',
        text: trimmed,
        content: trimmed,
        created_at: new Date().toISOString(),
      };
      const pendingAssistantMsg: ChatMessage = {
        role: 'assistant',
        text: '',
        content: '',
        isThinking: true,
        created_at: new Date().toISOString(),
        startedAtMs: enterTimestamp,
      };

      const updatedConversation = [...conversation, userMsg, pendingAssistantMsg];
      setConversation(updatedConversation);
      setActiveExecutingQuery(trimmed);
      setIsLoading(true);
      setIsAutoScrollLocked(false);
      setShowScrollToBottom(false);

      const threadId = currentSessionId || generateUUID();
      if (!currentSessionId) {
        setCurrentSessionId(threadId);
      }
      updateSessionInMemory(updatedConversation, threadId);
      const recentHistory = getFormattedChatHistory(conversation);

      const isConversational = isConversationalQuery(trimmed);
      const activeDocNames = sourceDocs.filter((d) => d.selected).map((d) => d.name);
      if (!isConversational && /^\/(?:compare|diff|versus|vs)\b/i.test(trimmed) && activeDocNames.length < 2) {
        setIsSourcesDrawerOpen(true);
      }

      const { hops: filterHops, topK: filterTopK, documentFilter: storeDocFilter } =
        useFilterStore.getState();
      latestStreamedTextRef.current = '';
      isUserAbortingRef.current = false;
      const reqId = generateUUID();
      activeRequestIdRef.current = reqId;

      try {
        const queryTask = chatService.querySubgraph(
          {
            request_id: reqId,
            query: trimmed,
            hops: isConversational ? 0 : (filterHops ?? (parseMode === 'expert' ? 3 : 1)),
            top_k: isConversational ? 0 : (filterTopK ?? (parseMode === 'expert' ? 8 : 4)),
            mode: isConversational ? 'conversational' : parseMode,
            thread_id: threadId,
            chat_history: recentHistory,
            active_docs: isConversational ? [] : activeDocNames,
            document_filter:
              isConversational
                ? undefined
                : storeDocFilter || (activeDocNames.length === 1 ? activeDocNames[0] : undefined),
            parser: isConversational ? 'fast' : (parseMode === 'expert' ? 'docling' : 'fast'),
            full_potential: !isConversational && parseMode === 'expert',
          },
          controller.signal,
          (_chunk, fullAccumulated) => {
            flushStreamToConversation('last', fullAccumulated);
          },
          (stageUpdate) => {
            setActiveStreamingStage(stageUpdate);
          }
        );

        const res = await queryTask;
        setActiveStreamingStage(null);
        flushPendingStreamRafImmediately('last');

        if (isUnmountedRef.current) return;
        const elapsedSec = Math.max(0.1, Number(((performance.now() - enterTimestamp) / 1000).toFixed(1)));

        let assistantMsg: ChatMessage;

        if (res.data) {
          const persisted = isResponsePersisted(res.data);
          const rawAns =
            (typeof res.data.grounded_answer === 'string' ? res.data.grounded_answer : '') ||
            (typeof res.data.answer === 'string' ? res.data.answer : '') ||
            latestStreamedTextRef.current ||
            '';
          const resolvedText = sanitizeStreamText(rawAns);
          assistantMsg = {
            role: 'assistant',
            text: resolvedText,
            content: resolvedText,
            response: res.data,
            durationSec: elapsedSec,
            created_at: new Date().toISOString(),
            persistenceFailed: !persisted,
            isThinking: false,
          };
        } else {
          const isManualAbort =
            isUserAbortingRef.current ||
            res.error?.code === 'CLIENT_REQUEST_CANCELLED' ||
            (typeof res.error?.message === 'string' && res.error.message.toLowerCase().includes('abort'));

          if (isManualAbort) {
            const abortText = latestStreamedTextRef.current || '';
            assistantMsg = {
              role: 'assistant',
              text: abortText,
              content: abortText,
              isStopped: true,
              durationSec: elapsedSec,
              isThinking: false,
            };
          } else {
            assistantMsg = {
              role: 'assistant',
              text: latestStreamedTextRef.current || '',
              content: latestStreamedTextRef.current || '',
              error: {
                title: 'Query Execution Error',
                message: res.error?.message || 'Server returned an error',
                cause: res.error?.code,
                status: res.error?.status,
              },
              durationSec: elapsedSec,
              isThinking: false,
            };
          }
        }

        // Attach initial version history
        const initialRespVer: ResponseVersion = {
          id: generateUUID(),
          text: assistantMsg.text,
          content: assistantMsg.content,
          response: assistantMsg.response,
          error: assistantMsg.error,
          durationSec: assistantMsg.durationSec,
          created_at: assistantMsg.created_at,
          isStopped: assistantMsg.isStopped,
        };
        const initialQVer: QuestionVersion = {
          id: generateUUID(),
          question: trimmed,
          responseVersions: [initialRespVer],
          currentResponseVersionIndex: 0,
        };

        const mergedAssistant: ChatMessage = {
          ...assistantMsg,
          currentQuestionVersionIndex: 0,
          questionVersions: [initialQVer],
        };

        setConversation((prev) => {
          const base = [...prev];
          const lastIdx = base.length - 1;
          if (lastIdx >= 0 && base[lastIdx]?.role === 'assistant') {
            base[lastIdx] = mergedAssistant;
          } else {
            base.push(mergedAssistant);
          }
          const committed = deduplicateTurns(base);
          if (res.data && !assistantMsg.persistenceFailed && committed.length > 0) {
            updateSessionInMemory(committed, threadId);
          }
          return committed;
        });
      } catch (err: any) {
        if (isUnmountedRef.current) return;
        const elapsedSec = Math.max(0.1, Number(((performance.now() - enterTimestamp) / 1000).toFixed(1)));
        const stoppedText = latestStreamedTextRef.current || '';
        const errorMsg: ChatMessage = {
          role: 'assistant',
          text: stoppedText,
          content: stoppedText,
          error: {
            title: 'Network / Inference Error',
            message: err?.message || 'Failed to complete query',
            cause: err?.code || 'FETCH_ERROR',
          },
          durationSec: elapsedSec,
          isThinking: false,
        };
        setConversation((prev) => {
          const base = [...prev];
          const lastIdx = base.length - 1;
          if (lastIdx >= 0 && base[lastIdx]?.role === 'assistant') {
            base[lastIdx] = errorMsg;
          } else {
            base.push(errorMsg);
          }
          return deduplicateTurns(base);
        });
      } finally {
        setIsLoading(false);
        setActiveStreamingStage(null);
        isSubmittingQueryRef.current = false;
      }
    },
    [
      conversation,
      currentSessionId,
      sourceDocs,
      parseMode,
      setConversation,
      setCurrentSessionId,
      setIsSourcesDrawerOpen,
      updateSessionInMemory,
      flushStreamToConversation,
      flushPendingStreamRafImmediately,
      setIsAutoScrollLocked,
      setShowScrollToBottom,
    ]
  );

  return {
    isLoading,
    setIsLoading,
    activeExecutingQuery,
    setActiveExecutingQuery,
    activeStreamingStage,
    littleErrorPopup,
    setLittleErrorPopup,
    executeQuery,
    abortActiveQuery,
    flushStreamToConversation,
    flushPendingStreamRafImmediately,
    latestStreamedTextRef,
    isSubmittingQueryRef,
  };
}
