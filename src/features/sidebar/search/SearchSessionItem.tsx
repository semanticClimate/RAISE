import { useEffect, useRef } from 'react';
import type React from 'react';
import {
  Download,
  Edit2,
  FileText,
  MessageSquare,
  MoreVertical,
  Pin,
  Trash2,
} from 'lucide-react';
import type { ChatSession } from '../../../types';
import { exportSessionAsPdf } from '../../../utils/exportFormats';
import { formatSessionDate } from '../../../utils/uuid';
import { useClickOutside } from '../../../hooks';

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
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown menu when clicking outside
  useClickOutside(
    menuRef,
    () => {
      if (isMenuOpen && setActiveSessionMenuId) {
        setActiveSessionMenuId(null);
      }
    },
    isMenuOpen
  );

  // Close dropdown on Escape key
  useEffect(() => {
    if (!isMenuOpen || !setActiveSessionMenuId) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setActiveSessionMenuId(null);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isMenuOpen, setActiveSessionMenuId]);

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
          ? 'bg-[#171717] border-[#292929] text-[#FFFFFF] font-semibold ring-1 ring-[#FFFFFF]/25'
          : isSelected
            ? 'bg-[#171717] border-[#292929] text-[#FFFFFF] font-semibold'
            : 'bg-transparent hover:bg-[#111111] border-transparent text-[#A3A3A3] hover:text-[#FFFFFF]'
      }`}
    >
      <div className="flex items-center gap-2.5 min-w-0 flex-1">
        {isPinned ? (
          <Pin className="w-3.5 h-3.5 text-[#FFFFFF] shrink-0 fill-current" />
        ) : (
          <MessageSquare className="w-3.5 h-3.5 text-[#A3A3A3] shrink-0" />
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
            className="w-full text-xs font-medium px-2 py-0.5 rounded bg-[#111111] border border-[#292929] text-[#FFFFFF] focus:outline-none focus:border-[#FFFFFF]/50"
          />
        ) : (
          <span
            className={`text-xs truncate ${
              isSelected ? 'font-semibold text-[#FFFFFF]' : 'font-medium'
            }`}
          >
            {session.title}
          </span>
        )}
      </div>

      {/* Right side: Drawer icon with count + Date + Three dots */}
      <div className="flex items-center gap-2 shrink-0">
        <div
          className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-[#171717] border border-[#292929] text-[#A3A3A3]"
          title={`${dataCount} source data added`}
        >
          <FileText className="w-3 h-3 text-[#A3A3A3] shrink-0" />
          <span className="text-[10px] font-mono font-medium text-[#FFFFFF]">
            {dataCount}
          </span>
        </div>

        <span className="text-[11px] font-mono text-[#A3A3A3] whitespace-nowrap min-w-[65px] text-right">
          {formatSessionDate(session.updated_at || session.created_at, session.timestamp)}
        </span>

        {setActiveSessionMenuId && (
          <div className="relative" ref={menuRef} onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => setActiveSessionMenuId(isMenuOpen ? null : session.id)}
              className={`p-1.5 rounded-lg text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] transition-all cursor-pointer ${
                isMenuOpen
                  ? 'opacity-100 bg-[#171717] text-[#FFFFFF]'
                  : 'opacity-70 sm:opacity-0 sm:group-hover:opacity-100 hover:opacity-100'
              }`}
              aria-label="Chat options"
            >
              <MoreVertical className="w-3.5 h-3.5 text-[#A3A3A3]" />
            </button>

            {isMenuOpen && (
              <div className="absolute right-0 top-full mt-1 w-36 bg-[#0A0A0A] border border-[#292929] rounded-xl shadow-2xl py-1 z-50 animate-in fade-in zoom-in-95 duration-100">
                {handleTogglePinSession && (
                  <button
                    type="button"
                    onClick={() => {
                      handleTogglePinSession(session.id);
                      setActiveSessionMenuId(null);
                    }}
                    className="w-full text-left px-3 py-1.5 text-xs text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <Pin className="w-3.5 h-3.5 text-[#A3A3A3]" />
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
                    className="w-full text-left px-3 py-1.5 text-xs text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <Edit2 className="w-3.5 h-3.5 text-[#A3A3A3]" />
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
                  className="w-full text-left px-3 py-1.5 text-xs text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] flex items-center gap-2 transition-colors cursor-pointer"
                  title="Download full conversation transcript as PDF"
                >
                  <Download className="w-3.5 h-3.5 text-[#A3A3A3]" />
                  <span>Download PDF</span>
                </button>

                {handleDeleteSession && (
                  <button
                    type="button"
                    onClick={() => {
                      handleDeleteSession(session.id);
                      setActiveSessionMenuId(null);
                    }}
                    className="w-full text-left px-3 py-1.5 text-xs text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-[#A3A3A3]" />
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
