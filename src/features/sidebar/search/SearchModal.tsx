import { Search, X } from 'lucide-react';
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
}) => {
  const [searchFilter, setSearchFilter] = useState('');
  const [activeSearchIndex, setActiveSearchIndex] = useState(-1);

  useScrollLock(isOpen);

  if (!isOpen) return null;

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(searchFilter.toLowerCase())
  );

  const isSessionPinned = (s: ChatSession) =>
    pinnedSessionIds.includes(s.id) ||
    (s.thread_id ? pinnedSessionIds.includes(s.thread_id) : false) ||
    (s.session_id ? pinnedSessionIds.includes(s.session_id) : false) ||
    Boolean((s as any).isPinned) ||
    Boolean((s as any).is_pinned) ||
    Boolean((s as any).pinned);

  const pinnedCount = sessions.filter(isSessionPinned).length;

  return (
    <div
      id="searchModalBackdrop"
      className="fixed inset-0 z-[110] flex items-start justify-center pt-[clamp(3.5rem,8vh,5rem)] p-3 sm:p-5 bg-[#000000]/40 backdrop-blur-md animate-in fade-in duration-150"
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
        className="w-[min(94vw,42rem)] max-h-[85dvh] bg-[#0A0A0A] text-[#FFFFFF] border border-[#292929] rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150 select-none font-sans"
      >
        {/* Search Input Header */}
        <div className="h-14 px-4 sm:px-5 border-b border-[#292929] flex items-center gap-2.5 bg-[#0A0A0A] shrink-0">
          <Search className="w-4 h-4 text-[#A3A3A3] shrink-0" />
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
            className="flex-1 bg-transparent border-0 text-sm text-[#FFFFFF] placeholder-[#A3A3A3] focus:outline-none focus:ring-0 p-0"
          />
          {searchFilter && (
            <button
              type="button"
              onClick={() => {
                setSearchFilter('');
                setActiveSearchIndex(-1);
              }}
              className="p-1 text-[#A3A3A3] hover:text-[#FFFFFF] rounded-md cursor-pointer"
              title="Clear search"
              aria-label="Clear search query"
            >
              <X className="w-3.5 h-3.5 text-[#A3A3A3]" />
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              onClose();
              if (setActiveSessionMenuId) setActiveSessionMenuId(null);
              setActiveSearchIndex(-1);
            }}
            className="p-1.5 text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] rounded-lg transition-colors cursor-pointer ml-1"
            aria-label="Close popup"
          >
            <X className="w-4 h-4 text-[#FFFFFF]" />
          </button>
        </div>

        {/* List of Chats */}
        <div
          id="search-chats-listbox"
          role="listbox"
          aria-label="Chat Sessions"
          className="flex-1 overflow-y-auto p-2 pb-6 space-y-1 bg-[#0A0A0A]"
          style={{ scrollbarWidth: 'thin' }}
        >
          <div className="px-2.5 py-1.5 text-[10px] font-mono font-medium text-[#A3A3A3] uppercase tracking-wider flex items-center justify-between">
            <span>All Chats</span>
            <span>
              {pinnedCount > 0 ? `${pinnedCount} pinned • ` : ''}
              {sessions.length} total
            </span>
          </div>
          {filteredSessions.map((s, sIdx) => {
            const isSelected = s.id === currentSessionId;
            const isHighlighted = activeSearchIndex === sIdx;
            const isPinned = isSessionPinned(s);
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
            <div className="text-center py-8 text-xs text-[#A3A3A3]">
              No chats found matching &ldquo;{searchFilter}&rdquo;
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
