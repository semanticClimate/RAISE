import { GitBranch } from 'lucide-react';
import type React from 'react';
import type { ChatSession } from '../types';

export interface BranchNotificationsProps {
  turnIndex: number;
  totalConversationTurns: number;
  currentSessionId: string | null;
  sessions: ChatSession[];
  forkNotification: {
    parentTitle: string;
    parentSessionId: string;
    forkedTurnIndex: number;
    forkedSessionId: string;
  } | null;
  originalNotification: {
    branchTitle: string;
    branchSessionId: string;
  } | null;
  onSelectSession: (session: ChatSession) => void;
  setOriginalNotification: React.Dispatch<
    React.SetStateAction<{
      branchTitle: string;
      branchSessionId: string;
    } | null>
  >;
}

export const BranchNotifications: React.FC<BranchNotificationsProps> = ({
  turnIndex,
  totalConversationTurns,
  currentSessionId,
  sessions,
  forkNotification,
  originalNotification,
  onSelectSession,
  setOriginalNotification,
}) => {
  const activeSession = sessions.find((s) => s.id === currentSessionId);

  const isForkBannerVisible = Boolean(
    currentSessionId &&
      ((forkNotification &&
        forkNotification.forkedSessionId === currentSessionId &&
        forkNotification.forkedTurnIndex === turnIndex) ||
        (!forkNotification &&
          activeSession?.forkedFromSessionId &&
          turnIndex === (activeSession.forkedAtTurnIndex ?? totalConversationTurns - 1)))
  );

  const matchingBranch = originalNotification
    ? sessions.find(
        (s) =>
          s.forkedFromSessionId === currentSessionId &&
          s.id === originalNotification.branchSessionId
      )
    : sessions.find((s) => s.forkedFromSessionId === currentSessionId);

  const targetTurnIndex = matchingBranch?.forkedAtTurnIndex;
  const isOriginalBannerVisible = Boolean(
    currentSessionId &&
      matchingBranch &&
      targetTurnIndex !== undefined &&
      turnIndex === targetTurnIndex
  );

  return (
    <>
      {/* Branch indicator immediately below this response */}
      {isForkBannerVisible && (
        <div className="w-full max-w-[clamp(36rem,90vw,58rem)] mx-auto mt-2 px-3 py-1.5 bg-indigo-50/80 dark:bg-indigo-950/30 border border-indigo-200/70 dark:border-indigo-500/30 rounded-xl flex items-center justify-between text-xs text-indigo-900 dark:text-indigo-200 shadow-2xs animate-in fade-in slide-in-from-top-1">
          <div className="flex items-center gap-2 min-w-0">
            <GitBranch className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />
            <span className="truncate">
              Branch of{' '}
              <span className="font-semibold text-slate-800 dark:text-slate-100">
                "{forkNotification?.parentTitle || activeSession?.forkedFromTitle || 'Previous chat'}"
              </span>
            </span>
          </div>
          <div className="flex items-center gap-2.5 shrink-0 ml-2">
            {(forkNotification?.parentSessionId || activeSession?.forkedFromSessionId) && (
              <button
                type="button"
                onClick={() => {
                  const parentId =
                    forkNotification?.parentSessionId || activeSession?.forkedFromSessionId;
                  const parent = sessions.find((s) => s.id === parentId);
                  if (parent) {
                    const currentTitle = activeSession?.title || 'Branch';
                    const currentId = currentSessionId || '';
                    onSelectSession(parent);
                    setOriginalNotification({
                      branchTitle: currentTitle,
                      branchSessionId: currentId,
                    });
                  }
                }}
                className="text-[11px] underline font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 cursor-pointer"
              >
                View original
              </button>
            )}
          </div>
        </div>
      )}

      {/* Original session indicator immediately below this response */}
      {isOriginalBannerVisible && (
        <div className="w-full max-w-[clamp(36rem,90vw,58rem)] mx-auto mt-2 px-3 py-1.5 bg-emerald-50/80 dark:bg-emerald-950/30 border border-emerald-200/70 dark:border-emerald-500/30 rounded-xl flex items-center justify-between text-xs text-emerald-900 dark:text-emerald-200 shadow-2xs animate-in fade-in slide-in-from-top-1">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-semibold text-emerald-700 dark:text-emerald-300 shrink-0">
              Original
            </span>
          </div>
        </div>
      )}
    </>
  );
};
