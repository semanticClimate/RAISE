import { useCallback } from 'react';
import { chatService } from '../../../services/ChatService';
import type { ChatMessage } from '../types';
import { getTurnQuestionVersions } from '../utils/speechUtils';

export interface UseChatEditingOptions {
  conversation: ChatMessage[];
  setConversation: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  currentSessionId: string | null;
  setCurrentSessionId: (id: string) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  setEditingMessageIndex: (idx: number | null) => void;
  setRegeneratingIndex: (idx: number | null) => void;
  setActiveExecutingQuery: (q: string) => void;
  updateSessionInMemory: (msgs: ChatMessage[], threadId: string) => void;
  executeQuery: (q: string) => Promise<void>;
  setIsAutoScrollLocked: (locked: boolean) => void;
  setShowScrollToBottom: (show: boolean) => void;
}

export function useChatEditing({
  conversation,
  setConversation,
  currentSessionId,
  isLoading,
  setEditingMessageIndex,
  setRegeneratingIndex,
  updateSessionInMemory,
  executeQuery,
  setIsAutoScrollLocked,
  setShowScrollToBottom,
}: UseChatEditingOptions) {
  const handleSwitchQuestionVersion = useCallback(
    (userIndex: number, targetQIdx: number) => {
      let committedSwitch: ChatMessage[] = [];
      setConversation((prev) => {
        const updated = [...prev];
        const userMsg = updated[userIndex];
        if (!userMsg || userMsg.role !== 'user') return prev;

        const assistantIndex = userIndex + 1;
        const assistantMsg =
          updated[assistantIndex]?.role === 'assistant' ? updated[assistantIndex] : undefined;

        const qVersions = getTurnQuestionVersions(userMsg, assistantMsg);
        if (targetQIdx < 0 || targetQIdx >= qVersions.length) return prev;

        const currQIdx = userMsg.currentQuestionVersionIndex ?? qVersions.length - 1;
        if (qVersions[currQIdx] && assistantMsg) {
          const currRespIdx = qVersions[currQIdx].currentResponseVersionIndex ?? 0;
          const respVersions = [...qVersions[currQIdx].responseVersions];
          if (respVersions[currRespIdx]) {
            respVersions[currRespIdx] = {
              ...respVersions[currRespIdx],
              text: assistantMsg.text,
              response: assistantMsg.response,
              error: assistantMsg.error,
              durationSec: assistantMsg.durationSec,
            };
          }
          qVersions[currQIdx] = {
            ...qVersions[currQIdx],
            responseVersions: respVersions,
          };
        }

        const targetQVer = qVersions[targetQIdx];
        const activeRespIdx =
          targetQVer.currentResponseVersionIndex ?? targetQVer.responseVersions.length - 1;
        const activeResp =
          targetQVer.responseVersions[activeRespIdx] || targetQVer.responseVersions[0];

        updated[userIndex] = {
          ...userMsg,
          text: targetQVer.question,
          questionVersions: qVersions,
          currentQuestionVersionIndex: targetQIdx,
        };

        if (updated[assistantIndex] && updated[assistantIndex].role === 'assistant') {
          updated[assistantIndex] = {
            ...updated[assistantIndex],
            text: activeResp?.text || '',
            response: activeResp?.response,
            error: activeResp?.error,
            durationSec: activeResp?.durationSec,
          };
        }

        committedSwitch = updated;
        return updated;
      });

      if (currentSessionId && committedSwitch.length > 0) {
        updateSessionInMemory(committedSwitch, currentSessionId);
      }
    },
    [currentSessionId, setConversation, updateSessionInMemory]
  );

  const handleSwitchResponseVersion = useCallback(
    (userIndex: number, targetRespIdx: number) => {
      let committedSwitch: ChatMessage[] = [];
      setConversation((prev) => {
        const updated = [...prev];
        const userMsg = updated[userIndex];
        if (!userMsg || userMsg.role !== 'user') return prev;

        const assistantIndex = userIndex + 1;
        const assistantMsg =
          updated[assistantIndex]?.role === 'assistant' ? updated[assistantIndex] : undefined;

        const qVersions = getTurnQuestionVersions(userMsg, assistantMsg);
        const currQIdx = userMsg.currentQuestionVersionIndex ?? qVersions.length - 1;
        const activeQVer = qVersions[currQIdx] || qVersions[0];
        if (!activeQVer) return prev;

        const targetResp = activeQVer.responseVersions[targetRespIdx];
        if (!targetResp) return prev;

        const updatedRespVersions = [...activeQVer.responseVersions];
        const updatedQVersions = [...qVersions];
        updatedQVersions[currQIdx] = {
          ...activeQVer,
          responseVersions: updatedRespVersions,
          currentResponseVersionIndex: targetRespIdx,
        };

        updated[userIndex] = {
          ...userMsg,
          questionVersions: updatedQVersions,
          currentQuestionVersionIndex: currQIdx,
        };

        if (updated[assistantIndex] && updated[assistantIndex].role === 'assistant') {
          updated[assistantIndex] = {
            ...updated[assistantIndex],
            text: targetResp.text,
            content: targetResp.content || targetResp.text,
            response: targetResp.response,
            error: targetResp.error,
            durationSec: targetResp.durationSec,
          };
        }

        committedSwitch = updated;
        return updated;
      });

      if (currentSessionId && committedSwitch.length > 0) {
        updateSessionInMemory(committedSwitch, currentSessionId);
      }
    },
    [currentSessionId, setConversation, updateSessionInMemory]
  );

  const handleSaveEditedQuestion = useCallback(
    async (userIndex: number, newQuestionText: string) => {
      const trimmed = newQuestionText.trim();
      if (!trimmed || isLoading) return;

      const userMsg = conversation[userIndex];
      if (!userMsg || userMsg.role !== 'user') return;

      const assistantIndex = userIndex + 1;
      const assistantMsg =
        conversation[assistantIndex]?.role === 'assistant'
          ? conversation[assistantIndex]
          : undefined;

      const existingQVers = getTurnQuestionVersions(userMsg, assistantMsg);
      const currQIdx = userMsg.currentQuestionVersionIndex ?? existingQVers.length - 1;

      if (existingQVers[currQIdx] && assistantMsg) {
        const respVersions = [...existingQVers[currQIdx].responseVersions];
        const currRespIdx = existingQVers[currQIdx].currentResponseVersionIndex ?? 0;
        if (respVersions[currRespIdx]) {
          respVersions[currRespIdx] = {
            ...respVersions[currRespIdx],
            text: assistantMsg.text,
            response: assistantMsg.response,
            error: assistantMsg.error,
          };
        } else if (assistantMsg.text || assistantMsg.error) {
          respVersions.push({
            id: `resp-${Date.now()}`,
            text: assistantMsg.text,
            response: assistantMsg.response,
            error: assistantMsg.error,
          });
        }
        existingQVers[currQIdx] = {
          ...existingQVers[currQIdx],
          responseVersions: respVersions,
        };
      }

      // Truncate to userIndex, updating with the edited question and clearing later turns
      const baseConversation = conversation.slice(0, userIndex);
      setConversation(baseConversation);
      setEditingMessageIndex(null);
      setIsAutoScrollLocked(false);
      setShowScrollToBottom(false);

      await executeQuery(trimmed);
    },
    [
      conversation,
      isLoading,
      executeQuery,
      setConversation,
      setEditingMessageIndex,
      setIsAutoScrollLocked,
      setShowScrollToBottom,
    ]
  );

  const handleRegenerateResponse = useCallback(
    async (assistantIndex: number) => {
      if (isLoading) return;
      const userIndex = assistantIndex - 1;
      if (userIndex < 0 || !conversation[userIndex] || conversation[userIndex].role !== 'user') {
        return;
      }

      const userMsg = conversation[userIndex];
      const assistantMsg = conversation[assistantIndex];

      const qVersions = getTurnQuestionVersions(userMsg, assistantMsg);
      const currQIdx = userMsg.currentQuestionVersionIndex ?? qVersions.length - 1;
      const activeQVer = qVersions[currQIdx] || qVersions[0];
      const activeQuestion = activeQVer?.question || userMsg.text;

      setRegeneratingIndex(assistantIndex);
      const baseConversation = conversation.slice(0, userIndex);
      setConversation(baseConversation);

      await executeQuery(activeQuestion);
      setRegeneratingIndex(null);
    },
    [conversation, isLoading, executeQuery, setConversation, setRegeneratingIndex]
  );

  const handleFeedback = useCallback(
    (idx: number, rating: 'thumbs_up' | 'thumbs_down') => {
      const msg = conversation[idx];
      if (!msg || msg.role !== 'assistant') return;

      setConversation((prev) =>
        prev.map((m, i) => (i === idx ? { ...m, feedback: rating } : m))
      );

      chatService
        .submitFeedback?.({
          message_id: msg.id || String(idx),
          session_id: currentSessionId || '',
          rating: rating,
        })
        .catch(() => {});
    },
    [conversation, currentSessionId, setConversation]
  );

  return {
    handleSwitchQuestionVersion,
    handleSwitchResponseVersion,
    handleSaveEditedQuestion,
    handleRegenerateResponse,
    handleFeedback,
  };
}
