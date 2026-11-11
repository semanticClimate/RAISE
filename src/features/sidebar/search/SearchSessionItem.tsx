import type React from 'react';
import type { ChatSession } from '../../../types';
import { exportSessionAsPdf } from '../../../utils/exportFormats';
import { formatSessionDate } from '../../../utils/uuid';

export interface SearchSessionItemProps {
  session: ChatSession;
  index: number;
  isSelected: boolean;
  isHighlighted: boolean;
  isPinned: boolean;
  isMenuOpen: boolean;
  isRenaming: boolean;
  dataCount: number;
  newSessionTitle: string;
  setNewSessionTitle?: (title: string) => void;
  setRenamingSessionId?: (id: string | null) => void;
  setActiveSessionMenuId?: (id: string | null) => void;
  handleSaveRename?: (id: string) => void;
  handleTogglePinSession?: (id: string) => void;
  handleDeleteSession?: (id: string) => void;
  onSelectSession: (session: ChatSession) => void;
  onClose: () => void;
}

export const SearchSessionItem: React.FC<SearchSessionItemProps> = ({
  session,
  index,
  isSelected,
  isHighlighted,
  isPinned,
  isMenuOpen,
  isRenaming,
  dataCount,
  newSessionTitle,
  setNewSessionTitle,
  setRenamingSessionId,
  setActiveSessionMenuId,
  handleSaveRename,
  handleTogglePinSession,
  handleDeleteSession,
  onSelectSession,
  onClose,
}) => {
  return (
    <div
      id={`search-chat-item-${index}`}
      role="option"
      aria-selected={isHighlighted || isSelected}
      tabIndex={0}
      onClick={() => {
        if (isRenaming) return;
        onSelectSession(session);
        onClose();
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          if (isRenaming) return;
          e.preventDefault();
          onSelectSession(session);
          onClose();
        }
      }}
      className={`group relative w-full text-left px-3.5 py-2.5 rounded-xl transition-all flex items-center justify-between gap-3 cursor-pointer border ${
        isHighlighted
          ? 'bg-indigo-50 border-indigo-300 text-indigo-950 font-semibold shadow-xs dark:bg-indigo-950/60 dark:border-indigo-700/60 dark:text-white ring-1 ring-indigo-400/40'
          : isSelected
            ? 'bg-slate-200/90 border-slate-300/90 text-slate-950 font-semibold shadow-xs dark:bg-white/10 dark:border-white/15 dark:text-white'
            : 'bg-transparent hover:bg-slate-100/90 border-transparent dark:hover:bg-white/[0.06] text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
      }`}
    >
      <div className="flex items-center gap-2.5 min-w-0 flex-1">
        {isPinned ? (
          <svg
            className="w-3.5 h-3.5 text-indigo-600 dark:text-[#a8c7fa] shrink-0"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M16 12V4H8v8l-2 3v1h12v-1l-2-3z" />
          </svg>
        ) : (
          <svg
            className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="1.8"
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        )}
        {isRenaming && setNewSessionTitle && handleSaveRename ? (
          <input
            type="text"
            autoFocus
            value={newSessionTitle}
            onChange={(e) => setNewSessionTitle(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleSaveRename(session.id);
              } else if (e.key === 'Escape' && setRenamingSessionId) {
                setRenamingSessionId(null);
              }
            }}
            onBlur={() => handleSaveRename(session.id)}
            className="w-full text-xs font-medium px-2 py-0.5 rounded bg-white dark:bg-slate-900 border border-indigo-500 text-slate-900 dark:text-slate-100 focus:outline-none shadow-xs"
          />
        ) : (
          <span
            className={`text-xs truncate ${isSelected ? 'font-semibold text-slate-950 dark:text-white' : 'font-medium'}`}
          >
            {session.title}
          </span>
        )}
      </div>

      {/* Right side: Drawer icon with count + Date + Three dots */}
      <div className="flex items-center gap-2 shrink-0">
        <div
          className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-slate-100 dark:bg-white/[0.06] border border-slate-200/80 dark:border-white/10 text-slate-600 dark:text-slate-400"
          title={`${dataCount} source data added`}
        >
          <svg
            className="w-3 h-3 text-slate-500 dark:text-slate-400 shrink-0"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.75"
            viewBox="0 0 24 24"
          >
            <path d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
          </svg>
          <span className="text-[10px] font-semibold tabular-nums text-slate-700 dark:text-slate-300">
            {dataCount}
          </span>
        </div>

        <span className="text-[11px] text-slate-400 dark:text-slate-500 whitespace-nowrap min-w-[65px] text-right">
          {session.timestamp || formatSessionDate(session.updated_at || session.created_at)}
        </span>

        {setActiveSessionMenuId && (
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => setActiveSessionMenuId(isMenuOpen ? null : session.id)}
              className={`p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/70 dark:hover:text-slate-200 dark:hover:bg-white/10 transition-all cursor-pointer ${
                isMenuOpen
                  ? 'opacity-100 bg-slate-200/70 dark:bg-white/10 text-slate-700 dark:text-slate-200'
                  : 'opacity-70 sm:opacity-0 sm:group-hover:opacity-100 hover:opacity-100'
              }`}
              aria-label="Chat options"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <circle cx="12" cy="5" r="1.75" />
                <circle cx="12" cy="12" r="1.75" />
                <circle cx="12" cy="19" r="1.75" />
              </svg>
            </button>

            {isMenuOpen && (
              <div className="absolute right-0 top-full mt-1 w-36 bg-white dark:bg-[#181b26] border border-slate-200 dark:border-white/10 rounded-xl shadow-xl py-1 z-50 animate-in fade-in zoom-in-95 duration-100 backdrop-blur-xl">
                {handleTogglePinSession && (
                  <button
                    type="button"
                    onClick={() => {
                      handleTogglePinSession(session.id);
                      setActiveSessionMenuId(null);
                    }}
                    className="w-full text-left px-3 py-1.5 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <svg
                      className="w-3.5 h-3.5 text-slate-400"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16 12V4H8v8l-2 3v1h12v-1l-2-3z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 16v5" />
                    </svg>
                    <span>{isPinned ? 'Unpin' : 'Pin to top'}</span>
                  </button>
                )}

                {setRenamingSessionId && setNewSessionTitle && (
                  <button
                    type="button"
                    onClick={() => {
                      setRenamingSessionId(session.id);
                      setNewSessionTitle(session.title);
                      setActiveSessionMenuId(null);
                    }}
                    className="w-full text-left px-3 py-1.5 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                      />
                    </svg>
                    <span>Rename</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    exportSessionAsPdf(session);
                    setActiveSessionMenuId(null);
                  }}
                  className="w-full text-left px-3 py-1.5 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors cursor-pointer"
                  title="Download full conversation transcript as PDF"
                >
                  <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <span>Download PDF</span>
                </button>

                {handleDeleteSession && (
                  <button
                    type="button"
                    onClick={() => {
                      handleDeleteSession(session.id);
                      setActiveSessionMenuId(null);
                    }}
                    className="w-full text-left px-3 py-1.5 text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                    <span>Delete</span>
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
