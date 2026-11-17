import React from 'react';
import { FileUp, BookOpen, Plus, ChevronDown } from 'lucide-react';

export interface SourcesDrawerAddMenuProps {
  isOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
  onBrowseFileClick: () => void;
  onOpenLibraryPicker: () => void;
}

export const SourcesDrawerAddMenu: React.FC<SourcesDrawerAddMenuProps> = ({
  isOpen,
  onToggle,
  onClose,
  onBrowseFileClick,
  onOpenLibraryPicker,
}) => {
  return (
    <div className="relative shrink-0" data-add-source-container="drawer">
      <button
        type="button"
        id="drawerAddSourcesBtn"
        onClick={onToggle}
        title="Add sources to chat"
        aria-label="Add sources"
        className="py-1.5 px-3 rounded-xl bg-[#FFFFFF] hover:bg-[#FFFFFF]/90 text-[#000000] text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shadow-xs active:scale-95 shrink-0"
      >
        <Plus className="w-3.5 h-3.5 shrink-0 stroke-[2.2]" />
        <span className="hidden sm:inline">Add Sources</span>
        <span className="sm:hidden font-medium">Add</span>
        <ChevronDown
          className={`w-3 h-3 shrink-0 transition-transform duration-150 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={onClose} aria-hidden="true" />
          <div className="absolute right-0 top-full mt-1.5 w-64 bg-[#0A0A0A] border border-[#292929] rounded-2xl shadow-2xl z-50 p-1.5 animate-in fade-in zoom-in-95 duration-150">
            <button
              type="button"
              onClick={() => {
                onClose();
                onBrowseFileClick();
              }}
              className="w-full text-left px-3 py-2 rounded-xl hover:bg-[#171717] text-[#FFFFFF] text-xs font-medium flex items-center gap-2.5 transition-colors cursor-pointer group"
            >
              <div className="w-7 h-7 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center text-[#FFFFFF] shrink-0">
                <FileUp className="w-3.5 h-3.5 text-[#FFFFFF]" />
              </div>
              <div>
                <p className="font-semibold text-[#FFFFFF]">Upload from PC</p>
                <p className="text-[10px] text-[#A3A3A3]">PDF, Markdown, TXT, CSV</p>
              </div>
            </button>

            <button
              type="button"
              onClick={() => {
                onClose();
                onOpenLibraryPicker();
              }}
              className="w-full text-left px-3 py-2 rounded-xl hover:bg-[#171717] text-[#FFFFFF] text-xs font-medium flex items-center gap-2.5 transition-colors cursor-pointer group mt-0.5"
            >
              <div className="w-7 h-7 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center text-[#FFFFFF] shrink-0">
                <BookOpen className="w-3.5 h-3.5 text-[#FFFFFF]" />
              </div>
              <div>
                <p className="font-semibold text-[#FFFFFF]">Knowledge Base Library</p>
                <p className="text-[10px] text-[#A3A3A3]">Select pre-indexed documents</p>
              </div>
            </button>
          </div>
        </>
      )}
    </div>
  );
};
