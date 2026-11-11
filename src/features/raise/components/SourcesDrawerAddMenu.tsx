import React from 'react';

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
        className="py-1.5 px-2.5 sm:px-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold flex items-center gap-1 sm:gap-1.5 transition-all cursor-pointer shadow-xs active:scale-95 shrink-0"
      >
        <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path d="M12 4v16m8-8H4" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
        </svg>
        <span className="hidden sm:inline">Add Sources</span>
        <span className="sm:hidden font-medium">Add</span>
        <svg
          className={`w-3 h-3 shrink-0 transition-transform duration-150 ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
        </svg>
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={onClose} aria-hidden="true" />
          <div className="absolute right-0 top-full mt-1.5 w-64 bg-white dark:bg-[#1e1f20] border border-slate-200/90 dark:border-white/10 rounded-2xl shadow-2xl z-50 p-1.5 animate-in fade-in zoom-in-95 duration-150">
            <button
              type="button"
              onClick={() => {
                onClose();
                onBrowseFileClick();
              }}
              className="w-full text-left px-3 py-2 rounded-xl hover:bg-slate-100 dark:hover:bg-white/10 text-slate-800 dark:text-slate-200 text-xs font-medium flex items-center gap-2.5 transition-colors cursor-pointer group"
            >
              <div className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-white/10 flex items-center justify-center text-slate-600 dark:text-slate-300 group-hover:bg-indigo-50 group-hover:text-indigo-600 dark:group-hover:bg-indigo-500/20 dark:group-hover:text-[#a8c7fa] shrink-0">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                  />
                </svg>
              </div>
              <div>
                <p className="font-semibold text-slate-900 dark:text-white">Upload from PC</p>
                <p className="text-[10px] text-slate-400">PDF, Markdown, TXT, CSV</p>
              </div>
            </button>

            <button
              type="button"
              onClick={() => {
                onClose();
                onOpenLibraryPicker();
              }}
              className="w-full text-left px-3 py-2 rounded-xl hover:bg-slate-100 dark:hover:bg-white/10 text-slate-800 dark:text-slate-200 text-xs font-medium flex items-center gap-2.5 transition-colors cursor-pointer group"
            >
              <div className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-white/10 flex items-center justify-center text-slate-600 dark:text-slate-300 group-hover:bg-indigo-50 group-hover:text-indigo-600 dark:group-hover:bg-indigo-500/20 dark:group-hover:text-[#a8c7fa] shrink-0">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                  />
                </svg>
              </div>
              <div>
                <p className="font-semibold text-slate-900 dark:text-white">
                  Knowledge Base Library
                </p>
                <p className="text-[10px] text-slate-400">Select pre-indexed documents</p>
              </div>
            </button>
          </div>
        </>
      )}
    </div>
  );
};
