import React from 'react';
import type { ChatMessage } from '../types';
import { getTurnQuestionVersions } from '../utils/speechUtils';
import { ActionTooltip } from './ActionTooltip';

export interface UserTurnItemProps {
  msg: ChatMessage;
  index: number;
  nextAssistant?: ChatMessage;
  editingMessageIndex: number | null;
  editingQuestionText: string;
  setEditingMessageIndex: (idx: number | null) => void;
  setEditingQuestionText: (text: string) => void;
  handleSaveEditedQuestion: (idx: number, text: string) => void;
  isLoading: boolean;
  copiedKey: string | null;
  handleCopyText: (text: string, key: string) => void;
  expandedQVersionsIndex: number | null;
  setExpandedQVersionsIndex: React.Dispatch<React.SetStateAction<number | null>>;
  handleSwitchQuestionVersion: (userIndex: number, targetVersionIndex: number) => void;
}

export const UserTurnItemBase: React.FC<UserTurnItemProps> = ({
  msg,
  index,
  nextAssistant,
  editingMessageIndex,
  editingQuestionText,
  setEditingMessageIndex,
  setEditingQuestionText,
  handleSaveEditedQuestion,
  isLoading,
  copiedKey,
  handleCopyText,
  expandedQVersionsIndex,
  setExpandedQVersionsIndex,
  handleSwitchQuestionVersion,
}) => {
  const qVersions = getTurnQuestionVersions(msg, nextAssistant);
  const currentQIdx = msg.currentQuestionVersionIndex ?? qVersions.length - 1;
  const currentQVerNum = currentQIdx + 1;
  const totalQVers = qVersions.length;

  return (
    <div
      key={`user-turn-${index}`}
      className="content-visibility-auto flex flex-col items-end group/query w-full max-w-[min(100%,clamp(42rem,90vw,56rem))] mx-auto"
    >
      {editingMessageIndex === index ? (
        /* Inline Question Editor */
        <div className="w-full max-w-[85%] bg-white dark:bg-[#131622] border border-indigo-400 dark:border-indigo-500/50 rounded-2xl rounded-tr-sm p-3.5 shadow-md dark:shadow-xl transition-all">
          <textarea
            value={editingQuestionText}
            onChange={(e) => setEditingQuestionText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSaveEditedQuestion(index, editingQuestionText);
              } else if (e.key === 'Escape') {
                setEditingMessageIndex(null);
              }
            }}
            autoFocus
            rows={3}
            className="w-full bg-transparent text-sm sm:text-base text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none resize-none font-normal leading-relaxed"
            placeholder="Edit your question..."
          />
          <div className="flex items-center justify-end mt-2 pt-2 border-t border-slate-200/70 dark:border-white/[0.08]">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setEditingMessageIndex(null)}
                className="px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white rounded-lg hover:bg-slate-100 dark:hover:bg-white/5 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!editingQuestionText.trim() || isLoading}
                onClick={() => handleSaveEditedQuestion(index, editingQuestionText)}
                className="px-3.5 py-1.5 text-xs font-medium bg-indigo-600 hover:bg-indigo-500 active:scale-95 disabled:opacity-50 disabled:pointer-events-none text-white rounded-lg transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
              >
                <span>Ask again</span>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* User Inquiry Bubble */}
          <div className="user-query-bubble max-w-[85%] bg-indigo-50/90 dark:bg-indigo-500/15 border border-indigo-200/80 dark:border-indigo-500/25 rounded-2xl rounded-tr-sm px-[clamp(0.75rem,2.5vw,1rem)] py-[clamp(0.5rem,2vw,0.75rem)] shadow-xs dark:shadow-md">
            <p className="text-sm sm:text-base leading-relaxed text-slate-900 dark:text-slate-100 font-normal select-text break-words">
              {msg.text || (msg as any).content || ''}
            </p>
          </div>

          {/* Question Action Bar directly below user inquiry */}
          <div className="flex items-center gap-1 mt-1.5 mr-1 text-slate-500 dark:text-slate-400">
            {/* Copy Question Button */}
            <ActionTooltip label={copiedKey === `q-${index}` ? 'Copied!' : 'Copy question'}>
              <button
                type="button"
                onClick={() => handleCopyText(msg.text || (msg as any).content || '', `q-${index}`)}
                title={copiedKey === `q-${index}` ? 'Copied!' : 'Copy question'}
                aria-label="Copy question"
                className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5 active:scale-95 transition-all cursor-pointer flex items-center justify-center"
              >
                {copiedKey === `q-${index}` ? (
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

            {/* Edit Question Pencil Button */}
            <ActionTooltip label="Edit question">
              <button
                type="button"
                onClick={() => {
                  setEditingMessageIndex(index);
                  setEditingQuestionText(msg.text || (msg as any).content || '');
                }}
                title="Edit question"
                aria-label="Edit question"
                className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5 active:scale-95 transition-all cursor-pointer flex items-center justify-center"
              >
                <svg
                  className="w-3.5 h-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </button>
            </ActionTooltip>

            {/* Question Versions Control (‹ X/Y ›) */}
            {totalQVers > 1 &&
              (expandedQVersionsIndex === index ? (
                <div
                  data-version-nav="true"
                  onClick={(e) => e.stopPropagation()}
                  className="flex items-center gap-0.5 bg-slate-100/90 dark:bg-[#1a1e2d] border border-indigo-300/80 dark:border-indigo-500/40 rounded-lg px-1 py-0.5 ml-0.5 animate-in fade-in zoom-in-95 duration-150"
                >
                  <ActionTooltip label="Previous version">
                    <button
                      type="button"
                      disabled={currentQVerNum <= 1}
                      onClick={() => handleSwitchQuestionVersion(index, currentQIdx - 1)}
                      title="Previous version"
                      aria-label="Previous version"
                      className="p-1 rounded text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/80 dark:hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition-all cursor-pointer flex items-center justify-center"
                    >
                      <svg
                        className="w-3 h-3"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="15 18 9 12 15 6" />
                      </svg>
                    </button>
                  </ActionTooltip>

                  <ActionTooltip label="Hide version navigation">
                    <button
                      type="button"
                      onClick={() => setExpandedQVersionsIndex(null)}
                      title="Hide version navigation"
                      aria-label="Hide version navigation"
                      className="flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-slate-200/70 dark:hover:bg-white/10 transition-colors cursor-pointer select-none"
                    >
                      <svg
                        className="w-3 h-3 text-indigo-600 dark:text-indigo-400"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <circle cx="12" cy="12" r="10" />
                        <polyline points="12 6 12 12 16 14" />
                      </svg>
                      <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">
                        {currentQVerNum}/{totalQVers}
                      </span>
                    </button>
                  </ActionTooltip>

                  <ActionTooltip label="Next version">
                    <button
                      type="button"
                      disabled={currentQVerNum >= totalQVers}
                      onClick={() => handleSwitchQuestionVersion(index, currentQIdx + 1)}
                      title="Next version"
                      aria-label="Next version"
                      className="p-1 rounded text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/80 dark:hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition-all cursor-pointer flex items-center justify-center"
                    >
                      <svg
                        className="w-3 h-3"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="9 18 15 12 9 6" />
                      </svg>
                    </button>
                  </ActionTooltip>
                </div>
              ) : (
                <ActionTooltip label="Show all question versions">
                  <button
                    type="button"
                    onClick={() => setExpandedQVersionsIndex(index)}
                    title="Show question versions"
                    aria-label="Show question versions"
                    className="flex items-center gap-1 px-1.5 py-0.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors cursor-pointer select-none"
                  >
                    <svg
                      className="w-3 h-3 text-indigo-500 dark:text-indigo-400"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                    <span className="text-[11px] font-medium">
                      {currentQVerNum}/{totalQVers}
                    </span>
                  </button>
                </ActionTooltip>
              ))}
          </div>
        </>
      )}
    </div>
  );
};

export const UserTurnItem = React.memo(UserTurnItemBase);
