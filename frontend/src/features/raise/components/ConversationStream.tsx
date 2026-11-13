import React from 'react';
import { RAISE_LAYOUT } from '../../../styles/layoutTokens';
import type { ChatMessage, ChatSession } from '../types';
import { AssistantTurnItem } from './AssistantTurnItem';
import { UserTurnItem } from './UserTurnItem';

export interface ConversationStreamProps {
  conversation: ChatMessage[];
  activeDocCount: number;
  editingMessageIndex: number | null;
  editingQuestionText: string;
  setEditingMessageIndex: (idx: number | null) => void;
  setEditingQuestionText: (text: string) => void;
  handleSaveEditedQuestion: (idx: number, text: string) => void;
  isLoading: boolean;
  regeneratingIndex: number | null;
  speakingMessageId: string | null;
  apiBaseUrl: string;
  appMode: string;
  currentSessionId: string | null;
  sessions: ChatSession[];
  forkNotification: any;
  originalNotification: any;
  copiedKey: string | null;
  expandedQVersionsIndex: number | null;
  expandedRespVersionsIndex: number | null;
  setExpandedQVersionsIndex: React.Dispatch<React.SetStateAction<number | null>>;
  setExpandedRespVersionsIndex: React.Dispatch<React.SetStateAction<number | null>>;
  setOriginalNotification: React.Dispatch<React.SetStateAction<any>>;
  runCapabilityProbe: () => Promise<any>;
  handleRegenerateResponse: (idx: number) => void;
  handleCopyText: (text: string, key: string) => void;
  handleToggleSpeak: (text: string, id: string) => void;
  handleForkConversation: (idx: number) => void;
  handleFeedback: (idx: number, rating: 'thumbs_up' | 'thumbs_down') => void;
  handleSwitchQuestionVersion: (userIndex: number, targetVersionIndex: number) => void;
  handleSwitchResponseVersion: (userIndex: number, targetVersionIndex: number) => void;
  onSelectSession: (session: ChatSession) => void;
  onOpenPdfViewer?: (fileName: string, page: number, mode?: 'page' | 'full' | 'view') => void;
  onOpenSettings: () => void;
}

export const ConversationStreamBase: React.FC<ConversationStreamProps> = ({
  conversation,
  activeDocCount,
  editingMessageIndex,
  editingQuestionText,
  setEditingMessageIndex,
  setEditingQuestionText,
  handleSaveEditedQuestion,
  isLoading,
  regeneratingIndex,
  speakingMessageId,
  apiBaseUrl,
  appMode,
  currentSessionId,
  sessions,
  forkNotification,
  originalNotification,
  copiedKey,
  expandedQVersionsIndex,
  expandedRespVersionsIndex,
  setExpandedQVersionsIndex,
  setExpandedRespVersionsIndex,
  setOriginalNotification,
  runCapabilityProbe,
  handleRegenerateResponse,
  handleCopyText,
  handleToggleSpeak,
  handleForkConversation,
  handleFeedback,
  handleSwitchQuestionVersion,
  handleSwitchResponseVersion,
  onSelectSession,
  onOpenPdfViewer,
  onOpenSettings,
}) => {
  if (conversation.length === 0) {
    return (
      <section className={RAISE_LAYOUT.queryHeader} data-purpose="hero-header">
        <div>
          <h1 className="text-[clamp(1.5rem,4.5vw,2.25rem)] font-semibold tracking-tight text-slate-900 dark:text-white mb-1.5">
            Welcome to RAISE
          </h1>
          <p className="text-[clamp(0.8125rem,2.2vw,0.9375rem)] text-slate-500 dark:text-slate-400 font-normal leading-relaxed">
            {activeDocCount === 0
              ? 'Ask research questions, synthesize knowledge, or attach documents for deep analysis.'
              : 'Explore insights from your attached sources or ask a follow-up inquiry.'}
          </p>
        </div>
      </section>
    );
  }

  return (
    <div className="space-y-6 mb-6">
      {conversation.map((msg, i) => {
        if (msg.role === 'user') {
          const nextAssistant =
            conversation[i + 1]?.role === 'assistant' ? conversation[i + 1] : undefined;

          return (
            <UserTurnItem
              key={`user-turn-${i}`}
              msg={msg}
              index={i}
              nextAssistant={nextAssistant}
              editingMessageIndex={editingMessageIndex}
              editingQuestionText={editingQuestionText}
              setEditingMessageIndex={setEditingMessageIndex}
              setEditingQuestionText={setEditingQuestionText}
              handleSaveEditedQuestion={handleSaveEditedQuestion}
              isLoading={isLoading}
              copiedKey={copiedKey}
              handleCopyText={handleCopyText}
              expandedQVersionsIndex={expandedQVersionsIndex}
              setExpandedQVersionsIndex={setExpandedQVersionsIndex}
              handleSwitchQuestionVersion={handleSwitchQuestionVersion}
            />
          );
        }

        const prevUser = conversation[i - 1]?.role === 'user' ? conversation[i - 1] : undefined;

        return (
          <AssistantTurnItem
            key={`assistant-turn-${i}`}
            turnIndex={i}
            msg={msg}
            prevUserMsg={prevUser}
            totalConversationTurns={conversation.length}
            isLoading={isLoading}
            regeneratingIndex={regeneratingIndex}
            speakingMessageId={speakingMessageId}
            apiBaseUrl={apiBaseUrl}
            appMode={appMode}
            currentSessionId={currentSessionId}
            sessions={sessions}
            forkNotification={forkNotification}
            originalNotification={originalNotification}
            copiedKey={copiedKey}
            expandedRespVersionsIndex={expandedRespVersionsIndex}
            setExpandedRespVersionsIndex={setExpandedRespVersionsIndex}
            setOriginalNotification={setOriginalNotification}
            runCapabilityProbe={runCapabilityProbe}
            handleRegenerateResponse={handleRegenerateResponse}
            handleCopyText={handleCopyText}
            handleToggleSpeak={handleToggleSpeak}
            handleForkConversation={handleForkConversation}
            handleFeedback={handleFeedback}
            handleSwitchResponseVersion={handleSwitchResponseVersion}
            onSelectSession={onSelectSession}
            onOpenPdfViewer={onOpenPdfViewer}
            onOpenSettings={onOpenSettings}
          />
        );
      })}
    </div>
  );
};

export const ConversationStream = React.memo(ConversationStreamBase);
