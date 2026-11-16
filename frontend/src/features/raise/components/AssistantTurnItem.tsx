import React, { useMemo } from 'react';
import { Zap, Sparkles, MessageSquare } from 'lucide-react';
import { AnswerMarkdown } from '../../../components/chat/AnswerMarkdown';
import {
  BackendErrorCard,
  ResponseStoppedBanner,
} from '../../../components/chat/BackendErrorCard';
import {
  LiveThoughtDuration,
  ThoughtDuration,
} from '../../../components/chat/QueryLifecycleTracker';
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
  const turnError = activeResp?.error || msg.error;

  if (turnError && !isCurrentlyActive && !isStopped) {
    return (
      <div key={`assistant-turn-${turnIndex}`} className="content-visibility-auto w-full mb-4">
        <BackendErrorCard
          error={turnError}
          targetUrl={apiBaseUrl}
          onRetry={async () => {
            if (turnError.isOffline || appMode === 'offline') {
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

  const hasMultipleVersions = respVersions.length > 1;
  const rawTurnContent = hasMultipleVersions
    ? activeResp?.text ||
      (activeResp as any)?.content ||
      activeResp?.response?.grounded_answer ||
      activeResp?.response?.answer ||
      activeResp?.response?.reply ||
      activeResp?.response?.content ||
      activeResp?.response?.text ||
      msg.text ||
      (msg as any).content ||
      ''
    : msg.text ||
      (msg as any).content ||
      msg.response?.grounded_answer ||
      msg.response?.answer ||
      msg.response?.reply ||
      msg.response?.content ||
      msg.response?.text ||
      activeResp?.text ||
      (activeResp as any)?.content ||
      activeResp?.response?.grounded_answer ||
      activeResp?.response?.answer ||
      '';

  const resolvedContent = rawTurnContent;

  const isUngroundedFallback = Boolean(
    !resolvedContent ||
    resolvedContent.toLowerCase().includes('no grounded answer could be synthesized')
  );

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

  const resolvedUserQuery =
    activeQVer?.question ||
    (prevUserMsg?.questionVersions &&
      prevUserMsg.questionVersions[prevUserMsg.currentQuestionVersionIndex ?? 0]?.question) ||
    prevUserMsg?.text ||
    (prevUserMsg as any)?.content ||
    msg.response?.query ||
    (msg as any)?.query ||
    '';

  const effectiveMode =
    msg.mode ||
    (activeResp?.response as any)?.mode_used ||
    (activeResp?.response as any)?.pipeline_info?.mode_used ||
    (msg.response as any)?.mode_used ||
    (msg.response as any)?.pipeline_info?.mode_used ||
    'fast';

  return (
    <div
      key={`assistant-turn-${turnIndex}`}
      className="content-visibility-auto flex flex-col items-start w-full max-w-[min(100%,clamp(42rem,90vw,56rem))] mx-auto"
    >
      {/* Thought Duration & Research Mode Header OUTSIDE response box */}
      {isCurrentlyActive ? (
        <div className="flex items-center justify-between w-full mb-1.5 px-0.5">
          <LiveThoughtDuration startTimeMs={msg.startedAtMs || Date.now()} />
        </div>
      ) : Boolean(resolvedContent) && !isUngroundedFallback ? (
        <div className="flex items-center justify-between w-full mb-1.5 px-0.5">
          {executionTimeSec > 0 ? (
            <ThoughtDuration executionTimeSec={executionTimeSec} />
          ) : (
            <div />
          )}
          <div className="mb-2 mr-0.5 select-none">
            {effectiveMode === 'expert' ? (
              <span
                data-testid="turn-mode-badge"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium bg-purple-500/10 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-500/20 shadow-2xs"
                title="Expert Mode: Cyclic Multi-Hop GraphRAG Reasoning"
              >
                <Sparkles className="w-3.5 h-3.5 text-purple-500 dark:text-purple-400" />
                <span>Expert Mode</span>
              </span>
            ) : effectiveMode === 'conversational' ? (
              <span
                data-testid="turn-mode-badge"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium bg-emerald-500/10 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 shadow-2xs"
                title="Conversational Mode: Direct Context Dialogue"
              >
                <MessageSquare className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" />
                <span>Conversational Mode</span>
              </span>
            ) : (
              <span
                data-testid="turn-mode-badge"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium bg-sky-500/10 dark:bg-sky-500/20 text-sky-700 dark:text-sky-300 border border-sky-500/20 shadow-2xs"
                title="Fast Mode: Dense Vector & BM25 Reciprocal Rank Fusion"
              >
                <Zap className="w-3.5 h-3.5 text-sky-500 dark:text-sky-400" />
                <span>Fast Mode</span>
              </span>
            )}
          </div>
        </div>
      ) : null}

      {Boolean(resolvedContent) ? (
        <div className="ai-response-card w-full max-w-[min(100%,clamp(42rem,90vw,56rem))] mx-auto bg-white dark:bg-[#131622] border border-slate-200/90 dark:border-white/[0.08] rounded-2xl rounded-tl-sm p-4 sm:p-5 shadow-sm dark:shadow-xl transition-all">
          <AnswerMarkdown
            content={resolvedContent}
            citations={stableCitations}
            showCitations={true}
            onViewPdf={onOpenPdfViewer}
          />
        </div>
      ) : !isCurrentlyActive ? (
        <div className="ai-response-card w-full max-w-[min(100%,clamp(42rem,90vw,56rem))] mx-auto bg-slate-50 dark:bg-white/[0.03] border border-slate-200/80 dark:border-white/10 rounded-2xl rounded-tl-sm p-4 sm:p-5 shadow-xs transition-all">
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            No grounded answer could be synthesized from the active documents. Please verify that your document is attached to your drawer, check your model configuration in the Control Center, or click Retry below.
          </p>
        </div>
      ) : null}

      {/* Action Toolbar placed OUTSIDE response box */}
      {!isCurrentlyActive && (
        <div className="w-full flex items-center justify-between px-1 mt-1.5">
          <AssistantActionToolbar
            turnIndex={turnIndex}
            msg={msg}
            resolvedContent={resolvedContent || 'No grounded answer could be synthesized from the active documents.'}
            userQuery={resolvedUserQuery}
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
        </div>
      )}

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
