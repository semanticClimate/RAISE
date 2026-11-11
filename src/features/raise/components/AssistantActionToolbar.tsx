import { GitFork } from 'lucide-react';
import type React from 'react';
import { ExportResponseDropdown } from '../../../components/chat/ExportResponseDropdown';
import type { ChatMessage, ResponseVersion } from '../types';
import { ActionTooltip } from './ActionTooltip';

export interface AssistantActionToolbarProps {
  turnIndex: number;
  msg: ChatMessage;
  resolvedContent: string;
  isSpeaking: boolean;
  isRegenerating: boolean;
  isLoading: boolean;
  copiedKey: string | null;
  handleCopyText: (text: string, key: string) => void;
  handleToggleSpeak: (text: string, id: string) => void;
  handleRegenerateResponse: (idx: number) => void;
  handleForkConversation: (idx: number) => void;
  handleFeedback: (idx: number, rating: 'thumbs_up' | 'thumbs_down') => void;
  respVersions: ResponseVersion[];
  currentRespIdx: number;
  currentRespVerNum: number;
  totalRespVers: number;
  expandedRespVersionsIndex: number | null;
  setExpandedRespVersionsIndex: React.Dispatch<React.SetStateAction<number | null>>;
  handleSwitchResponseVersion: (userIndex: number, targetVersionIndex: number) => void;
}

