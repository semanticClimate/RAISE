import type React from 'react';
import { useState } from 'react';
import { useScrollLock } from '../../../hooks';
import type { ChatSession } from '../../../types';
import { SearchSessionItem } from './SearchSessionItem';

export interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: ChatSession[];
  currentSessionId: string | null;
  pinnedSessionIds: string[];
  sourceDocs?: any[];
  activeSessionMenuId?: string | null;
  setActiveSessionMenuId?: (id: string | null) => void;
  renamingSessionId?: string | null;
  setRenamingSessionId?: (id: string | null) => void;
  newSessionTitle?: string;
  setNewSessionTitle?: (title: string) => void;
  handleSaveRename?: (id: string) => void;
  handleTogglePinSession?: (id: string) => void;
  handleDeleteSession?: (id: string) => void;
  onSelectSession: (session: ChatSession) => void;
  onNewChat?: () => void;
}

export const SearchModal: React.FC<SearchModalProps> = ({
  isOpen,
  onClose,
  sessions,
  currentSessionId,
  pinnedSessionIds,
  sourceDocs = [],
  activeSessionMenuId = null,
  setActiveSessionMenuId,
  renamingSessionId = null,
  setRenamingSessionId,
  newSessionTitle = '',
  setNewSessionTitle,
  handleSaveRename,
  handleTogglePinSession,
  handleDeleteSession,
  onSelectSession,
  onNewChat,
}) => {
  const [searchFilter, setSearchFilter] = useState('');
  const [activeSearchIndex, setActiveSearchIndex] = useState(-1);

  useScrollLock(isOpen);

  if (!isOpen) return null;

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div
      id="searchModalBackdrop"
      className="fixed inset-0 z-[110] flex items-start justify-center pt-[clamp(3.5rem,8vh,5rem)] p-[clamp(0.5rem,2vw,1rem)] bg-black/60 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        id="searchModalDialog"
        role="dialog"
        aria-modal="true"
        aria-label="Search all chats"
        onClick={(e) => {
          e.stopPropagation();
          if (setActiveSessionMenuId) setActiveSessionMenuId(null);
        }}
        className="w-[min(94vw,42rem)] max-h-[85dvh] bg-white dark:bg-[#181b26] text-slate-900 dark:text-slate-100 border border-slate-300 dark:border-white/15 rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150 select-none"
      >
        {/* Search Input Header */}
        <div className="p-[clamp(0.625rem,2vw,0.875rem)] border-b border-slate-200 dark:border-white/10 flex items-center gap-2.5 bg-slate-50/80 dark:bg-white/[0.02]">
          <svg
            className="w-4 h-4 text-slate-400 dark:text-slate-500 shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            autoFocus
            value={searchFilter}
            role="combobox"
            aria-label="Search all chats"
            aria-autocomplete="list"
            aria-expanded={true}
            aria-controls="search-chats-listbox"
            aria-activedescendant={
              activeSearchIndex >= 0 ? `search-chat-item-${activeSearchIndex}` : undefined
            }
            onChange={(e) => {
              setSearchFilter(e.target.value);
              setActiveSearchIndex(-1);
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                if (filteredSessions.length > 0) {
                  e.preventDefault();
                  setActiveSearchIndex((prev) =>
                    prev < filteredSessions.length - 1 ? prev + 1 : 0
                  );
                }
              } else if (e.key === 'ArrowUp') {
                if (filteredSessions.length > 0) {
                  e.preventDefault();
                  setActiveSearchIndex((prev) =>
                    prev > 0 ? prev - 1 : filteredSessions.length - 1
                  );
                }
              } else if (e.key === 'Enter') {
                if (activeSearchIndex >= 0 && activeSearchIndex < filteredSessions.length) {
                  e.preventDefault();
                  onSelectSession(filteredSessions[activeSearchIndex]);
                  onClose();
                  setActiveSearchIndex(-1);
                }
              } else if (e.key === 'Escape') {
                e.preventDefault();
                onClose();
                setActiveSearchIndex(-1);
              }
            }}
            placeholder="Search all chats..."
            className="flex-1 bg-transparent border-0 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-0 p-0"
          />
          {searchFilter && (
            <button
              type="button"
              onClick={() => {
                setSearchFilter('');
                setActiveSearchIndex(-1);
              }}
              className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-white rounded-md cursor-pointer"
              title="Clear search"
              aria-label="Clear search query"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              onClose();
              if (setActiveSessionMenuId) setActiveSessionMenuId(null);
              setActiveSearchIndex(-1);
            }}
            className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-white/10 rounded-md transition-colors cursor-pointer ml-1"
            aria-label="Close popup"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* List of Chats */}
        <div
          id="search-chats-listbox"
          role="listbox"
          aria-label="Chat Sessions"
          className="flex-1 overflow-y-auto p-2 pb-8 space-y-1"
          style={{ scrollbarWidth: 'thin' }}
        >
          <div className="px-2.5 py-1.5 text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider flex items-center justify-between">
            <span>All Chats</span>
            <span>{sessions.length} total</span>
          </div>
          {filteredSessions.map((s, sIdx) => {
            const isSelected = s.id === currentSessionId;
            const isHighlighted = activeSearchIndex === sIdx;
            const isPinned = pinnedSessionIds.includes(s.id);
            const isMenuOpen = activeSessionMenuId === s.id;
            const isRenaming = renamingSessionId === s.id;
            const dataCount = isSelected
              ? sourceDocs.filter((d: any) => d.selected).length
              : s.sources && s.sources.length > 0
                ? s.sources.filter((src: any) => src.selected !== false).length
                : (s.selectedSourceIds?.length ?? 0);

            return (
              <SearchSessionItem
                key={s.id}
                session={s}
                index={sIdx}
                isSelected={isSelected}
                isHighlighted={isHighlighted}
                isPinned={isPinned}
                isMenuOpen={isMenuOpen}
                isRenaming={isRenaming}
                dataCount={dataCount}
                newSessionTitle={newSessionTitle}
                setNewSessionTitle={setNewSessionTitle}
                setRenamingSessionId={setRenamingSessionId}
                setActiveSessionMenuId={setActiveSessionMenuId}
                handleSaveRename={handleSaveRename}
                handleTogglePinSession={handleTogglePinSession}
                handleDeleteSession={handleDeleteSession}
                onSelectSession={onSelectSession}
                onClose={onClose}
              />
            );
          })}
          {filteredSessions.length === 0 && (
            <div className="text-center py-8 text-xs text-slate-400 dark:text-slate-500">
              No chats found matching &ldquo;{searchFilter}&rdquo;
            </div>
          )}
        </div>

        {/* Footer with New Chat Action */}
        <div className="p-2.5 border-t border-slate-200 dark:border-white/10 bg-slate-50/70 dark:bg-white/[0.02] flex items-center justify-between">
          <button
            type="button"
            onClick={() => {
              if (onNewChat) onNewChat();
              onClose();
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-white/10 transition-all cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                d="M12 4v16m8-8H4"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
              />
            </svg>
            <span>Create New Chat</span>
          </button>
          <span className="text-[11px] text-slate-400 dark:text-slate-500">
            Click any chat to open
          </span>
        </div>
      </div>
    </div>
  );
};
