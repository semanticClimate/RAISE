import React, { useMemo } from 'react';
import { AnswerMarkdown } from '../../../components/chat/AnswerMarkdown';
import {
  BackendErrorCard,
  ResponseStoppedBanner,
} from '../../../components/chat/BackendErrorCard';
import {
  LiveThoughtDuration,
  ThoughtDuration,
} from '../../../components/chat/QueryLifecycleTracker';
import { VerifiedClaimsBadge } from '../../../components/chat/VerifiedClaimsBadge';
import {
  computeHistoricalDuration,
  resolveTurnExecutionTime,
} from '../../../components/chat/thoughtDurationUtils';
import type { Citation } from '../../../types';
import type { ChatMessage, ChatSession, ResponseVersion } from '../types';
import { getTurnQuestionVersions } from '../utils/speechUtils';
import { AssistantActionToolbar } from './AssistantActionToolbar';
import { BranchNotifications } from './BranchNotifications';

export interface AssistantTurnItemProps {
  turnIndex: number;
  msg: ChatMessage;
  prevUserMsg?: ChatMessage;
  totalConversationTurns: number;
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
  expandedRespVersionsIndex: number | null;
  setExpandedRespVersionsIndex: React.Dispatch<React.SetStateAction<number | null>>;
  setOriginalNotification: React.Dispatch<React.SetStateAction<any>>;
  runCapabilityProbe: () => Promise<any>;
  handleRegenerateResponse: (idx: number) => void;
  handleCopyText: (text: string, key: string) => void;
  handleToggleSpeak: (text: string, id: string) => void;
  handleForkConversation: (idx: number) => void;
  handleFeedback: (idx: number, rating: 'thumbs_up' | 'thumbs_down') => void;
  handleSwitchResponseVersion: (userIndex: number, targetVersionIndex: number) => void;
  onSelectSession: (session: ChatSession) => void;
  onOpenPdfViewer?: (fileName: string, page: number, mode?: 'page' | 'full' | 'view') => void;
  onOpenSettings: () => void;
}