export const AssistantActionToolbar: React.FC<AssistantActionToolbarProps> = ({
  turnIndex,
  msg,
  resolvedContent,
  isSpeaking,
  isRegenerating,
  isLoading,
  copiedKey,
  handleCopyText,
  handleToggleSpeak,
  handleRegenerateResponse,
  handleForkConversation,
  handleFeedback,
  currentRespIdx,
  currentRespVerNum,
  totalRespVers,
  expandedRespVersionsIndex,
  setExpandedRespVersionsIndex,
  handleSwitchResponseVersion,
}) => {
  return (
    <div className="flex items-center gap-1 mt-3 -ml-1 text-slate-500 dark:text-slate-400 select-none">
      {/* Copy Response Button */}
      <ActionTooltip label={copiedKey === `ans-${turnIndex}` ? 'Copied!' : 'Copy response'}>
        <button
          type="button"
          onClick={() => handleCopyText(resolvedContent, `ans-${turnIndex}`)}
          title={copiedKey === `ans-${turnIndex}` ? 'Copied!' : 'Copy response'}
          aria-label="Copy response"
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5 active:scale-95 transition-all cursor-pointer flex items-center justify-center"
        >
          {copiedKey === `ans-${turnIndex}` ? (
            <svg
              className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          )}
        </button>
      </ActionTooltip>

      {/* TTS Read Aloud */}
      <ActionTooltip label={isSpeaking ? 'Stop speaking' : 'Read aloud'}>
        <button
          type="button"
          onClick={() => handleToggleSpeak(resolvedContent, `msg-${turnIndex}`)}
          title={isSpeaking ? 'Stop speaking' : 'Read aloud'}
          aria-label={isSpeaking ? 'Stop speaking' : 'Read aloud'}
          className={`p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5 active:scale-95 transition-all cursor-pointer flex items-center justify-center ${
            isSpeaking ? 'text-indigo-600 dark:text-indigo-400 animate-pulse' : ''
          }`}
        >
          {isSpeaking ? (
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <line x1="23" y1="9" x2="17" y2="15" />
              <line x1="17" y1="9" x2="23" y2="15" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
            </svg>
          )}
        </button>
      </ActionTooltip>

      {/* Regenerate Response */}
      <ActionTooltip label="Regenerate response">
        <button
          type="button"
          disabled={isLoading}
          onClick={() => handleRegenerateResponse(turnIndex)}
          title="Regenerate response"
          aria-label="Regenerate response"
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5 active:scale-95 disabled:opacity-40 disabled:pointer-events-none transition-all cursor-pointer flex items-center justify-center"
        >
          <svg
            className={`w-3.5 h-3.5 ${isRegenerating ? 'animate-spin text-indigo-500' : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
        </button>
      </ActionTooltip>

      {/* Fork / Branch Conversation */}
      <ActionTooltip label="Branch into new chat from here">
        <button
          type="button"
          onClick={() => handleForkConversation(turnIndex)}
          title="Branch conversation from here"
          aria-label="Branch into new chat from here"
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5 active:scale-95 transition-all cursor-pointer flex items-center justify-center"
        >
          <GitFork className="w-3.5 h-3.5" />
        </button>
      </ActionTooltip>

      {/* Feedback Thumbs */}
      <ActionTooltip label="Good response">
        <button
          type="button"
          onClick={() => handleFeedback(turnIndex, 'thumbs_up')}
          aria-label="Good response"
          className={`p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5 active:scale-95 transition-all cursor-pointer flex items-center justify-center ${
            msg.feedback === 'thumbs_up' ? 'text-emerald-600 dark:text-emerald-400' : ''
          }`}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill={msg.feedback === 'thumbs_up' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
          </svg>
        </button>
      </ActionTooltip>

      <ActionTooltip label="Bad response">
        <button
          type="button"
          onClick={() => handleFeedback(turnIndex, 'thumbs_down')}
          aria-label="Bad response"
          className={`p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5 active:scale-95 transition-all cursor-pointer flex items-center justify-center ${
            msg.feedback === 'thumbs_down' ? 'text-rose-600 dark:text-rose-400' : ''
          }`}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill={msg.feedback === 'thumbs_down' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3" />
          </svg>
        </button>
      </ActionTooltip>

      {/* Export Dropdown - positioned on the left side with toolbar actions */}
      <ExportResponseDropdown
        query="Academic Research Response"
        answerText={resolvedContent}
        response={msg.response}
      />

      {/* Response Versions Navigation */}
      {totalRespVers > 1 &&
        (expandedRespVersionsIndex === turnIndex ? (
          <div
            data-version-nav="true"
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-0.5 bg-slate-100/90 dark:bg-[#1a1e2d] border border-indigo-300/80 dark:border-indigo-500/40 rounded-lg px-1 py-0.5 ml-auto animate-in fade-in zoom-in-95 duration-150"
          >
            <ActionTooltip label="Previous response version">
              <button
                type="button"
                disabled={currentRespVerNum <= 1}
                onClick={() => handleSwitchResponseVersion(turnIndex - 1, currentRespIdx - 1)}
                title="Previous response version"
                aria-label="Previous response version"
                className="p-1 rounded text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/80 dark:hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition-all cursor-pointer flex items-center justify-center"
              >
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="15 18 9 12 15 6" />
                </svg>
              </button>
            </ActionTooltip>

            <ActionTooltip label="Hide version navigation">
              <button
                type="button"
                onClick={() => setExpandedRespVersionsIndex(null)}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-slate-200/70 dark:hover:bg-white/10 transition-colors cursor-pointer select-none"
              >
                <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">
                  {currentRespVerNum}/{totalRespVers}
                </span>
              </button>
            </ActionTooltip>

            <ActionTooltip label="Next response version">
              <button
                type="button"
                disabled={currentRespVerNum >= totalRespVers}
                onClick={() => handleSwitchResponseVersion(turnIndex - 1, currentRespIdx + 1)}
                title="Next response version"
                aria-label="Next response version"
                className="p-1 rounded text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/80 dark:hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition-all cursor-pointer flex items-center justify-center"
              >
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
            </ActionTooltip>
          </div>
        ) : (
          <ActionTooltip label="Show response versions">
            <button
              type="button"
              onClick={() => setExpandedRespVersionsIndex(turnIndex)}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5 ml-auto transition-colors cursor-pointer select-none"
            >
              <span className="text-[11px] font-medium">
                {currentRespVerNum}/{totalRespVers}
              </span>
            </button>
          </ActionTooltip>
        ))}
    </div>
  );
};