export const AssistantTurnItemBase: React.FC<AssistantTurnItemProps> = ({
  turnIndex,
  msg,
  prevUserMsg,
  totalConversationTurns,
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
  expandedRespVersionsIndex,
  setExpandedRespVersionsIndex,
  setOriginalNotification,
  runCapabilityProbe,
  handleRegenerateResponse,
  handleCopyText,
  handleToggleSpeak,
  handleForkConversation,
  handleFeedback,
  handleSwitchResponseVersion,
  onSelectSession,
  onOpenPdfViewer,
  onOpenSettings,
}) => {
  const qVersions = prevUserMsg ? getTurnQuestionVersions(prevUserMsg, msg) : [];
  const currentQIdx = prevUserMsg ? (prevUserMsg.currentQuestionVersionIndex ?? qVersions.length - 1) : 0;
  const activeQVer = qVersions[currentQIdx];
  const respVersions: ResponseVersion[] =
    activeQVer?.responseVersions && activeQVer.responseVersions.length > 0
      ? activeQVer.responseVersions
      : [
          {
            id: `resp-${turnIndex}`,
            text: msg.text || (msg as any).content || '',
            content: (msg as any).content || msg.text || '',
            response: msg.response,
            error: msg.error,
            durationSec: msg.durationSec,
            isStopped: msg.isStopped,
          },
        ];
  const currentRespIdx = activeQVer?.currentResponseVersionIndex ?? respVersions.length - 1;
  const activeResp = respVersions[currentRespIdx] || respVersions[0];
  const currentRespVerNum = currentRespIdx + 1;
  const totalRespVers = respVersions.length;

  const isSpeaking = speakingMessageId === `msg-${turnIndex}`;
  const isRegenerating = regeneratingIndex === turnIndex;
  const isCurrentlyActive = Boolean(
    isLoading &&
      (isRegenerating ||
        (turnIndex === totalConversationTurns - 1 && !msg.error && !msg.isStopped))
  );

  const isStopped = Boolean(activeResp?.isStopped ?? msg.isStopped ?? msg.error?.isAborted);

  if (msg.error && !isCurrentlyActive && !isStopped) {
    return (
      <div key={`assistant-turn-${turnIndex}`} className="content-visibility-auto w-full mb-4">
        <BackendErrorCard
          error={msg.error}
          targetUrl={apiBaseUrl}
          onRetry={async () => {
            if (msg.error?.isOffline || appMode !== 'connected') {
              await runCapabilityProbe();
            }
            handleRegenerateResponse(turnIndex);
          }}
          onOpenSettings={onOpenSettings}
        />
      </div>
    );
  }

  const calcHistoryDuration = computeHistoricalDuration(
    (prevUserMsg as any)?.created_at,
    (msg as any)?.created_at
  );

  const executionTimeSec = resolveTurnExecutionTime({
    activeRespDuration: activeResp?.durationSec,
    msgDuration: msg.durationSec,
    activeResp,
    msg,
    calcHistoryDuration,
  });

  const rawTurnContent =
    activeResp?.text ||
    (activeResp as any)?.content ||
    activeResp?.response?.grounded_answer ||
    activeResp?.response?.answer ||
    activeResp?.response?.reply ||
    activeResp?.response?.content ||
    activeResp?.response?.text ||
    msg.text ||
    (msg as any).content ||
    '';

  const resolvedContent = rawTurnContent;

  const rawCitations =
    activeResp?.response?.citations ||
    activeResp?.response?.top_chunks ||
    msg.response?.citations ||
    msg.response?.top_chunks ||
    [];

  // Stable citations reference
  const stableCitations = useMemo<Citation[]>(() => {
    return Array.isArray(rawCitations) ? (rawCitations as Citation[]) : [];
  }, [rawCitations]);

  return (
    <div
      key={`assistant-turn-${turnIndex}`}
      className="content-visibility-auto flex flex-col items-start w-full max-w-[clamp(28rem,85vw,44rem)] mx-auto"
    >
      <div className="w-full bg-white/70 dark:bg-[#131622]/80 border border-slate-200/80 dark:border-white/[0.08] rounded-2xl rounded-tl-sm p-[clamp(0.875rem,2.5vw,1.25rem)] shadow-xs dark:shadow-md backdrop-blur-md">
        {/* Thought Duration Header */}
        <div className="flex items-center justify-between mb-2 pb-2 border-b border-slate-100 dark:border-white/[0.04]">
          {isCurrentlyActive ? (
            <LiveThoughtDuration startTimeMs={msg.startedAtMs || Date.now()} />
          ) : (
            <ThoughtDuration executionTimeSec={executionTimeSec} />
          )}

          {activeResp?.response?.verified_claims &&
            activeResp.response.verified_claims.length > 0 && (
              <VerifiedClaimsBadge claims={activeResp.response.verified_claims} />
            )}
        </div>

        {/* Answer Markdown Content */}
        {resolvedContent ? (
          <AnswerMarkdown
            content={resolvedContent}
            citations={stableCitations}
            showCitations={true}
            onViewPdf={onOpenPdfViewer}
          />
        ) : isCurrentlyActive ? (
          <div className="flex items-center gap-2 py-4 text-sm text-slate-500 dark:text-slate-400">
            <span className="w-2 h-2 rounded-full bg-indigo-500 animate-ping" />
            <span className="font-mono text-xs">Synthesizing research synthesis...</span>
          </div>
        ) : null}

        {/* Action Toolbar */}
        {Boolean(resolvedContent) && !isCurrentlyActive && (
          <AssistantActionToolbar
            turnIndex={turnIndex}
            msg={msg}
            resolvedContent={resolvedContent}
            isSpeaking={isSpeaking}
            isRegenerating={isRegenerating}
            isLoading={isLoading}
            copiedKey={copiedKey}
            handleCopyText={handleCopyText}
            handleToggleSpeak={handleToggleSpeak}
            handleRegenerateResponse={handleRegenerateResponse}
            handleForkConversation={handleForkConversation}
            handleFeedback={handleFeedback}
            respVersions={respVersions}
            currentRespIdx={currentRespIdx}
            currentRespVerNum={currentRespVerNum}
            totalRespVers={totalRespVers}
            expandedRespVersionsIndex={expandedRespVersionsIndex}
            setExpandedRespVersionsIndex={setExpandedRespVersionsIndex}
            handleSwitchResponseVersion={handleSwitchResponseVersion}
          />
        )}
      </div>

      {/* Response Stopped Notice */}
      {isStopped && !isCurrentlyActive && (
        <ResponseStoppedBanner
          onRetry={() => handleRegenerateResponse(turnIndex)}
          className="mt-2 mb-1"
        />
      )}

      {/* Branch & Original line banners */}
      <BranchNotifications
        turnIndex={turnIndex}
        totalConversationTurns={totalConversationTurns}
        currentSessionId={currentSessionId}
        sessions={sessions}
        forkNotification={forkNotification}
        originalNotification={originalNotification}
        onSelectSession={onSelectSession}
        setOriginalNotification={setOriginalNotification}
      />
    </div>
  );
};

export const AssistantTurnItem = React.memo(AssistantTurnItemBase);
